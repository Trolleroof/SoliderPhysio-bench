"""Fail-closed Linux development isolation: Landlock filesystem + seccomp.

Requires Landlock ABI >= 3 and the system libseccomp (no Python dependency).
This is not Docker resource accounting and must never label a run official.
"""
import ctypes as C
import errno
import os
from pathlib import Path
import platform
import sys


def restrict(workspace, temporary):
    if sys.platform != 'linux' or platform.machine() not in ('x86_64', 'aarch64'):
        raise RuntimeError('local backend requires Linux x86_64/aarch64')
    libc = C.CDLL(None, use_errno=True)
    sec = C.CDLL('libseccomp.so.2', use_errno=True)
    sec.seccomp_init.argtypes = [C.c_uint32]
    sec.seccomp_init.restype = C.c_void_p
    sec.seccomp_syscall_resolve_name.argtypes = [C.c_char_p]
    sec.seccomp_rule_add.argtypes = [C.c_void_p, C.c_uint32, C.c_int, C.c_uint]
    sec.seccomp_load.argtypes = [C.c_void_p]
    sec.seccomp_release.argtypes = [C.c_void_p]

    def check(result):
        if result < 0:
            raise OSError(C.get_errno(), 'Linux isolation unavailable')
        return result

    check(libc.prctl(38, 1, 0, 0, 0))  # PR_SET_NO_NEW_PRIVS
    abi = check(libc.syscall(444, 0, 0, 1))
    if abi < 3:
        raise RuntimeError('Landlock ABI >= 3 required')
    handled = (1 << 15) - 1  # ABI 3 filesystem rights including REFER, TRUNCATE
    attr = C.c_uint64(handled)
    ruleset = check(libc.syscall(444, C.byref(attr), C.sizeof(attr), 0))

    class Rule(C.Structure):
        _pack_ = 1
        _fields_ = [('allowed_access', C.c_uint64), ('parent_fd', C.c_int32)]

    read = (1 << 0) | (1 << 2) | (1 << 3)  # execute, read file, read directory
    paths = [(Path(p), read) for p in ('/usr', '/bin', '/lib', '/lib64')]
    paths += [(Path(sys.prefix)/'lib', read), (Path(sys.prefix)/'pyvenv.cfg', read)]
    paths += [(Path(p), read) for p in ('/etc/ld.so.cache', '/dev/urandom')]
    paths += [(Path('/dev/null'), read | (1 << 1))]
    paths += [(Path(workspace), handled), (Path(temporary), handled)]
    try:
        for path, rights in paths:
            if not path.exists():
                continue
            if not path.is_dir():
                rights &= (1 << 0) | (1 << 1) | (1 << 2) | (1 << 14)
            fd = os.open(path.resolve(), os.O_PATH | os.O_CLOEXEC)
            try:
                rule = Rule(rights, fd)
                check(libc.syscall(445, ruleset, 1, C.byref(rule), 0))
            finally:
                os.close(fd)
        check(libc.syscall(446, ruleset, 0))
    finally:
        os.close(ruleset)
    ctx = sec.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not ctx:
        raise RuntimeError('seccomp initialization failed')
    try:
        # No sockets (including Unix), process inspection, kernel bypass, or
        # detached descendants that could survive the worker's process group.
        for name in ('socket', 'socketpair', 'ptrace', 'process_vm_readv', 'process_vm_writev',
                     'pidfd_getfd', 'io_uring_setup', 'mount', 'bpf', 'setsid', 'setpgid',
                     'kill', 'tkill', 'tgkill', 'rt_sigqueueinfo', 'rt_tgsigqueueinfo',
                     'pidfd_send_signal', 'process_madvise'):
            number = sec.seccomp_syscall_resolve_name(name.encode())
            if number >= 0:
                check(sec.seccomp_rule_add(ctx, 0x50000 | errno.EPERM, number, 0))
        check(sec.seccomp_load(ctx))
    finally:
        sec.seccomp_release(ctx)
