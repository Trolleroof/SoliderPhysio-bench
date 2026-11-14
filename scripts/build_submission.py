"""Build the micro1 hackathon submission zip.

Includes repo files (tracked + untracked, minus .gitignore) and a slim copy of the
2026-11-07 roster run: answers, grades, judgments and frozen predictor artifacts.
Excludes controller SQLite logs, .env files, and source files the eval does not use.

    python3 scripts/build_submission.py [--out dist/soldierphysio-bench.zip]
"""
import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".benchmark-runs" / "rerun-20261107"
RESULT_NAMES = {"submissions.json", "judged.json", "rating.json", "grader.json",
                "identity.json", "artifact_hashes.json", "completion-audit.json",
                "final-leaderboard.json", "score-components.json"}
EXCLUDE = (re.compile(r"(^|/)\.env($|\.(?!example$))"),
           re.compile(r"^sources/hardware-final-v2\.xlsx$"),   # unused, provenance unknown
           re.compile(r"^sources/physionet-wearable/"),        # unused by active tasks
           re.compile(r"(^|/)__pycache__/"),
           re.compile(r"\.(sqlite|log|pid|plist)$"))
SECRET = re.compile(rb"sk-or-v1-[A-Za-z0-9]{20}|sk-ant-[A-Za-z0-9_-]{20}|sk-proj-[A-Za-z0-9_-]{20}"
                    rb"|AKIA[0-9A-Z]{16}|OPENROUTER_API_KEY=\S{8}")
MAX_ARTIFACT_FILE = 1 << 20
MAX_ZIP = 50 * 1024 * 1024


def repo_files():
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, check=True, capture_output=True).stdout
    return [p for p in out.decode().split("\0") if p and (ROOT / p).is_file()]


def run_files():
    for p in sorted(RUN.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(RUN).as_posix()
        if p.name in RESULT_NAMES or ("/artifact/" in f"/{rel}" and p.stat().st_size <= MAX_ARTIFACT_FILE):
            yield p, f"results/rerun-20261107/{rel}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist" / "soldierphysio-bench.zip"))
    args = ap.parse_args()
    entries = [(ROOT / p, p) for p in repo_files()] + list(run_files())
    entries = [(src, arc) for src, arc in entries if not any(rx.search(arc) for rx in EXCLUDE)]
    leaks = [arc for src, arc in entries if SECRET.search(src.read_bytes())]
    if leaks:
        sys.exit(f"secret-like strings found, refusing to build: {leaks}")
    if not any(arc == "README.md" for _, arc in entries):
        sys.exit("README.md missing at root")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in entries:
            z.write(src, f"soldierphysio-bench/{arc}")
    size = out.stat().st_size
    print(f"{out}  {len(entries)} files  {size / 1e6:.1f} MB")
    if size > MAX_ZIP:
        sys.exit("zip exceeds 50 MB")


if __name__ == "__main__":
    main()
