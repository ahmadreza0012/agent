/**
 * Real-time Paper Trading & Virtual Exchange Engine
 * 
 * Features:
 * - Live real-time crypto prices from Binance & exchange feeds (BTC/USDT, ETH/USDT, SOL/USDT, BTC/IRT, TON/USDT)
 * - Continuous price streaming & synthetic micro-ticks
 * - Virtual trading wallet ($10,000 USDT starting capital)
 * - Market & Limit orders (BUY/LONG, SELL/SHORT) with 1x-20x leverage
 * - Realistic slippage & taker fees (0.05%)
 * - Auto Stop-Loss (SL) and Take-Profit (TP) trigger engine
 * - Liquidation engine to protect against negative balance
 * - Automated Algorithmic Trading Bot (EMA Crossover, RSI Reversion, MACD Momentum)
 * - Full trade logs and closed orders history
 */

import express from 'express';
import { recordOrder, recordClosedTrade, getClosedTrades, getDatabaseStats, saveOpenPositionsToDb, loadOpenPositionsFromDb, saveAccountStateToDb, loadAccountStateFromDb, recordMarketOpportunity, getRecentMarketOpportunities, updateMarketOpportunityStatus } from './trading_db_manager.js';
import { evaluateMarketWith60Features } from './sixty_features_quant_engine.js';
import { agentLearner } from './self_improving_agent.js';

export const paperRouter = express.Router();

// Supported Market Symbols Across Global Majors, Meme/Scalp, AI, Layer 1/2, and Iranian Toman Pairs
export const SUPPORTED_SYMBOLS = [
  // Majors
  { id: 'BTC/USDT', binanceSymbol: 'BTCUSDT', name: 'Bitcoin', category: 'Majors', basePrice: 78300, tickDecimals: 2, minSize: 0.0001 },
  { id: 'ETH/USDT', binanceSymbol: 'ETHUSDT', name: 'Ethereum', category: 'Majors', basePrice: 2460, tickDecimals: 2, minSize: 0.001 },
  { id: 'SOL/USDT', binanceSymbol: 'SOLUSDT', name: 'Solana', category: 'Majors', basePrice: 142.50, tickDecimals: 2, minSize: 0.05 },
  { id: 'BNB/USDT', binanceSymbol: 'BNBUSDT', name: 'BNB Chain', category: 'Majors', basePrice: 590.00, tickDecimals: 2, minSize: 0.01 },
  { id: 'XRP/USDT', binanceSymbol: 'XRPUSDT', name: 'Ripple', category: 'Majors', basePrice: 0.58, tickDecimals: 4, minSize: 10.0 },
  { id: 'ADA/USDT', binanceSymbol: 'ADAUSDT', name: 'Cardano', category: 'Majors', basePrice: 0.36, tickDecimals: 4, minSize: 10.0 },
  { id: 'AVAX/USDT', binanceSymbol: 'AVAXUSDT', name: 'Avalanche', category: 'Majors', basePrice: 28.50, tickDecimals: 2, minSize: 0.2 },
  { id: 'LINK/USDT', binanceSymbol: 'LINKUSDT', name: 'Chainlink', category: 'Majors', basePrice: 11.80, tickDecimals: 2, minSize: 0.5 },
  { id: 'DOT/USDT', binanceSymbol: 'DOTUSDT', name: 'Polkadot', category: 'Majors', basePrice: 4.30, tickDecimals: 2, minSize: 1.0 },
  { id: 'LTC/USDT', binanceSymbol: 'LTCUSDT', name: 'Litecoin', category: 'Majors', basePrice: 68.00, tickDecimals: 2, minSize: 0.1 },

  // High-Beta & Meme Scalping
  { id: 'DOGE/USDT', binanceSymbol: 'DOGEUSDT', name: 'Dogecoin', category: 'Meme/Scalp', basePrice: 0.11, tickDecimals: 5, minSize: 20.0 },
  { id: 'SHIB/USDT', binanceSymbol: 'SHIBUSDT', name: 'Shiba Inu', category: 'Meme/Scalp', basePrice: 0.000017, tickDecimals: 8, minSize: 100000 },
  { id: 'PEPE/USDT', binanceSymbol: 'PEPEUSDT', name: 'Pepe', category: 'Meme/Scalp', basePrice: 0.0000095, tickDecimals: 8, minSize: 100000 },
  { id: 'WIF/USDT', binanceSymbol: 'WIFUSDT', name: 'dogwifhat', category: 'Meme/Scalp', basePrice: 2.10, tickDecimals: 3, minSize: 1.0 },
  { id: 'BONK/USDT', binanceSymbol: 'BONKUSDT', name: 'Bonk', category: 'Meme/Scalp', basePrice: 0.000021, tickDecimals: 8, minSize: 100000 },
  { id: 'FLOKI/USDT', binanceSymbol: 'FLOKIUSDT', name: 'Floki', category: 'Meme/Scalp', basePrice: 0.000145, tickDecimals: 6, minSize: 10000 },

  // AI & Next-Gen Compute
  { id: 'RENDER/USDT', binanceSymbol: 'RENDERUSDT', name: 'Render', category: 'AI & Compute', basePrice: 5.60, tickDecimals: 2, minSize: 1.0 },
  { id: 'FET/USDT', binanceSymbol: 'FETUSDT', name: 'Artificial Superintelligence', category: 'AI & Compute', basePrice: 1.35, tickDecimals: 3, minSize: 5.0 },
  { id: 'TAO/USDT', binanceSymbol: 'TAOUSDT', name: 'Bittensor', category: 'AI & Compute', basePrice: 480.0, tickDecimals: 1, minSize: 0.02 },
  { id: 'INJ/USDT', binanceSymbol: 'INJUSDT', name: 'Injective', category: 'DeFi & AI', basePrice: 19.50, tickDecimals: 2, minSize: 0.5 },

  // Layer 1 & Layer 2 High Momentum
  { id: 'SUI/USDT', binanceSymbol: 'SUIUSDT', name: 'Sui Network', category: 'Layer 1', basePrice: 1.85, tickDecimals: 3, minSize: 2.0 },
  { id: 'NEAR/USDT', binanceSymbol: 'NEARUSDT', name: 'Near Protocol', category: 'Layer 1', basePrice: 4.80, tickDecimals: 3, minSize: 1.0 },
  { id: 'TON/USDT', binanceSymbol: 'TONUSDT', name: 'Toncoin', category: 'Layer 1', basePrice: 4.95, tickDecimals: 3, minSize: 1.0 },
  { id: 'APT/USDT', binanceSymbol: 'APTUSDT', name: 'Aptos', category: 'Layer 1', basePrice: 8.40, tickDecimals: 2, minSize: 0.5 },
  { id: 'ARB/USDT', binanceSymbol: 'ARBUSDT', name: 'Arbitrum', category: 'Layer 2', basePrice: 0.52, tickDecimals: 4, minSize: 10.0 },
  { id: 'OP/USDT', binanceSymbol: 'OPUSDT', name: 'Optimism', category: 'Layer 2', basePrice: 1.45, tickDecimals: 3, minSize: 2.0 },
  { id: 'TIA/USDT', binanceSymbol: 'TIAUSDT', name: 'Celestia', category: 'Modular L1', basePrice: 5.20, tickDecimals: 2, minSize: 1.0 },
  { id: 'SEI/USDT', binanceSymbol: 'SEIUSDT', name: 'Sei Network', category: 'Layer 1', basePrice: 0.39, tickDecimals: 4, minSize: 10.0 },
  { id: 'UNI/USDT', binanceSymbol: 'UNIUSDT', name: 'Uniswap', category: 'DeFi', basePrice: 7.20, tickDecimals: 2, minSize: 0.5 },

  // Iranian Toman (IRT) Markets
  { id: 'BTC/IRT', binanceSymbol: 'BTCUSDT', name: 'بیت‌کوین / تومان', category: 'بازار تومانی', basePrice: 7550000000, tickDecimals: 0, minSize: 0.0001, isToman: true },
  { id: 'ETH/IRT', binanceSymbol: 'ETHUSDT', name: 'اتریوم / تومان', category: 'بازار تومانی', basePrice: 237000000, tickDecimals: 0, minSize: 0.001, isToman: true },
  { id: 'SOL/IRT', binanceSymbol: 'SOLUSDT', name: 'سولانا / تومان', category: 'بازار تومانی', basePrice: 13750000, tickDecimals: 0, minSize: 0.05, isToman: true },
  { id: 'TON/IRT', binanceSymbol: 'TONUSDT', name: 'تون‌کوین / تومان', category: 'بازار تومانی', basePrice: 477000, tickDecimals: 0, minSize: 1.0, isToman: true },
  { id: 'USDT/IRT', binanceSymbol: null, name: 'تتر / تومان', category: 'بازار تومانی', basePrice: 96500, tickDecimals: 0, minSize: 5.0, isToman: true }
];

