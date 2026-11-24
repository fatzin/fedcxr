#!/usr/bin/env bash
# Sobe (ou reinicia) o dashboard em segundo plano. Uso: bash scripts/serve_dashboard.sh [--runs runs_final] [--host 127.0.0.1]
cd "$(dirname "$0")/.."
if [ -f dashboard.pid ] && kill -0 "$(cat dashboard.pid)" 2>/dev/null; then kill "$(cat dashboard.pid)"; sleep 1; fi
nohup .venv/bin/python dashboard/server.py "$@" > dashboard.log 2>&1 < /dev/null &
echo $! > dashboard.pid
sleep 2
cat dashboard.log
