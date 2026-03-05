#!/usr/bin/env python3
"""
ORBIT Pulse Bot - Telegram Crypto Trading Bot
Shows top 50 cryptocurrencies with pagination
Includes technical analysis and YouTube downloader
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
    ConversationHandler,
    MessageHandler,
    filters,
)

# Import new modules
from technical_analysis import calculate_rsi, detect_trend, get_signal, format_analysis, format_pro_analysis
from universal_downloader import detect_platform, get_media_info, download_media, format_size, suggest_format

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
# CONVERSATION HANDLERS (States)
# ============================================
ANALYZE_COIN, DOWNLOAD_LINK, DOWNLOAD_FORMAT = range(3)


# ============================================
# ANALYZE COMMAND
# ============================================
async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start /analyze conversation"""
    await update.message.reply_text(
        "📊 Technical Analysis\n\n"
        "Enter a coin symbol (e.g., BTC, ETH, SOL) to analyze:"
    )
    return ANALYZE_COIN


async def analyze_coin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process coin symbol input"""
    coin_symbol = update.message.text.upper().strip()
    
    # Fetch coin data
    coins = fetch_top_coins(limit=250)  # Get more coins to find the one requested
    
    if not coins:
        await update.message.reply_text("⏳ Unable to fetch data. Try again.")
        return ConversationHandler.END
    
    # Find coin by symbol
    coin = None
    for c in coins:
        if c.get("symbol") == coin_symbol:
            coin = c
            break
    
    if not coin:
        await update.message.reply_text(
            f"❌ Coin '{coin_symbol}' not found.\n\n"
            "Try another symbol."
        )
        return ANALYZE_COIN
    
    # Get price history (mock - using market data as proxy)
    current_price = coin.get("current_price", 0)
    change_24h = coin.get("price_change_percentage_24h_in_currency", 0)
    
    # Mock price history for RSI calculation
    # In production, fetch real historical data
    prices = [current_price * (1 - change_24h/100), current_price]
    
    # Calculate RSI (with mock data)
    rsi = calculate_rsi(prices)
    trend = detect_trend(prices)
    signal_info = get_signal(rsi, trend)
    
    analysis = format_analysis(
        coin.get("name", coin_symbol),
        current_price,
        rsi,
        trend,
        signal_info,
        change_24h
    )
    
    await update.message.reply_text(analysis)
    await update.message.reply_text("Enter another coin symbol or /cancel to exit.")
    return ANALYZE_COIN


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


# ============================================
# DOWNLOAD COMMAND
# ============================================
async def download_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start /download conversation"""
    await update.message.reply_text(
        "⬇️ Universal Downloader\n\n"
        "Send any media link:\n"
        "🎥 YouTube, TikTok, Instagram, X, Facebook\n"
        "🖼️ Images, videos, audio\n\n"
        "I'll auto-detect and download for you."
    )
    return DOWNLOAD_LINK


