#!/usr/bin/env python3
"""
ORBIT Pulse Bot - Telegram Crypto Trading Bot
Shows top 50 cryptocurrencies with pagination
"""

import os
import time
import requests
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Import downloader
from simple_downloader import detect_platform, download_from_platform


# ============================================
# COIN ANALYSIS (Simple)
# ============================================
def simple_coin_analysis(coin_name, price, change_24h, market_cap, volume):
    """Simple coin analysis without complex modules"""
    msg = f"📊 {coin_name.upper()}\n"
    msg += f"━━━━━━━━━━━━━━━━\n"
    msg += f"💰 Price: ${price:,.2f}\n"
    msg += f"24h: {change_24h:+.2f}%\n\n"
    
    # Simple trend
    if change_24h > 5:
        trend = "🟢 STRONG BULLISH"
    elif change_24h > 0:
        trend = "🟢 BULLISH"
    elif change_24h < -5:
        trend = "🔴 STRONG BEARISH"
    else:
        trend = "🔴 BEARISH"
    
    msg += f"Trend: {trend}\n\n"
    
    # Market data
    if market_cap:
        if market_cap >= 1e12:
            mcap_str = f"${market_cap / 1e12:.2f}T"
        elif market_cap >= 1e9:
            mcap_str = f"${market_cap / 1e9:.2f}B"
        else:
            mcap_str = f"${market_cap / 1e6:.2f}M"
        msg += f"Market Cap: {mcap_str}\n"
    
    if volume:
        if volume >= 1e9:
            vol_str = f"${volume / 1e9:.2f}B"
        else:
            vol_str = f"${volume / 1e6:.2f}M"
        msg += f"24h Volume: {vol_str}\n"
    
    msg += f"\n⚠️ Not financial advice"
    return msg

# ============================================
# CONFIG
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",")]
ADMIN_NAME = os.getenv("ADMIN_NAME", "admin")

PULSE_CACHE_TTL = 300  # 5 minutes
pulse_cache = None
pulse_cache_time = 0

coin_pagination = {}  # Format: {user_id: current_page}

# ============================================
# API CALLS
# ============================================
def cg_request(endpoint, params=None):
    """Fetch from CoinGecko API"""
    try:
        url = f"https://api.coingecko.com/api/v3{endpoint}"
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[CG_ERROR] {e}")
    return None


def coincap_fetch_top(limit=50):
    """Fallback to CoinCap API"""
    try:
        url = f"https://api.coincap.io/v2/assets?limit={limit}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            coins = []
            for c in data:
                coin = {
                    "id": c.get("id", "").lower(),
                    "name": c.get("name", "Unknown"),
                    "symbol": c.get("symbol", "???").upper(),
                    "current_price": float(c.get("priceUsd", 0)),
                    "market_cap": None,
                    "total_volume": None,
                    "price_change_percentage_1h_in_currency": float(
                        c.get("changePercent24Hr", 0)
                    ) / 24,  # Rough estimate
                    "price_change_percentage_24h_in_currency": float(
                        c.get("changePercent24Hr", 0)
                    ),
                }
                coins.append(coin)
            return coins
    except Exception as e:
        print(f"[COINCAP_ERROR] {e}")
    return None


def normalize_coin_list(raw):
    """Normalize CoinGecko response"""
    normalized = []
    for c in raw:
        normalized.append(
            {
                "id": c.get("id", "").lower(),
                "name": c.get("name", "Unknown"),
                "symbol": c.get("symbol", "???").upper(),
                "current_price": c.get("current_price"),
                "market_cap": c.get("market_cap"),
                "total_volume": c.get("total_volume"),
                "price_change_percentage_1h_in_currency": c.get(
                    "price_change_percentage_1h_in_currency"
                ),
                "price_change_percentage_24h_in_currency": c.get(
                    "price_change_percentage_24h_in_currency"
                ),
            }
        )
    return normalized


# ============================================
# FORMATTING
# ============================================
def fmt_price(price):
    """Format price"""
    if not price:
        return "N/A"
    if price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.8f}"


def fmt_change(change):
    """Format percentage change"""
    if change is None:
        return "N/A"
    emoji = "📈" if change >= 0 else "📉"
    return f"{emoji} {change:+.2f}%"


def fmt_mcap(mcap):
    """Format market cap"""
    if not mcap:
        return "N/A"
    if mcap >= 1e9:
        return f"${mcap / 1e9:.1f}B"
    elif mcap >= 1e6:
        return f"${mcap / 1e6:.1f}M"
    else:
        return f"${mcap:,.0f}"


def fmt_vol(vol):
    """Format volume"""
    if not vol:
        return "N/A"
    if vol >= 1e9:
        return f"${vol / 1e9:.1f}B"
    elif vol >= 1e6:
        return f"${vol / 1e6:.1f}M"
    else:
        return f"${vol:,.0f}"


def get_coin_change(coin, period):
    """Get price change for period"""
    if period == "1h":
        return coin.get("price_change_percentage_1h_in_currency")
    elif period == "24h":
        return coin.get("price_change_percentage_24h_in_currency")
    return None


