#!/bin/bash
# One-time Mac setup: reliable hourly trigger + no sleep on charger.
set -e
GH=$(command -v gh)
LINE="17 8-23 * * * $GH workflow run post-short -R shubhamtiw17/kpop-shorts >/dev/null 2>&1"
(crontab -l 2>/dev/null | grep -v "workflow run post-short"; echo "$LINE") | crontab -
echo "✓ Hourly trigger set (08:17–23:17 Mac time)"
sudo pmset -c sleep 0 displaysleep 10
echo "✓ Mac won't sleep on charger (screen still turns off)"
crontab -l | grep post-short
