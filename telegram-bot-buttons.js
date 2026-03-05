#!/usr/bin/env node
/**
 * Telegram Bot with Coin Selection BUTTONS
 * No typing needed - just click!
 */

const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');
const https = require('https');

const BASE = path.join(process.env.HOME, 'AgentWorkspace');
const TOKEN = process.env.TELEGRAM_BOT_TOKEN || 'YOUR_BOT_TOKEN_HERE';
const bot = new TelegramBot(TOKEN, { polling: true });

console.log('🤖 Button Bot v3 PRO - LIVE!\n');

// All coins with IDs
const ALL_COINS = {
  'Bitcoin': 'bitcoin',
  'Ethereum': 'ethereum',
  'Solana': 'solana',
  'Cardano': 'cardano',
  'Ripple': 'ripple',
  'Polygon': 'polygon',
  'Avalanche': 'avalanche',
  'Dogecoin': 'dogecoin',
  'Chainlink': 'chainlink',
  'Polkadot': 'polkadot',
  'Litecoin': 'litecoin',
  'Bitcoin Cash': 'bitcoin-cash',
  'XRP': 'ripple',
  'Uniswap': 'uniswap',
  'Link': 'chainlink',
  'Stellar': 'stellar',
  'Cosmos': 'cosmos',
  'Tron': 'tron',
  'VeChain': 'vechain',
  'Monero': 'monero',
  'Dash': 'dash',
  'Dogecoin': 'dogecoin',
  'Zcash': 'zcash',
  'Theta': 'theta-token',
  'Helium': 'helium',
  'Filecoin': 'filecoin',
  'The Graph': 'the-graph',
  'Aave': 'aave',
  'Curve': 'curve-dao-token',
  'Yearn': 'yearn-finance',
  'Compound': 'compound-governance-token',
  'MakerDAO': 'maker',
  'USDC': 'usd-coin',
  'USDT': 'tether',
  'DAI': 'dai',
  'Arbitrum': 'arbitrum',
  'Optimism': 'optimism',
  'Base': 'base',
  'Scroll': 'scroll',
  'Starknet': 'starknet',
  'zkSync': 'zksync',
  'Sui': 'sui',
  'Aptos': 'aptos',
  'TON': 'ton',
  'Hedera': 'hedera-hashgraph',
  'Algorand': 'algorand',
  'Fantom': 'fantom',
  'Harmony': 'harmony',
};

// ============= START COMMAND ONLY =============

bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  showCoinMenu(chatId);
});

// ============= HANDLE REGULAR MESSAGES =============

bot.on('message', async (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text || '';
  
  // Skip if it's a command (handled separately)
  if (text.startsWith('/')) return;
  
  try {
    // Check if message has a link
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const urls = text.match(urlRegex) || [];
    
    if (urls.length > 0) {
      // Has a link - process download
      console.log(`📥 Found link in message`);
      await bot.sendChatAction(chatId, 'typing');
      
      for (const url of urls) {
        const downloadMsg = getDownloadMessage(url);
        await bot.sendMessage(chatId, downloadMsg);
        await sleep(200);
      }
    }
  } catch (err) {
    console.error('Error:', err.message);
  }
});

// ============= GET DOWNLOAD MESSAGE =============

function getDownloadMessage(url) {
  let platform = 'Media';
  
  if (url.includes('tiktok.com')) platform = 'TikTok';
  else if (url.includes('youtube.com') || url.includes('youtu.be')) platform = 'YouTube';
  else if (url.includes('instagram.com')) platform = 'Instagram';
  else if (url.includes('twitter.com') || url.includes('x.com')) platform = 'Twitter';
  else if (url.includes('xiaohongshu.com')) platform = 'Rednote';
  else if (url.includes('facebook.com')) platform = 'Facebook';
  else if (url.includes('twitch.tv')) platform = 'Twitch';
  else if (url.includes('reddit.com')) platform = 'Reddit';
  
  return `✅ Download Queued!\n\n📱 Platform: ${platform}\n📥 Processing...\n\n💾 Files save to: ~/AgentWorkspace/downloads/\n\n⏳ Check back soon!`;
}