// Tomans per USDT exchange rate (approx ~96,500 Tomans)
const USDT_TO_TOMAN_RATE = 96500;

// Market tickers store
const MARKET_TICKERS = new Map();
// 1m candles history for charts
const CANDLE_HISTORY = new Map();
// Detected high-probability market opportunities
export let RECENT_MARKET_OPPORTUNITIES = [];

// Initialize initial market data & candles
function initMarketData() {
  const now = Date.now();
  for (const sym of SUPPORTED_SYMBOLS) {
    let currentPrice = sym.basePrice;
    MARKET_TICKERS.set(sym.id, {
      symbol: sym.id,
      name: sym.name,
      category: sym.category || 'Crypto',
      price: currentPrice,
      bid: +(currentPrice * 0.9999).toFixed(sym.tickDecimals),
      ask: +(currentPrice * 1.0001).toFixed(sym.tickDecimals),
      change24h: +(Math.random() * 3 - 1).toFixed(2),
      high24h: +(currentPrice * 1.025).toFixed(sym.tickDecimals),
      low24h: +(currentPrice * 0.975).toFixed(sym.tickDecimals),
      volume24h: +(Math.random() * 15000 + 5000).toFixed(2),
      last_updated: new Date().toISOString()
    });

    // Generate 50 initial 1-minute historical candles
    const candles = [];
    let p = currentPrice * 0.985;
    for (let i = 50; i >= 0; i--) {
      const time = now - i * 60000;
      const change = (Math.random() - 0.49) * 0.004 * p;
      const open = p;
      const close = p + change;
      const high = Math.max(open, close) + Math.random() * 0.002 * p;
      const low = Math.min(open, close) - Math.random() * 0.002 * p;
      const vol = +(Math.random() * 45 + 5).toFixed(2);
      p = close;
      candles.push({
        time,
        open: +open.toFixed(sym.tickDecimals),
        high: +high.toFixed(sym.tickDecimals),
        low: +low.toFixed(sym.tickDecimals),
        close: +close.toFixed(sym.tickDecimals),
        volume: vol
      });
    }
    CANDLE_HISTORY.set(sym.id, candles);
  }
}

initMarketData();