async def download_link_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process any media link"""
    url = update.message.text.strip()
    
    # Validate URL format
    if not url.startswith("http"):
        await update.message.reply_text("❌ Invalid URL. Make sure it starts with http/https.")
        return DOWNLOAD_LINK
    
    # Detect platform
    platform = detect_platform(url)
    
    if not platform:
        await update.message.reply_text(
            "❌ Unsupported link.\n\n"
            "Supported: YouTube, TikTok, Instagram, X, Facebook, Xiaohongshu\n\n"
            "Send another link:"
        )
        return DOWNLOAD_LINK
    
    await update.message.reply_text(f"⏳ Fetching {platform['platform']}...")
    
    try:
        info = get_media_info(url, platform["platform"])
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error fetching info: {str(e)[:100]}\n\n"
            "Try another link:"
        )
        return DOWNLOAD_LINK
    
    # Store in context
    context.user_data["download_url"] = url
    context.user_data["platform"] = platform
    context.user_data["media_info"] = info
    
    # Show format options
    formats = suggest_format(platform["platform"], platform["type"])
    msg = f"✅ Detected: {platform['platform'].upper()}\n"
    msg += f"Title: {info['title']}\n\n"
    msg += "Available formats:\n"
    
    for i, fmt in enumerate(formats[:6], 1):  # Show up to 6 formats
        msg += f"{i}️⃣ {fmt}\n"
    
    msg += "\nReply with number (or /cancel):"
    
    await update.message.reply_text(msg)
    return DOWNLOAD_FORMAT


async def download_format_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process format choice and download"""
    choice = update.message.text.strip()
    
    # Validate choice exists
    if not context.user_data.get("platform"):
        await update.message.reply_text("❌ Session expired. Send /download again.")
        return ConversationHandler.END
    
    formats = suggest_format(
        context.user_data["platform"]["platform"],
        context.user_data["platform"]["type"]
    )
    
    try:
        choice_idx = int(choice) - 1
        if choice_idx < 0 or choice_idx >= len(formats):
            await update.message.reply_text(f"❌ Invalid choice. Reply 1-{len(formats)}.")
            return DOWNLOAD_FORMAT
    except ValueError:
        await update.message.reply_text("❌ Please reply with a number.")
        return DOWNLOAD_FORMAT
    
    format_choice = formats[choice_idx]
    url = context.user_data["download_url"]
    platform = context.user_data["platform"]["platform"]
    
    status_msg = await update.message.reply_text(
        f"⏳ Downloading {platform}...\n"
        f"Format: {format_choice}\n"
        f"This may take 1-2 minutes..."
    )
    
    # Download (no temp files, direct streaming)
    try:
        result = download_media(url, format_choice)
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Download failed\n\n"
            f"Error: {str(e)[:150]}\n\n"
            f"Try another link or /cancel."
        )
        return DOWNLOAD_LINK
    
    if not result["success"]:
        await status_msg.edit_text(
            f"❌ Download failed\n\n"
            f"Error: {result['error']}\n\n"
            f"Try another link or /cancel."
        )
        return DOWNLOAD_LINK
    
    # Send file directly (no temp storage)
    try:
        from io import BytesIO
        
        file_data = BytesIO(result["data"])
        file_data.name = result["filename"]
        
        await status_msg.edit_text(
            f"✅ Download successful!\n"
            f"Size: {format_size(result['size'])}\n"
            f"Sending to you..."
        )
        
        if "MP4" in format_choice or result["filename"].endswith(".mp4"):
            await update.message.reply_video(
                file_data,
                caption=f"✅ Downloaded\n{format_size(result['size'])}"
            )
        elif "MP3" in format_choice or result["filename"].endswith(".mp3"):
            await update.message.reply_audio(
                file_data,
                title=context.user_data["media_info"]["title"]
            )
        elif "JPG" in format_choice or result["filename"].endswith((".jpg", ".png")):
            await update.message.reply_photo(
                file_data,
                caption=f"✅ Downloaded\n{format_size(result['size'])}"
            )
        else:
            await update.message.reply_document(
                file_data,
                caption=f"✅ Downloaded\n{format_size(result['size'])}"
            )
        
        await update.message.reply_text(
            "✅ Complete!\n\n"
            "Send another link or /cancel."
        )
        return DOWNLOAD_LINK
    
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to send file\n\n"
            f"Error: {str(e)[:150]}\n\n"
            f"The download worked but couldn't send. Try again or /cancel."
        )
        return DOWNLOAD_LINK


# ============================================
# COMMANDS
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "🚀 Welcome to ORBIT Pulse!\n\n"
        "/pulse - Top 50 cryptocurrencies\n"
        "/analyze - Technical analysis of a coin\n"
        "/download - Download YouTube videos\n"
        "/help - Show all commands"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        "📖 ORBIT Pulse Commands:\n\n"
        "/pulse - Top 50 cryptocurrencies\n"
        "/analyze - Technical analysis (RSI, trend, signals)\n"
        "/download - Download from any platform\n"
        "/help - Show this message\n"
        "/start - Welcome\n\n"
        "Download Supported:\n"
        "🎥 YouTube, TikTok, Instagram, X, Facebook\n"
        "🖼️ Images, videos, audio\n\n"
        "Smart features:\n"
        "✅ Auto-detect format\n"
        "✅ No watermarks\n"
        "✅ Clean, private downloads"
    )


async def pulse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top 50 coins with pagination"""
    user_id = update.effective_user.id
    
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
        # Coin analysis from button click
        coin_id = data[3:]  # e.g., "bitcoin"
        
        # Fetch coin data
        coins = fetch_top_coins(limit=250)
        if not coins:
            await query.answer("⏳ Data unavailable", show_alert=True)
            return
        
        # Find exact coin
        coin = None
        for c in coins:
            if get_coin_short_id(c.get("id", ""))[:len(coin_id)] == coin_id[:10]:
                coin = c
                break
        
        if not coin:
            await query.answer("❌ Coin not found", show_alert=True)
            return
        
        # Analyze
        current_price = coin.get("current_price", 0)
        change_1h = coin.get("price_change_percentage_1h_in_currency", 0)
        change_24h = coin.get("price_change_percentage_24h_in_currency", 0)
        market_cap = coin.get("market_cap", 0)
        volume = coin.get("total_volume", 0)
        
        prices = [current_price * (1 - change_24h/100), current_price]
        
        rsi = calculate_rsi(prices)
        trend = detect_trend(prices)
        signal_info = get_signal(rsi, trend)
        
        # Use professional analysis
        analysis = format_pro_analysis(
            coin.get("name", ""),
            current_price,
            change_1h,
            change_24h,
            market_cap,
            volume,
            rsi,
            trend,
            signal_info
        )
        
        await query.edit_message_text(analysis)


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
    
    # Analyze conversation handler
    analyze_handler = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_cmd)],
        states={
            ANALYZE_COIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_coin_input),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )
    
    # Download conversation handler
    download_handler = ConversationHandler(
        entry_points=[CommandHandler("download", download_cmd)],
        states={
            DOWNLOAD_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, download_link_input),
            ],
            DOWNLOAD_FORMAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, download_format_input),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("pulse", pulse))
    app.add_handler(analyze_handler)
    app.add_handler(download_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("✅ Bot started. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
