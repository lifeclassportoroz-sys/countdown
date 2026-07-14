"""
Self-hosted countdown image generator for email campaigns.

How it works
------------
Email clients re-fetch remote images each time a message is opened
(they don't run JS or CSS animations), so "live" countdown images work
by having a server compute the *actual* time remaining at request time
and draw a fresh image on every request. This app does exactly that.

Usage
-----
Embed in your email HTML like:

    <img src="https://your-domain.com/countdown.png?to=2026-08-01T09:00:00Z"
         width="600" alt="Countdown timer">

Query params:
    to      (required) ISO 8601 target datetime, e.g. 2026-08-01T09:00:00Z
    style   (optional) "dark" or "light" (default: dark)
    label   (optional) text shown above the numbers, e.g. "SALE ENDS IN"
    w, h    (optional) image width/height in px (default 600x150)

Run locally:
    pip install -r requirements.txt
    python app.py
    # then visit http://localhost:8000/countdown.png?to=2026-08-01T09:00:00Z

Deploy anywhere that runs a small Python web service (see README.md).
"""

from datetime import datetime, timezone
from io import BytesIO

from flask import Flask, request, send_file, abort
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

THEMES = {
    "dark": {"bg": (17, 17, 17), "fg": (255, 255, 255), "accent": (255, 90, 90)},
    "light": {"bg": (255, 255, 255), "fg": (20, 20, 20), "accent": (200, 30, 30)},
}

FONT_PATH_BOLD = "DejaVuSans-Bold.ttf"   # bundled with most systems / Pillow installs
FONT_PATH_REG = "DejaVuSans.ttf"


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        # Fallback: Pillow's built-in bitmap font (always available, less pretty)
        return ImageFont.load_default()


def parse_target(raw: str) -> datetime:
    try:
        # Accept trailing 'Z' as UTC
        raw = raw.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        abort(400, "Invalid 'to' datetime. Use ISO 8601, e.g. 2026-08-01T09:00:00Z")


def time_remaining(target: datetime):
    now = datetime.now(timezone.utc)
    delta = target - now
    ended = delta.total_seconds() <= 0
    total_seconds = max(int(delta.total_seconds()), 0)
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return ended, days, hours, minutes, seconds


def draw_countdown(days, hours, minutes, seconds, ended, theme, label, w, h):
    colors = THEMES.get(theme, THEMES["dark"])
    img = Image.new("RGB", (w, h), colors["bg"])
    draw = ImageDraw.Draw(img)

    label_font = load_font(FONT_PATH_REG, max(h // 10, 14))
    num_font = load_font(FONT_PATH_BOLD, max(h // 3, 28))
    unit_font = load_font(FONT_PATH_REG, max(h // 12, 12))

    y_cursor = int(h * 0.08)

    if label:
        bbox = draw.textbbox((0, 0), label, font=label_font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) / 2, y_cursor), label, font=label_font, fill=colors["fg"])
        y_cursor += (bbox[3] - bbox[1]) + int(h * 0.06)

    if ended:
        msg = "OFFER ENDED"
        bbox = draw.textbbox((0, 0), msg, font=num_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((w - tw) / 2, (h - th) / 2), msg, font=num_font, fill=colors["accent"])
        return img

    segments = [
        (f"{days:02d}", "DAYS"),
        (f"{hours:02d}", "HRS"),
        (f"{minutes:02d}", "MIN"),
        (f"{seconds:02d}", "SEC"),
    ]

    # Measure total width needed to center the row of segments
    gap = int(w * 0.05)
    seg_widths = []
    for num, unit in segments:
        nb = draw.textbbox((0, 0), num, font=num_font)
        ub = draw.textbbox((0, 0), unit, font=unit_font)
        seg_widths.append(max(nb[2] - nb[0], ub[2] - ub[0]))
    total_w = sum(seg_widths) + gap * (len(segments) - 1)

    x = (w - total_w) / 2
    num_area_h = h - y_cursor
    for (num, unit), seg_w in zip(segments, seg_widths):
        nb = draw.textbbox((0, 0), num, font=num_font)
        nh = nb[3] - nb[1]
        ny = y_cursor + (num_area_h * 0.55 - nh) / 2
        draw.text((x + (seg_w - (nb[2] - nb[0])) / 2, ny), num, font=num_font, fill=colors["accent"])

        ub = draw.textbbox((0, 0), unit, font=unit_font)
        uy = ny + nh + int(h * 0.03)
        draw.text((x + (seg_w - (ub[2] - ub[0])) / 2, uy), unit, font=unit_font, fill=colors["fg"])

        x += seg_w + gap

    return img


@app.route("/countdown.png")
@app.route("/countdown.gif")  # same handler; email clients don't care about the extension
def countdown():
    to_raw = request.args.get("to")
    if not to_raw:
        abort(400, "Missing required 'to' query param, e.g. ?to=2026-08-01T09:00:00Z")

    target = parse_target(to_raw)
    theme = request.args.get("style", "dark")
    label = request.args.get("label", "")
    w = int(request.args.get("w", 600))
    h = int(request.args.get("h", 150))

    ended, days, hours, minutes, seconds = time_remaining(target)
    img = draw_countdown(days, hours, minutes, seconds, ended, theme, label, w, h)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = send_file(buf, mimetype="image/png")
    # Critical: prevent email clients / proxies from caching a stale frame
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    return (
        "Countdown image generator is running. "
        "Try /countdown.png?to=2026-08-01T09:00:00Z&label=SALE+ENDS+IN"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
