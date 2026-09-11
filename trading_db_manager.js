// trading_db_manager.js - Native SQLite persistence manager for trading records, 60 features, and agent training
import { DatabaseSync } from 'node:sqlite';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DB_PATH = path.join(__dirname, 'data', 'trading.db');

// Ensure directory exists
const dataDir = path.dirname(DB_PATH);
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

let dbInstance = null;

export function getDatabase() {
  if (!dbInstance) {
    try {
      dbInstance = new DatabaseSync(DB_PATH);
      initDatabaseTables(dbInstance);
    } catch (err) {
      console.warn('[Database Recovery] Detected corrupted database:', err.message);
      try {
        if (dbInstance) dbInstance.close();
      } catch {}
      dbInstance = null;
      try {
        const corruptedPath = `${DB_PATH}.corrupted.${Date.now()}`;
        if (fs.existsSync(DB_PATH)) {
          fs.renameSync(DB_PATH, corruptedPath);
          console.log(`[Database Recovery] Renamed malformed DB to ${corruptedPath}`);
        }
      } catch (backupErr) {
        console.warn('[Database Recovery] Could not rename corrupted file:', backupErr);
      }
      dbInstance = new DatabaseSync(DB_PATH);
      initDatabaseTables(dbInstance);
    }
  }
  return dbInstance;
}

function initDatabaseTables(db) {
  // Ensure base tables exist
  db.exec(`
    CREATE TABLE IF NOT EXISTS orders (
      order_id TEXT PRIMARY KEY,
      client_order_id TEXT,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL,
      order_type TEXT DEFAULT 'MARKET',
      price REAL DEFAULT 0,
      amount REAL DEFAULT 0,
      filled_amount REAL DEFAULT 0,
      status TEXT DEFAULT 'FILLED',
      fee REAL DEFAULT 0,
      fee_currency TEXT DEFAULT 'USDT',
      error_message TEXT,
      created_at TIMESTAMP NOT NULL,
      updated_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS trades (
      order_id TEXT PRIMARY KEY,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL,
      price REAL DEFAULT 0,
      amount REAL DEFAULT 0,
      fee REAL DEFAULT 0,
      fee_currency TEXT DEFAULT 'USDT',
      exchange_id TEXT DEFAULT 'paper_exchange',
      timestamp TIMESTAMP NOT NULL,
      created_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS closed_trades (
      id TEXT PRIMARY KEY,
      order_id TEXT,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL,
      size REAL NOT NULL,
      leverage INTEGER DEFAULT 1,
      entry_price REAL NOT NULL,
      exit_price REAL NOT NULL,
      gross_pnl REAL NOT NULL,
      fee REAL NOT NULL,
      net_pnl REAL NOT NULL,
      roi_pct REAL NOT NULL,
      close_reason TEXT,
      opened_at TIMESTAMP NOT NULL,
      closed_at TIMESTAMP NOT NULL,
      created_at TIMESTAMP NOT NULL,
      strategy TEXT,
      features_snapshot_json TEXT
    );

    CREATE TABLE IF NOT EXISTS capability_executions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      cycle_id TEXT NOT NULL,
      capability_id TEXT NOT NULL,
      timestamp TIMESTAMP NOT NULL,
      category TEXT NOT NULL,
      status TEXT NOT NULL,
      confidence REAL DEFAULT 0.95,
      signal_direction REAL DEFAULT 0.0,
      metrics_json TEXT,
      details_json TEXT,
      recommendation TEXT,
      llm_analysis TEXT,
      created_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS agent_training_epochs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      epoch INTEGER NOT NULL,
      generation_id TEXT NOT NULL,
      timestamp TIMESTAMP NOT NULL,
      trades_evaluated INTEGER DEFAULT 0,
      win_rate REAL DEFAULT 0.0,
      net_pnl REAL DEFAULT 0.0,
      average_reward REAL DEFAULT 0.0,
      policy_loss REAL DEFAULT 0.0,
      cumulative_reward REAL DEFAULT 0.0,
      feature_weights_json TEXT NOT NULL,
      prompt_guidelines TEXT,
      status TEXT DEFAULT 'COMPLETED',
      notes TEXT,
      created_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS agent_cycles (
      id TEXT PRIMARY KEY,
      timestamp TIMESTAMP NOT NULL,
      symbol TEXT NOT NULL,
      price REAL NOT NULL,
      overall_signal TEXT NOT NULL,
      composite_score REAL NOT NULL,
      decision_rationale TEXT,
      features_active_count INTEGER DEFAULT 60,
      executed_order_id TEXT,
      agent_generation TEXT,
      created_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS open_positions (
      id TEXT PRIMARY KEY,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL,
      type TEXT DEFAULT 'MARKET',
      size REAL NOT NULL,
      notional REAL NOT NULL,
      margin REAL NOT NULL,
      leverage INTEGER DEFAULT 15,
      entry_price REAL NOT NULL,
      current_price REAL NOT NULL,
      liquidation_price REAL,
      stop_loss REAL,
      take_profit REAL,
      unrealized_pnl REAL DEFAULT 0.0,
      unrealized_pnl_pct REAL DEFAULT 0.0,
      fee_paid REAL DEFAULT 0.0,
      opened_at TIMESTAMP NOT NULL,
      last_updated TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS account_state (
      id TEXT PRIMARY KEY,
      initial_balance REAL NOT NULL,
      cash_balance REAL NOT NULL,
      total_equity REAL NOT NULL,
      currency TEXT DEFAULT 'USDT',
      bot_config_json TEXT,
      updated_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS online_learning_observations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TIMESTAMP NOT NULL,
      symbol TEXT NOT NULL,
      price REAL NOT NULL,
      score REAL NOT NULL,
      signal TEXT NOT NULL,
      feature_deltas_json TEXT,
      reward REAL DEFAULT 0.0,
      source TEXT DEFAULT 'MARKET_TICK',
      created_at TIMESTAMP NOT NULL
    );

    CREATE TABLE IF NOT EXISTS market_opportunities (
      id TEXT PRIMARY KEY,
      symbol TEXT NOT NULL,
      price REAL NOT NULL,
      change24h REAL NOT NULL,
      volume24h REAL NOT NULL,
      profit_potential REAL NOT NULL,
      signal TEXT NOT NULL,
      timeframe TEXT DEFAULT 'SHORT_TERM_SCALP',
      rationale TEXT,
      take_profit REAL,
      stop_loss REAL,
      status TEXT DEFAULT 'DETECTED',
      trade_id TEXT,
      scanned_at TIMESTAMP NOT NULL,
      created_at TIMESTAMP NOT NULL
    );
  `);
}

