"""K-pop dance highlights, in two halves:

  python3 pipeline.py prepare   (your Mac, whenever it's awake)
      find new clips -> download -> highlight -> 9:16 edit -> park in the GitHub "queue" release
  python3 pipeline.py publish   (GitHub cloud, hourly, Mac can be off)
      take the oldest queued clip -> post to YouTube + Instagram -> log -> remove from queue
"""
import csv, json, os, subprocess, sys, datetime as dt
import numpy as np, yaml, yt_dlp

CFG = yaml.safe_load(open("config.yaml"))
LOG = "posted_log.csv"
WORK = "work"; os.makedirs(WORK, exist_ok=True)


REPO = os.environ.get("GITHUB_REPOSITORY", "shubhamtiw17/kpop-shorts")
QUEUE = "queue"


def gh(*args, check=True):
    return subprocess.run(["gh", *args, "-R", REPO], capture_output=True, text=True, check=check).stdout


def queue_assets():
    """Assets in the queue release, oldest first."""
    out = gh("release", "view", QUEUE, "--json", "assets", check=False)
    if not out:
        gh("release", "create", QUEUE, "-t", "clip queue", "-n", "Auto-managed by the bot",
           "--prerelease", check=False)
        return []
    return sorted(json.loads(out)["assets"], key=lambda a: a["createdAt"])


def posted_ids():
    if not os.path.exists(LOG):
        return set()
    return {r["video_id"] for r in csv.DictReader(open(LOG))}


def posted_today(col):
    """How many posts went to a platform today (col = 'yt_id' or 'ig_id')."""
    if not os.path.exists(LOG):
        return 0
    today = str(dt.date.today())
    return sum(1 for r in csv.DictReader(open(LOG))
               if r["date"] == today and r.get(col) not in (None, "", "None", "skipped"))


def candidates(extra_seen=()):
    seen = posted_ids() | set(extra_seen)
    blocked = [k.lower() for k in CFG["blocked_title_keywords"]]
    groups = [g.lower() for names in CFG["focus_groups"].values() for g in names]
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True,
                           "playlistend": CFG.get("scan_depth", 300)}) as y:
        for src in CFG["sources"]:
            for e in y.extract_info(src["url"], download=False).get("entries", []):
                vid, title = e["id"], e.get("title", "")
                t = title.lower()
                if vid in seen or any(b in t for b in blocked):
                    continue
                if not any(g in t for g in groups):
                    continue
                if src["require_cc"]:
                    info = y.extract_info(f"https://youtu.be/{vid}", download=False)
                    if "creative commons" not in (info.get("license") or "").lower():
                        continue
                yield src, vid, title


def download(vid):
    out = f"{WORK}/{vid}.mp4"
    with yt_dlp.YoutubeDL({"quiet": True, "outtmpl": out,
                           "format": "bv*[height<=1080]+ba/b", "merge_output_format": "mp4"}) as y:
        y.download([f"https://youtu.be/{vid}"])
    return out


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    return float(json.loads(r.stdout)["format"]["duration"])


