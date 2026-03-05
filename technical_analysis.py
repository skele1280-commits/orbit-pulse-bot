"""
Technical Analysis Module for Crypto Bot
Provides RSI, trend detection, and buy/sell signals
"""

def calculate_rsi(prices, period=14):
    """
    Calculate Relative Strength Index (RSI)
    RSI measures momentum: 0-100 scale
    
    Args:
        prices: list of float prices (oldest to newest)
        period: lookback period (default 14)
    
    Returns:
        float: RSI value 0-100
    """
    if len(prices) < period:
        return 50  # Neutral if not enough data
    
    # Calculate price changes
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # Separate gains and losses
    gains = [c if c > 0 else 0 for c in changes[-period:]]
    losses = [-c if c < 0 else 0 for c in changes[-period:]]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0:
        return 100 if avg_gain > 0 else 50
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def detect_trend(prices):
    """
    Detect trend direction based on recent price movement
    
    Args:
        prices: list of float prices (oldest to newest)
    
    Returns:
        str: "up", "down", or "sideways"
    """
    if len(prices) < 2:
        return "sideways"
    
    # Compare last 5 prices with previous 5 (if available)
    if len(prices) >= 10:
        recent_avg = sum(prices[-5:]) / 5
        previous_avg = sum(prices[-10:-5]) / 5
        
        change_percent = ((recent_avg - previous_avg) / previous_avg) * 100
        
        if change_percent > 2:
            return "up"
        elif change_percent < -2:
            return "down"
    else:
        # Fallback: just check if last price > first price
        if prices[-1] > prices[0] * 1.02:
            return "up"
        elif prices[-1] < prices[0] * 0.98:
            return "down"
    
    return "sideways"


def get_signal(rsi_value, price_trend):
    """
    Generate buy/sell signal based on RSI and trend
    
    Args:
        rsi_value: float RSI value 0-100
        price_trend: str "up", "down", or "sideways"
    
    Returns:
        dict: {"signal": "BUY|SELL|HOLD", "strength": "strong|moderate|weak"}
    """
    if rsi_value < 30:
        strength = "strong" if rsi_value < 20 else "moderate"
        return {"signal": "🟢 BUY", "strength": strength, "reason": f"Oversold (RSI {rsi_value:.1f})"}
    elif rsi_value > 70:
        strength = "strong" if rsi_value > 80 else "moderate"
        return {"signal": "🔴 SELL", "strength": strength, "reason": f"Overbought (RSI {rsi_value:.1f})"}
    else:
        return {"signal": "⚪ HOLD", "strength": "weak", "reason": f"Neutral (RSI {rsi_value:.1f})"}


def get_support_resistance(current_price, change_24h, market_cap, volume):
    """Calculate support and resistance levels"""
    # Simple calculation based on 24h range
    range_percent = abs(change_24h) / 2
    support = current_price * (1 - range_percent / 100)
    resistance = current_price * (1 + range_percent / 100)
    return support, resistance


def get_trend_description(change_1h, change_24h):
    """Generate trend description for different timeframes"""
    trends = {}
    
    # 1H trend
    if change_1h > 2:
        trends["1H"] = "🟢 Bullish"
    elif change_1h < -2:
        trends["1H"] = "🔴 Bearish"
    else:
        trends["1H"] = "⚪ Neutral"
    
    # 24H trend
    if change_24h > 3:
        trends["1D"] = "🟢 Strong Bullish"
    elif change_24h > 0:
        trends["1D"] = "🟢 Mildly Bullish"
    elif change_24h < -3:
        trends["1D"] = "🔴 Strong Bearish"
    else:
        trends["1D"] = "🔴 Mildly Bearish"
    
    # 4H (interpolate)
    change_4h = change_24h * (4 / 24)
    if change_4h > 1.5:
        trends["4H"] = "🟢 Bullish"
    elif change_4h < -1.5:
        trends["4H"] = "🔴 Bearish"
    else:
        trends["4H"] = "⚪ Neutral"
    
    return trends


def format_pro_analysis(coin_name, current_price, change_1h, change_24h, market_cap, volume, rsi, trend, signal_info):
    """
    Format professional trader analysis
    
    Returns:
        str: Formatted PRO TRADER SUMMARY
    """
    support, resistance = get_support_resistance(current_price, change_24h, market_cap, volume)
    trends = get_trend_description(change_1h, change_24h)
    
    msg = f"🤖 PRO TRADER SUMMARY\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 {coin_name} — ${current_price:,.2f}\n\n"
    
    # TREND ANALYSIS
    msg += f"📈 TREND ANALYSIS\n"
    msg += f" 1H: {trends['1H']} — {change_1h:+.2f}%\n"
    msg += f" 4H: {trends['4H']} — Interpolated\n"
    msg += f" 1D: {trends['1D']} — {change_24h:+.2f}%\n\n"
    
    # SUPPORT & RESISTANCE
    msg += f"🎯 SUPPORT & RESISTANCE\n"
    msg += f" Support: ${support:,.2f}\n"
    msg += f" Resistance: ${resistance:,.2f}\n"
    invalidation = support * 0.99
    msg += f" ⚠️ Invalidation: below ${invalidation:,.2f}\n\n"
    
    # SIGNAL
    signal_emoji = signal_info['signal'].split()[0]  # Get emoji
    msg += f"⚡ SIGNAL: {signal_info['signal']}\n"
    
    if change_24h > 0:
        msg += f"Price up {abs(change_24h):.2f}% with momentum. Watch for continuation.\n\n"
    else:
        msg += f"Price down {abs(change_24h):.2f}%. Monitor support levels.\n\n"
    
    # KEY METRICS
    msg += f"📊 Key Metrics:\n"
    if market_cap:
        mcap_str = format_mcap(market_cap)
        msg += f" • Market Cap: {mcap_str}\n"
    if volume:
        vol_str = format_mvol(volume)
        msg += f" • 24h Volume: {vol_str}\n"
    
    msg += f" • 24h Change: {change_24h:+.2f}%\n"
    msg += f" • RSI: {rsi:.1f} ({trend})\n"
    msg += f" • Trend: {signal_info['strength'].upper()}\n\n"
    
    msg += f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} | Source: CoinGecko\n"
    msg += f"⚠️ Not financial advice. DYOR."
    
    return msg


def format_mcap(mcap):
    """Format market cap"""
    if not mcap:
        return "N/A"
    if mcap >= 1e12:
        return f"${mcap / 1e12:.2f}T"
    elif mcap >= 1e9:
        return f"${mcap / 1e9:.2f}B"
    elif mcap >= 1e6:
        return f"${mcap / 1e6:.2f}M"
    return f"${mcap:,.0f}"


def format_mvol(vol):
    """Format volume"""
    if not vol:
        return "N/A"
    if vol >= 1e9:
        return f"${vol / 1e9:.2f}B"
    elif vol >= 1e6:
        return f"${vol / 1e6:.2f}M"
    return f"${vol:,.0f}"


from datetime import datetime
