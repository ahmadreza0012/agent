// mcp_server.js - Model Context Protocol (MCP) Server Implementation for Crypto Trading Agent & 60-Features Database
import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { getDatabaseStats, getClosedTrades, getOrders, getCapabilityExecutions, getTrainingEpochs } from './trading_db_manager.js';
import { evaluateMarketWith60Features } from './sixty_features_quant_engine.js';
import { agentLearner } from './self_improving_agent.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const mcpRouter = express.Router();

// MCP Server Metadata
export const MCP_SERVER_INFO = {
  name: 'crypto-60features-trading-agent-mcp',
  version: '2.4.0',
  protocolVersion: '2024-11-05',
  description: 'Model Context Protocol (MCP) Server for BTC/IRT and Crypto Algorithmic Trading with 60 Domain Capabilities, SQLite Persistence, and Self-Improving Agent Loop',
  capabilities: {
    tools: { listChanged: false },
    resources: { subscribe: false, listChanged: false },
    prompts: { listChanged: false }
  }
};

// Tools registry
export const MCP_TOOLS = [
  {
    name: 'execute_60_capabilities',
    description: 'Executes all 60 domain capabilities of the crypto trading system, computes directional signals, logs each analysis to SQLite (data/trading.db), and returns full results.',
    inputSchema: {
      type: 'object',
      properties: {
        symbol: { type: 'string', description: 'Trading pair symbol (e.g. BTC/USDT, BTC/IRT, ETH/USDT)', default: 'BTC/USDT' },
        price: { type: 'number', description: 'Current market price', default: 65200 }
      }
    }
  },
  {
    name: 'get_database_trades',
    description: 'Queries closed trades, orders, and execution records directly from the persistent SQLite database (data/trading.db).',
    inputSchema: {
      type: 'object',
      properties: {
        limit: { type: 'number', description: 'Maximum number of trades to return (1-100)', default: 20 },
        table: { type: 'string', enum: ['closed_trades', 'orders'], default: 'closed_trades' }
      }
    }
  },
  {
    name: 'get_60_feature_analyses',
    description: 'Retrieves stored capability execution records and analyses from the SQLite capability_executions table.',
    inputSchema: {
      type: 'object',
      properties: {
        limit: { type: 'number', description: 'Maximum number of records to return', default: 60 },
        capability_id: { type: 'string', description: 'Optional filter by capability ID (e.g. crypto_algo_trading, circuit_breaker)' }
      }
    }
  },
  {
    name: 'train_agent_reinforcement_epoch',
    description: 'Triggers a self-improvement training epoch on historical trade logs in SQLite. Updates the 60 feature weights vector, policy loss, and advances model generation (e.g. Gen-1 -> Gen-2).',
    inputSchema: {
      type: 'object',
      properties: {
        notes: { type: 'string', description: 'Optional description or trigger reason for this training epoch' }
      }
    }
  },
  {
    name: 'get_agent_lineage_and_evolution',
    description: 'Returns the complete lineage, training epochs history, cumulative reward progression, 60-feature learned weights, and adaptive LLM prompt guidelines.',
    inputSchema: {
      type: 'object',
      properties: {}
    }
  },
  {
    name: 'evaluate_market_60_features_decision',
    description: 'Calculates the multi-factor weighted consensus score across all 60 capabilities using the agent’s learned weights and provides a BUY / SELL / HOLD action recommendation with risk bounds.',
    inputSchema: {
      type: 'object',
      properties: {
        symbol: { type: 'string', default: 'BTC/USDT' },
        price: { type: 'number', default: 65200 }
      }
    }
  },
  {
    name: 'export_mcp_configuration',
    description: 'Generates the Claude Desktop / Cursor / external MCP configuration JSON for connecting to this server.',
    inputSchema: {
      type: 'object',
      properties: {}
    }
  }
];

// Resources registry
export const MCP_RESOURCES = [
  {
    uri: 'mcp://trading/database/trades',
    name: 'Persistent SQLite Trades',
    description: 'Real-time feed of recorded trades from data/trading.db',
    mimeType: 'application/json'
  },
  {
    uri: 'mcp://trading/database/60_features',
    name: '60 Capability Execution Records',
    description: 'Latest analytical outputs, recommendations, and status of all 60 features',
    mimeType: 'application/json'
  },
  {
    uri: 'mcp://trading/agent/evolution',
    name: 'Agent & LLM Lineage Data',
    description: 'Epoch history, reward curves, and feature weight progression',
    mimeType: 'application/json'
  },
  {
    uri: 'mcp://trading/system/status',
    name: 'Trading System Health & Stats',
    description: 'SQLite database record counts and service status',
    mimeType: 'application/json'
  }
];

