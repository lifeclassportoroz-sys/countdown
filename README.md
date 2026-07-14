# Self-hosted email countdown image

Generates a countdown image on demand — no third-party branding, full
control over styling. Works the same way commercial countdown-GIF
services do: your server computes the *real* time remaining every time
the image is requested (which happens each time someone opens the
email), and returns a freshly drawn image.

## 1. Test it locally

```bash
pip install -r requirements.txt
python app.py
```

Visit:
```
http://localhost:8000/countdown.png?to=2026-08-01T09:00:00Z&label=SALE+ENDS+IN
```

## 2. Deploy it somewhere with a public URL

Any host that runs a small Python web app works. A few easy options:

- **Render.com** — connect a GitHub repo, "Web Service", start command:
  `gunicorn app:app`. Free tier is fine for testing (note: free tier
  sleeps when idle, which adds a few seconds' delay to the first email
  open after inactivity — fine for most campaigns, but upgrade to a
  paid tier if you're sending high-volume blasts).
- **Railway.app** — similar, one-click deploy from repo.
- **Fly.io** — `fly launch` in this folder, it detects the Flask app.
- **A basic VPS** (e.g. DigitalOcean droplet) — run with gunicorn +
  nginx as a reverse proxy, put it behind your own domain/subdomain
  (e.g. `countdown.yourdomain.com`) so it looks fully first-party.

Whatever you pick, the only requirement is: `gunicorn app:app` (or
equivalent) needs to be reachable over HTTPS at a public URL, since
most email clients only load images over HTTPS.

## 3. Use it in your email HTML

```html
<img src="https://countdown.yourdomain.com/countdown.png?to=2026-08-01T09:00:00Z&label=SALE+ENDS+IN"
     width="600" height="150" alt="Offer ends in 3 days" border="0"
     style="display:block;width:100%;max-width:600px;">
```

Always set a descriptive `alt` text — some email clients block images
by default until the user clicks "show images," so the countdown
number itself may not always be visible on first open.

### Query parameters

| Param   | Required | Example                     | Notes                                  |
|---------|----------|------------------------------|-----------------------------------------|
| `to`    | yes      | `2026-08-01T09:00:00Z`       | ISO 8601, UTC recommended               |
| `label` | no       | `SALE ENDS IN`                | Text above the numbers                  |
| `style` | no       | `dark` or `light`             | Default: `dark`                         |
| `w`,`h` | no       | `600`, `150`                  | Image size in px, default 600x150       |

When the target time has passed, it automatically renders "OFFER
ENDED" instead of negative numbers.

## Notes / limitations

- This produces a **static image per request**, not an animated GIF —
  which is actually how real countdown emails work, since the "live"
  effect comes from the client re-fetching the image each time the
  email is opened, not from GIF animation. (True multi-frame animated
  GIFs can't reflect real elapsed time anyway, since they'd loop the
  same fixed sequence regardless of when opened.)
- Cache headers are set to prevent stale caching, but some email
  clients/providers (e.g. Gmail image proxy) cache remote images for
  a period regardless. This is a known limitation of *all* countdown
  email services, not specific to this one.
- For higher email volume, consider adding simple rate limiting or
  running behind a CDN with short TTL caching (a few minutes) to
  reduce server load, at the cost of slightly less real-time accuracy.
