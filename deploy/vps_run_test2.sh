#!/usr/bin/env bash
# Run Test 2 on VPS (data already on disk from Test 1).
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/xau}"
SESSION="${SESSION:-xau-test2}"

cd "$REPO_DIR"
git pull --ff-only || true
source .venv/bin/activate

RUN_SH="${REPO_DIR}/deploy/run_test2.sh"
cat > "$RUN_SH" <<'INNER'
#!/usr/bin/env bash
set -euo pipefail
cd /root/xau
source .venv/bin/activate
export PYTHONUNBUFFERED=1
echo "=== $(date -u) Test 2 start ===" | tee results/test2_run.log
python3 backtests/test2_session_timing.py 2>&1 | tee -a results/test2_run.log
echo "=== $(date -u) DONE ===" | tee results/test2.done
INNER
chmod +x "$RUN_SH"

if command -v tmux >/dev/null 2>&1; then
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  tmux new-session -d -s "$SESSION" "bash $RUN_SH"
  echo "Started tmux: $SESSION"
  echo "  tail -f ${REPO_DIR}/results/test2_run.log"
else
  nohup bash "$RUN_SH" > "${REPO_DIR}/results/test2.nohup.log" 2>&1 &
  echo "nohup PID $!"
fi