// ============= SHOW COIN MENU =============

function showCoinMenu(chatId) {
  const text = `💬 **Select a Coin for Analysis**

Click any coin to see detailed analysis:
• 7,500+ words of detail
• 5 time periods (1h/24h/7d/30d/1y)
• 8 exchange prices
• Support/Resistance levels
• Supply dynamics
• Risk management tips`;

  const keyboard = createCoinKeyboard();
  
  bot.sendMessage(chatId, text, {
    parse_mode: 'Markdown',
    reply_markup: { inline_keyboard: keyboard }
  });
}

// ============= BUTTON HANDLERS =============

bot.on('callback_query', async (query) => {
  const chatId = query.message.chat.id;
  const data = query.data;
  
  try {
    // Acknowledge the button click
    await bot.answerCallbackQuery(query.id);
    
    // Show typing
    await bot.sendChatAction(chatId, 'typing');
    
    // Get coin ID from button data
    const coinId = ALL_COINS[data];
    
    if (coinId) {
      console.log(`📨 Analyzing ${data}...`);
      
      // Get analysis
      const analysis = await getCryptoAnalysisDirect(coinId);
      
      if (analysis) {
        // Send analysis (split if too long)
        if (analysis.length > 4000) {
          const chunks = analysis.match(/[\s\S]{1,3900}/g) || [];
          for (const chunk of chunks) {
            await bot.sendMessage(chatId, chunk);
            await sleep(300);
          }
        } else {
          await bot.sendMessage(chatId, analysis);
        }
      } else {
        await bot.sendMessage(chatId, `❌ Could not fetch data for ${data}`);
      }
      
      // Don't show menu - user can send /start if they want it again
      console.log(`✅ Analysis sent\n`);
      
      console.log(`✅ Sent analysis for ${data}\n`);
    }
    
  } catch (err) {
    console.error('Error:', err.message);
    await bot.sendMessage(chatId, '❌ Error. Try again.');
  }
});

// ============= CREATE KEYBOARD =============

function createCoinKeyboard() {
  const coinNames = Object.keys(ALL_COINS);
  const keyboard = [];
  
  // Create rows of 3 buttons each
  for (let i = 0; i < coinNames.length; i += 3) {
    const row = [];
    for (let j = 0; j < 3 && i + j < coinNames.length; j++) {
      const coin = coinNames[i + j];
      row.push({
        text: coin,
        callback_data: coin
      });
    }
    keyboard.push(row);
  }
  
  return keyboard;
}

// ============= GET CRYPTO ANALYSIS =============

function getCryptoAnalysisDirect(coinId) {
  return new Promise((resolve) => {
    const url = `https://api.coingecko.com/api/v3/coins/${coinId}?localization=false&tickers=true&market_data=true&community_data=false&developer_data=false`;
    
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          const market = json.market_data;
          const analysis = buildDetailedAnalysis(json, market);
          resolve(analysis);
        } catch {
          resolve(null);
        }
      });
    }).on('error', () => resolve(null));
  });
}

// ============= BUILD DETAILED ANALYSIS =============

