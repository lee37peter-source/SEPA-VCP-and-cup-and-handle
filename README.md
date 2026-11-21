# Breakout Screener

A free website that scans all US stocks every weekday morning (about 7:30am Hong Kong time,
after the US close) for five chart patterns:

| Pattern | Rules (standard O'Neil / Minervini) |
|---|---|
| **VCP** | Trend Template + RS ≥ 70; 2–6 tightening contractions, final ≤ 10%, volume drying up |
| **Cup with handle** | 30%+ prior uptrend; cup 6–65 wks, 12–35% deep, rounded; handle 1–4 wks, ≤ 12%, upper half, light volume |
| **High tight flag** | +90% in ≤ 8 weeks, then a 3–5 week flag ≤ 25% deep |
| **Double bottom** | 30%+ prior uptrend; W ≥ 7 wks, 12–35% deep; 2nd low undercuts the 1st; pivot = middle peak |
| **Flat base** | Trend Template; ≥ 5 weeks sideways within 15% after a 20%+ advance |

The page shows:
- the market condition (index trend, distribution days, breadth)
- today's **breakouts**, **setups** (near the pivot) and **extended** names
- an interactive chart for each stock, with the pattern, pivot and stop drawn on it
- a **signal history** that tracks every breakout for 60 sessions

It can also email you when there's a new breakout.

Everything runs on GitHub for free. Your computer can stay off.

---

## Setup (about 15 minutes, one time)

### 1. Create the repository
1. Sign up at [github.com](https://github.com) if you don't have an account.
2. Click **+** (top right) → **New repository**.
   - Name: `screener` (any name works; it becomes part of your web address).
   - Choose **Public**. Free GitHub Pages needs a public repository. Anyone with the link could view the
     page, but it isn't listed or indexed anywhere.
   - Click **Create repository**.

### 2. Upload the files
1. On the new repository page, click **uploading an existing file**.
2. Unzip the download. Open the `momentum-screener` folder and drag **everything inside it** onto the
   GitHub page. That's `screener`, `web`, `state`, `tests`, `.github`, `README.md` and `requirements.txt`.
   - **Mac:** Finder hides the `.github` folder. Press **Cmd + Shift + .** in Finder to show it.
   - If `.github` still doesn't upload, create the file by hand instead. Click **Add file → Create new file**,
     type the name `.github/workflows/daily.yml`, paste in the contents of that file, and commit.
3. Click **Commit changes**.

### 3. Turn on the website
**Settings → Pages → Build and deployment → Source: GitHub Actions.**

### 4. Email alerts (optional)
1. In your Google account, turn on 2-Step Verification. Then go to
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) and create an app
   password called "screener". Copy the 16-character password.
2. In the repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `SMTP_USER`: your Gmail address
   - `SMTP_PASSWORD`: the app password from step 1
   - `ALERT_TO` (optional): where to send alerts, if not your Gmail. Separate several addresses with commas.

You'll get an email only on mornings with a new breakout.

### 5. First run
1. Go to **Actions → Daily screen → Run workflow**. Set *backfill* to `30` to fill the history with the
   last 30 sessions of breakouts, then click **Run workflow**.
2. The first run takes about 15–30 minutes, mostly downloading ~6,000 stocks.
3. Your site is then at `https://YOUR-USERNAME.github.io/screener/`.
   On your phone, open it and choose **Add to Home Screen**.

From then on it runs by itself every Tuesday to Saturday at about 07:30 HKT.

---

## Good to know
- **Timing:** GitHub sometimes starts scheduled runs 5–30 minutes late. The page header shows which US close
  the data is from. If the data is more than 4 days old, a warning appears. If that happens, open the Actions
  tab to see why a run failed.
- **Data:** Prices come from Yahoo Finance through `yfinance`, adjusted for splits and dividends. It's free
  and unofficial. If Yahoo throttles a run, a few tickers may be missing that day, and the run retries them
  automatically.
- **Inactivity:** GitHub pauses scheduled workflows in repositories with no activity for 60 days. The daily
  history update should count as activity. If GitHub ever emails that the workflow was disabled, open
  **Actions** and click **Enable workflow**.
- **History commits:** each run saves `state/history.json` back to the repository. That's the only file
  that changes.
- **If the "Save signal history" step fails** with a permission error, go to
  **Settings → Actions → General → Workflow permissions** and choose **Read and write permissions**.

## Tuning
All thresholds are in `screener/config.py`, with comments. Common changes:
- `Universe.min_price` / `min_dollar_vol`: the liquidity filter
- `Status.breakout_vol`: breakout volume required (1.4× average by default)
- `VCP.max_last_depth`, `Cup.max_depth`, `FlatBase.max_depth`: how strict each pattern is
- `Config.min_rs`: the RS floor

Edit the file on GitHub (pencil icon) and commit. The next run uses the new values.

## Running it on your own computer
```bash
pip install -r requirements.txt
python -m screener.run --demo --out build --backfill 40         # synthetic data, no download
python -m http.server -d build 8000                             # open http://localhost:8000
python -m screener.run --tickers NVDA ANET CRWD --out build --debug   # explains each rejection
python -m tests.test_patterns                                   # regression test on synthetic patterns
```

This is a screen to find ideas, not investment advice. Check every chart, the earnings date and the
news before you trade.
