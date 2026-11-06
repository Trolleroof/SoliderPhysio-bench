# Leaderboard ratings

The active rules and commands are in [LEADERBOARD.md](LEADERBOARD.md).
Prediction Elo and uncertainty Elo are separate per task. The overall suite uses
equal task votes, with explicit failures, three matched agent seeds, and the same
frozen data/resource protocol. No legacy recovery/synthetic rating is retained.

`benchmark/ratings.py` is a legacy recovery-campaign implementation kept for source
compatibility; its reports are not accepted as three-task leaderboard entries.
