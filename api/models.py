"""
API Models - Pydantic models for request/response validation.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


# --- Base ---
class TimestampedModel(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)


class ResponseModel(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# --- Health ---
class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    status: HealthStatus
    version: str
    uptime_seconds: float
    components: Dict[str, bool]
    timestamp: datetime


# --- Status ---
class SystemStatusResponse(BaseModel):
    mode: str  # PAPER, SHADOW, LIVE
    trading_allowed: bool
    kill_switch_active: bool
    circuit_breaker_state: str
    reconciliation_state: str
    last_update: datetime
    daily_pnl: float
    current_drawdown: float
    exposure_ratio: float
    active_positions: int
    open_orders: int


# --- Portfolio ---
class PositionResponse(BaseModel):
    symbol: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    value: float
    weight: float


class PortfolioResponse(BaseModel):
    total_equity: float
    cash: float
    positions_value: float
    positions: List[PositionResponse]
    weights: Dict[str, float]
    timestamp: datetime


# --- Orders ---
class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    order_type: OrderType
    amount: float = Field(gt=0)
    price: Optional[float] = Field(None, gt=0)


class OrderResponse(BaseModel):
    id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    amount: float
    filled_amount: float
    status: OrderStatus
    fee: float
    fee_currency: str
    created_at: datetime
    updated_at: datetime


# --- Risk ---
class RiskLimitsResponse(BaseModel):
    max_daily_loss: float
    max_total_drawdown: float
    max_position_size: float
    max_exposure: float
    current_drawdown: float
    current_exposure: float
    daily_pnl: float
    is_halted: bool
    halt_reason: Optional[str]


# --- System Control ---
class SystemControlRequest(BaseModel):
    reason: str


class SystemControlResponse(BaseModel):
    success: bool
    action: str
    message: str
    timestamp: datetime


# --- Metrics ---
class PerformanceMetricsResponse(BaseModel):
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_fees: float
    total_slippage: float
    turnover: float
    num_trades: int
    period_start: datetime
    period_end: datetime


class DailySnapshotResponse(BaseModel):
    date: str
    equity: float
    positions_value: float
    cash: float
    drawdown: float
    exposure: float
