# AGENTS.md

## Cursor Cloud specific instructions

BiofilmAnalysis is a single Python/Streamlit app (no other services). Source lives in
`src/biofilm_analyzer/`; the GUI entrypoint is `src/biofilm_analyzer/app.py`.

- Dependencies are installed into a local virtualenv at `.venv` (created by the startup
  update script, equivalent to `scripts/setup_environment.sh`). Use `.venv/bin/python`
  for commands, or `source .venv/bin/activate`.
- System requirement: creating the venv needs the `python3.12-venv` apt package. If
  `python3 -m venv` fails with an `ensurepip is not available` error, install it with
  `sudo apt-get install -y python3.12-venv`.
- Run the app: `scripts/run_app.sh` (or `make run`). It serves Streamlit on
  `0.0.0.0:8501` (configured in `.streamlit/config.toml`). Health check:
  `curl http://localhost:8501/_stcore/health` returns `ok`.
- Smoke test the UI without uploading files: the sidebar defaults to
  "Demo synthetic stack", which immediately segments a generated AO/PI volume and
  renders statistics plus live/dead/merge 3D reconstructions.
- Tests: `make test` (or `.venv/bin/python -m pytest`). There is no separate linter
  configured; `pyproject.toml` only wires up `pytest`.
- Generate uploadable demo PNGs with `make demo-data` (writes to `demo_data/`, which is
  gitignored).
- A non-fatal scikit-image `FutureWarning` about `remove_small_objects(min_size=...)` is
  expected and does not affect results.
