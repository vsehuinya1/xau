#!/usr/bin/env bash
# Clone/setup xau repo on VPS and run Test 1 in tmux.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/root/xau}"
SESSION="${SESSION:-xau-test1}"
GITHUB_REPO="${GITHUB_REPO:-vsehuinya1/xau}"

echo "=== xau VPS setup $(date -u) ==="

if [ ! -d "$REPO_DIR/.git" ]; then
  git clone "https://github.com/${GITHUB_REPO}.git" "$REPO_DIR"
fi

cd "$REPO_DIR"
git pull --ff-only || true

python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt

mkdir -p data results
python3 data/download_xauusd.py --start 2018 --end 2025

RUN_SH="${REPO_DIR}/deploy/run_test1.sh"
cat > "$RUN_SH" <<'INNER'
#!/usr/bin/env bash
set -euo pipefail
cd /root/xau
source .venv/bin/activate
export PYTHONUNBUFFERED=1
echo "=== $(date -u) Test 1 start ===" | tee results/test1_run.log
python3 backtests/test1_macro_momentum.py 2>&1 | tee -a results/test1_run.log
echo "=== $(date -u) DONE ===" | tee results/test1.done
INNER
chmod +x "$RUN_SH"

if command -v tmux >/dev/null 2>&1; then
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  tmux new-session -d -s "$SESSION" "bash $RUN_SH"
  echo "Started tmux: $SESSION"
  echo "  tail -f ${REPO_DIR}/results/test1_run.log"
else
  nohup bash "$RUN_SH" > "${REPO_DIR}/results/test1.nohup.log" 2>&1 &
  echo "nohup PID $!"
fi
