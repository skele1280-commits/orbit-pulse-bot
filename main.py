#!/usr/bin/env python3
"""
ORBIT Pulse Bot - Advanced Crypto Trading Assistant
Features: Link downloads, crypto analysis, price alerts, GPT chat
"""

import os
import json
import time
import asyncio
import subprocess
import tempfile
import requests
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================
# CONFIG
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Cache settings
PULSE_CACHE_TTL = 60  # 60 seconds
COIN_LIST_CACHE_TTL = 86400  # 24 hours
ALERT_CHECK_INTERVAL = 60  # Check alerts every 60 seconds

# Storage files
URL_STORE_FILE = "url_store.json"
ALERTS_FILE = "alerts.json"
GPT_HISTORY_FILE = "gpt_history.json"

# Global caches
pulse_cache = None
pulse_cache_time = 0
coin_list_cache = None
coin_list_cache_time = 0
price_cache = {}
price_cache_time = 0

# User state
url_store = {}  # {user_id: {"url": str, "platform": str, "timestamp": int}}
gpt_chat_active = {}  # {user_id: bool}
gpt_history = {}  # {user_id: [messages]}

# ============================================
# PERSISTENCE
# ============================================
def load_json(filename, default=None):
    """Load JSON from file"""
    if default is None:
        default = {}
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[LOAD_ERROR] {filename}: {e}")
    return default

def save_json(filename, data):
    """Save JSON to file"""
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[SAVE_ERROR] {filename}: {e}")

# Load persistent data
alerts_db = load_json(ALERTS_FILE, {})  # {user_id: [{coin, direction, price, id}]}
url_store = load_json(URL_STORE_FILE, {})
gpt_history = load_json(GPT_HISTORY_FILE, {})

# ============================================
# API HELPERS
# ============================================
def cg_request(endpoint, params=None, retries=3):
    """CoinGecko API with retry on 429"""
    for attempt in range(retries):
        try:
            url = f"https://api.coingecko.com/api/v3{endpoint}"
            resp = requests.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = 5 * (2 ** attempt)  # 5s, 10s, 20s
                print(f"[CG_429] Retry in {wait}s...")
                time.sleep(wait)
            else:
                print(f"[CG_ERROR] {resp.status_code}")
                return None
        except Exception as e:
            print(f"[CG_ERROR] {e}")
            return None
    return None

def coincap_fetch(endpoint, params=None):
    """CoinCap API fallback"""
    try:
        url = f"https://api.coincap.io/v2{endpoint}"
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data")
    except Exception as e:
        print(f"[CC_ERROR] {e}")
    return None

def binance_fetch_top(limit=100):
    """Binance public API - fastest, no auth needed"""
    try:
        # Get top coins by volume (24h)
        url = "https://api.binance.com/api/v3/ticker/24hr"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        
        tickers = resp.json()
        # Filter USDT pairs only
        usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
        # Sort by quote volume (biggest first)
        usdt_pairs.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
        
        coins = []
        for i, ticker in enumerate(usdt_pairs[:limit]):
            symbol = ticker['symbol'].replace('USDT', '')
            coins.append({
                "id": symbol.lower(),
                "name": symbol,
                "symbol": symbol,
                "current_price": float(ticker.get('lastPrice', 0)),
                "price_change_percentage_24h_in_currency": float(ticker.get('priceChangePercent', 0)),
                "total_volume": float(ticker.get('quoteVolume', 0)),
                "market_cap": None,  # Binance doesn't provide this
            })
        
        print(f"[BINANCE] Fetched {len(coins)} coins")
        return coins
    except Exception as e:
        print(f"[BINANCE_ERROR] {e}")
        return None

# ============================================
# COIN DATA FETCHING
# ============================================
def fetch_coin_list():
    """Fetch full coin list (cached 24h)"""
    global coin_list_cache, coin_list_cache_time
    now = time.time()
    
    if coin_list_cache and (now - coin_list_cache_time) < COIN_LIST_CACHE_TTL:
        return coin_list_cache
    
    data = cg_request("/coins/list")
    if data:
        coin_list_cache = data
        coin_list_cache_time = now
        return data
    
    return coin_list_cache or []