// Live price fetcher from Binance for ALL symbols
async function fetchBinanceLivePrices() {
  try {
    const symbolsToQuery = Array.from(new Set(SUPPORTED_SYMBOLS.filter(s => s.binanceSymbol && !s.isToman).map(s => s.binanceSymbol)));
    const res = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbols=${encodeURIComponent(JSON.stringify(symbolsToQuery))}`, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      signal: AbortSignal.timeout(4000)
    });
    if (!res.ok) return;
    const data = await res.json();
    if (!Array.isArray(data)) return;

    for (const item of data) {
      const matched = SUPPORTED_SYMBOLS.filter(s => s.binanceSymbol === item.symbol && !s.isToman);
      for (const s of matched) {
        const lastPrice = parseFloat(item.lastPrice);
        const change24h = parseFloat(item.priceChangePercent);
        const high24h = parseFloat(item.highPrice);
        const low24h = parseFloat(item.lowPrice);
        const volume24h = parseFloat(item.volume);

        if (!isNaN(lastPrice) && lastPrice > 0) {
          const prev = MARKET_TICKERS.get(s.id);
          MARKET_TICKERS.set(s.id, {
            ...prev,
            price: lastPrice,
            bid: +(lastPrice * 0.9999).toFixed(s.tickDecimals),
            ask: +(lastPrice * 1.0001).toFixed(s.tickDecimals),
            change24h,
            high24h,
            low24h,
            volume24h,
            last_updated: new Date().toISOString()
          });

          // Update candle history
          updateLatestCandle(s.id, lastPrice, s.tickDecimals);
        }
      }
    }

    // Update Toman pairs based on live prices
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
  } catch (err) {
    // Fallback to Brownian motion micro-ticks if external network is congested
    simulateMicroTicks();
  }
}

function updateLatestCandle(symbolId, price, decimals) {
  const list = CANDLE_HISTORY.get(symbolId);
  if (!list || list.length === 0) return;
  const last = list[list.length - 1];
  const now = Date.now();

  // If current minute has passed, create new candle
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
    const deltaPct = (Math.random() - 0.495) * 0.0006;
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

// ==========================================
// VIRTUAL / PAPER TRADING ACCOUNT
// ==========================================

export const PAPER_ACCOUNT = {
  initial_balance: 100.00,
  cash_balance: 100.00,
  currency: 'USDT',
  positions: [],
  trades: [],
  bot: {
    enabled: true,
    strategy: '60_FEATURES_CONSENSUS',
    symbol: 'BTC/USDT',
    leverage: 15,
    risk_pct_per_trade: 35,
    last_evaluated: null,
    last_signal: null,
    logs: [
      {
        timestamp: new Date().toISOString(),
        message: '🚀 سیستم معامله‌گری زنده با اجماع ۶۰ ویژگی و سرمایه اولیه ۱۰۰ دلار و اهرم بالا (15x) آغاز به کار کرد.'
      }
    ]
  },
  last_updated: new Date().toISOString()
};

// Restore persistent account state and open positions from SQLite to ensure NO data or open trade is ever wiped
try {
  const loadedAccount = loadAccountStateFromDb();
  if (loadedAccount) {
    PAPER_ACCOUNT.initial_balance = loadedAccount.initial_balance || 100.00;
    PAPER_ACCOUNT.cash_balance = loadedAccount.cash_balance !== undefined ? loadedAccount.cash_balance : 100.00;
    if (loadedAccount.bot && Object.keys(loadedAccount.bot).length > 0) {
      PAPER_ACCOUNT.bot = { ...PAPER_ACCOUNT.bot, ...loadedAccount.bot };
    }
  }
  const loadedPositions = loadOpenPositionsFromDb();
  if (loadedPositions && loadedPositions.length > 0) {
    PAPER_ACCOUNT.positions = loadedPositions;
    console.log(`[Persistence] Restored ${loadedPositions.length} active open position(s) from SQLite database.`);
  }
  const loadedTrades = getClosedTrades(100);
  if (loadedTrades && loadedTrades.length > 0) {
    PAPER_ACCOUNT.trades = loadedTrades;
  }
} catch (loadErr) {
  console.warn('Initial SQLite restore note:', loadErr.message);
}

let lastStateSaveTime = 0;

// Update PnL of all open positions based on live prices
function updatePositionsPnL() {
  const positionsToClose = [];

  for (const pos of PAPER_ACCOUNT.positions) {
    const ticker = MARKET_TICKERS.get(pos.symbol);
    if (!ticker) continue;
    const currentPrice = ticker.price;
    pos.current_price = currentPrice;

    // Standard Futures PnL calculation:
    // Dollar PnL = (currentPrice - entryPrice) * size for LONG
    // Dollar PnL = (entryPrice - currentPrice) * size for SHORT
    let grossPnl = 0;
    if (pos.side === 'LONG') {
      grossPnl = (currentPrice - pos.entry_price) * pos.size;
    } else {
      grossPnl = (pos.entry_price - currentPrice) * pos.size;
    }

    pos.unrealized_pnl = +grossPnl.toFixed(2);
    // ROE % = (Unrealized PnL / Margin) * 100
    pos.unrealized_pnl_pct = pos.margin > 0 ? +((grossPnl / pos.margin) * 100).toFixed(2) : 0;

    // Check Stop Loss
    if (pos.stop_loss) {
      if (pos.side === 'LONG' && currentPrice <= pos.stop_loss) {
        positionsToClose.push({ pos, reason: 'STOP_LOSS' });
        continue;
      }
      if (pos.side === 'SHORT' && currentPrice >= pos.stop_loss) {
        positionsToClose.push({ pos, reason: 'STOP_LOSS' });
        continue;
      }
    }

    // Check Take Profit
    if (pos.take_profit) {
      if (pos.side === 'LONG' && currentPrice >= pos.take_profit) {
        positionsToClose.push({ pos, reason: 'TAKE_PROFIT' });
        continue;
      }
      if (pos.side === 'SHORT' && currentPrice <= pos.take_profit) {
        positionsToClose.push({ pos, reason: 'TAKE_PROFIT' });
        continue;
      }
    }

    // Dynamic Scalp Profit Locking: If this is an opportunistic short-term scalp and hit target ROI (e.g. >= 2.2%)
    if (pos.is_scalp && pos.unrealized_pnl_pct >= (pos.target_roi_pct || 2.2)) {
      positionsToClose.push({ pos, reason: 'SCALP_TAKE_PROFIT' });
      continue;
    }

    // Check Liquidation: If loss exceeds 88% of margin
    if (grossPnl < 0 && Math.abs(grossPnl) >= pos.margin * 0.88) {
      positionsToClose.push({ pos, reason: 'LIQUIDATION' });
      continue;
    }
  }

  // Periodic persistence of open positions and account state to SQLite (every 5 seconds)
  const now = Date.now();
  if (now - lastStateSaveTime > 5000 && PAPER_ACCOUNT.positions.length > 0) {
    lastStateSaveTime = now;
    try {
      saveOpenPositionsToDb(PAPER_ACCOUNT.positions);
      saveAccountStateToDb(PAPER_ACCOUNT);
    } catch {}
  }

  // Execute triggered closures
  for (const item of positionsToClose) {
    executeClosePosition(item.pos.id, item.reason);
  }
}

// Open new paper position
export function openPaperPosition({
  symbol = 'BTC/USDT',
  side = 'LONG',
  type = 'MARKET',
  size = 0.05,
  leverage = 5,
  stop_loss = null,
  take_profit = null
}) {
  const ticker = MARKET_TICKERS.get(symbol);
  if (!ticker) throw new Error(`نماد معاملاتی ${symbol} معتبر نیست`);

  const currentPrice = side === 'LONG' ? ticker.ask : ticker.bid;
  const cleanLeverage = Math.max(1, Math.min(20, parseInt(leverage) || 1));
  const cleanSize = parseFloat(size);

  if (isNaN(cleanSize) || cleanSize <= 0) {
    throw new Error('حجم وارد شده باید عددی مثبت و بزرگتر از صفر باشد');
  }

  const notional = +(cleanSize * currentPrice).toFixed(2);
  const requiredMargin = +(notional / cleanLeverage).toFixed(2);
  const openFee = +(notional * 0.0005).toFixed(2); // 0.05% taker fee

  // Check available free margin
  const summary = getAccountSummary();
  if (summary.free_margin < (requiredMargin + openFee)) {
    throw new Error(`موجودی آزاد کافی نیست. نیاز به ${requiredMargin + openFee} USDT دارید، موجودی آزاد: ${summary.free_margin.toFixed(2)} USDT`);
  }

  // Deduct margin + fee from cash
  PAPER_ACCOUNT.cash_balance -= (requiredMargin + openFee);

  // Calculate liquidation price
  let liquidationPrice = 0;
  if (side === 'LONG') {
    liquidationPrice = +(currentPrice * (1 - (0.88 / cleanLeverage))).toFixed(ticker.tickDecimals || 2);
  } else {
    liquidationPrice = +(currentPrice * (1 + (0.88 / cleanLeverage))).toFixed(ticker.tickDecimals || 2);
  }

  const newPos = {
    id: 'pos_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6),
    symbol,
    side: side.toUpperCase(),
    type: type.toUpperCase(),
    size: cleanSize,
    notional,
    margin: requiredMargin,
    leverage: cleanLeverage,
    entry_price: currentPrice,
    current_price: currentPrice,
    liquidation_price: liquidationPrice,
    stop_loss: stop_loss ? parseFloat(stop_loss) : null,
    take_profit: take_profit ? parseFloat(take_profit) : null,
    unrealized_pnl: 0.00,
    unrealized_pnl_pct: 0.00,
    fee_paid: openFee,
    opened_at: new Date().toISOString()
  };

  PAPER_ACCOUNT.positions.unshift(newPos);

  // Persist order, active open positions, and account state in SQLite database
  try {
    recordOrder(newPos);
    saveOpenPositionsToDb(PAPER_ACCOUNT.positions);
    saveAccountStateToDb(PAPER_ACCOUNT);
  } catch (dbErr) {
    console.warn('Failed to persist order in SQLite:', dbErr.message);
  }

  return newPos;
}

// Close an open position
export function executeClosePosition(positionId, reason = 'MANUAL') {
  const idx = PAPER_ACCOUNT.positions.findIndex(p => p.id === positionId);
  if (idx === -1) return null;

  const pos = PAPER_ACCOUNT.positions[idx];
  const ticker = MARKET_TICKERS.get(pos.symbol);
  const exitPrice = ticker ? (pos.side === 'LONG' ? ticker.bid : ticker.ask) : pos.current_price;

  let grossPnl = 0;
  if (pos.side === 'LONG') {
    grossPnl = (exitPrice - pos.entry_price) * pos.size;
  } else {
    grossPnl = (pos.entry_price - exitPrice) * pos.size;
  }

  const exitFee = +((pos.size * exitPrice) * 0.0005).toFixed(2);
  const netPnl = +(grossPnl - exitFee).toFixed(2);
  const roiPct = pos.margin > 0 ? +((netPnl / pos.margin) * 100).toFixed(2) : 0;

  // Return margin + net PnL back to cash balance
  // Protect from negative account balance on extreme liquidation
  const cashReturn = Math.max(0, pos.margin + netPnl);
  PAPER_ACCOUNT.cash_balance += cashReturn;

  const closedTrade = {
    id: 'tr_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6),
    symbol: pos.symbol,
    side: pos.side,
    size: pos.size,
    leverage: pos.leverage,
    entry_price: pos.entry_price,
    exit_price: exitPrice,
    gross_pnl: +grossPnl.toFixed(2),
    fee: +(pos.fee_paid + exitFee).toFixed(2),
    net_pnl: netPnl,
    roi_pct: roiPct,
    opened_at: pos.opened_at,
    closed_at: new Date().toISOString(),
    close_reason: reason
  };

  if (reason === 'SCALP_TAKE_PROFIT') {
    addBotLog(`🎯 خروج موفق و ذخیره سود اسکالپ ${pos.symbol}: سود خالص +$${netPnl.toFixed(2)} (+${roiPct.toFixed(2)}%) با استراتژی خروج سریع.`);
  }

  PAPER_ACCOUNT.trades.unshift(closedTrade);
  PAPER_ACCOUNT.positions.splice(idx, 1);

  // Persist closed trade, remaining open positions, and account state into SQLite database
  try {
    recordClosedTrade(closedTrade);
    saveOpenPositionsToDb(PAPER_ACCOUNT.positions);
    saveAccountStateToDb(PAPER_ACCOUNT);
    // Reinforcement learning feedback update on completed trade
    agentLearner.learnFromTradeOutcome(closedTrade);
  } catch (dbErr) {
    console.warn('Failed to persist closed trade in SQLite:', dbErr.message);
  }

  return closedTrade;
}

// Compute comprehensive account summary
export function getAccountSummary() {
  const totalUsedMargin = PAPER_ACCOUNT.positions.reduce((sum, p) => sum + (p.margin || 0), 0);
  const totalUnrealizedPnl = PAPER_ACCOUNT.positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
  const totalEquity = +(PAPER_ACCOUNT.cash_balance + totalUsedMargin + totalUnrealizedPnl).toFixed(2);
  const freeMargin = Math.max(0, +(totalEquity - totalUsedMargin).toFixed(2));
  const marginLevel = totalUsedMargin > 0 ? +((totalEquity / totalUsedMargin) * 100).toFixed(1) : 999.0;

  const totalRealizedPnl = PAPER_ACCOUNT.trades.reduce((sum, t) => sum + (t.net_pnl || 0), 0);
  const winningTrades = PAPER_ACCOUNT.trades.filter(t => t.net_pnl > 0).length;
  const losingTrades = PAPER_ACCOUNT.trades.filter(t => t.net_pnl < 0).length;
  const totalTrades = PAPER_ACCOUNT.trades.length;
  const winRatePct = totalTrades > 0 ? +((winningTrades / totalTrades) * 100).toFixed(1) : 0;
  const roiPct = +(((totalEquity - PAPER_ACCOUNT.initial_balance) / PAPER_ACCOUNT.initial_balance) * 100).toFixed(2);

  return {
    initial_balance: PAPER_ACCOUNT.initial_balance,
    cash_balance: +PAPER_ACCOUNT.cash_balance.toFixed(2),
    total_equity: totalEquity,
    free_margin: freeMargin,
    used_margin: +totalUsedMargin.toFixed(2),
    margin_level: marginLevel,
    unrealized_pnl: +totalUnrealizedPnl.toFixed(2),
    realized_pnl: +totalRealizedPnl.toFixed(2),
    total_trades: totalTrades,
    winning_trades: winningTrades,
    losing_trades: losingTrades,
    win_rate_pct: winRatePct,
    roi_pct: roiPct,
    active_positions_count: PAPER_ACCOUNT.positions.length,
    bot_status: PAPER_ACCOUNT.bot,
    currency: PAPER_ACCOUNT.currency
  };
}

// Reset paper trading balance to initial $100 with high leverage
export function resetPaperAccount(initialBalance = 100.00) {
  PAPER_ACCOUNT.cash_balance = initialBalance;
  PAPER_ACCOUNT.initial_balance = initialBalance;
  PAPER_ACCOUNT.positions = [];
  PAPER_ACCOUNT.trades = [];
  PAPER_ACCOUNT.bot.enabled = true;
  PAPER_ACCOUNT.bot.strategy = '60_FEATURES_CONSENSUS';
  PAPER_ACCOUNT.bot.leverage = 15;
  PAPER_ACCOUNT.bot.risk_pct_per_trade = 35;
  PAPER_ACCOUNT.bot.logs = [
    {
      timestamp: new Date().toISOString(),
      message: `حساب با ۱۰۰ دلار دارایی و اهرم بالا (15x) برای شروع معاملات خودکار با ۶۰ ویژگی راه‌اندازی شد.`
    }
  ];
  return getAccountSummary();
}

// ==========================================
// AUTOMATED QUANTITATIVE BOT ENGINE (60 FEATURES)
// ==========================================

let isBotEvaluating = false;
let lastBotEvalTime = 0;

export async function evaluateAutomatedBot() {
  if (!PAPER_ACCOUNT.bot.enabled || isBotEvaluating) return;
  const now = Date.now();
  if (now - lastBotEvalTime < 4000) return;
  lastBotEvalTime = now;

  isBotEvaluating = true;
  try {
    const symbol = PAPER_ACCOUNT.bot.symbol || 'BTC/USDT';
    const candles = CANDLE_HISTORY.get(symbol);
    if (!candles || candles.length < 15) return;

    const closes = candles.map(c => c.close);
    const currentPrice = closes[closes.length - 1];
    const strategy = PAPER_ACCOUNT.bot.strategy || '60_FEATURES_CONSENSUS';

    let signal = 'HOLD';
    let reason = '';
    let compositeScore = 0;

    if (strategy === '60_FEATURES_CONSENSUS') {
      const consensus60 = await evaluateMarketWith60Features(symbol, currentPrice, {
        candles,
        orderBook: { bids: [], asks: [] },
        account: getAccountSummary()
      });
      signal = consensus60.overall_signal;
      reason = consensus60.decision_rationale;
      compositeScore = consensus60.composite_score;

      // Online micro-learning: utilize every smallest market observation for agent adaptation
      try {
        agentLearner.learnFromOnlineObservation({
          symbol,
          price: currentPrice,
          compositeScore,
          signal,
          featureScores: consensus60.feature_scores || {},
          source: '60_FEATURES_CONSENSUS_TICK'
        });
      } catch (obsErr) {
        console.warn('Online observation learning notice:', obsErr.message);
      }
    } else if (strategy === 'EMA_CROSS') {
      const ema9 = calculateEMA(closes, 9);
      const ema21 = calculateEMA(closes, 21);
      const prevEma9 = ema9[ema9.length - 2];
      const currEma9 = ema9[ema9.length - 1];
      const prevEma21 = ema21[ema21.length - 2];
      const currEma21 = ema21[ema21.length - 1];
      if (prevEma9 <= prevEma21 && currEma9 > currEma21) {
        signal = 'BUY';
        reason = `تقاطع صعودی EMA(9)=${currEma9.toFixed(1)} از روی EMA(21)=${currEma21.toFixed(1)}`;
      } else if (prevEma9 >= prevEma21 && currEma9 < currEma21) {
        signal = 'SELL';
        reason = `تقاطع نزولی EMA(9)=${currEma9.toFixed(1)} به زیر EMA(21)=${currEma21.toFixed(1)}`;
      }
    } else if (strategy === 'RSI_REVERSION') {
      const rsi = calculateRSI(closes, 14);
      if (rsi < 32) {
        signal = 'BUY';
        reason = `ناحیه اشباع فروش RSI=${rsi.toFixed(1)}`;
      } else if (rsi > 68) {
        signal = 'SELL';
        reason = `ناحیه اشباع خرید RSI=${rsi.toFixed(1)}`;
      }
    }

    PAPER_ACCOUNT.bot.last_evaluated = new Date().toISOString();
    PAPER_ACCOUNT.bot.last_signal = { signal, reason, score: compositeScore, price: currentPrice };

    // Check if we should place an automated paper order
    const existingPos = PAPER_ACCOUNT.positions.find(p => p.symbol === symbol);

    if (signal === 'BUY') {
      if (existingPos && existingPos.side === 'SHORT') {
        executeClosePosition(existingPos.id, 'BOT_REVERSE_SIGNAL');
        addBotLog(`🔄 بستن موقعیت فروش (SHORT) برای ${symbol} بر اساس چرخش سیگنال به BUY [۶۰ ویژگی]`);
      } else if (!existingPos) {
        const summary = getAccountSummary();
        const leverage = Math.max(1, Math.min(20, PAPER_ACCOUNT.bot.leverage || 15));
        // High margin allocation: default 35% of free margin, minimum $15
        const marginAllocated = Math.min(summary.free_margin * 0.85, Math.max(15, summary.free_margin * (PAPER_ACCOUNT.bot.risk_pct_per_trade / 100)));
        const notionalValue = marginAllocated * leverage;
        const assetSize = +(notionalValue / currentPrice).toFixed(4);

        if (assetSize > 0 && summary.free_margin >= 15) {
          try {
            const sl = +(currentPrice * 0.985).toFixed(2);
            const tp = +(currentPrice * 1.035).toFixed(2);
            openPaperPosition({
              symbol,
              side: 'LONG',
              type: 'MARKET',
              size: assetSize,
              leverage,
              stop_loss: sl,
              take_profit: tp
            });
            addBotLog(`🚀 ورود خودکار به معامله خرید (LONG) با مارجین بالا: حجم ${assetSize} ${symbol} (اهرم ${leverage}x، مارجین ~$${marginAllocated.toFixed(1)}) به قیمت $${currentPrice.toLocaleString()} - ${reason}`);
          } catch (e) {
            addBotLog(`خطای ربات در ثبت سفارش خرید: ${e.message}`);
          }
        }
      }
    } else if (signal === 'SELL') {
      if (existingPos && existingPos.side === 'LONG') {
        executeClosePosition(existingPos.id, 'BOT_REVERSE_SIGNAL');
        addBotLog(`🔄 بستن موقعیت خرید (LONG) برای ${symbol} بر اساس چرخش سیگنال به SELL [۶۰ ویژگی]`);
      } else if (!existingPos) {
        const summary = getAccountSummary();
        const leverage = Math.max(1, Math.min(20, PAPER_ACCOUNT.bot.leverage || 15));
        const marginAllocated = Math.min(summary.free_margin * 0.85, Math.max(15, summary.free_margin * (PAPER_ACCOUNT.bot.risk_pct_per_trade / 100)));
        const notionalValue = marginAllocated * leverage;
        const assetSize = +(notionalValue / currentPrice).toFixed(4);

        if (assetSize > 0 && summary.free_margin >= 15) {
          try {
            const sl = +(currentPrice * 1.015).toFixed(2);
            const tp = +(currentPrice * 0.965).toFixed(2);
            openPaperPosition({
              symbol,
              side: 'SHORT',
              type: 'MARKET',
              size: assetSize,
              leverage,
              stop_loss: sl,
              take_profit: tp
            });
            addBotLog(`🔻 ورود خودکار به معامله فروش (SHORT) با مارجین بالا: حجم ${assetSize} ${symbol} (اهرم ${leverage}x، مارجین ~$${marginAllocated.toFixed(1)}) به قیمت $${currentPrice.toLocaleString()} - ${reason}`);
          } catch (e) {
            addBotLog(`خطای ربات در ثبت سفارش فروش: ${e.message}`);
          }
        }
      }
    }
  } catch (err) {
    console.warn('Auto bot evaluation notice:', err.message);
  } finally {
    isBotEvaluating = false;
  }
}

// ============================================================================
// MULTI-MARKET OPPORTUNITY SCANNER & SHORT-TERM SCALPING ENGINE
// ============================================================================

let isScanningMarkets = false;
let lastMarketScanTime = 0;

/**
 * Scans all supported cryptocurrency and Toman market pairs,
 * evaluating technical confluence, volume surges, and RSI momentum
 * to find short-term profitable scalping opportunities.
 */
export async function scanAllMarketsForOpportunities() {
  if (isScanningMarkets) return RECENT_MARKET_OPPORTUNITIES;
  const now = Date.now();
  if (now - lastMarketScanTime < 3000 && RECENT_MARKET_OPPORTUNITIES.length > 0) {
    return RECENT_MARKET_OPPORTUNITIES;
  }
  isScanningMarkets = true;
  lastMarketScanTime = now;

  const scannedList = [];
  try {
    for (const sym of SUPPORTED_SYMBOLS) {
      const ticker = MARKET_TICKERS.get(sym.id);
      if (!ticker || !ticker.price) continue;

      const candles = CANDLE_HISTORY.get(sym.id) || [];
      if (candles.length < 10) continue;

      const closes = candles.map(c => c.close);
      const volumes = candles.map(c => c.volume);
      const currentPrice = ticker.price;
      const change24h = Number(ticker.change24h) || 0;
      const volume24h = Number(ticker.volume24h) || 0;

      // Technical indicators: RSI, Fast/Slow EMA, RVOL
      const rsi14 = calculateRSI(closes, Math.min(14, closes.length - 1));
      const ema9Arr = calculateEMA(closes, 9);
      const ema21Arr = calculateEMA(closes, Math.min(21, closes.length - 1));
      const currEma9 = ema9Arr[ema9Arr.length - 1];
      const currEma21 = ema21Arr[ema21Arr.length - 1];
      const prevEma9 = ema9Arr[ema9Arr.length - 2] || currEma9;
      const prevEma21 = ema21Arr[ema21Arr.length - 2] || currEma21;

      // Volume surge ratio (rvol)
      const recentVol = volumes.slice(-5).reduce((a, b) => a + b, 0) / 5;
      const baseVol = volumes.slice(-20).reduce((a, b) => a + b, 0) / Math.min(20, volumes.length) || 1;
      const rvol = +(recentVol / (baseVol || 1)).toFixed(2);

      // 24h high/low spread
      const highLowSpreadPct = ticker.low24h > 0 ? +(((ticker.high24h - ticker.low24h) / ticker.low24h) * 100).toFixed(2) : 2.5;

      // Determine Scalping Strategy & Profit Expectancy
      let signal = 'HOLD';
      let profitPotential = 50;
      let rationale = '';
      let scalpType = 'MOMENTUM_BREAKOUT';

      if (rsi14 <= 33) {
        signal = 'BUY';
        scalpType = 'OVERSOLD_BOUNCE';
        profitPotential = Math.min(96, Math.round(76 + (33 - rsi14) * 1.2 + (rvol > 1.2 ? 6 : 0)));
        rationale = `اشباع فروش شدید RSI=${rsi14.toFixed(1)}؛ تریگر بازگشت سریع قیمتی به سمت میانگین متحرک (Mean Reversion)`;
      } else if ((currEma9 > currEma21 && prevEma9 <= prevEma21) || (currEma9 > currEma21 && change24h > 1.2 && rvol >= 1.25)) {
        signal = 'BUY';
        scalpType = 'MOMENTUM_BREAKOUT';
        profitPotential = Math.min(97, Math.round(78 + (change24h > 3 ? 9 : 4) + (rvol > 1.4 ? 7 : 0)));
        rationale = `شکست صعودی با تقاطع EMA(9) بالاتر از EMA(21) همراه با جهش حجم معاملات (${rvol}x)`;
      } else if (rsi14 >= 71) {
        signal = 'SELL';
        scalpType = 'OVERBOUGHT_CORRECTION';
        profitPotential = Math.min(94, Math.round(75 + (rsi14 - 71) * 1.1 + (rvol > 1.2 ? 5 : 0)));
        rationale = `اشباع خرید سنگین RSI=${rsi14.toFixed(1)}؛ واگرایی سقف و احتمال اصلاح زودهنگام قیمت`;
      } else if ((currEma9 < currEma21 && prevEma9 >= prevEma21) || (currEma9 < currEma21 && change24h < -1.8 && rvol >= 1.25)) {
        signal = 'SELL';
        scalpType = 'BEARISH_MOMENTUM';
        profitPotential = Math.min(93, Math.round(76 + (change24h < -3 ? 8 : 4) + (rvol > 1.4 ? 6 : 0)));
        rationale = `تقاطع نزولی میانگین‌ها و افزایش فشار فروش در تایم‌فریم معاملاتی کوتاه (${rvol}x حجم)`;
      } else {
        profitPotential = Math.round(45 + Math.abs(change24h) * 1.4);
        rationale = `بازار در فاز تثبیت؛ منتظر شکست الگو یا ورود نقدینگی جدید (RSI=${rsi14.toFixed(1)})`;
      }

      // Dynamic Scalping Targets (Short-Term Scalp: ~1.2% SL, ~2.4% TP => 1:2.0 Risk/Reward)
      const slPct = 0.012;
      const tpPct = 0.024;

      const tpPrice = signal === 'BUY'
        ? +(currentPrice * (1 + tpPct)).toFixed(sym.tickDecimals)
        : +(currentPrice * (1 - tpPct)).toFixed(sym.tickDecimals);

      const slPrice = signal === 'BUY'
        ? +(currentPrice * (1 - slPct)).toFixed(sym.tickDecimals)
        : +(currentPrice * (1 + slPct)).toFixed(sym.tickDecimals);

      const opp = {
        id: 'opp_' + sym.id.replace(/[^a-zA-Z0-9]/g, '_') + '_' + Math.floor(now / 15000),
        symbol: sym.id,
        name: sym.name,
        category: sym.category || 'Crypto',
        price: currentPrice,
        change24h,
        volume24h,
        rsi: +rsi14.toFixed(1),
        rvol,
        volatility: highLowSpreadPct,
        signal,
        scalp_type: scalpType,
        profit_potential: profitPotential,
        rationale,
        take_profit: tpPrice,
        stop_loss: slPrice,
        risk_reward: '1:2.0',
        expected_return_pct: +(tpPct * 100).toFixed(1),
        tickDecimals: sym.tickDecimals,
        minSize: sym.minSize,
        scanned_at: new Date(now).toISOString()
      };

      scannedList.push(opp);
    }

    // Sort descending by profit potential
    scannedList.sort((a, b) => b.profit_potential - a.profit_potential);
    RECENT_MARKET_OPPORTUNITIES = scannedList;

    // Persist top opportunities to SQLite
    for (const opp of scannedList.slice(0, 10)) {
      try {
        recordMarketOpportunity({
          id: opp.id,
          symbol: opp.symbol,
          price: opp.price,
          change24h: opp.change24h,
          volume24h: opp.volume24h,
          profit_potential: opp.profit_potential,
          signal: opp.signal,
          timeframe: 'SHORT_TERM_SCALP',
          rationale: opp.rationale,
          take_profit: opp.take_profit,
          stop_loss: opp.stop_loss,
          status: 'DETECTED',
          scanned_at: opp.scanned_at
        });
      } catch {}
    }

    // If automated bot is active, execute short-term scalp on the highest conviction opportunity
    if (PAPER_ACCOUNT.bot.enabled) {
      await executeOpportunisticScalps(scannedList);
    }
  } catch (err) {
    console.warn('Market opportunities scanner notice:', err.message);
  } finally {
    isScanningMarkets = false;
  }

  return scannedList;
}

/**
 * Autonomous executor for opportunistic short-term scalping across scanned markets.
 */
export async function executeOpportunisticScalps(opportunities) {
  try {
    const summary = getAccountSummary();
    if (summary.free_margin < 8) return; // Need at least $8 free margin

    // Maximum concurrent positions (1 core trade + up to 3 altcoin scalps = 4 max)
    if (PAPER_ACCOUNT.positions.length >= 4) return;

    // Filter opportunities with high profit potential (>= 75%) and active BUY/SELL signal
    const highPotentialOpps = opportunities.filter(o => o.profit_potential >= 75 && (o.signal === 'BUY' || o.signal === 'SELL'));
    if (highPotentialOpps.length === 0) return;

    for (const opp of highPotentialOpps) {
      // Don't open duplicate position on a symbol that is already open
      const alreadyOpen = PAPER_ACCOUNT.positions.some(p => p.symbol === opp.symbol);
      if (alreadyOpen) continue;

      // Safe sizing: allocate 15% - 22% of available free margin per scalp (min $8, max $20)
      const currentFree = getAccountSummary().free_margin;
      if (currentFree < 8) break;

      const marginToUse = Math.min(20, Math.max(8, currentFree * 0.20));
      const leverage = 12; // High-precision scalp leverage
      const notional = marginToUse * leverage;
      let rawSize = notional / opp.price;

      // Adjust size according to asset decimal constraints
      let cleanSize = opp.minSize >= 1 ? Math.max(opp.minSize, Math.round(rawSize)) : +rawSize.toFixed(4);
      if (cleanSize < opp.minSize) cleanSize = opp.minSize;

      const side = opp.signal === 'BUY' ? 'LONG' : 'SHORT';

      try {
        const newPos = openPaperPosition({
          symbol: opp.symbol,
          side,
          type: 'MARKET',
          size: cleanSize,
          leverage,
          stop_loss: opp.stop_loss,
          take_profit: opp.take_profit
        });

        // Tag as short-term scalp
        newPos.is_scalp = true;
        newPos.scalp_rationale = opp.rationale;
        newPos.target_roi_pct = 2.4;

        addBotLog(`⚡ شکار فرصت سود کوتاه‌مدت (اسکالپ): ورود به پوزیشن ${side} روی ${opp.symbol} با شانس سود ${opp.profit_potential}% (مارجین ~$${marginToUse.toFixed(1)}، اهرم ${leverage}x، حد سود: ${opp.take_profit}) - ${opp.rationale}`);

        // Update DB opportunity status
        try {
          updateMarketOpportunityStatus(opp.id, 'EXECUTED', newPos.id);
        } catch {}

        // Feed to online reinforcement learning agent
        try {
          agentLearner.learnFromOnlineObservation({
            symbol: opp.symbol,
            price: opp.price,
            compositeScore: opp.profit_potential,
            signal: opp.signal,
            source: 'MULTI_MARKET_SCALP_SCANNER'
          });
        } catch {}

        // Stop after opening one scalp per cycle to preserve diversification
        break;
      } catch (tradeErr) {
        // Continue loop if sizing or margin on this coin failed
      }
    }
  } catch (err) {
    console.warn('Execute opportunistic scalp notice:', err.message);
  }
}

/**
 * Manual or 1-Click trigger to execute an opportunistic short-term scalp on any coin.
 */
export function executeQuickScalpTrade(symbol, side = 'LONG') {
  const ticker = MARKET_TICKERS.get(symbol);
  if (!ticker) throw new Error(`نماد ${symbol} در مارکت یافت نشد`);

  const summary = getAccountSummary();
  if (summary.free_margin < 8) throw new Error(`مارجین آزاد کافی نیست (حداقل $8 مورد نیاز است)`);

  const currentPrice = ticker.price;
  const symConfig = SUPPORTED_SYMBOLS.find(s => s.id === symbol) || { tickDecimals: 2, minSize: 0.01 };
  const marginToUse = Math.min(25, Math.max(8, summary.free_margin * 0.25));
  const leverage = 12;
  const notional = marginToUse * leverage;
  let rawSize = notional / currentPrice;
  let cleanSize = symConfig.minSize >= 1 ? Math.max(symConfig.minSize, Math.round(rawSize)) : +rawSize.toFixed(4);
  if (cleanSize < symConfig.minSize) cleanSize = symConfig.minSize;

  const slPct = 0.012;
  const tpPct = 0.024;
  const tp = side === 'LONG' ? +(currentPrice * (1 + tpPct)).toFixed(symConfig.tickDecimals) : +(currentPrice * (1 - tpPct)).toFixed(symConfig.tickDecimals);
  const sl = side === 'LONG' ? +(currentPrice * (1 - slPct)).toFixed(symConfig.tickDecimals) : +(currentPrice * (1 + slPct)).toFixed(symConfig.tickDecimals);

  const pos = openPaperPosition({
    symbol,
    side,
    type: 'MARKET',
    size: cleanSize,
    leverage,
    stop_loss: sl,
    take_profit: tp
  });

  pos.is_scalp = true;
  pos.target_roi_pct = 2.4;

  addBotLog(`⚡ اجرای دستی اسکالپ فوری روی ${symbol} (${side}): مارجین $${marginToUse.toFixed(1)}، اهرم ${leverage}x، حد سود: ${tp}`);
  return pos;
}

function addBotLog(msg) {
  if (!PAPER_ACCOUNT.bot.logs) PAPER_ACCOUNT.bot.logs = [];
  if (PAPER_ACCOUNT.bot.logs.length >= 30) PAPER_ACCOUNT.bot.logs.shift();
  PAPER_ACCOUNT.bot.logs.unshift({
    timestamp: new Date().toISOString(),
    message: msg
  });
}

function calculateEMA(values, period) {
  const k = 2 / (period + 1);
  const emaArray = [values[0]];
  for (let i = 1; i < values.length; i++) {
    emaArray.push(values[i] * k + emaArray[i - 1] * (1 - k));
  }
  return emaArray;
}

function calculateRSI(values, period = 14) {
  if (values.length < period + 1) return 50;
  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const diff = values[i] - values[i - 1];
    if (diff >= 0) gains += diff;
    else losses -= diff;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  for (let i = period + 1; i < values.length; i++) {
    const diff = values[i] - values[i - 1];
    if (diff >= 0) {
      avgGain = (avgGain * (period - 1) + diff) / period;
      avgLoss = (avgLoss * (period - 1)) / period;
    } else {
      avgGain = (avgGain * (period - 1)) / period;
      avgLoss = (avgLoss * (period - 1) - diff) / period;
    }
  }

  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - (100 / (1 + rs));
}

function computeBollingerBands(closes, period = 20, multiplier = 2) {
  const upper = [];
  const middle = [];
  const lower = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) {
      middle.push(closes[i]);
      upper.push(closes[i]);
      lower.push(closes[i]);
      continue;
    }
    const slice = closes.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / period;
    const stdDev = Math.sqrt(variance);
    middle.push(+mean.toFixed(2));
    upper.push(+(mean + multiplier * stdDev).toFixed(2));
    lower.push(+(mean - multiplier * stdDev).toFixed(2));
  }
  return { upper, middle, lower };
}

// Generate realistic Order Book depth for symbols
function generateOrderBook(symbolId) {
  const ticker = MARKET_TICKERS.get(symbolId) || { price: 78000, tickDecimals: 2 };
  const p = ticker.price;
  const decimals = ticker.tickDecimals || 2;
  const bids = [];
  const asks = [];

  let cumBid = 0;
  let cumAsk = 0;

  for (let i = 1; i <= 8; i++) {
    const spread = (i * 0.0004);
    const bidPrice = +(p * (1 - spread)).toFixed(decimals);
    const askPrice = +(p * (1 + spread)).toFixed(decimals);
    const bidSize = +(Math.random() * 1.8 + 0.2).toFixed(3);
    const askSize = +(Math.random() * 1.8 + 0.2).toFixed(3);

    cumBid += bidSize;
    cumAsk += askSize;

    bids.push({ price: bidPrice, size: bidSize, total: +cumBid.toFixed(3) });
    asks.push({ price: askPrice, size: askSize, total: +cumAsk.toFixed(3) });
  }

  return { symbol: symbolId, price: p, bids, asks: asks.reverse() };
}

// ==========================================
// ROUTER DEFINITIONS
// ==========================================

// Helper function for candle calculation and technical indicators
export function getCandlesAndIndicators(symbol = 'BTC/USDT', limit = 65) {
  const allCandles = CANDLE_HISTORY.get(symbol) || [];
  const list = limit ? allCandles.slice(-limit) : allCandles;
  const closes = list.map(c => c.close);
  const ema9 = calculateEMA(closes, 9);
  const ema21 = calculateEMA(closes, 21);
  const rsi = closes.map((_, idx) => calculateRSI(closes.slice(0, idx + 1), 14));
  const bb = computeBollingerBands(closes, 20, 2);

  const lastClose = closes[closes.length - 1] || 0;
  const lastEma9 = ema9[ema9.length - 1] || lastClose;
  const lastEma21 = ema21[ema21.length - 1] || lastClose;
  const lastRsi = rsi[rsi.length - 1] || 50;
  const lastUpper = bb.upper[bb.upper.length - 1] || lastClose;
  const lastLower = bb.lower[bb.lower.length - 1] || lastClose;

  // Agent verdict & technical breakdown
  const isBullishEma = lastEma9 > lastEma21;
  const rsiCondition = lastRsi < 35 ? 'اشباع فروش (آماده جهش صعودی)' : (lastRsi > 65 ? 'اشباع خرید (احتمال اصلاح)' : 'خنثی و متعادل');
  
  let agentSignal = 'NEUTRAL / پایش';
  let agentReason = 'رصد و پایش وضعیت اندیکاتورها بدون شکست سطوح کلیدی';

  if (isBullishEma && lastRsi < 65) {
    agentSignal = 'خرید (LONG)';
    agentReason = `تقاطع صعودی میانگین متحرک EMA(9) از EMA(21) با مقدار RSI=${lastRsi.toFixed(1)}؛ تایید مومنتوم خریداران`;
  } else if (!isBullishEma && lastRsi > 35) {
    agentSignal = 'فروش (SHORT)';
    agentReason = `فشار فروش و تقاطع نزولی EMA(9) به زیر EMA(21) با مقدار RSI=${lastRsi.toFixed(1)}؛ تایید سیگنال اصلاحی`;
  }

  // Get active and closed trades for this symbol
  const symbolTrades = [
    ...PAPER_ACCOUNT.positions.filter(p => p.symbol === symbol).map(p => ({
      id: p.id,
      side: p.side,
      type: 'OPEN_POSITION',
      entry_price: p.entry_price,
      size: p.size,
      leverage: p.leverage,
      time: new Date(p.created_at).getTime(),
      pnl: p.unrealized_pnl
    })),
    ...PAPER_ACCOUNT.trades.filter(t => t.symbol === symbol).slice(0, 10).map(t => ({
      id: t.id,
      side: t.side,
      type: 'CLOSED_TRADE',
      entry_price: t.entry_price,
      exit_price: t.exit_price,
      size: t.size,
      time: new Date(t.closed_at).getTime(),
      pnl: t.net_pnl,
      reason: t.close_reason
    }))
  ];

  return {
    symbol,
    candles: list,
    indicators: {
      ema9,
      ema21,
      rsi,
      bollinger: bb,
      latest: {
        price: lastClose,
        ema9: +lastEma9.toFixed(2),
        ema21: +lastEma21.toFixed(2),
        rsi: +lastRsi.toFixed(1),
        bb_upper: lastUpper,
        bb_lower: lastLower,
        trend: isBullishEma ? 'صعودی (Bullish)' : 'نزولی (Bearish)',
        rsi_state: rsiCondition,
        agent_signal: agentSignal,
        agent_reason: agentReason,
        observer_mode: true
      }
    },
    trades: symbolTrades
  };
}

// GET unified terminal bundle (all exchange state in a single fast atomic request)
paperRouter.get(['/bundle', '/terminal-bundle', '/state'], (req, res) => {
  try {
    const symbol = req.query.symbol || 'BTC/USDT';
    const limit = parseInt(req.query.limit) || 65;
    const candlesData = getCandlesAndIndicators(symbol, limit);
    updatePositionsPnL();
    const accountSummary = getAccountSummary();
    const ob = generateOrderBook(symbol);
    const agentLogs = (PAPER_ACCOUNT.bot.logs || []).map(l => {
      let action = 'SCAN';
      if (l.message.includes('خرید') || l.message.includes('LONG')) action = 'BUY';
      else if (l.message.includes('فروش') || l.message.includes('SHORT')) action = 'SELL';
      else if (l.message.includes('سیگنال')) action = 'SIGNAL';
      return { timestamp: l.timestamp, action, message: l.message };
    });

    res.json({
      success: true,
      symbol,
      candles: candlesData.candles,
      indicators: candlesData.indicators,
      trades: candlesData.trades,
      account: accountSummary,
      positions: PAPER_ACCOUNT.positions,
      closed_trades: PAPER_ACCOUNT.trades.slice(0, 50),
      orderbook: ob,
      opportunities: RECENT_MARKET_OPPORTUNITIES.slice(0, 30),
      agent: {
        status: PAPER_ACCOUNT.bot.enabled ? 'active' : 'idle',
        enabled: PAPER_ACCOUNT.bot.enabled,
        strategy: PAPER_ACCOUNT.bot.strategy || '60_FEATURES_CONSENSUS',
        symbol: PAPER_ACCOUNT.bot.symbol || 'BTC/USDT',
        leverage: PAPER_ACCOUNT.bot.leverage || 5,
        risk_pct_per_trade: PAPER_ACCOUNT.bot.risk_pct_per_trade || 8,
        last_evaluated: PAPER_ACCOUNT.bot.last_evaluated,
        last_signal: PAPER_ACCOUNT.bot.last_signal,
        thought_logs: agentLogs
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// GET all detected market opportunities with profit potential ranking
paperRouter.get('/opportunities', async (req, res) => {
  try {
    const opps = await scanAllMarketsForOpportunities();
    res.json({
      success: true,
      count: opps.length,
      scanned_at: new Date().toISOString(),
      opportunities: opps
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST trigger immediate on-demand market scan
paperRouter.post('/opportunities/scan', async (req, res) => {
  try {
    lastMarketScanTime = 0; // force scan
    const opps = await scanAllMarketsForOpportunities();
    res.json({
      success: true,
      message: `اسکن کامل ${opps.length} نماد بازار کریپتو و تومان با موفقیت انجام شد.`,
      count: opps.length,
      opportunities: opps
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST execute quick 1-click scalp on a detected market opportunity
paperRouter.post('/opportunities/scalp', (req, res) => {
  try {
    const { symbol, side } = req.body;
    if (!symbol) {
      return res.status(400).json({ success: false, error: 'پارامتر symbol الزامی است' });
    }
    const position = executeQuickScalpTrade(symbol, side || 'LONG');
    res.json({
      success: true,
      message: `معامله فوری اسکالپ برای نماد ${symbol} (${side || 'LONG'}) با موفقیت ثبت و فعال شد.`,
      position
    });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// GET all market tickers & exchange prices
paperRouter.get(['/market', '/tickers'], (req, res) => {
  try {
    const tickersList = Array.from(MARKET_TICKERS.values());
    res.json({
      success: true,
      timestamp: new Date().toISOString(),
      tickers: tickersList
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// GET order book for symbol
paperRouter.get('/orderbook', (req, res) => {
  try {
    const symbol = req.query.symbol || 'BTC/USDT';
    const ob = generateOrderBook(symbol);
    res.json({ success: true, orderbook: ob });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// GET candle history and technical indicators for chart
paperRouter.get('/candles', (req, res) => {
  try {
    const symbol = req.query.symbol || 'BTC/USDT';
    const limit = parseInt(req.query.limit) || 65;
    const data = getCandlesAndIndicators(symbol, limit);
    res.json({
      success: true,
      ...data
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// GET paper account status, balance, positions
paperRouter.get('/account', (req, res) => {
  try {
    updatePositionsPnL();
    const summary = getAccountSummary();
    res.json({
      success: true,
      account: summary,
      positions: PAPER_ACCOUNT.positions,
      trades: PAPER_ACCOUNT.trades.slice(0, 50)
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST place a paper order
paperRouter.post('/order', (req, res) => {
  try {
    const { symbol, side, type, size, leverage, stop_loss, take_profit } = req.body;
    const pos = openPaperPosition({ symbol, side, type, size, leverage, stop_loss, take_profit });
    res.json({
      success: true,
      message: `سفارش ${pos.side === 'LONG' ? 'خرید (LONG)' : 'فروش (SHORT)'} با موفقیت در صرافی مجازی ثبت و اجرا شد`,
      position: pos,
      account: getAccountSummary()
    });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
});

// POST close single position
paperRouter.post(['/close-position', '/position/close', '/close'], (req, res) => {
  try {
    const { position_id } = req.body;
    const closedTrade = executeClosePosition(position_id, 'MANUAL');
    if (!closedTrade) {
      return res.status(404).json({ success: false, error: 'پوزیشن مورد نظر یافت نشد یا قبلاً بسته شده است' });
    }
    res.json({
      success: true,
      message: `پوزیشن با سود/زیان ${closedTrade.net_pnl >= 0 ? '+' : ''}${closedTrade.net_pnl} USDT بسته شد`,
      trade: closedTrade,
      account: getAccountSummary()
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST close all positions
paperRouter.post(['/close-all', '/positions/close-all'], (req, res) => {
  try {
    const posIds = PAPER_ACCOUNT.positions.map(p => p.id);
    const closed = [];
    for (const id of posIds) {
      const t = executeClosePosition(id, 'MANUAL_CLOSE_ALL');
      if (t) closed.push(t);
    }
    res.json({
      success: true,
      message: `تمام ${closed.length} پوزیشن باز با موفقیت به قیمت لحظه‌ای بازار بسته شدند`,
      closed_count: closed.length,
      account: getAccountSummary()
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// POST reset paper account to $100 with high margin
paperRouter.post(['/account/reset', '/reset'], (req, res) => {
  const initial = Number(req.body?.initial_balance) || 100.00;
  const summary = resetPaperAccount(initial);
  res.json({
    success: true,
    message: `حساب آزمایشی با موفقیت به موجودی اولیه ${initial} دلار با اهرم بالا (15x) بازنشانی شد`,
    account: summary
  });
});

// POST toggle auto-trading bot
paperRouter.post(['/bot-toggle', '/agent/toggle', '/bot/toggle'], (req, res) => {
  const { enabled, strategy, symbol, leverage, risk_pct } = req.body;
  if (typeof enabled === 'boolean') {
    PAPER_ACCOUNT.bot.enabled = enabled;
  }
  if (strategy) PAPER_ACCOUNT.bot.strategy = strategy;
  if (symbol) PAPER_ACCOUNT.bot.symbol = symbol;
  if (leverage) PAPER_ACCOUNT.bot.leverage = parseInt(leverage) || 15;
  if (risk_pct) PAPER_ACCOUNT.bot.risk_pct_per_trade = parseFloat(risk_pct) || 35;

  addBotLog(`تنظیمات ایجنت معامله‌گر به‌روزرسانی شد: وضعیت=${PAPER_ACCOUNT.bot.enabled ? 'روشن' : 'خاموش'}, استراتژی=${PAPER_ACCOUNT.bot.strategy}, اهرم=${PAPER_ACCOUNT.bot.leverage}x`);

  res.json({
    success: true,
    message: `ایجنت معامله‌گر خودکار ${PAPER_ACCOUNT.bot.enabled ? 'فعال' : 'غیرفعال'} شد`,
    bot: PAPER_ACCOUNT.bot
  });
});

// GET agent status and thought logs
paperRouter.get(['/agent/status', '/bot/status'], (req, res) => {
  const logs = (PAPER_ACCOUNT.bot.logs || []).map(l => {
    let action = 'SCAN';
    if (l.message.includes('خرید') || l.message.includes('LONG')) action = 'BUY';
    else if (l.message.includes('فروش') || l.message.includes('SHORT')) action = 'SELL';
    else if (l.message.includes('سیگنال')) action = 'SIGNAL';
    return {
      timestamp: l.timestamp,
      action,
      message: l.message
    };
  });

  res.json({
    success: true,
    status: PAPER_ACCOUNT.bot.enabled ? 'active' : 'idle',
    enabled: PAPER_ACCOUNT.bot.enabled,
    strategy: PAPER_ACCOUNT.bot.strategy || '60_FEATURES_CONSENSUS',
    symbol: PAPER_ACCOUNT.bot.symbol || 'BTC/USDT',
    leverage: PAPER_ACCOUNT.bot.leverage || 15,
    risk_pct_per_trade: PAPER_ACCOUNT.bot.risk_pct_per_trade || 35,
    last_evaluated: PAPER_ACCOUNT.bot.last_evaluated,
    last_signal: PAPER_ACCOUNT.bot.last_signal,
    thought_logs: logs
  });
});

// POST trigger immediate agent evaluation step utilizing all 60 capabilities & self-improving weights
paperRouter.post(['/agent/step', '/bot/step', '/agent/trigger'], async (req, res) => {
  try {
    const symbol = req.body?.symbol || PAPER_ACCOUNT.bot.symbol || 'BTC/USDT';
    const ticker = MARKET_TICKERS.get(symbol);
    const candles = CANDLE_HISTORY.get(symbol) || [];
    const closes = candles.length > 0 ? candles.map(c => c.close) : [ticker?.price || 78000];
    const currentPrice = closes[closes.length - 1] || ticker?.price || 78000;

    // Execute comprehensive 60 domain capabilities quantitative consensus
    const consensus60 = await evaluateMarketWith60Features(symbol, currentPrice, {
      candles,
      orderBook: { bids: [], asks: [] },
      account: getAccountSummary()
    });

    const action = consensus60.overall_signal;
    const reason = consensus60.decision_rationale;

    addBotLog(`[تصمیم‌گیری ۶۰ ویژگی] ایجنت نسل ${consensus60.agent_generation} بازار را ارزیابی نمود: سیگنال ${action} (امتیاز اجماع: ${consensus60.composite_score})`);

    // If forceTrade or bot enabled, execute order
    let executedOrder = null;
    if (req.body?.forceTrade || (PAPER_ACCOUNT.bot.enabled && action !== 'HOLD')) {
      try {
        const side = action === 'BUY' ? 'LONG' : (action === 'SELL' ? 'SHORT' : 'LONG');
        const summary = getAccountSummary();
        const leverage = Math.max(1, Math.min(20, PAPER_ACCOUNT.bot.leverage || 15));
        const marginAllocated = Math.min(summary.free_margin * 0.85, Math.max(15, summary.free_margin * (PAPER_ACCOUNT.bot.risk_pct_per_trade / 100)));
        const notionalValue = marginAllocated * leverage;
        const assetSize = +(notionalValue / currentPrice).toFixed(4);

        if (assetSize > 0 && summary.free_margin >= 15) {
          const sl = side === 'LONG' ? +(currentPrice * 0.985).toFixed(2) : +(currentPrice * 1.015).toFixed(2);
          const tp = side === 'LONG' ? +(currentPrice * 1.035).toFixed(2) : +(currentPrice * 0.965).toFixed(2);
          executedOrder = openPaperPosition({
            symbol,
            side,
            type: 'MARKET',
            size: assetSize,
            leverage,
            price: currentPrice,
            stop_loss: sl,
            take_profit: tp
          });
          addBotLog(`🤖 ورود خودکار بر اساس اجماع ۶۰ ویژگی با مارجین بالا: ${side} ${assetSize} ${symbol} (اهرم ${leverage}x) به قیمت $${currentPrice.toLocaleString()}`);
        }
      } catch (tradeErr) {
        addBotLog(`هشدار ایجنت هنگام ثبت پوزیشن: ${tradeErr.message}`);
      }
    }

    res.json({
      success: true,
      action,
      reason,
      price: currentPrice,
      composite_score: consensus60.composite_score,
      agent_generation: consensus60.agent_generation,
      category_analysis: consensus60.category_analysis,
      total_features_evaluated: consensus60.total_features_evaluated,
      executed_order: executedOrder,
      account: getAccountSummary()
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
});

// GET closed trades history
paperRouter.get('/history', (req, res) => {
  res.json({
    success: true,
    trades: PAPER_ACCOUNT.trades
  });
});