// Prompts registry
export const MCP_PROMPTS = [
  {
    name: 'quant_market_analysis',
    description: 'Analyzes market conditions using the consensus of all 60 trading system capabilities.',
    arguments: [
      { name: 'symbol', description: 'Market symbol', required: true },
      { name: 'horizon', description: 'Trading horizon (e.g. 1h, 4h, 1d)', required: false }
    ]
  },
  {
    name: 'agent_self_reflection_and_learning',
    description: 'Prompts LLM to review recent closed trades from SQLite and formulate updated rules for the self-improving agent.',
    arguments: [
      { name: 'min_trades', description: 'Minimum number of recent trades to inspect', required: false }
    ]
  }
];

// Tool call handler
export async function handleToolCall(name, args = {}) {
  switch (name) {
    case 'execute_60_capabilities':
    case 'evaluate_market_60_features_decision': {
      const symbol = args.symbol || 'BTC/USDT';
      const price = Number(args.price) || 65200;
      const result = await evaluateMarketWith60Features(symbol, price);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2)
          }
        ]
      };
    }

    case 'get_database_trades': {
      const limit = Math.min(100, Math.max(1, Number(args.limit) || 20));
      const table = args.table === 'orders' ? 'orders' : 'closed_trades';
      const records = table === 'orders' ? getOrders(limit) : getClosedTrades(limit);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ table, count: records.length, records }, null, 2)
          }
        ]
      };
    }

    case 'get_60_feature_analyses': {
      const limit = Math.min(200, Math.max(1, Number(args.limit) || 60));
      const records = getCapabilityExecutions(limit, args.capability_id || null);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ count: records.length, records }, null, 2)
          }
        ]
      };
    }

    case 'train_agent_reinforcement_epoch': {
      const trainResult = agentLearner.trainNextGeneration({ notes: args.notes || 'MCP Triggered Training Epoch' });
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(trainResult, null, 2)
          }
        ]
      };
    }

    case 'get_agent_lineage_and_evolution': {
      const status = agentLearner.getStatus();
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(status, null, 2)
          }
        ]
      };
    }

    case 'export_mcp_configuration': {
      const config = generateMcpClientConfig();
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(config, null, 2)
          }
        ]
      };
    }

    default:
      throw new Error(`Unknown MCP tool: ${name}`);
  }
}

// Resource read handler
export async function handleResourceRead(uri) {
  switch (uri) {
    case 'mcp://trading/database/trades': {
      const trades = getClosedTrades(50);
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(trades, null, 2)
          }
        ]
      };
    }

    case 'mcp://trading/database/60_features': {
      const executions = getCapabilityExecutions(60);
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(executions, null, 2)
          }
        ]
      };
    }

    case 'mcp://trading/agent/evolution': {
      const history = getTrainingEpochs(20);
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(history, null, 2)
          }
        ]
      };
    }

    case 'mcp://trading/system/status': {
      const stats = getDatabaseStats();
      const agentStatus = agentLearner.getStatus();
      return {
        contents: [
          {
            uri,
            mimeType: 'application/json',
            text: JSON.stringify({ db_stats: stats, agent_status: agentStatus }, null, 2)
          }
        ]
      };
    }

    default:
      throw new Error(`Unknown resource URI: ${uri}`);
  }
}

// Helper to generate ready-to-use client config
export function generateMcpClientConfig() {
  return {
    mcpServers: {
      "crypto-trading-agent": {
        url: "http://localhost:3000/api/mcp",
        transport: "http-jsonrpc",
        description: "Adaptive Crypto Agent with 60 Features & SQLite Persistence"
      }
    }
  };
}