def get_coin_short_id(coin_id):
    """Get short ID for callback"""
    return coin_id[:10] if coin_id else "unknown"


# ============================================
# FETCH TOP 50 COINS
# ============================================
def fetch_top_coins(limit=50):
    """Fetch top coins with caching"""
    global pulse_cache, pulse_cache_time
    now = time.time()
    
    # Check cache
    if pulse_cache and (now - pulse_cache_time) < PULSE_CACHE_TTL:
        print(f"[CACHE] Serving pulse from cache (age: {int(now - pulse_cache_time)}s)")
        return pulse_cache
    
    # Try CoinGecko
    raw = cg_request(
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
    
    if raw:
        validated = normalize_coin_list(raw)
        if len(validated) >= 5:
            pulse_cache = validated
            pulse_cache_time = now
            return validated
    
    # Fallback to CoinCap
    print("[FALLBACK] CoinGecko failed, trying CoinCap...")
    cc_data = coincap_fetch_top(limit)
    if cc_data and len(cc_data) >= 5:
        pulse_cache = cc_data
        pulse_cache_time = now
        return cc_data
    
    # Return stale cache if available
    if pulse_cache:
        print("[CACHE] Both APIs failed — serving stale cache")
        return pulse_cache
    
    return None


# ============================================
# BUILD PAGINATED MESSAGE
# ============================================
def build_coins_page_text(coins, page=0, total_pages=5):
    """Build message for a specific page"""
    coins_per_page = 10
    start = page * coins_per_page
    end = start + coins_per_page
    page_coins = coins[start:end]
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = f"📊 TOP CRYPTOCURRENCIES (Page {page+1}/{total_pages})\n"
    msg += "─────────────────────────────────────────\n"
    
    for i, c in enumerate(page_coins, start + 1):
        name = c.get("name", "Unknown")
        sym = c.get("symbol", "???")
        price = fmt_price(c.get("current_price"))
        ch1h = fmt_change(get_coin_change(c, "1h"))
        ch24h = fmt_change(get_coin_change(c, "24h"))
        mcap = fmt_mcap(c.get("market_cap"))
        vol = fmt_vol(c.get("total_volume"))
        
        msg += f"\n{i}. {name} ({sym})\n"
        msg += f" {price} 1h: {ch1h} 24h: {ch24h}\n"
        msg += f" Cap: {mcap} | Vol: {vol}\n"
    
    msg += f"\n⏱ {now} | Source: CoinGecko"
    msg += f"\n\nPage {page+1} of {total_pages}"
    return msg


# ============================================
# BUILD PAGINATION KEYBOARD
# ============================================
def build_pagination_keyboard(coins, page=0):
    """Build coin buttons with pagination controls"""
    coins_per_page = 10
    total_pages = (len(coins) + coins_per_page - 1) // coins_per_page
    
    start = page * coins_per_page
    end = start + coins_per_page
    page_coins = coins[start:end]
    
    keyboard = []
    row = []
    for c in page_coins:
        coin_id = c.get("id", "")
        short = get_coin_short_id(coin_id)
        sym = c.get("symbol", "???")
        row.append(InlineKeyboardButton(sym, callback_data=f"ci_{short}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    # Pagination controls
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️ Previous", callback_data=f"pulse_page_{page-1}")
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"pulse_page_{page+1}")
        )
    nav_row.append(InlineKeyboardButton("🔄 Refresh", callback_data="pulse_refresh_page"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    return keyboard


# ============================================
# COMMANDS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🚀 ORBIT Pulse Bot\n\n"
        "/pulse - Top 50 cryptos\n"
        "/help - Commands\n\n"
        "✅ Click coin → See details\n"
        "✅ Send link → Auto-download"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        "📖 ORBIT Pulse Bot\n\n"
        "📊 Crypto Commands:\n"
        "/pulse - Browse top 50 cryptocurrencies\n"
        "/pulse [coin] - Quick lookup (e.g., /pulse btc)\n\n"
        "🎥 Media Downloads:\n"
        "• Send any link (YouTube, TikTok, X, Facebook, Instagram)\n"
        "• Bot auto-detects and downloads\n"
        "• Supports video & audio\n\n"
        "Other Commands:\n"
        "/help - This message\n"
        "/start - Welcome\n\n"
        "💡 Examples:\n"
        "• /pulse sol → Solana analysis\n"
        "• /pulse ethereum → ETH details\n"
        "• Send TikTok link → Auto-download"
    )


async def pulse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 50 coins with pagination OR search for specific coin"""
    user_id = update.effective_user.id
    
    # Check if user provided a coin name/symbol
    if context.args and len(context.args) > 0:
        search_term = " ".join(context.args).lower().strip()
        
        await update.message.reply_text(f"🔍 Searching for {search_term}...")
        
        # Fetch more coins for better search results
        coins = fetch_top_coins(limit=250)
        
        if not coins:
            await update.message.reply_text(
                "⏳ Data temporarily unavailable — try again in a moment."
            )
            return
        
        # Search for matching coin
        found_coin = None
        for coin in coins:
            coin_id = coin.get("id", "").lower()
            coin_name = coin.get("name", "").lower()
            coin_symbol = coin.get("symbol", "").lower()
            
            if search_term in coin_id or search_term in coin_name or search_term == coin_symbol:
                found_coin = coin
                break
        
        if not found_coin:
            await update.message.reply_text(
                f"❌ Coin '{search_term}' not found.\n\n"
                "Try:\n"
                "• /pulse btc\n"
                "• /pulse solana\n"
                "• /pulse shib\n\n"
                "Or use /pulse to browse all coins."
            )
            return
        
        # Show coin analysis
        analysis = simple_coin_analysis(
            found_coin.get("name", "Unknown"),
            found_coin.get("current_price", 0),
            found_coin.get("price_change_percentage_24h_in_currency", 0),
            found_coin.get("market_cap"),
            found_coin.get("total_volume")
        )
        await update.message.reply_text(analysis)
        return
    
    # No args - show paginated list
    await update.message.reply_text("📊 Loading top 50 coins...")
    coins = fetch_top_coins(limit=50)
    
    if not coins:
        await update.message.reply_text(
            "⏳ Data temporarily unavailable — try again in a moment."
        )
        return
    
    # Reset to page 0
    coin_pagination[user_id] = 0
    
    page = 0
    total_pages = (len(coins) + 9) // 10
    msg = build_coins_page_text(coins, page, total_pages)
    keyboard = build_pagination_keyboard(coins, page)
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


# ============================================
# CALLBACKS
# ============================================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses"""
    query = update.callback_query
    data = query.data
    
    if data.startswith("pulse_page_"):
        page_num = int(data.split("_")[-1])
        coins = fetch_top_coins(limit=50)
        
        if not coins:
            await query.edit_message_text("⏳ Data temporarily unavailable.")
            return
        
        total_pages = (len(coins) + 9) // 10
        msg = build_coins_page_text(coins, page_num, total_pages)
        keyboard = build_pagination_keyboard(coins, page_num)
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "pulse_refresh_page":
        user_id = query.from_user.id
        page = coin_pagination.get(user_id, 0)
        coins = fetch_top_coins(limit=50)
        
        if not coins:
            await query.edit_message_text("⏳ Data temporarily unavailable.")
            return
        
        total_pages = (len(coins) + 9) // 10
        msg = build_coins_page_text(coins, page, total_pages)
        keyboard = build_pagination_keyboard(coins, page)
        
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("ci_"):
        coin_id = data[3:]  # e.g., "bitcoin"
        
        # Fetch coin data
        coins = fetch_top_coins(limit=250)
        if not coins:
            await query.answer("⏳ Data unavailable", show_alert=True)
            return
        
        # Find exact coin
        coin = None
        for c in coins:
            c_id = c.get("id", "").lower()[:len(coin_id)]
            if c_id == coin_id[:len(c_id)]:
                coin = c
                break
        
        if not coin:
            await query.answer("❌ Coin not found", show_alert=True)
            return
        
        # Show analysis
        analysis = simple_coin_analysis(
            coin.get("name", "Unknown"),
            coin.get("current_price", 0),
            coin.get("price_change_percentage_24h_in_currency", 0),
            coin.get("market_cap"),
            coin.get("total_volume")
        )
        
        await query.edit_message_text(analysis)


# ============================================
# AUTO LINK DETECTION & DOWNLOAD
# ============================================
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-detect and handle links"""
    text = update.message.text.strip()
    
    # Check if it's a link
    if not text.startswith("http"):
        return  # Not a link, ignore
    
    platform = detect_platform(text)
    
    if not platform:
        return  # Not supported, ignore
    
    # Store link for format selection
    context.user_data["download_link"] = text
    context.user_data["download_platform"] = platform
    
    # Show format options
    msg = f"🔗 {platform} link detected!\n\n"
    msg += "Choose format:\n"
    msg += "1️⃣ Best Quality (MP4)\n"
    msg += "2️⃣ Audio Only (MP3)\n"
    msg += "3️⃣ High Quality\n\n"
    msg += "Reply with number:"
    
    await update.message.reply_text(msg)


async def handle_format_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle format choice and download"""
    choice = update.message.text.strip()
    
    # Only process if they recently sent a link
    if "download_link" not in context.user_data:
        return  # Not in download context
    
    if choice not in ["1", "2", "3"]:
        return  # Invalid choice, ignore
    
    url = context.user_data["download_link"]
    platform = context.user_data["download_platform"]
    
    status = await update.message.reply_text(f"⏳ Downloading from {platform}...\nPlease wait (1-2 min)")
    
    # Download
    result = download_from_platform(url)
    
    if not result["success"]:
        await status.edit_text(f"❌ Failed: {result['error']}")
        context.user_data.pop("download_link", None)
        context.user_data.pop("download_platform", None)
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
    
    finally:
        context.user_data.pop("download_link", None)
        context.user_data.pop("download_platform", None)


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
    
    # Handlers (order matters - most specific first)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("pulse", pulse))
    
    # Link detection (catches http/https links)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^https?://"), handle_link))
    
    # Format choice handler (catches numbers 1-3)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^[1-3]$"), handle_format_choice))
    
    # Callback buttons
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("✅ Bot started. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
