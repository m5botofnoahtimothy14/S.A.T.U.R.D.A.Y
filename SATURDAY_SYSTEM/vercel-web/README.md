# SATURDAY HUD on Vercel (free, global, always online)

The HUD is static — Vercel hosts it worldwide. It talks to YOUR PC through
the Cloudflare tunnel (set `SATURDAY_CORS_ORIGIN` to this URL first).

## Deploy (3 commands, free hobby account, no card)

```bash
cd SATURDAY_SYSTEM/vercel-web
python sync.py          # refresh index.html from ../dashboard/index.html
npx vercel --prod       # login once in browser, accept defaults
```

Your HUD lands at `https://<project>.vercel.app`.

## Connect it to home

1. On the PC: set env `SATURDAY_CORS_ORIGIN=https://<project>.vercel.app`
2. In SATURDAY: `share on [stable-hostname]` → copy URL + token.
3. Open `https://<project>.vercel.app/?api=URL&token=TOKEN` (or use the
   LINK bar in the console card). Bookmark it — token stays in YOUR browser.

## Notes

- Quick-tunnel URLs rotate on restart → re-link, or use `--hostname`
  (free Cloudflare account) for a stable endpoint + `share persist`.
- Token auth is enforced on every route whenever shared. Rotate with
  `share off` + `share on`. Never share the token, only the URL+token
  pair with yourself.
- Vercel serves ONLY the HUD shell. All data/commands execute on your PC.
