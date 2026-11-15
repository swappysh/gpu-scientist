#!/bin/sh
# One agent reads what another wrote, on past.dev. Needs PAST_API_KEY in the environment.
#   ./demo_read.sh              # fresh scope: evaluator writes, proposer and critic read
#   ./demo_read.sh scored37-d   # read a finished loop run as the proposer
set -eu
cd "$(dirname "$0")"
: "${PAST_API_KEY:?set PAST_API_KEY (a past.dev project key)}"
exec uv run python scripts/demo_read.py "$@"
