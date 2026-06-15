"""
🟣 Solana News Agent
====================
A simple, beginner-friendly Python agent that fetches and shows you
news only about Solana (SOL). No API keys required.

How it works:
  - Pulls a few public RSS feeds that publish Solana-tagged stories.
  - Combines them, removes duplicates, sorts by date (newest first).
  - Shows them in a small REPL where you can type commands like
    `latest`, `top 10`, `search etf`, `summary`, `price`, `exit`.

Run:
    pip install requests
    python solana_news_agent.py
"""

import html
import re
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from xml.etree import ElementTree as ET

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Public RSS feeds that already filter for Solana content.
# We pull from several and merge the results, so a story shows up once.
SOLANA_RSS_FEEDS: List[Dict[str, str]] = [
    {"source": "Bitcoinist",   "url": "https://bitcoinist.com/tag/solana/feed/"},
    {"source": "NewsBTC",      "url": "https://www.newsbtc.com/news/solana/feed/"},
    {"source": "AMBCrypto",    "url": "https://ambcrypto.com/tag/solana/feed/"},
]

# Bigger general crypto feeds — we keep only the items that mention Solana.
GENERAL_RSS_FEEDS: List[Dict[str, str]] = [
    {"source": "CoinDesk",     "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"source": "Cointelegraph","url": "https://cointelegraph.com/rss"},
    {"source": "Decrypt",      "url": "https://decrypt.co/feed"},
]

SOL_KEYWORDS = ("solana", "sol ")  # 'sol ' catches '$SOL' / 'SOL price' but not 'resolve'

COINGECKO_PRICE_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=solana&vs_currencies=usd&include_24hr_change=true"
    "&include_market_cap=true&include_24hr_vol=true"
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SolanaNewsAgent/0.1)"}

# Cache of the last fetched solana news, so `search` and `summary` are fast.
CACHE: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities — feeds come full of <p> etc."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _is_solana_related(title: str, body: str) -> bool:
    """Return True if the article is talking about Solana (rough but good)."""
    blob = f" {title} {body} ".lower()
    if "solana" in blob:
        return True
    if " sol " in blob or "$sol" in blob or " sol-" in blob:
        return True
    return False


def _parse_pub_date(raw: str) -> int:
    """Return a unix timestamp from an RSS pubDate string. Fallback = now."""
    if not raw:
        return int(time.time())
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            return int(datetime.strptime(raw, fmt).timestamp())
        except ValueError:
            continue
    return int(time.time())


def _fetch_feed(source: str, url: str) -> List[Dict[str, Any]]:
    """Download one RSS feed and turn each <item> into a clean dict."""
    try:
        resp = requests.get(url, timeout=10, headers=HEADERS)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f"  ⚠️  {source}: {e}")
        return []

    items: List[Dict[str, Any]] = []
    for it in root.iter("item"):
        title = _strip_html((it.findtext("title") or "").strip())
        body = _strip_html((it.findtext("description") or "").strip())
        link = (it.findtext("link") or "").strip()
        pub = _parse_pub_date((it.findtext("pubDate") or "").strip())
        if not title or not link:
            continue
        items.append({
            "title": title,
            "body": body,
            "url": link,
            "source": source,
            "ts": pub,
        })
    return items


