# K-pop Dance Highlights Bot

Fetches new uploads from permitted sources → picks the highest-energy 25s (dance break) → 9:16 + caption + credit → posts to YouTube Shorts + Instagram Reels, 2x/day.

## Setup
1. Push this folder to a new GitHub repo.
2. Add repo secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` (Google Cloud OAuth, YouTube Data API v3), `IG_USER_ID`, `IG_TOKEN` (IG Business account + Instagram Login API token, no Facebook Page needed).
3. Actions tab → run `post-short` once manually to test.

## Rules
- Only add sources to `config.yaml` you have permission for, or verified original CC cammers.
- Keep `blocked_title_keywords` updated with under-18 members.
- `posted_log.csv` is your proof trail (source, video ID, date).

## Known limits
- YouTube may block yt-dlp from GitHub's servers. If downloads fail, run on your Mac with cron instead.
- Song audio can trigger Content ID claims (revenue goes to the label).
- IG tokens expire after 60 days; refresh them.
