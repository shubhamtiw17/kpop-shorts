#!/bin/bash
# One-time Mac setup. The Mac only PREPARES clips (downloads + edits) whenever it's awake;
# posting happens in GitHub's cloud, so the Mac can be closed.
set -e
DIR="$HOME/Projects/kpop-shorts"
BREW="/opt/homebrew/bin"
LINE="*/30 * * * * export PATH=$BREW:/usr/local/bin:/usr/bin:/bin; cd $DIR && git pull -q --rebase origin main && python3 pipeline.py prepare >> $DIR/prepare.log 2>&1"
(crontab -l 2>/dev/null | grep -v "post-short" | grep -v "pipeline.py prepare"; echo "$LINE") | crontab -
echo "✓ Mac fills the clip queue every 30 min while awake (log: prepare.log)"

# Old self-hosted runner is no longer needed
if [ -d "$DIR/actions-runner" ]; then
  (cd "$DIR/actions-runner" && ./svc.sh stop >/dev/null 2>&1; ./svc.sh uninstall >/dev/null 2>&1) || true
  echo "✓ Old Mac runner service stopped"
fi

# Restore normal sleep (no longer needed to stay awake)
sudo pmset -c sleep 1 displaysleep 10 || true
echo "✓ Normal sleep restored"

echo "Filling the queue now (first run can take a while)..."
cd "$DIR" && python3 pipeline.py prepare
