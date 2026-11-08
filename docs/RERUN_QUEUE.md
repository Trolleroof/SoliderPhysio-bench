# Local rerun queue

The current rerun is supervised by macOS LaunchAgent
`dev.soldierphysio.rerun-20261107`, independent of the chat terminal.
Its configuration is in
`~/Library/LaunchAgents/dev.soldierphysio.rerun-20261107.plist`.
Docker Desktop must be running. The service PATH includes
`/Applications/Docker.app/Contents/Resources/bin`.

The supervisor uses `eval_suite.resume_sweep`, holds an exclusive lock, and
updates `.benchmark-runs/rerun-20261107/control/status.json` every 20 seconds
while a child runs. `launchd.stdout.log` and `launchd.stderr.log` in that same
folder contain its output. macOS restarts an unsuccessful supervisor after a
60-second throttle. A successful disposable restart probe was run on 2026-11-08.
The supervisor prevents idle sleep while running; shutdown or logout interrupts it.

On restart, the queue inventories saved cases, rejects duplicates, and requests
only missing cases. Original attempts and unknown-cost reservations remain in
aggregate model spend. It revisits source submissions for missing judgments.
A pass with missing model cases retries; exhausted caps or judge failures are
reported as blocked, never complete. Carbon has no configured provider and is
excluded from runnable coverage. Gemini 3.8 replaces 3.7; 3.7 outputs are excluded.

Inspect and stop this job only:

```sh
launchctl print gui/$(id -u)/dev.soldierphysio.rerun-20261107
launchctl bootout gui/$(id -u)/dev.soldierphysio.rerun-20261107
```

To reload the installed configuration after a stop:

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dev.soldierphysio.rerun-20261107.plist
```

Service state `running` proves only that the supervisor is alive. Check the
heartbeat, active child, saved case coverage and judge records for progress.