def fetch_top_coins(limit=50):
    """Fetch top coins with caching - tries Binance (fastest) first"""
    global pulse_cache, pulse_cache_time
    now = time.time()
    
    if pulse_cache and (now - pulse_cache_time) < PULSE_CACHE_TTL:
        return pulse_cache
    
    # Try Binance first (fastest, most reliable)
    binance_data = binance_fetch_top(limit)
    if binance_data and len(binance_data) >= 5:
        pulse_cache = binance_data
        pulse_cache_time = now
        return binance_data
    
    # Fallback to CoinGecko
    print("[FALLBACK] Binance failed, trying CoinGecko...")
    data = cg_request(
        "/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h",
        },
    )
    
    if data and len(data) >= 5:
        pulse_cache = data
        pulse_cache_time = now
        return data
    
    # Final fallback to CoinCap
    print("[FALLBACK] CoinGecko failed, trying CoinCap...")
    cc_data = coincap_fetch("/assets", {"limit": limit})
    if cc_data:
        normalized = []
        for c in cc_data:
            normalized.append({
                "id": c.get("id", "").lower(),
                "name": c.get("name", "Unknown"),
                "symbol": c.get("symbol", "???").upper(),
                "current_price": float(c.get("priceUsd", 0)),
                "market_cap": float(c.get("marketCapUsd", 0)) if c.get("marketCapUsd") else None,
                "total_volume": float(c.get("volumeUsd24Hr", 0)) if c.get("volumeUsd24Hr") else None,
                "price_change_percentage_24h_in_currency": float(c.get("changePercent24Hr", 0)),
            })
        pulse_cache = normalized
        pulse_cache_time = now
        return normalized
    
    # Return stale cache if everything fails
    return pulse_cache or []

def fetch_top_gainers(limit=100, min_volume=100000):
    """Fetch top 3 gainers"""
    coins = fetch_top_coins(limit)
    
    filtered = [
        c for c in coins
        if c.get("total_volume", 0) and c.get("total_volume") >= min_volume
        and c.get("price_change_percentage_24h_in_currency") is not None
    ]
    
    sorted_coins = sorted(
        filtered,
        key=lambda x: x.get("price_change_percentage_24h_in_currency", 0),
        reverse=True
    )
    
    return sorted_coins[:3]

def search_coin(query):
    """Search for coin by symbol/name"""
    query = query.lower().strip()
    coins = fetch_coin_list()
    
    matches = []
    for coin in coins:
        if (
            query in coin.get("id", "").lower()
            or query in coin.get("name", "").lower()
            or query == coin.get("symbol", "").lower()
        ):
            matches.append(coin)
            if len(matches) >= 5:
                break
    
    return matches

# ============================================
# FORMATTING
# ============================================
def fmt_price(price):
    if not price:
        return "N/A"
    if price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"

def fmt_change(change):
    if change is None:
        return "N/A"
    emoji = "📈" if change >= 0 else "📉"
    return f"{emoji} {change:+.2f}%"

def fmt_mcap(mcap):
    if not mcap:
        return "N/A"
    if mcap >= 1e9:
        return f"${mcap / 1e9:.1f}B"
    elif mcap >= 1e6:
        return f"${mcap / 1e6:.1f}M"
    else:
        return f"${mcap:,.0f}"

# ============================================
# DOWNLOAD FUNCTIONALITY
# ============================================
def detect_platform(url):
    """Detect platform from URL"""
    url_lower = url.lower()
    platforms = {
        "youtube": ["youtube.com", "youtu.be"],
        "tiktok": ["tiktok.com", "vm.tiktok.com"],
        "instagram": ["instagram.com"],
        "twitter": ["twitter.com", "x.com"],
        "facebook": ["facebook.com", "fb.watch"],
    }
    
    for platform, domains in platforms.items():
        if any(d in url_lower for d in domains):
            return platform.upper()
    return None

