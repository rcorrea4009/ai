# Deploy the PUBLIC DEMO (safe, no real money)

This puts a **demo-only** copy of the app online 24/7 so you can share a link.
The hosted copy has **no live-trading ability** — `DEMO_ONLY=true` hard-disables
the Tiger connection and the live password gate, and no broker keys ever leave
your computer. Real-money trading stays only on your local machine.

You need to do these steps yourself (they use *your* GitHub + Streamlit accounts —
I can't log in as you). ~10–15 minutes, at your computer.

## 1. Put the code on GitHub
- Make a free account at https://github.com if you don't have one.
- Easiest way: install **GitHub Desktop** (https://desktop.github.com), then
  *File → Add local repository →* `C:\Users\rache\Kronos` *→ Publish repository*.
  Keep it **Private** (your `.env` and `venv` are already git-ignored, so no
  secrets get uploaded).

## 2. Use the slim requirements for the cloud
- In the repo, rename **`requirements-cloud.txt` → `requirements.txt`**
  (or paste its contents over the existing `requirements.txt`) and commit.
  This drops the heavy torch/Kronos libs the free tier can't handle.

## 3. Deploy on Streamlit Community Cloud
- Go to https://share.streamlit.io and sign in **with GitHub**.
- **Create app → From existing repo.** Pick your `Kronos` repo.
- **Main file path:** `app.py`
- Click **Advanced settings → Secrets** and paste exactly:
  ```
  DEMO_ONLY = "true"
  FRED_API_KEY = "2c12429352d97f7eb5b2261aad583fdd"
  ```
  (Do **NOT** add TIGER_* or LIVE_UNLOCK_HASH — leaving them out is what keeps
  the public copy demo-only.)
- Click **Deploy**. First build takes a few minutes.

## 4. Share it
- You'll get a public URL like `https://your-app.streamlit.app`.
- Anyone with it can use **Paper (Demo)** and all the analysis. The Live toggle
  will show "Live trading is disabled" — it cannot touch a real account.

## Notes
- The Kronos AI forecast won't run on the demo (skipped to fit the free tier);
  the backtest, scan, Monte Carlo, news, and charts all work.
- To update the live site later, just commit to the repo — it redeploys.
- Your local app (with live trading) is unchanged and still runs the same way.
