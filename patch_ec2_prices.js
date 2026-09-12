import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function runPatch() {
  console.log('🚀 [Patch] Starting Crypto Bot Price Engine Patch...');

  // 1. Verify KuCoin connectivity from this server
  try {
    const testRes = await fetch('https://api.kucoin.com/api/v1/market/allTickers', {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      signal: AbortSignal.timeout(5000)
    });
    if (testRes.ok) {
      const data = await testRes.json();
      const btc = data?.data?.ticker?.find(t => t.symbol === 'BTC-USDT');
      const sol = data?.data?.ticker?.find(t => t.symbol === 'SOL-USDT');
      console.log(`✅ [KuCoin API Connected] Live BTC: $${btc?.last || 'N/A'}, Live SOL: $${sol?.last || 'N/A'}`);
    } else {
      console.warn('⚠️ KuCoin returned status:', testRes.status);
    }
  } catch (e) {
    console.warn('⚠️ KuCoin connectivity test warning:', e.message);
  }

  // 2. Read paper_exchange_engine.js
  const targetFile = path.resolve(__dirname, 'paper_exchange_engine.js');
  if (!fs.existsSync(targetFile)) {
    console.error('❌ Could not find paper_exchange_engine.js in current directory:', targetFile);
    process.exit(1);
  }

  let code = fs.readFileSync(targetFile, 'utf8');

  // Fix 1: Base prices inside SUPPORTED_SYMBOLS
  code = code.replace(/basePrice:\s*67250(\.00)?/g, 'basePrice: 77250.00');
  code = code.replace(/basePrice:\s*2480(\.00)?/g, 'basePrice: 2540.00');
  code = code.replace(/basePrice:\s*142(\.50)?/g, 'basePrice: 101.50');

  // Fix 2: simulateMicroTicks upward drift bug: replace (Math.random() - 0.495) with zero-drift mean reversion
  const driftRegex = /function simulateMicroTicks\(\)\s*\{[\s\S]*?updateLatestCandle\(s\.id,\s*newPrice,\s*s\.tickDecimals\);\s*\}\s*\}/;
  const newSimulateMicroTicks = `function simulateMicroTicks() {
  for (const s of SUPPORTED_SYMBOLS) {
    const t = MARKET_TICKERS.get(s.id);
    if (!t) continue;
    // Mean-reverting micro fluctuations with ZERO directional drift
    const anchor = s.basePrice || t.price;
    const deviation = (t.price - anchor) / anchor;
    // Pull back towards anchor if deviating
    const pull = -deviation * 0.08;
    const deltaPct = ((Math.random() - 0.5) * 0.0002) + pull;
    const newPrice = +(t.price * (1 + deltaPct)).toFixed(s.tickDecimals);
    t.price = newPrice;
    t.bid = +(newPrice * 0.9999).toFixed(s.tickDecimals);
    t.ask = +(newPrice * 1.0001).toFixed(s.tickDecimals);
    t.last_updated = new Date().toISOString();
    updateLatestCandle(s.id, newPrice, s.tickDecimals);
  }
}`;

  if (driftRegex.test(code)) {
    code = code.replace(driftRegex, newSimulateMicroTicks);
    console.log('✅ [Patch] simulateMicroTicks drift bug fixed.');
  }

  // Fix 3: Multi-exchange live fetcher with KuCoin & Binance US
  const kucoinFetchBlock = `  // 1. Try KuCoin allTickers first (globally accessible, unblocked on AWS EC2, covers 980+ pairs in one call)
  try {
    const kuRes = await fetch('https://api.kucoin.com/api/v1/market/allTickers', {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      signal: AbortSignal.timeout(4500)
    });
    if (kuRes.ok) {
      const kuJson = await kuRes.json();
      if (kuJson?.data?.ticker && Array.isArray(kuJson.data.ticker)) {
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
              const change24h = !isNaN(changeRate) ? +(changeRate * 100).toFixed(2) : (prev?.change24h || 0);
              MARKET_TICKERS.set(s.id, {
                ...prev,
                price: lastPrice,
                bid: +(lastPrice * 0.9999).toFixed(s.tickDecimals),
                ask: +(lastPrice * 1.0001).toFixed(s.tickDecimals),
                change24h,
                high24h: !isNaN(high24h) && high24h > 0 ? high24h : +(lastPrice * 1.02).toFixed(s.tickDecimals),
                low24h: !isNaN(low24h) && low24h > 0 ? low24h : +(lastPrice * 0.98).toFixed(s.tickDecimals),
                volume24h: !isNaN(volume24h) && volume24h > 0 ? +volume24h.toFixed(2) : (prev?.volume24h || 1000),
                last_updated: new Date().toISOString()
              });
              updateLatestCandle(s.id, lastPrice, s.tickDecimals);
              fetchedSuccessfully = true;
            }
          }
        }
      }
    }
  } catch (kuErr) {
    // Silently continue to next provider
  }`;

  if (!code.includes('api.kucoin.com')) {
    // Insert KuCoin before Binance
    code = code.replace(
      /(\/\/ 1\. Try Binance first[\s\S]*?async function fetchBinanceLivePrices\(\)\s*\{[\s\S]*?let fetchedSuccessfully = false;)/,
      `async function fetchBinanceLivePrices() {\n  let fetchedSuccessfully = false;\n\n${kucoinFetchBlock}`
    );
    console.log('✅ [Patch] KuCoin high-speed live price pipeline injected.');
  }

  // Write updated file
  fs.writeFileSync(targetFile, code, 'utf8');
  console.log('🎉 [Patch] paper_exchange_engine.js updated successfully!');
  console.log('👉 Next step: Run "npx pm2 restart all" to apply changes.');
}

runPatch().catch(err => {
  console.error('❌ Patch failed:', err);
  process.exit(1);
});
