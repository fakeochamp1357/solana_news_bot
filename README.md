# 🟣 Solana News Telegram Bot

A small Python Telegram bot that shows you the latest **Solana (SOL) news**
and the current **SOL price**. Designed to run for free on [Render](https://render.com).

## What's in here

| File | What it is |
|------|-----------|
| `solana_news_agent.py`  | The news fetcher (RSS + CoinGecko price) |
| `solana_telegram_bot.py`| The Telegram bot that uses the agent |
| `requirements.txt`      | Python dependencies |
| `Procfile`              | Tells Render how to run the bot |
| `runtime.txt`           | Python version |
| `render.yaml`           | Render "one-click deploy" config |
| `.env.example`          | Template for your bot token (don't commit the real one) |
| `.gitignore`            | Stops secrets from being committed |

---

## 🚀 Deploy to Render in ~5 minutes (free, 24/7)

### Step 1 — Put the code on GitHub

You need a GitHub account. If you don't have one, sign up at <https://github.com> (free, 1 min).

Then:
1. Click the **`+`** in the top right → **New repository**
2. Name it `solana-news-bot` (or whatever you like)
3. Choose **Public** (so Render can read it for free)
4. Click **Create repository**
5. On the next page, click **uploading an existing file** (the link near "Quick setup")
6. Drag in **all the files from this folder** (everything except the `.env` and `bot.log`)
7. Click **Commit changes**

### Step 2 — Sign up for Render

Go to <https://render.com> → **Get Started for Free** → sign up with your GitHub account (one click).

### Step 3 — One-click deploy

Click this button 👇

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/YOUR_USERNAME/solana-news-bot)

> Replace `YOUR_USERNAME` with your GitHub username in that URL, then open it.

### Step 4 — Add your bot token

Render will ask for one environment variable:

- Key:   `TELEGRAM_BOT_TOKEN`
- Value: your bot token (the long `123456:ABC...` string from BotFather)

Click **Apply** → Render builds and starts the bot. Takes ~2 min the first time.

### Step 5 — Use it

Open Telegram → search for your bot by its username → tap **Start** → send `/latest` 🎉

---

## 🧪 Run it locally (for testing)

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and put your real token in it
python solana_telegram_bot.py
```

---

## 🤖 Bot commands (type these in Telegram)

| Command | What it does |
|---------|-------------|
| `/start`   | Welcome message |
| `/latest`  | Top 5 Solana stories |
| `/top 10`  | Top 10 stories |
| `/search etf` | Search the cached news |
| `/summary` | Quick overview |
| `/price`   | Current SOL price + 24h change |
| `/refresh` | Re-fetch news |
| `/help`    | List of commands |

---

## 🔒 After-deploy cleanup (security)

Your bot token got typed into a chat earlier. To be safe:

1. Open Telegram, message **@BotFather**
2. Send `/mybots` → pick your bot → **API Token** → **Revoke current token**
3. BotFather gives you a new one
4. In Render, go to your service → **Environment** → update `TELEGRAM_BOT_TOKEN` → **Save Changes**
5. Render auto-redeploys with the fresh token

---

## 💸 How much does this cost?

**$0.** Render's free tier runs one background worker 24/7, indefinitely. The
bot uses free public APIs (RSS feeds, CoinGecko, Telegram Bot API). No credit
card needed. Render may email you if the worker is idle, but it keeps running.