// Record an order into the orders table
export function recordOrder(order) {
  const db = getDatabase();
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO orders (
      order_id, client_order_id, symbol, side, order_type, price, amount, filled_amount, status, fee, fee_currency, error_message, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const now = new Date().toISOString();
  stmt.run(
    order.id || ('ord_' + Date.now()),
    order.client_order_id || ('cl_' + Date.now()),
    order.symbol || 'BTC/USDT',
    order.side || 'LONG',
    order.type || 'MARKET',
    Number(order.price) || 0,
    Number(order.size || order.amount) || 0,
    Number(order.filled_amount || order.size || order.amount) || 0,
    order.status || 'FILLED',
    Number(order.fee_paid || order.fee) || 0,
    order.fee_currency || 'USDT',
    order.error_message || null,
    order.opened_at || now,
    now
  );
}

// Record a trade into the trades table
export function recordTrade(trade) {
  const db = getDatabase();
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO trades (
      order_id, symbol, side, price, amount, fee, fee_currency, exchange_id, timestamp, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const now = new Date().toISOString();
  stmt.run(
    trade.order_id || trade.id || ('tr_' + Date.now()),
    trade.symbol || 'BTC/USDT',
    trade.side || 'LONG',
    Number(trade.price || trade.exit_price || trade.entry_price) || 0,
    Number(trade.amount || trade.size) || 0,
    Number(trade.fee) || 0,
    trade.fee_currency || 'USDT',
    trade.exchange_id || 'paper_exchange',
    trade.timestamp || trade.closed_at || now,
    now
  );
}

// Record a fully closed trade into closed_trades
export function recordClosedTrade(trade) {
  const db = getDatabase();
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO closed_trades (
      id, order_id, symbol, side, size, leverage, entry_price, exit_price, gross_pnl, fee, net_pnl, roi_pct, close_reason, opened_at, closed_at, created_at, strategy, features_snapshot_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const now = new Date().toISOString();
  stmt.run(
    trade.id || ('ct_' + Date.now()),
    trade.order_id || trade.id || ('ord_' + Date.now()),
    trade.symbol,
    trade.side,
    Number(trade.size) || 0,
    Number(trade.leverage) || 1,
    Number(trade.entry_price) || 0,
    Number(trade.exit_price) || 0,
    Number(trade.gross_pnl) || 0,
    Number(trade.fee) || 0,
    Number(trade.net_pnl) || 0,
    Number(trade.roi_pct) || 0,
    trade.close_reason || 'MANUAL',
    trade.opened_at || now,
    trade.closed_at || now,
    now,
    trade.strategy || 'AGENT_60_FEATURES',
    trade.features_snapshot_json ? JSON.stringify(trade.features_snapshot_json) : null
  );

  // Also log into standard trades and orders tables
  recordTrade({
    order_id: trade.id,
    symbol: trade.symbol,
    side: trade.side,
    price: trade.exit_price,
    amount: trade.size,
    fee: trade.fee,
    timestamp: trade.closed_at
  });
}

// Batch record all 60 capability execution results
export function recordCapabilityExecutionBatch(cycleId, records) {
  const db = getDatabase();
  const stmt = db.prepare(`
    INSERT INTO capability_executions (
      cycle_id, capability_id, timestamp, category, status, confidence, signal_direction, metrics_json, details_json, recommendation, llm_analysis, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const now = new Date().toISOString();
  for (const rec of records) {
    stmt.run(
      cycleId,
      rec.capability_id,
      rec.timestamp || now,
      rec.category || 'general',
      rec.status || 'healthy',
      Number(rec.confidence) || 0.95,
      Number(rec.signal_direction) || 0.0,
      typeof rec.metrics === 'object' ? JSON.stringify(rec.metrics) : (rec.metrics || '{}'),
      typeof rec.details === 'object' ? JSON.stringify(rec.details) : (rec.details || '{}'),
      rec.recommendation || '',
      rec.llm_analysis || rec.summary || '',
      now
    );
  }
}

// Record an agent cycle (consensus of 60 features)
export function recordAgentCycle(cycle) {
  const db = getDatabase();
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO agent_cycles (
      id, timestamp, symbol, price, overall_signal, composite_score, decision_rationale, features_active_count, executed_order_id, agent_generation, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const now = new Date().toISOString();
  stmt.run(
    cycle.id || ('cyc_' + Date.now()),
    cycle.timestamp || now,
    cycle.symbol || 'BTC/USDT',
    Number(cycle.price) || 0,
    cycle.overall_signal || 'HOLD',
    Number(cycle.composite_score) || 0.0,
    cycle.decision_rationale || '',
    Number(cycle.features_active_count) || 60,
    cycle.executed_order_id || null,
    cycle.agent_generation || 'Gen-1',
    now
  );
}

// Record an agent training epoch
export function recordTrainingEpoch(epochData) {
  const db = getDatabase();
  const stmt = db.prepare(`
    INSERT INTO agent_training_epochs (
      epoch, generation_id, timestamp, trades_evaluated, win_rate, net_pnl, average_reward, policy_loss, cumulative_reward, feature_weights_json, prompt_guidelines, status, notes, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const now = new Date().toISOString();
  stmt.run(
    Number(epochData.epoch) || 1,
    epochData.generation_id || ('Gen-' + epochData.epoch),
    epochData.timestamp || now,
    Number(epochData.trades_evaluated) || 0,
    Number(epochData.win_rate) || 0.0,
    Number(epochData.net_pnl) || 0.0,
    Number(epochData.average_reward) || 0.0,
    Number(epochData.policy_loss) || 0.0,
    Number(epochData.cumulative_reward) || 0.0,
    typeof epochData.feature_weights === 'object' ? JSON.stringify(epochData.feature_weights) : epochData.feature_weights,
    epochData.prompt_guidelines || '',
    epochData.status || 'COMPLETED',
    epochData.notes || '',
    now
  );
}

// Query closed trades
export function getClosedTrades(limit = 50) {
  const db = getDatabase();
  const stmt = db.prepare(`
    SELECT * FROM closed_trades ORDER BY closed_at DESC LIMIT ?
  `);
  return stmt.all(limit);
}

// Query orders
export function getOrders(limit = 50) {
  const db = getDatabase();
  const stmt = db.prepare(`
    SELECT * FROM orders ORDER BY created_at DESC LIMIT ?
  `);
  return stmt.all(limit);
}

// Query capability executions
export function getCapabilityExecutions(limit = 120, capabilityId = null) {
  const db = getDatabase();
  if (capabilityId) {
    const stmt = db.prepare(`
      SELECT * FROM capability_executions WHERE capability_id = ? ORDER BY timestamp DESC LIMIT ?
    `);
    return stmt.all(capabilityId, limit);
  }
  const stmt = db.prepare(`
    SELECT * FROM capability_executions ORDER BY timestamp DESC LIMIT ?
  `);
  return stmt.all(limit);
}

// Query training epochs
export function getTrainingEpochs(limit = 50) {
  const db = getDatabase();
  const stmt = db.prepare(`
    SELECT * FROM agent_training_epochs ORDER BY epoch DESC LIMIT ?
  `);
  return stmt.all(limit);
}

// Query recent agent cycles
export function getAgentCycles(limit = 30) {
  const db = getDatabase();
  const stmt = db.prepare(`
    SELECT * FROM agent_cycles ORDER BY timestamp DESC LIMIT ?
  `);
  return stmt.all(limit);
}

// Get comprehensive database statistics
export function getDatabaseStats() {
  const db = getDatabase();
  const getCount = (tbl) => {
    try {
      const row = db.prepare(`SELECT COUNT(*) as cnt FROM ${tbl}`).get();
      return row ? row.cnt : 0;
    } catch {
      return 0;
    }
  };

  return {
    closed_trades: getCount('closed_trades'),
    open_positions: getCount('open_positions'),
    orders: getCount('orders'),
    trades: getCount('trades'),
    capability_executions: getCount('capability_executions'),
    agent_training_epochs: getCount('agent_training_epochs'),
    agent_cycles: getCount('agent_cycles'),
    online_learning_observations: getCount('online_learning_observations'),
    db_file_path: DB_PATH,
    db_size_bytes: fs.existsSync(DB_PATH) ? fs.statSync(DB_PATH).size : 0,
    timestamp: new Date().toISOString()
  };
}

// Persist all open positions to SQLite (ensures no open trade is ever lost)
export function saveOpenPositionsToDb(positions = []) {
  try {
    const db = getDatabase();
    const now = new Date().toISOString();
    
    // Clear stale open positions not in current list
    const currentIds = positions.map(p => p.id);
    if (currentIds.length > 0) {
      const placeholders = currentIds.map(() => '?').join(',');
      db.prepare(`DELETE FROM open_positions WHERE id NOT IN (${placeholders})`).run(...currentIds);
    } else {
      db.prepare(`DELETE FROM open_positions`).run();
    }

    const stmt = db.prepare(`
      INSERT OR REPLACE INTO open_positions (
        id, symbol, side, type, size, notional, margin, leverage, entry_price, current_price, liquidation_price, stop_loss, take_profit, unrealized_pnl, unrealized_pnl_pct, fee_paid, opened_at, last_updated
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    for (const pos of positions) {
      stmt.run(
        pos.id,
        pos.symbol || 'BTC/USDT',
        pos.side || 'LONG',
        pos.type || 'MARKET',
        Number(pos.size) || 0,
        Number(pos.notional) || 0,
        Number(pos.margin) || 0,
        Number(pos.leverage) || 15,
        Number(pos.entry_price) || 0,
        Number(pos.current_price) || Number(pos.entry_price) || 0,
        pos.liquidation_price ? Number(pos.liquidation_price) : null,
        pos.stop_loss ? Number(pos.stop_loss) : null,
        pos.take_profit ? Number(pos.take_profit) : null,
        Number(pos.unrealized_pnl) || 0,
        Number(pos.unrealized_pnl_pct) || 0,
        Number(pos.fee_paid) || 0,
        pos.opened_at || now,
        now
      );
    }

    // Always sync to JSON backup file
    try {
      const backupPath = path.join(dataDir, 'positions_backup.json');
      fs.writeFileSync(backupPath, JSON.stringify(positions, null, 2), 'utf8');
    } catch {}
  } catch (err) {
    console.warn('SQLite save open positions notice:', err.message);
  }
}

// Load persisted open positions from SQLite on boot with dual-redundant fallback
export function loadOpenPositionsFromDb() {
  try {
    const db = getDatabase();
    const rows = db.prepare(`SELECT * FROM open_positions ORDER BY opened_at ASC`).all();
    if (rows && rows.length > 0) {
      return rows.map(r => ({
        id: r.id,
        symbol: r.symbol,
        side: r.side,
        type: r.type,
        size: Number(r.size),
        notional: Number(r.notional),
        margin: Number(r.margin),
        leverage: Number(r.leverage),
        entry_price: Number(r.entry_price),
        current_price: Number(r.current_price),
        liquidation_price: r.liquidation_price ? Number(r.liquidation_price) : null,
        stop_loss: r.stop_loss ? Number(r.stop_loss) : null,
        take_profit: r.take_profit ? Number(r.take_profit) : null,
        unrealized_pnl: Number(r.unrealized_pnl),
        unrealized_pnl_pct: Number(r.unrealized_pnl_pct),
        fee_paid: Number(r.fee_paid),
        opened_at: r.opened_at
      }));
    }
  } catch (err) {
    console.warn('SQLite load open positions notice:', err.message);
  }

  // Dual-redundant JSON safety fallback
  try {
    const backupPath = path.join(dataDir, 'positions_backup.json');
    if (fs.existsSync(backupPath)) {
      const data = JSON.parse(fs.readFileSync(backupPath, 'utf8'));
      if (Array.isArray(data) && data.length > 0) {
        console.log(`[Persistence Safety] Restored ${data.length} position(s) from JSON backup.`);
        return data;
      }
    }
  } catch {}

  return [];
}

// Persist account state to SQLite with dual-redundant storage
export function saveAccountStateToDb(account) {
  const now = new Date().toISOString();
  try {
    const db = getDatabase();
    const stmt = db.prepare(`
      INSERT OR REPLACE INTO account_state (
        id, initial_balance, cash_balance, total_equity, currency, bot_config_json, updated_at
      ) VALUES ('primary', ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      Number(account.initial_balance) || 100.0,
      Number(account.cash_balance) || 100.0,
      Number(account.total_equity ?? account.cash_balance) || 100.0,
      account.currency || 'USDT',
      JSON.stringify(account.bot || {}),
      now
    );
  } catch (err) {
    console.warn('SQLite save account state notice:', err.message);
  }

  // Always sync to JSON backup file
  try {
    const backupPath = path.join(dataDir, 'account_backup.json');
    fs.writeFileSync(backupPath, JSON.stringify({
      initial_balance: account.initial_balance,
      cash_balance: account.cash_balance,
      total_equity: account.total_equity,
      currency: account.currency,
      bot: account.bot,
      updated_at: now
    }, null, 2), 'utf8');
  } catch {}
}

// Load persisted account state from SQLite with dual-redundant fallback
export function loadAccountStateFromDb() {
  try {
    const db = getDatabase();
    const row = db.prepare(`SELECT * FROM account_state WHERE id = 'primary'`).get();
    if (row) {
      let botConfig = {};
      try {
        if (row.bot_config_json) botConfig = JSON.parse(row.bot_config_json);
      } catch {}
      return {
        initial_balance: Number(row.initial_balance),
        cash_balance: Number(row.cash_balance),
        total_equity: Number(row.total_equity),
        currency: row.currency,
        bot: botConfig,
        updated_at: row.updated_at
      };
    }
  } catch (err) {
    console.warn('SQLite load account state notice:', err.message);
  }

  // Dual-redundant JSON safety fallback
  try {
    const backupPath = path.join(dataDir, 'account_backup.json');
    if (fs.existsSync(backupPath)) {
      const data = JSON.parse(fs.readFileSync(backupPath, 'utf8'));
      if (data && data.cash_balance !== undefined) {
        console.log(`[Persistence Safety] Restored account state from JSON backup ($${data.cash_balance} cash).`);
        return data;
      }
    }
  } catch {}

  return null;
}

// Record an online learning micro-observation from every market tick or 60-feature evaluation
export function recordOnlineLearningObservation(obs) {
  const db = getDatabase();
  const now = new Date().toISOString();
  const stmt = db.prepare(`
    INSERT INTO online_learning_observations (
      timestamp, symbol, price, score, signal, feature_deltas_json, reward, source, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  stmt.run(
    obs.timestamp || now,
    obs.symbol || 'BTC/USDT',
    Number(obs.price) || 0,
    Number(obs.score) || 0,
    obs.signal || 'HOLD',
    obs.feature_deltas ? JSON.stringify(obs.feature_deltas) : null,
    Number(obs.reward) || 0.0,
    obs.source || 'MARKET_TICK',
    now
  );
}

// Query recent online learning observations
export function getOnlineLearningObservations(limit = 50) {
  const db = getDatabase();
  try {
    const stmt = db.prepare(`
      SELECT * FROM online_learning_observations ORDER BY id DESC LIMIT ?
    `);
    return stmt.all(limit);
  } catch {
    return [];
  }
}

// Record a detected market opportunity
export function recordMarketOpportunity(opp) {
  const db = getDatabase();
  const now = new Date().toISOString();
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO market_opportunities (
      id, symbol, price, change24h, volume24h, profit_potential, signal, timeframe, rationale, take_profit, stop_loss, status, trade_id, scanned_at, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  stmt.run(
    opp.id || ('opp_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6)),
    opp.symbol,
    Number(opp.price) || 0,
    Number(opp.change24h) || 0,
    Number(opp.volume24h) || 0,
    Number(opp.profit_potential) || 0,
    opp.signal || 'BUY',
    opp.timeframe || 'SHORT_TERM_SCALP',
    opp.rationale || '',
    opp.take_profit ? Number(opp.take_profit) : null,
    opp.stop_loss ? Number(opp.stop_loss) : null,
    opp.status || 'DETECTED',
    opp.trade_id || null,
    opp.scanned_at || now,
    now
  );
}

// Update market opportunity status (e.g. EXECUTED or EXPIRED)
export function updateMarketOpportunityStatus(id, status, tradeId = null) {
  const db = getDatabase();
  try {
    const stmt = db.prepare(`
      UPDATE market_opportunities SET status = ?, trade_id = ? WHERE id = ?
    `);
    stmt.run(status, tradeId, id);
  } catch (err) {
    console.warn('Could not update opportunity status:', err.message);
  }
}

// Query recent detected market opportunities
export function getRecentMarketOpportunities(limit = 25) {
  const db = getDatabase();
  try {
    const stmt = db.prepare(`
      SELECT * FROM market_opportunities ORDER BY scanned_at DESC LIMIT ?
    `);
    return stmt.all(limit);
  } catch {
    return [];
  }
}