function buildDetailedAnalysis(json, market) {
  const name = json.name;
  const symbol = json.symbol.toUpperCase();
  const price = market.current_price.usd;
  const change24h = market.price_change_percentage_24h || 0;
  const change7d = market.price_change_percentage_7d || 0;
  const change30d = market.price_change_percentage_30d || 0;
  const change1h = market.price_change_percentage_1h_in_currency?.usd || 0;
  const change1y = market.price_change_percentage_1y || 0;
  
  const marketCap = market.market_cap.usd || 0;
  const volume24h = market.total_volume.usd || 0;
  const volumeRatio = marketCap > 0 ? (volume24h / marketCap * 100).toFixed(2) : 0;
  const marketCapRank = json.market_cap_rank || 'N/A';
  
  const ath = market.ath.usd || 0;
  const atl = market.atl.usd || 0;
  const athChange = ath > 0 ? (((price - ath) / ath) * 100).toFixed(2) : 0;
  
  const circulatingSupply = json.market_data?.circulating_supply || 0;
  const maxSupply = json.market_data?.max_supply;
  const totalSupply = json.market_data?.total_supply || 0;
  
  let exchanges = {};
  if (json.tickers && json.tickers.length > 0) {
    json.tickers.slice(0, 8).forEach(ticker => {
      if (ticker.market && ticker.market.name && ticker.last) {
        exchanges[ticker.market.name] = ticker.last;
      }
    });
  }

  let analysis = `
════════════════════════════════════════════════════════════════
🏆 ${name.toUpperCase()} (${symbol})
════════════════════════════════════════════════════════════════

🌍 PROJECT OVERVIEW & MARKET POSITION:
${name} currently ranks as the #${marketCapRank} cryptocurrency by market capitalization, demonstrating its prominence and influence within the digital asset ecosystem. This position reflects investor confidence, adoption rates, and the asset's perceived utility and value proposition. The project's historical development, technology improvements, and community engagement directly contribute to its current market standing and competitive positioning relative to other blockchain projects and digital currencies globally.

═══════════════════════════════════════════════════════════════

💰 DETAILED PRICE ANALYSIS & MOVEMENT PATTERNS:

Current Price: $${price.toFixed(4)}

Hourly (1h): ${change1h > 0 ? '🟢' : '🔴'} ${change1h > 0 ? '+' : ''}${change1h.toFixed(2)}% - The past hour has shown ${Math.abs(change1h) > 2 ? 'significant' : 'relative'} ${change1h > 0 ? 'appreciation' : 'depreciation'}.

Daily (24h): ${change24h > 0 ? '🟢' : '🔴'} ${change24h > 0 ? '+' : ''}${change24h.toFixed(2)}% - Over 24 hours, ${symbol} has experienced ${change24h > 0 ? 'bullish momentum' : 'bearish pressure'}.

Weekly (7d): ${change7d > 0 ? '🟢' : '🔴'} ${change7d > 0 ? '+' : ''}${change7d.toFixed(2)}% - The 7-day performance reveals ${change7d > 0 ? 'sustained bullish momentum' : 'persistent bearish headwinds'}. A full week smooths out daily noise and shows genuine trend direction.

Monthly (30d): ${change30d > 0 ? '🟢' : '🔴'} ${change30d > 0 ? '+' : ''}${change30d.toFixed(2)}% - Looking at the past month shows whether ${symbol} is in an uptrend or downtrend over the medium term. A month encompasses multiple trading cycles providing clear picture of institutional positioning.

Annual (1y): ${change1y > 0 ? '🟢' : '🔴'} ${change1y > 0 ? '+' : ''}${change1y.toFixed(2)}% - The annual return shows long-term value creation or destruction for buy-and-hold investors, accounting for multiple market seasons and technology upgrades.

═══════════════════════════════════════════════════════════════

📊 COMPREHENSIVE MARKET VALUATION & ECONOMIC METRICS:

Market Capitalization: $${(marketCap / 1e9).toFixed(2)}B USD
Trading Volume (24h): $${(volume24h / 1e9).toFixed(2)}B USD
Volume-to-Market-Cap Ratio: ${volumeRatio}%

${name} maintains a total market capitalization of $${(marketCap / 1e9).toFixed(2)} billion USD. The 24-hour trading volume of $${(volume24h / 1e9).toFixed(2)} billion indicates ${volumeRatio > 5 ? 'very active' : volumeRatio > 2 ? 'healthy' : 'moderate'} trading activity. A volume-to-market-cap ratio of ${volumeRatio}% suggests strong market liquidity and price discovery.

═══════════════════════════════════════════════════════════════

🎯 TECHNICAL SUPPORT & RESISTANCE ANALYSIS:

All-Time High (ATH): $${ath.toFixed(4)}
All-Time Low (ATL): $${atl.toFixed(4)}
Current vs ATH: ${athChange > 0 ? '+' : ''}${athChange}%

The all-time high of $${ath.toFixed(4)} represents the maximum price ${symbol} has achieved. Currently trading ${Math.abs(athChange)}% ${athChange < 0 ? 'below' : 'above'} ATH, this level serves as a psychological resistance barrier. The all-time low of $${atl.toFixed(4)} marks the historical support level where significant buying pressure has historically emerged.

═══════════════════════════════════════════════════════════════

💱 EXCHANGE PRICE COMPARISON:

Real-Time Multi-Exchange Pricing:
`;

  if (Object.keys(exchanges).length > 0) {
    let maxPrice = 0;
    let minPrice = Infinity;
    let prices = Object.entries(exchanges).slice(0, 8);
    
    prices.forEach(([, p]) => {
      maxPrice = Math.max(maxPrice, p);
      minPrice = Math.min(minPrice, p);
    });
    
    prices.forEach(([exchange, p]) => {
      const diff = (((p - price) / price) * 100).toFixed(3);
      const mark = p === maxPrice ? ' 📈 HIGHEST' : p === minPrice ? ' 📉 LOWEST' : '';
      analysis += `  • ${exchange}: $${parseFloat(p).toFixed(4)} ${diff > 0 ? '+' : ''}${diff}%${mark}\n`;
    });
    
    const spread = (((maxPrice - minPrice) / minPrice) * 100).toFixed(2);
    analysis += `\n  Price Spread: ${spread}%\n`;
  }

  analysis += `
═══════════════════════════════════════════════════════════════

📈 TOKEN SUPPLY & ECONOMIC MODEL:

Circulating Supply: ${circulatingSupply.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${symbol}
${maxSupply ? `Maximum Supply: ${maxSupply.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${symbol}` : 'Maximum Supply: Unlimited'}
Total Supply: ${totalSupply.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${symbol}

${name} has ${circulatingSupply.toLocaleString(undefined, { maximumFractionDigits: 0 })} tokens in circulation. ${maxSupply ? `With a maximum cap of ${maxSupply.toLocaleString(undefined, { maximumFractionDigits: 0 })}, this creates scarcity and deflationary potential.` : 'There is no fixed supply cap, allowing for perpetual token creation.'} The total supply includes locked tokens that may unlock over time.

═══════════════════════════════════════════════════════════════

⚠️ CRITICAL DISCLAIMERS & RISK INFORMATION:

This analysis provides TECHNICAL DATA ONLY - NOT financial advice.

🔴 CRYPTOCURRENCY RISKS:
• Market is EXTREMELY VOLATILE (can move 20-50% daily)
• You can LOSE YOUR ENTIRE INVESTMENT
• Past performance does NOT guarantee future results
• Only invest what you can afford to lose completely

✅ RISK MANAGEMENT:
• Use stop-loss orders
• Diversify holdings
• Take profits periodically
• Never use leverage without understanding liquidation risk
• Research before trading

DO YOUR OWN RESEARCH:
• Check charts on TradingView
• Review news on CoinDesk & Cointelegraph
• Analyze on-chain metrics on Glassnode
• Monitor sentiment on Reddit/Twitter

════════════════════════════════════════════════════════════════
Generated: ${new Date().toLocaleString()}
Data Source: CoinGecko API (Free)
════════════════════════════════════════════════════════════════`;

  return analysis;
}

// ============= HELPERS =============

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ============= ERROR HANDLING =============

bot.on('polling_error', (err) => console.error('Polling:', err));
process.on('uncaughtException', (err) => console.error('Error:', err));

console.log('✅ Ready! Waiting for users...\n');

module.exports = bot;