def download_video(url):
    """Download video using yt-dlp"""
    temp_file = None
    cookies_path = None
    
    try:
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"orbit_{os.urandom(4).hex()}")
        
        # Check for cookies file (Railway volume mount or local)
        possible_paths = [
            "/app/cookies_filtered.txt",  # Railway volume
            os.path.join(os.path.dirname(__file__), "cookies_filtered.txt"),  # Local
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and os.path.getsize(path) > 200:
                cookies_path = path
                print(f"[DOWNLOAD] Using YouTube cookies from {path}")
                break
        
        # Fallback: Check environment variable
        if not cookies_path:
            yt_cookies = os.getenv("YOUTUBE_COOKIES")
            if yt_cookies and len(yt_cookies) > 100:
                cookies_path = os.path.join(temp_dir, f"cookies_{os.urandom(4).hex()}.txt")
                with open(cookies_path, "w") as f:
                    f.write(yt_cookies)
                print(f"[DOWNLOAD] Using YouTube cookies from environment")
        
        # Add flags to bypass age restrictions and improve success rate
        cmd = [
            "yt-dlp",
            "--no-check-certificate",
            "-f", "best[height<=720]",  # Limit to 720p for faster downloads
            "--no-playlist",
            "-o", f"{temp_file}.%(ext)s",
        ]
        
        # Add cookies if available
        if cookies_path:
            cmd.extend(["--cookies", cookies_path])
        
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Download failed"
            
            # Better error messages
            if "Sign in to confirm" in error_msg or "age" in error_msg.lower():
                return {"success": False, "error": "Age-restricted video (requires login)"}
            elif "Video unavailable" in error_msg:
                return {"success": False, "error": "Video unavailable or private"}
            elif "429" in error_msg or "rate" in error_msg.lower():
                return {"success": False, "error": "Rate limited - try again later"}
            else:
                return {"success": False, "error": error_msg[:80]}
        
        # Find downloaded file
        for ext in [".mp4", ".mkv", ".webm", ".m4a", ".mp3"]:
            path = f"{temp_file}{ext}"
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read()
                
                if len(data) > 50 * 1024 * 1024:
                    return {"success": False, "error": f"File too large: {len(data) / 1024 / 1024:.1f}MB"}
                
                return {
                    "success": True,
                    "data": data,
                    "filename": os.path.basename(path),
                    "size": len(data)
                }
        
        return {"success": False, "error": "No file created"}
    
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Download timeout (>2min)"}
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}
    finally:
        # Cleanup downloaded files
        if temp_file:
            for ext in [".mp4", ".mkv", ".webm", ".m4a", ".mp3", ""]:
                try:
                    path = f"{temp_file}{ext}"
                    if os.path.exists(path):
                        os.remove(path)
                except:
                    pass
        
        # Cleanup temp cookies file
        if cookies_path and os.path.exists(cookies_path):
            try:
                os.remove(cookies_path)
            except:
                pass

# ============================================
# COMMANDS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    msg = """🚀 ORBIT Pulse Bot

📊 **Crypto Commands:**
/pulse - Top 50 cryptocurrencies
/pulse [coin] - Quick lookup (e.g., /pulse btc)
/winner - Top 3 gainers (24h)
/alert BTC above 50000 - Set price alert
/alerts - View your alerts

🎥 **Media Commands:**
Send any link → Auto-detect
/scan - Analyze last link
/grab - Download last link

🤖 **AI Commands:**
/gpt - Start chat mode
/gpt off - Stop chat mode
/ask [question] - One-shot question
/clear - Clear chat history

🔒 **Security:**
/security - Safety checklist

