"""
🟣 Solana News Telegram Bot
============================
A Telegram bot that talks to your phone and tells you the latest
Solana news + price. Run it once and it stays running, polling
Telegram for messages.

Setup:
    pip install python-telegram-bot requests
    # Put your token in a .env file:
    #   TELEGRAM_BOT_TOKEN=your:token

Run:
    python solana_telegram_bot.py
"""

import html
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any

# Reuse the news fetching logic from the agent we already wrote.
from solana_news_agent import (
    fetch_solana_news,
    get_sol_price,
    summarize,
)

from telegram import Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Read the token from the .env file (a simple way to keep it out of code).
def _load_token() -> str:
    # 1) Prefer the .env file in this folder (the user's own token).
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    # 2) Fall back to env var (useful for deploys like Docker / PaaS).
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if tok:
        return tok
    return ""


TOKEN = _load_token()
if not TOKEN:
    sys.exit("❌  TELEGRAM_BOT_TOKEN not set. Add it to .env or as an env var.")

# Cache the latest fetched news in memory so /search and /summary are instant.
NEWS_CACHE: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Formatters (output -> Telegram-friendly HTML)
# ---------------------------------------------------------------------------

TELEGRAM_MAX = 4000  # Telegram limit is 4096; leave a little headroom.


def _format_news(news: List[Dict[str, Any]], n: int) -> str:
    """Turn the news list into a single HTML string for Telegram."""
    if not news:
        return "🤷 No Solana news right now. Try /refresh in a minute."

    n = min(n, len(news))
    lines = [f"🟣 <b>Top {n} Solana stories:</b>\n"]
    for i, item in enumerate(news[:n], 1):
        ts = datetime.fromtimestamp(item["ts"], tz=timezone.utc)
        when = ts.strftime("%Y-%m-%d %H:%M UTC")
        snippet = item["body"][:200] + ("…" if len(item["body"]) > 200 else "")

        lines.append(f"<b>{i}. {html.escape(item['title'])}</b>")
        lines.append(f"   🕒 {when}  |  📰 {html.escape(item['source'])}")
        if snippet:
            lines.append(f"   {html.escape(snippet)}")
        lines.append(f"   🔗 {item['url']}\n")
    return "\n".join(lines)


def _format_summary(news: List[Dict[str, Any]]) -> str:
    """Return the summary as a string (not printed)."""
    if not news:
        return "Nothing to summarize yet — try /latest first."

    sources: Dict[str, int] = {}
    for it in news:
        sources[it["source"]] = sources.get(it["source"], 0) + 1
    top_sources = sorted(sources.items(), key=lambda x: -x[1])[:3]

    lines = [f"📊 <b>Solana quick summary</b> ({len(news)} items):"]
    lines.append("• Top sources: " + ", ".join(f"{html.escape(s)} ({c})" for s, c in top_sources))
    lines.append(f"• Newest:  {html.escape(news[0]['title'])}")
    lines.append(f"• Oldest:  {html.escape(news[-1]['title'])}")
    lines.append("• Tip: /search &lt;word&gt; to dig into a topic.")
    return "\n".join(lines)


def _format_price() -> str:
    """Fetch the price and return a formatted string."""
    import requests
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=solana&vs_currencies=usd&include_24hr_change=true"
            "&include_market_cap=true&include_24hr_vol=true",
            timeout=10,
        )
        r.raise_for_status()
        d = r.json().get("solana", {})
    except Exception as e:
        return f"⚠️ Could not fetch price: {e}"

    price = d.get("usd")
    if price is None:
        return "⚠️ Price data not available right now."

    change = d.get("usd_24h_change", 0) or 0
    arrow = "🟢" if change >= 0 else "🔴"
    lines = [f"💰 <b>SOL price:</b> ${price:,.2f}  {arrow} {change:+.2f}% (24h)"]
    if d.get("usd_market_cap"):
        lines.append(f"   Market cap: ${d['usd_market_cap']:,.0f}")
    if d.get("usd_24h_vol"):
        lines.append(f"   24h volume: ${d['usd_24h_vol']:,.0f}")
    return "\n".join(lines)


