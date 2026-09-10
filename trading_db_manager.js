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
    dbInstance = new DatabaseSync(DB_PATH);
    initDatabaseTables(dbInstance);
  }
  return dbInstance;
}

function initDatabaseTables(db) {
  // Ensure base tables exist
  db.exec(`
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
    orders: getCount('orders'),
    trades: getCount('trades'),
    capability_executions: getCount('capability_executions'),
    agent_training_epochs: getCount('agent_training_epochs'),
    agent_cycles: getCount('agent_cycles'),
    db_file_path: DB_PATH,
    db_size_bytes: fs.existsSync(DB_PATH) ? fs.statSync(DB_PATH).size : 0,
    timestamp: new Date().toISOString()
  };
}