// Write mcp_server.json to project root for standard discovery
export function writeMcpConfigFile() {
  try {
    const configPath = path.join(__dirname, 'mcp_server.json');
    const content = JSON.stringify({
      ...MCP_SERVER_INFO,
      tools: MCP_TOOLS,
      resources: MCP_RESOURCES,
      prompts: MCP_PROMPTS,
      clientConfiguration: generateMcpClientConfig()
    }, null, 2);
    fs.writeFileSync(configPath, content, 'utf8');
  } catch (err) {
    console.warn('Could not write mcp_server.json file:', err.message);
  }
}

writeMcpConfigFile();

// GET /api/mcp - Discovery & status endpoint
mcpRouter.get(['/', '/info'], (req, res) => {
  res.json({
    success: true,
    server: MCP_SERVER_INFO,
    tools: MCP_TOOLS,
    resources: MCP_RESOURCES,
    prompts: MCP_PROMPTS,
    database_stats: getDatabaseStats(),
    agent_status: {
      generation: agentLearner.generationId,
      epochs: agentLearner.epochCount,
      cumulative_reward: agentLearner.cumulativeReward
    },
    client_config: generateMcpClientConfig()
  });
});

// POST /api/mcp - Official JSON-RPC 2.0 MCP Endpoint
mcpRouter.post('/', async (req, res) => {
  const { jsonrpc, id, method, params } = req.body || {};

  if (jsonrpc !== '2.0') {
    return res.status(400).json({
      jsonrpc: '2.0',
      id: id || null,
      error: { code: -32600, message: 'Invalid Request: jsonrpc version must be 2.0' }
    });
  }

  try {
    switch (method) {
      case 'initialize': {
        return res.json({
          jsonrpc: '2.0',
          id,
          result: {
            protocolVersion: MCP_SERVER_INFO.protocolVersion,
            capabilities: MCP_SERVER_INFO.capabilities,
            serverInfo: {
              name: MCP_SERVER_INFO.name,
              version: MCP_SERVER_INFO.version
            }
          }
        });
      }

      case 'notifications/initialized': {
        return res.json({ jsonrpc: '2.0', id, result: {} });
      }

      case 'tools/list': {
        return res.json({
          jsonrpc: '2.0',
          id,
          result: {
            tools: MCP_TOOLS
          }
        });
      }

      case 'tools/call': {
        const { name, arguments: toolArgs } = params || {};
        if (!name) {
          return res.status(400).json({
            jsonrpc: '2.0',
            id,
            error: { code: -32602, message: 'Missing tool name parameter' }
          });
        }
        const toolResult = await handleToolCall(name, toolArgs);
        return res.json({
          jsonrpc: '2.0',
          id,
          result: toolResult
        });
      }

      case 'resources/list': {
        return res.json({
          jsonrpc: '2.0',
          id,
          result: {
            resources: MCP_RESOURCES
          }
        });
      }

      case 'resources/read': {
        const { uri } = params || {};
        if (!uri) {
          return res.status(400).json({
            jsonrpc: '2.0',
            id,
            error: { code: -32602, message: 'Missing resource URI' }
          });
        }
        const resourceResult = await handleResourceRead(uri);
        return res.json({
          jsonrpc: '2.0',
          id,
          result: resourceResult
        });
      }

      case 'prompts/list': {
        return res.json({
          jsonrpc: '2.0',
          id,
          result: {
            prompts: MCP_PROMPTS
          }
        });
      }

      case 'prompts/get': {
        const { name, arguments: promptArgs } = params || {};
        const matched = MCP_PROMPTS.find(p => p.name === name);
        if (!matched) {
          return res.status(404).json({
            jsonrpc: '2.0',
            id,
            error: { code: -32602, message: `Prompt not found: ${name}` }
          });
        }
        return res.json({
          jsonrpc: '2.0',
          id,
          result: {
            description: matched.description,
            messages: [
              {
                role: 'user',
                content: {
                  type: 'text',
                  text: `تحلیل کمی بازار کریپتو بر اساس اجماع ۶۰ قابلیت سامانه برای نماد ${promptArgs?.symbol || 'BTC/USDT'}`
                }
              }
            ]
          }
        });
      }

      default: {
        return res.status(404).json({
          jsonrpc: '2.0',
          id,
          error: { code: -32601, message: `Method not found: ${method}` }
        });
      }
    }
  } catch (err) {
    return res.status(500).json({
      jsonrpc: '2.0',
      id,
      error: { code: -32000, message: err.message }
    });
  }
});
