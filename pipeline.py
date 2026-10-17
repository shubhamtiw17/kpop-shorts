"""K-pop dance highlights: fetch -> detect highlight -> 9:16 edit -> upload YT + IG.
Run: python pipeline.py   (env vars: see README)"""
import csv, json, os, subprocess, sys, datetime as dt
import numpy as np, yaml, yt_dlp

CFG = yaml.safe_load(open("config.yaml"))
LOG = "posted_log.csv"
WORK = "work"; os.makedirs(WORK, exist_ok=True)


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


def candidates():
    seen, blocked = posted_ids(), [k.lower() for k in CFG["blocked_title_keywords"]]
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


def main():
    n = 0
    yt_left = CFG["yt_daily_max"] - posted_today("yt_id")
    ig_left = CFG["ig_daily_max"] - posted_today("ig_id")
    if yt_left <= 0 and ig_left <= 0:
        print("Daily limits reached on both platforms"); return
    for src, vid, title in candidates():
        path = download(vid)
        length = min(CFG["clip_seconds"], int(duration(path)))
        if length < CFG["min_clip_seconds"]:
            continue
        start = highlight_start(path, length)
        caption = title[:60]
        short = edit(path, start, length, caption, src["credit"], vid)
        desc = f"{title}\n\n{CFG['hashtags']}\n\n{src['credit']} · youtu.be/{vid}"

        from uploaders import upload_youtube, upload_instagram
        yt = ig = "skipped"
        if yt_left > 0:
            try:
                yt = upload_youtube(short, caption, desc); yt_left -= 1
            except Exception as e:  # e.g. quotaExceeded: still post to IG
                print("YouTube upload failed:", str(e)[:200]); yt_left = 0
        if ig_left > 0:
            try:
                ig = upload_instagram(short, desc); ig_left -= 1
            except Exception as e:
                print("Instagram upload failed:", str(e)[:200])

        new = not os.path.exists(LOG)
        with open(LOG, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["date", "source", "video_id", "title", "yt_id", "ig_id"])
            w.writerow([dt.date.today(), src["name"], vid, title, yt, ig])
        n += 1
        if n >= CFG["posts_per_run"] or (yt_left <= 0 and ig_left <= 0):
            break
    print(f"Posted {n}") if n else sys.exit("Backlog empty: no new eligible clips")


if __name__ == "__main__":
    main()
