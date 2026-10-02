#!/bin/sh
# Run the exact CI checks locally, with CI's pinned, hash-checked tool versions
# (.github/workflows/ci.yml, jobs "checks" and "review-app"). Run before every push.
# Builds .venv once from requirements/ci.lock with Python 3.12, as CI does.
# Works on Linux, macOS and Windows (Git Bash).
set -e
cd "$(dirname "$0")/.."
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    bin=.venv/Scripts
    # the lock is resolved for Linux; on Windows install exactly the locked
    # packages, plus the timezone data that Windows lacks
    nodeps=--no-deps
    export PYTHONUTF8=1
    ;;
  *)
    bin=.venv/bin
    nodeps=
    ;;
esac
if [ ! -x "$bin/ruff" ] && [ ! -x "$bin/ruff.exe" ]; then
  uv venv -q -p python3.12 .venv
  VIRTUAL_ENV=.venv uv pip install -q --require-hashes $nodeps -r requirements/ci.lock
  if [ -n "$nodeps" ]; then VIRTUAL_ENV=.venv uv pip install -q tzdata; fi
  VIRTUAL_ENV=.venv uv pip install -q --no-deps -e .
fi
PATH="$PWD/$bin:$PATH"
ruff check .
ruff format --check .
pyright
python scripts/export_schema.py --check
python scripts/export_review_data.py --check
python scripts/export_clinical_bundle.py --check
python scripts/export_openapi.py --check
pytest -q -W ignore
if [ "${SKIP_APP:-0}" != "1" ]; then
  (cd review-app && npm ci --no-audit --no-fund >/dev/null && npx tsc --noEmit && npx vitest run)
fi
echo "ci_local: all checks passed"