def _chunk(text: str, size: int = TELEGRAM_MAX) -> List[str]:
    """Split a long string into pieces that fit Telegram's message limit."""
    parts = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut == -1:
            cut = size
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts or [""]


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

HELP_TEXT = """\
🟣 <b>Solana News Bot — Commands</b>

/latest — show top 5 Solana stories
/top &lt;N&gt; — show top N, e.g. <code>/top 10</code>
/search &lt;keyword&gt; — search the cached news
/summary — quick overview
/price — current SOL price (CoinGecko)
/refresh — re-fetch news without showing
/help — this message

The bot pulls from 6 RSS feeds (Bitcoinist, NewsBTC, AMBCrypto, CoinDesk, Cointelegraph, Decrypt) and keeps only the Solana items.
"""


async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name or "friend"
    await update.message.reply_text(
        f"Hey {name} 👋\n\n"
        f"I'm your Solana news buddy.\n"
        f"Type /help to see what I can do, or just /latest for the freshest SOL news.",
        parse_mode=ParseMode.HTML,
    )


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def latest_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global NEWS_CACHE
    await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    NEWS_CACHE = fetch_solana_news()
    text = _format_news(NEWS_CACHE, 5)
    for chunk in _chunk(text):
        await update.message.reply_text(
            chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        )


async def top_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global NEWS_CACHE
    try:
        n = int(ctx.args[0]) if ctx.args else 5
    except ValueError:
        await update.message.reply_text("Usage: <code>/top 10</code>  (N must be a number)")
        return
    if n < 1 or n > 50:
        await update.message.reply_text("Pick a number between 1 and 50.")
        return
    await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    if not NEWS_CACHE:
        NEWS_CACHE = fetch_solana_news()
    text = _format_news(NEWS_CACHE, n)
    for chunk in _chunk(text):
        await update.message.reply_text(
            chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        )


async def search_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global NEWS_CACHE
    if not ctx.args:
        await update.message.reply_text("Usage: <code>/search etf</code>")
        return
    keyword = " ".join(ctx.args)
    if not NEWS_CACHE:
        NEWS_CACHE = fetch_solana_news()
    hits = [
        it for it in NEWS_CACHE
        if keyword.lower() in (it["title"] + " " + it["body"]).lower()
    ]
    if not hits:
        await update.message.reply_text(
            f"🤷 Nothing matched <b>{html.escape(keyword)}</b>. Try /refresh first.",
            parse_mode=ParseMode.HTML,
        )
        return
    text = _format_news(hits, len(hits))
    for chunk in _chunk(text):
        await update.message.reply_text(
            chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        )


async def summary_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global NEWS_CACHE
    if not NEWS_CACHE:
        NEWS_CACHE = fetch_solana_news()
    await update.message.reply_text(
        _format_summary(NEWS_CACHE), parse_mode=ParseMode.HTML,
    )


async def price_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    await update.message.reply_text(
        _format_price(), parse_mode=ParseMode.HTML,
    )


async def refresh_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    global NEWS_CACHE
    await ctx.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    NEWS_CACHE = fetch_solana_news()
    await update.message.reply_text(
        f"✅ Refreshed — {len(NEWS_CACHE)} Solana items in the cache."
    )


async def unknown_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤔 I didn't catch that. Type /help to see commands."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("🟣 Solana News Bot starting...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",   start_cmd))
    app.add_handler(CommandHandler("help",    help_cmd))
    app.add_handler(CommandHandler("latest",  latest_cmd))
    app.add_handler(CommandHandler("top",     top_cmd))
    app.add_handler(CommandHandler("search",  search_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("price",   price_cmd))
    app.add_handler(CommandHandler("refresh", refresh_cmd))
    # Catch-all for unknown commands (anything starting with "/")
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    print("✅ Bot is live. Open Telegram and message your bot.")
    print("   Press Ctrl+C here to stop it.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