💡 **Examples:**
• /pulse sol
• /alert ETH below 2500
• Send YouTube link → /grab"""
    
    await update.message.reply_text(msg)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await start(update, context)

async def security(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Security checklist"""
    msg = """🔒 **Security Checklist**

✅ Never share:
• Seed phrases
• Private keys
• Passwords
• Recovery phrases

✅ This bot will NEVER:
• Ask for your seed phrase
• Request your private keys
• Promise guaranteed profits
• Give buy/sell orders

✅ Best practices:
• Use hardware wallets
• Enable 2FA everywhere
• Verify contract addresses
• Research before investing

⚠️ **This bot provides information only.**
**Not financial advice. DYOR.**"""
    
    await update.message.reply_text(msg)

# ============================================
# LINK DETECTION
# ============================================
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detect and store links"""
    text = update.message.text.strip()
    
    if not text.startswith("http"):
        return
    
    platform = detect_platform(text)
    if not platform:
        return
    
    user_id = str(update.effective_user.id)
    url_store[user_id] = {
        "url": text,
        "platform": platform,
        "timestamp": int(time.time())
    }
    save_json(URL_STORE_FILE, url_store)
    
    msg = f"🔗 {platform} link detected!\n\nUse:\n/scan - Analyze\n/grab - Download"
    await update.message.reply_text(msg)

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze last detected link"""
    user_id = str(update.effective_user.id)
    
    if user_id not in url_store:
        await update.message.reply_text("❌ No recent link found.\nSend a link first!")
        return
    
    data = url_store[user_id]
    age = int(time.time()) - data["timestamp"]
    
    msg = f"📊 **Link Analysis**\n\n"
    msg += f"Platform: {data['platform']}\n"
    msg += f"URL: {data['url'][:50]}...\n"
    msg += f"Detected: {age}s ago\n\n"
    msg += "Use /grab to download"
    
    await update.message.reply_text(msg)

async def grab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Download last detected link"""
    user_id = str(update.effective_user.id)
    
    if user_id not in url_store:
        await update.message.reply_text("❌ No recent link found.\nSend a link first!")
        return
    
    data = url_store[user_id]
    url = data["url"]
    platform = data["platform"]
    
    print(f"[GRAB] User {user_id} downloading from {platform}: {url[:80]}")
    
    status = await update.message.reply_text(f"⏳ Downloading from {platform}...\nPlease wait (1-2 min)")
    
    result = download_video(url)
    
    print(f"[GRAB] Result: success={result.get('success')}, error={result.get('error', 'none')[:80]}")
    
    if not result["success"]:
        error_detail = result.get('error', 'Unknown error')
        await status.edit_text(
            f"❌ Download failed\n\n"
            f"Error: {error_detail}\n\n"
            f"Platform: {platform}\n"
            f"If age-restricted, cookies may need refresh."
        )
        return
    
    try:
        from io import BytesIO
        file_data = BytesIO(result["data"])
        file_data.name = result["filename"]
        
        await status.edit_text(f"✅ Downloaded! Sending...")
        
        if result["filename"].endswith(".mp4"):
            await update.message.reply_video(file_data)
        elif result["filename"].endswith(".mp3"):
            await update.message.reply_audio(file_data)
        else:
            await update.message.reply_document(file_data)
        
        await update.message.reply_text("✅ Done!")
    except Exception as e:
        await update.message.reply_text(f"❌ Send failed: {str(e)[:50]}")

# ============================================
# /pulse COMMAND
# ============================================
async def pulse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 50 coins or search"""
    # Search mode
    if context.args:
        search_term = " ".join(context.args).lower().strip()
        
        coins = fetch_top_coins(100)
        found = None
        
        for coin in coins:
            if (
                search_term in coin.get("id", "").lower()
                or search_term in coin.get("name", "").lower()
                or search_term == coin.get("symbol", "").lower()
            ):
                found = coin
                break
        
        if not found:
            await update.message.reply_text(
                f"❌ '{search_term}' not found.\n\n"
                "Try: /pulse btc, /pulse solana"
            )
            return
        
        msg = f"📊 **{found['name']} ({found['symbol'].upper()})**\n\n"
        msg += f"💰 Price: {fmt_price(found.get('current_price'))}\n"
        msg += f"24h: {fmt_change(found.get('price_change_percentage_24h_in_currency'))}\n"
        msg += f"Market Cap: {fmt_mcap(found.get('market_cap'))}\n"
        
        await update.message.reply_text(msg)
        return
    
    # Browse mode - fetch 100 coins (Binance is fast enough)
    coins = fetch_top_coins(100)
    
    if not coins:
        await update.message.reply_text("⏳ Data unavailable - try again")
        return
    
    msg = "📊 **Top Cryptocurrencies (by 24h Volume)**\n\n"
    for i, coin in enumerate(coins[:20], 1):
        name = coin.get("name", "Unknown")[:12]
        symbol = coin.get("symbol", "???").upper()
        price = fmt_price(coin.get("current_price"))
        change = fmt_change(coin.get("price_change_percentage_24h_in_currency"))
        msg += f"{i}. **{name}** ({symbol})\n   {price} | {change}\n\n"
    
    msg += f"\nShowing 20/{len(coins)} coins\nUse /pulse [coin] to search"
    await update.message.reply_text(msg)

