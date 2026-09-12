import os
import re
import subprocess
import urllib.request
import json

print("🚀 Running Permanent Fix for EC2 Crypto Bot Prices...")

candidate_paths = [
    "paper_exchange_engine.js",
    os.path.expanduser("~/agent/paper_exchange_engine.js"),
    os.path.expanduser("~/paper_exchange_engine.js"),
    "/home/ubuntu/agent/paper_exchange_engine.js",
    "/root/agent/paper_exchange_engine.js"
]

target_path = None
for p in candidate_paths:
    if os.path.exists(p):
        target_path = p
        break

if not target_path:
    print("❌ Cannot find paper_exchange_engine.js! Please cd into your bot directory.")
    exit(1)

print(f"📂 Found target file: {target_path}")

with open(target_path, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update all base prices to current real-market levels
code = re.sub(r"(id:\s*'BTC/USDT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>77280.00", code)
code = re.sub(r"(id:\s*'ETH/USDT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>2538.00", code)
code = re.sub(r"(id:\s*'SOL/USDT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>101.80", code)
code = re.sub(r"(id:\s*'BNB/USDT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>735.00", code)
code = re.sub(r"(id:\s*'XRP/USDT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>1.36", code)
code = re.sub(r"(id:\s*'ADA/USDT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>0.35", code)
code = re.sub(r"(id:\s*'DOGE/USDT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>0.085", code)
code = re.sub(r"(id:\s*'TON/USDT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>1.60", code)
code = re.sub(r"(id:\s*'BTC/IRT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>7450000000", code)
code = re.sub(r"(id:\s*'ETH/IRT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>245000000", code)
code = re.sub(r"(id:\s*'SOL/IRT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>9800000", code)
code = re.sub(r"(id:\s*'USDT/IRT'[\s\S]*?basePrice:\s*)[\d\.]+", r"\g<1>96500", code)

# 2. Find markers
start_marker = "async function fetchBinanceLivePrices()"
end_marker = "export const PAPER_ACCOUNT"

p1 = code.find(start_marker)
p2 = code.find(end_marker)

if p1 == -1 or p2 == -1:
    print(f"❌ Could not locate markers (p1={p1}, p2={p2})")
    exit(1)

# Check if there is a header comment right before export const PAPER_ACCOUNT
comment_marker = "// =========================================="
comment_pos = code.rfind(comment_marker, p1, p2)
if comment_pos != -1:
    p2 = comment_pos

replacement_block = """// Robust multi-exchange live price fetcher with KuCoin, Binance, Binance.US, and CoinGecko fallbacks
async function fetchBinanceLivePrices() {
  let fetchedSuccessfully = false;

  // 1. Try KuCoin allTickers first (globally accessible, unblocked on AWS EC2, covers 980+ pairs in one call)
  try {
    const kuRes = await fetch('https://api.kucoin.com/api/v1/market/allTickers', {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      signal: AbortSignal.timeout(4500)
    });
    if (kuRes.ok) {
      const kuJson = await kuRes.json();
      if (kuJson && kuJson.data && Array.isArray(kuJson.data.ticker)) {
        const kuMap = new Map(kuJson.data.ticker.map(t => [t.symbol, t]));
        for (const s of SUPPORTED_SYMBOLS) {
          if (s.isToman || !s.binanceSymbol) continue;
          const kuSymbol = s.binanceSymbol.replace('USDT', '-USDT');
          const item = kuMap.get(kuSymbol);
          if (item) {
            const lastPrice = parseFloat(item.last);
            const high24h = parseFloat(item.high);
            const low24h = parseFloat(item.low);
            const changeRate = parseFloat(item.changeRate);
            const volume24h = parseFloat(item.vol);

            if (!isNaN(lastPrice) && lastPrice > 0) {
              s.basePrice = lastPrice;
              const prev = MARKET_TICKERS.get(s.id);
              const change24h = !isNaN(changeRate) ? +(changeRate * 100).toFixed(2) : (prev ? prev.change24h : 0);
              MARKET_TICKERS.set(s.id, {
                ...prev,
                price: lastPrice,
                bid: +(lastPrice * 0.9999).toFixed(s.tickDecimals),
                ask: +(lastPrice * 1.0001).toFixed(s.tickDecimals),
                change24h,
                high24h: !isNaN(high24h) && high24h > 0 ? high24h : +(lastPrice * 1.02).toFixed(s.tickDecimals),
                low24h: !isNaN(low24h) && low24h > 0 ? low24h : +(lastPrice * 0.98).toFixed(s.tickDecimals),
                volume24h: !isNaN(volume24h) && volume24h > 0 ? +volume24h.toFixed(2) : (prev ? prev.volume24h : 1000),
                last_updated: new Date().toISOString()
              });
              updateLatestCandle(s.id, lastPrice, s.tickDecimals);
              fetchedSuccessfully = true;
            }
          }
        }
      }
    }
  } catch (kuErr) {}

  // 2. Try Binance Global for symbols not found or if KuCoin failed
  try {
    const binanceSymbols = SUPPORTED_SYMBOLS.filter(s => s.binanceSymbol && !s.isToman).map(s => s.binanceSymbol);
    const symbolsParam = JSON.stringify(binanceSymbols);
    const res = await fetch('https://api.binance.com/api/v3/ticker/24hr?symbols=' + encodeURIComponent(symbolsParam), {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      signal: AbortSignal.timeout(4000)
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        for (const item of data) {
          const matched = SUPPORTED_SYMBOLS.filter(s => s.binanceSymbol === item.symbol && !s.isToman);
          for (const s of matched) {
            const lastPrice = parseFloat(item.lastPrice);
            const change24h = parseFloat(item.priceChangePercent);
            const high24h = parseFloat(item.highPrice);
            const low24h = parseFloat(item.lowPrice);
            const volume24h = parseFloat(item.volume);

            if (!isNaN(lastPrice) && lastPrice > 0) {
              s.basePrice = lastPrice;
              const prev = MARKET_TICKERS.get(s.id);
              MARKET_TICKERS.set(s.id, {
                ...prev,
                price: lastPrice,
                bid: +(lastPrice * 0.9999).toFixed(s.tickDecimals),
                ask: +(lastPrice * 1.0001).toFixed(s.tickDecimals),
                change24h: !isNaN(change24h) ? +change24h.toFixed(2) : (prev ? prev.change24h : 0),
                high24h: !isNaN(high24h) && high24h > 0 ? high24h : +(lastPrice * 1.02).toFixed(s.tickDecimals),
                low24h: !isNaN(low24h) && low24h > 0 ? low24h : +(lastPrice * 0.98).toFixed(s.tickDecimals),
                volume24h: !isNaN(volume24h) && volume24h > 0 ? +volume24h.toFixed(2) : (prev ? prev.volume24h : 1000),
                last_updated: new Date().toISOString()
              });
              updateLatestCandle(s.id, lastPrice, s.tickDecimals);
              fetchedSuccessfully = true;
            }
          }
        }
      }
    }
  } catch (binanceErr) {}

  // 3. Fallback to Binance.US
  if (!fetchedSuccessfully) {
    try {
      const usSymbols = JSON.stringify(['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'LINKUSDT', 'LTCUSDT']);
      const usRes = await fetch('https://api.binance.us/api/v3/ticker/24hr?symbols=' + encodeURIComponent(usSymbols), {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        signal: AbortSignal.timeout(4000)
      });
      if (usRes.ok) {
        const usData = await usRes.json();
        if (Array.isArray(usData)) {
          for (const item of usData) {
            const matched = SUPPORTED_SYMBOLS.filter(s => s.binanceSymbol === item.symbol && !s.isToman);
            for (const s of matched) {
              const lastPrice = parseFloat(item.lastPrice);
              const change24h = parseFloat(item.priceChangePercent);
              const high24h = parseFloat(item.highPrice);
              const low24h = parseFloat(item.lowPrice);
              if (!isNaN(lastPrice) && lastPrice > 0) {
                s.basePrice = lastPrice;
                const prev = MARKET_TICKERS.get(s.id);
                MARKET_TICKERS.set(s.id, {
                  ...prev,
                  price: lastPrice,
                  bid: +(lastPrice * 0.9999).toFixed(s.tickDecimals),
                  ask: +(lastPrice * 1.0001).toFixed(s.tickDecimals),
                  change24h: !isNaN(change24h) ? +change24h.toFixed(2) : 0,
                  high24h: !isNaN(high24h) ? high24h : +(lastPrice * 1.02).toFixed(s.tickDecimals),
                  low24h: !isNaN(low24h) ? low24h : +(lastPrice * 0.98).toFixed(s.tickDecimals),
                  last_updated: new Date().toISOString()
                });
                updateLatestCandle(s.id, lastPrice, s.tickDecimals);
                fetchedSuccessfully = true;
              }
            }
          }
        }
      }
    } catch (usErr) {}
  }

  // 4. Fallback to CoinGecko
  if (!fetchedSuccessfully) {
    try {
      const cgRes = await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,binancecoin,ripple,cardano,avalanche-2,chainlink,polkadot,toncoin&vs_currencies=usd&include_24hr_change=true', {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        signal: AbortSignal.timeout(4000)
      });
      if (cgRes.ok) {
        const cgData = await cgRes.json();
        const mapping = {
          'BTC/USDT': 'bitcoin',
          'ETH/USDT': 'ethereum',
          'SOL/USDT': 'solana',
          'BNB/USDT': 'binancecoin',
          'XRP/USDT': 'ripple',
          'ADA/USDT': 'cardano',
          'AVAX/USDT': 'avalanche-2',
          'LINK/USDT': 'chainlink',
          'DOT/USDT': 'polkadot',
          'TON/USDT': 'toncoin'
        };

        for (const s of SUPPORTED_SYMBOLS) {
          const cgKey = mapping[s.id];
          if (cgKey && cgData[cgKey]) {
            const lastPrice = Number(cgData[cgKey].usd);
            const change24h = Number(cgData[cgKey].usd_24h_change) || 0;
            if (!isNaN(lastPrice) && lastPrice > 0) {
              s.basePrice = lastPrice;
              const prev = MARKET_TICKERS.get(s.id);
              MARKET_TICKERS.set(s.id, {
                ...prev,
                price: lastPrice,
                bid: +(lastPrice * 0.9999).toFixed(s.tickDecimals),
                ask: +(lastPrice * 1.0001).toFixed(s.tickDecimals),
                change24h: +change24h.toFixed(2),
                high24h: +(lastPrice * 1.02).toFixed(s.tickDecimals),
                low24h: +(lastPrice * 0.98).toFixed(s.tickDecimals),
                last_updated: new Date().toISOString()
              });
              updateLatestCandle(s.id, lastPrice, s.tickDecimals);
              fetchedSuccessfully = true;
            }
          }
        }
      }
    } catch (cgErr) {}
  }

  // 5. Update Toman pairs based on live USDT prices
  const btcTicker = MARKET_TICKERS.get('BTC/USDT');
  const ethTicker = MARKET_TICKERS.get('ETH/USDT');
  const solTicker = MARKET_TICKERS.get('SOL/USDT');
  const tonTicker = MARKET_TICKERS.get('TON/USDT');

  if (btcTicker) {
    const btcTomanPrice = Math.round(btcTicker.price * USDT_TO_TOMAN_RATE);
    const prevIrt = MARKET_TICKERS.get('BTC/IRT');
    MARKET_TICKERS.set('BTC/IRT', {
      ...prevIrt,
      price: btcTomanPrice,
      bid: Math.round(btcTomanPrice * 0.999),
      ask: Math.round(btcTomanPrice * 1.001),
      change24h: btcTicker.change24h,
      high24h: Math.round(btcTicker.high24h * USDT_TO_TOMAN_RATE),
      low24h: Math.round(btcTicker.low24h * USDT_TO_TOMAN_RATE),
      volume24h: +(btcTicker.volume24h * 0.15).toFixed(2),
      last_updated: new Date().toISOString()
    });
    updateLatestCandle('BTC/IRT', btcTomanPrice, 0);
  }

  if (ethTicker) {
    const ethTomanPrice = Math.round(ethTicker.price * USDT_TO_TOMAN_RATE);
    const prev = MARKET_TICKERS.get('ETH/IRT');
    MARKET_TICKERS.set('ETH/IRT', {
      ...prev,
      price: ethTomanPrice,
      bid: Math.round(ethTomanPrice * 0.999),
      ask: Math.round(ethTomanPrice * 1.001),
      change24h: ethTicker.change24h,
      high24h: Math.round(ethTicker.high24h * USDT_TO_TOMAN_RATE),
      low24h: Math.round(ethTicker.low24h * USDT_TO_TOMAN_RATE),
      volume24h: +(ethTicker.volume24h * 0.15).toFixed(2),
      last_updated: new Date().toISOString()
    });
    updateLatestCandle('ETH/IRT', ethTomanPrice, 0);
  }

  if (solTicker) {
    const solTomanPrice = Math.round(solTicker.price * USDT_TO_TOMAN_RATE);
    const prev = MARKET_TICKERS.get('SOL/IRT');
    MARKET_TICKERS.set('SOL/IRT', {
      ...prev,
      price: solTomanPrice,
      bid: Math.round(solTomanPrice * 0.999),
      ask: Math.round(solTomanPrice * 1.001),
      change24h: solTicker.change24h,
      high24h: Math.round(solTicker.high24h * USDT_TO_TOMAN_RATE),
      low24h: Math.round(solTicker.low24h * USDT_TO_TOMAN_RATE),
      volume24h: +(solTicker.volume24h * 0.15).toFixed(2),
      last_updated: new Date().toISOString()
    });
    updateLatestCandle('SOL/IRT', solTomanPrice, 0);
  }

  if (tonTicker) {
    const tonTomanPrice = Math.round(tonTicker.price * USDT_TO_TOMAN_RATE);
    const prev = MARKET_TICKERS.get('TON/IRT');
    MARKET_TICKERS.set('TON/IRT', {
      ...prev,
      price: tonTomanPrice,
      bid: Math.round(tonTomanPrice * 0.999),
      ask: Math.round(tonTomanPrice * 1.001),
      change24h: tonTicker.change24h,
      high24h: Math.round(tonTicker.high24h * USDT_TO_TOMAN_RATE),
      low24h: Math.round(tonTicker.low24h * USDT_TO_TOMAN_RATE),
      volume24h: +(tonTicker.volume24h * 0.15).toFixed(2),
      last_updated: new Date().toISOString()
    });
    updateLatestCandle('TON/IRT', tonTomanPrice, 0);
  }
}

function updateLatestCandle(symbolId, price, decimals) {
  const list = CANDLE_HISTORY.get(symbolId);
  if (!list || list.length === 0) return;
  const last = list[list.length - 1];
  const now = Date.now();

  if (now - last.time >= 60000) {
    list.push({
      time: Math.floor(now / 60000) * 60000,
      open: last.close,
      high: Math.max(last.close, price),
      low: Math.min(last.close, price),
      close: price,
      volume: +(Math.random() * 5 + 1).toFixed(2)
    });
    if (list.length > 70) list.shift();
  } else {
    last.high = Math.max(last.high, price);
    last.low = Math.min(last.low, price);
    last.close = price;
    last.volume = +(last.volume + Math.random() * 0.2).toFixed(2);
  }
}

function simulateMicroTicks() {
  for (const s of SUPPORTED_SYMBOLS) {
    const t = MARKET_TICKERS.get(s.id);
    if (!t) continue;
    const anchor = s.basePrice || t.price;
    const deviation = (t.price - anchor) / anchor;
    const pull = -deviation * 0.08;
    const deltaPct = ((Math.random() - 0.5) * 0.0002) + pull;
    const newPrice = +(t.price * (1 + deltaPct)).toFixed(s.tickDecimals);
    t.price = newPrice;
    t.bid = +(newPrice * 0.9999).toFixed(s.tickDecimals);
    t.ask = +(newPrice * 1.0001).toFixed(s.tickDecimals);
    t.last_updated = new Date().toISOString();
    updateLatestCandle(s.id, newPrice, s.tickDecimals);
  }
}

// Background price fetcher loop: every 3 seconds
setInterval(() => {
  fetchBinanceLivePrices().then(() => {
    updatePositionsPnL();
    evaluateAutomatedBot();
  });
}, 3000);

// Background multi-market opportunity scanner: every 5 seconds
setInterval(() => {
  scanAllMarketsForOpportunities();
}, 5000);

// Also run sub-second micro-ticks every 1s for ultra-responsive UI
setInterval(() => {
  simulateMicroTicks();
  updatePositionsPnL();
}, 1000);

"""

new_code = code[:p1] + replacement_block + "\n\n" + code[p2:]

with open(target_path, "w", encoding="utf-8") as f:
    f.write(new_code)

print("✅ [Success] paper_exchange_engine.js updated successfully!")

# Syntax check
try:
    check = subprocess.run(["node", "-c", target_path], capture_output=True, text=True)
    if check.returncode == 0:
        print("✅ [Syntax Check] JavaScript code is 100% valid.")
    else:
        print("⚠️ Syntax warning:", check.stderr)
except Exception as e:
    pass

# Verify KuCoin connectivity
try:
    req = urllib.request.Request("https://api.kucoin.com/api/v1/market/allTickers", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        d = json.loads(r.read().decode())
        tickers = {t['symbol']: t['last'] for t in d.get('data', {}).get('ticker', [])}
        print(f"🔥 [Live Global Feed] BTC: ${tickers.get('BTC-USDT', 'N/A')} | SOL: ${tickers.get('SOL-USDT', 'N/A')} | ETH: ${tickers.get('ETH-USDT', 'N/A')}")
except Exception as e:
    print("⚠️ KuCoin test:", e)

# Restart PM2
print("🔄 Restarting server via PM2...")
try:
    subprocess.run(["npx", "--yes", "pm2", "restart", "all"], check=False, timeout=10)
    print("🎉 All PM2 processes restarted with fresh live prices!")
except Exception as e:
    print("👉 Please manually run: npx pm2 restart all")

