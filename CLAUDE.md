# Cavcraft

Minecraft world of Caversham from OSM + EA LiDAR. Read BRIEF.md (what) and PROGRESS.md (where we are).

- Work through PROGRESS.md continuously with no check-ins; the user has approved
  downloading whatever data/tools are needed.
- Java Edition first. Bedrock only by converting (Chunker) once the user is happy.
- After every step: append to PROGRESS.md log, commit (author a-adz-1 <a-adz-1@proton.me>).
- Big data lives in .downloads/ (gitignored); the built world in world/ (gitignored).
- Run tools from the repo root: .venv/bin/python tools/<name>.py (tools/ must stay on sys.path, so no -I).