# ============================================
# /winner COMMAND
# ============================================
async def winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 3 gainers"""
    gainers = fetch_top_gainers()
    
    if not gainers:
        await update.message.reply_text("⏳ Data unavailable")
        return
    
    msg = "🏆 **Top 3 Gainers (24h)**\n\n"
    for i, coin in enumerate(gainers, 1):
        name = coin.get("name", "Unknown")
        symbol = coin.get("symbol", "???").upper()
        price = fmt_price(coin.get("current_price"))
        change = fmt_change(coin.get("price_change_percentage_24h_in_currency"))
        vol = fmt_mcap(coin.get("total_volume"))
        
        msg += f"{i}. **{name}** ({symbol})\n"
        msg += f"   {price} | {change}\n"
        msg += f"   Volume: {vol}\n\n"
    
    await update.message.reply_text(msg)

# ============================================
# ALERT SYSTEM
# ============================================
async def alert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage price alerts"""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "/alert BTC above 50000\n"
            "/alert ETH below 2500\n"
            "/alerts - View all\n"
            "/alert clear - Remove all"
        )
        return
    
    # Clear all alerts
    if context.args[0].lower() == "clear":
        alerts_db[user_id] = []
        save_json(ALERTS_FILE, alerts_db)
        await update.message.reply_text("✅ All alerts cleared")
        return
    
    # Create alert
    if len(context.args) < 3:
        await update.message.reply_text("❌ Format: /alert SYMBOL above/below PRICE")
        return
    
    symbol = context.args[0].upper()
    direction = context.args[1].lower()
    
    try:
        price = float(context.args[2])
    except:
        await update.message.reply_text("❌ Invalid price")
        return
    
    if direction not in ["above", "below"]:
        await update.message.reply_text("❌ Use 'above' or 'below'")
        return
    
    # Find coin
    matches = search_coin(symbol)
    if not matches:
        await update.message.reply_text(f"❌ Coin '{symbol}' not found")
        return
    
    coin_id = matches[0]["id"]
    coin_name = matches[0]["name"]
    
    # Create alert
    if user_id not in alerts_db:
        alerts_db[user_id] = []
    
    if len(alerts_db[user_id]) >= 10:
        await update.message.reply_text("❌ Max 10 alerts per user")
        return
    
    alert = {
        "id": int(time.time()),
        "coin_id": coin_id,
        "coin_name": coin_name,
        "symbol": symbol,
        "direction": direction,
        "price": price,
    }
    
    alerts_db[user_id].append(alert)
    save_json(ALERTS_FILE, alerts_db)
    
    await update.message.reply_text(
        f"✅ Alert set: {coin_name} ({symbol}) {direction} ${price:,.2f}"
    )