def highlight_start(path, win):
    """Pick the window with the highest audio energy (chorus / dance break)."""
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32)
    if len(a) < 8000 * win:
        return 0.0
    sec = np.sqrt((a[: len(a) // 8000 * 8000].reshape(-1, 8000) ** 2).mean(1))
    scores = np.convolve(sec, np.ones(win), "valid")
    return float(np.argmax(scores))


FONTS = ["/System/Library/Fonts/AppleSDGothicNeo.ttc",          # macOS (Korean ok)
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]   # Linux fallback


def _font(size):
    from PIL import ImageFont
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, maxw):
    lines, cur = [], ""
    for word in text.split():
        test = f"{cur} {word}".strip()
        if cur and draw.textlength(test, font=font) > maxw:
            lines.append(cur); cur = word
        else:
            cur = test
    return lines + [cur] if cur else lines


def make_overlay(caption, credit, path):
    """Render text to a transparent PNG (no ffmpeg drawtext needed)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f1, f2 = _font(56), _font(38)
    y = 150
    for line in _wrap(d, caption, f1, 960)[:2]:
        w = d.textlength(line, font=f1)
        d.rectangle([(1080 - w) / 2 - 16, y - 8, (1080 + w) / 2 + 16, y + 72], fill=(0, 0, 0, 140))
        d.text(((1080 - w) / 2, y), line, font=f1, fill="white")
        y += 84
    img.save(path)  # credit goes in the description, not on screen


def edit(src_path, start, length, caption, credit, vid):
    out, ov = f"{WORK}/{vid}_short.mp4", f"{WORK}/{vid}_ov.png"
    make_overlay(caption, credit, ov)
    fc = ("[0:v]crop='min(iw,ih*9/16)':ih,scale=1080:1920,setsar=1[v];"
          "[v][1:v]overlay=0:0[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-t", str(length),
                    "-i", src_path, "-i", ov, "-filter_complex", fc, "-map", "[out]",
                    "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", out],
                   check=True)
    return out


def prepare():
    """Mac side: fill the queue up to queue_target clips."""
    assets = queue_assets()
    queued = {a["name"].rsplit(".", 1)[0] for a in assets}
    need = CFG["queue_target"] - sum(a["name"].endswith(".mp4") for a in assets)
    print(f"Queue has {len(queued)} clips, adding up to {max(need, 0)}")
    added = 0
    for src, vid, title in candidates(queued):
        if added >= need:
            break
        try:
            path = download(vid)
            length = min(CFG["clip_seconds"], int(duration(path)))
            if length < CFG["min_clip_seconds"]:
                continue
            caption = title[:60]
            short = edit(path, highlight_start(path, length), length, caption, src["credit"], vid)
        except Exception as e:
            print(f"skip {vid}: {str(e)[:150]}"); continue
        desc = f"{title}\n\n{CFG['hashtags']}"
        if src.get("credit"):  # only sources that require attribution (e.g. CC BY)
            desc += f"\n\n{src['credit']} · youtu.be/{vid}"
        meta = f"{WORK}/{vid}.json"
        json.dump({"vid": vid, "source": src["name"], "title": title,
                   "caption": caption, "desc": desc}, open(meta, "w"), ensure_ascii=False)
        clip = f"{WORK}/{vid}.mp4"
        os.replace(short, clip)
        gh("release", "upload", QUEUE, meta, clip, "--clobber")
        for f in os.listdir(WORK):
            os.remove(os.path.join(WORK, f))
        added += 1
        print(f"queued {vid}: {title}")
    print(f"Added {added}. Queue now ~{len(queued) + added}")


def publish():
    """Cloud side: post the oldest queued clip, within daily limits."""
    yt_left = CFG["yt_daily_max"] - posted_today("yt_id")
    ig_left = CFG["ig_daily_max"] - posted_today("ig_id")
    if yt_left <= 0 and ig_left <= 0:
        print("Daily limits reached on both platforms"); return
    mp4s = [a for a in queue_assets() if a["name"].endswith(".mp4")]
    if not mp4s:
        sys.exit("Queue empty: open your Mac so it can prepare more clips")
    vid = mp4s[0]["name"][:-4]
    gh("release", "download", QUEUE, "-p", f"{vid}.*", "-D", WORK, "--clobber")
    m = json.load(open(f"{WORK}/{vid}.json"))
    clip = f"{WORK}/{vid}.mp4"
    url = f"https://github.com/{REPO}/releases/download/{QUEUE}/{vid}.mp4"

    from uploaders import upload_youtube, upload_instagram
    yt = ig = "skipped"
    if yt_left > 0:
        try:
            yt = upload_youtube(clip, m["caption"], m["desc"])
        except Exception as e:  # e.g. quotaExceeded: still post to IG
            print("YouTube upload failed:", str(e)[:200])
    if ig_left > 0:
        try:
            ig = upload_instagram(url, m["desc"])
        except Exception as e:
            print("Instagram upload failed:", str(e)[:200])

    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "source", "video_id", "title", "yt_id", "ig_id"])
        w.writerow([dt.date.today(), m["source"], vid, m["title"], yt, ig])
    for ext in ("mp4", "json"):
        gh("release", "delete-asset", QUEUE, f"{vid}.{ext}", "-y", check=False)
    print(f"Posted {vid} | YT: {yt} | IG: {ig} | {len(mp4s) - 1} left in queue")


if __name__ == "__main__":
    {"prepare": prepare, "publish": publish}[sys.argv[1] if len(sys.argv) > 1 else "publish"]()