def fetch_solana_news(limit_per_feed: int = 25) -> List[Dict[str, Any]]:
    """Fetch from all feeds, filter to Solana, dedupe, sort newest first."""
    print("📡 Pulling fresh Solana news...", end=" ", flush=True)

    candidates: List[Dict[str, Any]] = []
    for feed in SOLANA_RSS_FEEDS + GENERAL_RSS_FEEDS:
        candidates.extend(_fetch_feed(feed["source"], feed["url"]))

    solana_only = [c for c in candidates if _is_solana_related(c["title"], c["body"])]

    # Dedupe by article URL; fall back to title if URL is missing.
    seen = set()
    unique: List[Dict[str, Any]] = []
    for c in solana_only:
        key = c["url"] or c["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    unique.sort(key=lambda x: x["ts"], reverse=True)
    print(f"got {len(unique)} items.")
    return unique[:limit_per_feed]


def get_sol_price() -> None:
    """Show current SOL price + 24h change + market cap."""
    try:
        r = requests.get(COINGECKO_PRICE_URL, timeout=10, headers=HEADERS)
        r.raise_for_status()
        data = r.json().get("solana", {})
    except Exception as e:
        print(f"  ⚠️  Could not fetch price: {e}\n")
        return

    price = data.get("usd")
    change = data.get("usd_24h_change")
    mcap = data.get("usd_market_cap")
    vol = data.get("usd_24h_vol")

    if price is None:
        print("  ⚠️  Price data not available right now.\n")
        return

    arrow = "🟢" if (change or 0) >= 0 else "🔴"
    print(f"\n💰 SOL price: ${price:,.2f}  {arrow} {change:+.2f}% (24h)")
    if mcap:  print(f"   Market cap: ${mcap:,.0f}")
    if vol:   print(f"   24h volume: ${vol:,.0f}")
    print()


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def pretty_print(news: List[Dict[str, Any]], n: int = 5) -> None:
    """Show the top n items in a friendly layout."""
    if not news:
        print("\n🤷 No Solana news right now. Try `refresh` in a minute.\n")
        return

    print(f"\n🟣 Top {min(n, len(news))} Solana stories:\n")
    for i, item in enumerate(news[:n], 1):
        ts = datetime.fromtimestamp(item["ts"], tz=timezone.utc)
        when = ts.strftime("%Y-%m-%d %H:%M UTC")
        snippet = item["body"][:220] + ("..." if len(item["body"]) > 220 else "")

        print(f"{i}. {item['title']}")
        print(f"   🕒 {when}  |  📰 {item['source']}")
        if snippet:
            print(f"   {snippet}")
        print(f"   🔗 {item['url']}")
        print()
    print("-" * 60)


def summarize(news: List[Dict[str, Any]]) -> None:
    """Quick textual summary of the latest Solana news set."""
    if not news:
        print("\nNothing to summarize yet — try `latest` first.\n")
        return

    sources: Dict[str, int] = {}
    for it in news:
        sources[it["source"]] = sources.get(it["source"], 0) + 1
    top_sources = sorted(sources.items(), key=lambda x: -x[1])[:3]

    print(f"\n📊 Solana quick summary ({len(news)} items):")
    print("   • Top sources:", ", ".join(f"{s} ({c})" for s, c in top_sources))
    print(f"   • Newest:  {news[0]['title']}")
    print(f"   • Oldest:  {news[-1]['title']}")
    print("   • Tip: type `search <word>` to dig into a topic.\n")
    print("-" * 60)


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

HELP_TEXT = """
Commands:
  latest            -> fetch & show top 5 Solana stories
  top <N>           -> show top N items, e.g. `top 10`
  search <keyword>  -> search inside the cached Solana news
  summary           -> quick overview of the latest batch
  price             -> show current SOL price (via CoinGecko)
  refresh           -> re-fetch news without showing
  help              -> this help text
  exit / quit       -> leave the agent
"""


def repl() -> None:
    """The main interactive loop."""
    print("🟣 Solana News Agent — your AI buddy for SOL news")
    print("Type `help` anytime. Type `exit` to leave.\n")

    while True:
        try:
            cmd = input("sol-agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye! 👋")
            return
        if not cmd:
            continue

        low = cmd.lower()

        if low in ("exit", "quit", "q"):
            print("Bye! 👋")
            return
        if low == "help":
            print(HELP_TEXT)
            continue
        if low == "refresh":
            globals()["CACHE"] = fetch_solana_news()
            print(f"✅ Cache now has {len(CACHE)} items.\n")
            continue
        if low == "summary":
            if not CACHE:
                globals()["CACHE"] = fetch_solana_news()
            summarize(CACHE)
            continue
        if low == "price":
            get_sol_price()
            continue
        if low == "latest":
            globals()["CACHE"] = fetch_solana_news()
            pretty_print(CACHE, 5)
            continue
        if low.startswith("top "):
            try:
                n = int(low.split()[1])
            except (ValueError, IndexError):
                print("Usage: top <N>  (e.g. `top 10`)\n")
                continue
            if not CACHE:
                globals()["CACHE"] = fetch_solana_news()
            pretty_print(CACHE, n)
            continue
        if low.startswith("search "):
            keyword = cmd[7:].strip()
            if not keyword:
                print("Usage: search <keyword>\n")
                continue
            if not CACHE:
                globals()["CACHE"] = fetch_solana_news()
            hits = [
                it for it in CACHE
                if keyword.lower() in (it["title"] + " " + it["body"]).lower()
            ]
            if not hits:
                print(f"🤷 Nothing in the cache matched '{keyword}'. Try `refresh`.\n")
            else:
                print(f"\n🔍 {len(hits)} match(es) for '{keyword}':")
                pretty_print(hits, len(hits))
            continue

        print("🤔 I didn't catch that. Type `help` to see commands.\n")


if __name__ == "__main__":
    repl()