async def alerts_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all alerts"""
    user_id = str(update.effective_user.id)
    
    if user_id not in alerts_db or not alerts_db[user_id]:
        await update.message.reply_text("No active alerts\n\nUse /alert to create one")
        return
    
    msg = "🔔 **Your Alerts**\n\n"
    for alert in alerts_db[user_id]:
        msg += f"• {alert['coin_name']} ({alert['symbol']}) {alert['direction']} ${alert['price']:,.2f}\n"
    
    msg += f"\n{len(alerts_db[user_id])} active alerts"
    await update.message.reply_text(msg)

# ============================================
# GPT INTEGRATION
# ============================================
async def gpt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle GPT chat mode"""
    user_id = str(update.effective_user.id)
    
    if context.args and context.args[0].lower() == "off":
        gpt_chat_active[user_id] = False
        await update.message.reply_text("🤖 GPT chat mode OFF")
        return
    
    gpt_chat_active[user_id] = True
    await update.message.reply_text(
        "🤖 GPT chat mode ON\n\n"
        "Send any message to chat.\n"
        "Use /gpt off to stop."
    )

async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """One-shot GPT question"""
    if not context.args:
        await update.message.reply_text("Usage: /ask [your question]")
        return
    
    question = " ".join(context.args)
    await update.message.reply_text("🤔 Thinking...")
    
    # TODO: Implement OpenAI call
    await update.message.reply_text(
        "⚠️ GPT integration coming soon!\n"
        f"Your question: {question[:100]}"
    )

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear GPT history"""
    user_id = str(update.effective_user.id)
    gpt_history[user_id] = []
    save_json(GPT_HISTORY_FILE, gpt_history)
    await update.message.reply_text("✅ Chat history cleared")

# ============================================
# ALERT CHECKER (Background)
# ============================================
async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Background task to check alerts"""
    global price_cache, price_cache_time
    
    if not alerts_db:
        return
    
    # Fetch current prices
    coins = fetch_top_coins(250)
    current_prices = {c["id"]: c.get("current_price") for c in coins}
    
    # Check each user's alerts
    for user_id, alerts in list(alerts_db.items()):
        triggered = []
        
        for alert in alerts[:]:
            coin_id = alert["coin_id"]
            target_price = alert["price"]
            direction = alert["direction"]
            
            current = current_prices.get(coin_id)
            if not current:
                continue
            
            # Check if triggered
            if (direction == "above" and current >= target_price) or \
               (direction == "below" and current <= target_price):
                triggered.append(alert)
                alerts.remove(alert)
        
        # Send notifications
        if triggered:
            for alert in triggered:
                msg = f"🔔 **Alert Triggered!**\n\n"
                msg += f"{alert['coin_name']} ({alert['symbol']})\n"
                msg += f"Target: {alert['direction']} ${alert['price']:,.2f}\n"
                msg += f"Current: ${current_prices[alert['coin_id']]:,.2f}"
                
                try:
                    await context.bot.send_message(chat_id=int(user_id), text=msg)
                except Exception as e:
                    print(f"[ALERT_SEND_ERROR] {e}")
        
        # Update database
        alerts_db[user_id] = alerts
    
    save_json(ALERTS_FILE, alerts_db)

# ============================================
# MAIN
# ============================================
def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not set!")
        return
    
    print("🚀 Starting ORBIT Pulse Bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("security", security))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("grab", grab))
    app.add_handler(CommandHandler("pulse", pulse))
    app.add_handler(CommandHandler("winner", winner))
    app.add_handler(CommandHandler("alert", alert_cmd))
    app.add_handler(CommandHandler("alerts", alerts_list))
    app.add_handler(CommandHandler("gpt", gpt_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("clear", clear_history))
    
    # Link detection
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^https?://"), handle_link))
    
    # Background alert checker
    app.job_queue.run_repeating(check_alerts, interval=ALERT_CHECK_INTERVAL, first=10)
    
    print("✅ Bot started. Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
