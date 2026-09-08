"""
Capabilities Routes - Track and analyze all system capabilities with LLM integration.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import logging
import os

from ..models import ResponseModel
from observability.logger import LoggerFactory
from ai_sentiment import AISentimentAnalyzer

logger = logging.getLogger(__name__)
capabilities_logger = LoggerFactory.get_logger('capabilities', 'capabilities', 'INFO')

router = APIRouter(prefix="/capabilities", tags=["Capabilities"])

# Capability categories based on user requirements
CAPABILITY_CATEGORIES = {
    "core_trading": [
        "algorithmic_crypto_trading",
        "multi_exchange_support",
        "market_data_fetching",
        "multi_timeframe_analysis",
        "technical_strategies",
        "market_regime_detection",
        "ensemble_strategies",
        "portfolio_optimization"
    ],
    "risk_management": [
        "risk_management",
        "position_sizing",
        "stop_loss_take_profit",
        "trailing_stop",
        "breakeven_stop",
        "partial_take_profit",
        "max_positions_exposure",
        "circuit_breaker",
        "kill_switch",
        "live_safety_engine"
    ],
    "order_management": [
        "order_manager",
        "idempotency",
        "fill_manager",
        "position_manager",
        "exchange_reconciliation",
        "crash_recovery",
        "persistence_database"
    ],
    "backtesting_quant": [
        "walk_forward_backtesting",
        "out_of_sample_testing",
        "transaction_cost_modeling",
        "slippage_modeling",
        "no_trade_zone",
        "benchmarking",
        "ensemble_backtesting",
        "performance_metrics",
        "regime_based_analysis",
        "monte_carlo_robustness"
    ],
    "ai_ml": [
        "ml_pipeline",
        "feature_engineering",
        "causal_feature_engineering",
        "purged_walk_forward_validation",
        "ml_prediction",
        "model_registry",
        "model_versioning",
        "model_drift_monitoring",
        "ml_strategy_integration"
    ],
    "ai_sentiment": [
        "sentiment_analysis",
        "news_context_analysis",
        "llm_integration",
        "sentiment_as_signal"
    ],
    "infrastructure": [
        "fastapi",
        "trading_api",
        "health_status_monitoring",
        "logging",
        "observability",
        "configuration_management",
        "sqlite_postgresql",
        "docker_deployment",
        "ci_cd_support",
        "paper_trading",
        "shadow_trading",
        "live_trading_architecture"
    ]
}

# Flatten all capabilities
ALL_CAPABILITIES = []
for caps in CAPABILITY_CATEGORIES.values():
    ALL_CAPABILITIES.extend(caps)


class CapabilityLog(BaseModel):
    """Log entry for a capability."""
    capability: str
    category: str
    status: str = "executing"  # executing, success, warning, error
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMAnalysisRequest(BaseModel):
    """Request for LLM analysis of a log entry."""
    capability: str
    log_message: str
    log_data: Optional[Dict[str, Any]] = None
    context: Optional[str] = None


class LLMAnalysisResponse(BaseModel):
    """Response from LLM analysis."""
    capability: str
    analysis: str
    recommendation: str
    confidence: float
    risk_level: str  # low, medium, high, critical
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CapabilityStatus(BaseModel):
    """Status of a capability."""
    capability: str
    category: str
    last_log_time: Optional[datetime] = None
    total_logs: int = 0
    success_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    status: str = "unknown"  # healthy, degraded, failing


class CapabilitiesDashboardResponse(BaseModel):
    """Dashboard response showing all capabilities."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_capabilities: int = len(ALL_CAPABILITIES)
    categories: Dict[str, List[CapabilityStatus]]
    summary: Dict[str, int]


# In-memory storage for capability logs (in production, use database)
_capability_logs: Dict[str, List[CapabilityLog]] = {cap: [] for cap in ALL_CAPABILITIES}
_llm_analyses: Dict[str, LLMAnalysisResponse] = {}

# Initialize LLM analyzer
_llm_analyzer = None


def get_llm_analyzer() -> Optional[AISentimentAnalyzer]:
    """Get or create LLM analyzer instance."""
    global _llm_analyzer
    if _llm_analyzer is None:
        try:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                _llm_analyzer = AISentimentAnalyzer(api_key=api_key)
                logger.info("LLM analyzer initialized with Groq API")
            else:
                logger.warning("GROQ_API_KEY not set, LLM analysis will use mock mode")
                _llm_analyzer = AISentimentAnalyzer(api_key=None)
        except Exception as e:
            logger.error(f"Failed to initialize LLM analyzer: {e}")
            _llm_analyzer = None
    return _llm_analyzer


def _get_category_for_capability(capability: str) -> str:
    """Get the category for a capability."""
    for category, caps in CAPABILITY_CATEGORIES.items():
        if capability in caps:
            return category
    return "unknown"


async def _analyze_with_llm(capability: str, log_message: str, log_data: Optional[Dict] = None) -> LLMAnalysisResponse:
    """Analyze a log entry using LLM."""
    analyzer = get_llm_analyzer()
    
    # Build context for analysis
    context = f"""
    Capability: {capability}
    Category: {_get_category_for_capability(capability)}
    Log Message: {log_message}
    Log Data: {log_data if log_data else 'None'}
    Timestamp: {datetime.now(timezone.utc).isoformat()}
    
    Analyze this trading system capability log and provide:
    1. A brief analysis of what this indicates about system health/performance
    2. A recommendation for any action needed
    3. A confidence score (0-1) in your analysis
    4. A risk level assessment (low, medium, high, critical)
    
    Respond in JSON format with keys: analysis, recommendation, confidence, risk_level
    """
    
    # Try LLM analysis
    if analyzer and analyzer.client:
        try:
            prompt = f"""You are a trading system analyst. Analyze the following capability log:
            
            {context}
            
            Provide your response as a JSON object with this EXACT structure:
            {{
                "analysis": "<brief analysis>",
                "recommendation": "<action recommendation>",
                "confidence": <float between 0 and 1>,
                "risk_level": "<low|medium|high|critical>"
            }}
            
            Output ONLY valid JSON, no markdown, no explanations."""
            
            response = analyzer._call_llm(prompt)
            if response:
                parsed = analyzer._parse_llm_response(response)
                if parsed and 'analysis' in parsed and 'risk_level' in parsed:
                    result = LLMAnalysisResponse(
                        capability=capability,
                        analysis=parsed.get('analysis', 'Analysis unavailable'),
                        recommendation=parsed.get('recommendation', 'No specific recommendation'),
                        confidence=float(parsed.get('confidence', 0.5)),
                        risk_level=parsed.get('risk_level', 'medium')
                    )
                    _llm_analyses[f"{capability}_{datetime.now(timezone.utc).isoformat()}"] = result
                    return result
        except Exception as e:
            logger.warning(f"LLM analysis failed for {capability}: {e}")
    
    # Fallback rule-based analysis
    risk_level = "low"
    if "error" in log_message.lower() or "fail" in log_message.lower():
        risk_level = "high"
    elif "warning" in log_message.lower() or "warn" in log_message.lower():
        risk_level = "medium"
    
    return LLMAnalysisResponse(
        capability=capability,
        analysis=f"Rule-based analysis: Log indicates {'potential issue' if risk_level != 'low' else 'normal operation'} for {capability}",
        recommendation="Monitor closely" if risk_level != "low" else "Continue normal operations",
        confidence=0.6,
        risk_level=risk_level
    )


@router.post("/log", response_model=ResponseModel)
async def log_capability_event(log_entry: CapabilityLog, background_tasks: BackgroundTasks):
    """
    Log an event for a capability and trigger LLM analysis.
    
    This endpoint should be called whenever a capability executes.
    It logs the event and asynchronously analyzes it with LLM.
    """
    if log_entry.capability not in ALL_CAPABILITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown capability: {log_entry.capability}. Valid capabilities: {ALL_CAPABILITIES[:5]}..."
        )
    
    # Store log
    _capability_logs[log_entry.capability].append(log_entry)
    
    # Log to structured logger (avoid 'message' key conflict with LogRecord)
    capabilities_logger.info(f"Capability Event: {log_entry.capability} - {log_entry.message}", extra={
        "category": log_entry.category,
        "status": log_entry.status,
        "capability_data": log_entry.data
    })
    
    # Trigger async LLM analysis
    background_tasks.add_task(_analyze_with_llm, log_entry.capability, log_entry.message, log_entry.data)
    
    return ResponseModel(
        success=True,
        message=f"Logged event for capability: {log_entry.capability}",
        data={"log_id": len(_capability_logs[log_entry.capability]) - 1}
    )


@router.get("/{capability}/logs", response_model=List[CapabilityLog])
async def get_capability_logs(capability: str, limit: int = 50):
    """Get recent logs for a specific capability."""
    if capability not in ALL_CAPABILITIES:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability}")
    
    logs = _capability_logs[capability][-limit:]
    return logs


@router.get("/{capability}/analysis", response_model=Optional[LLMAnalysisResponse])
async def get_latest_analysis(capability: str):
    """Get the latest LLM analysis for a capability."""
    # Find most recent analysis for this capability
    matching_analyses = [
        (k, v) for k, v in _llm_analyses.items() 
        if k.startswith(capability)
    ]
    
    if not matching_analyses:
        return None
    
    # Return most recent
    latest = max(matching_analyses, key=lambda x: x[0])
    return latest[1]


@router.post("/{capability}/analyze", response_model=LLMAnalysisResponse)
async def analyze_capability(capability: str, request: LLMAnalysisRequest):
    """Manually trigger LLM analysis for a capability."""
    if capability not in ALL_CAPABILITIES:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability}")
    
    return await _analyze_with_llm(capability, request.log_message, request.log_data)


@router.get("/dashboard", response_model=CapabilitiesDashboardResponse)
async def get_capabilities_dashboard():
    """
    Get dashboard showing status of all capabilities.
    
    This is the main UI endpoint for monitoring all system capabilities.
    """
    categories_status = {}
    summary = {"healthy": 0, "degraded": 0, "failing": 0, "unknown": 0}
    
    for category, caps in CAPABILITY_CATEGORIES.items():
        cat_statuses = []
        for cap in caps:
            logs = _capability_logs[cap]
            
            # Calculate statistics
            total = len(logs)
            success = sum(1 for l in logs if l.status == "success")
            warnings = sum(1 for l in logs if l.status == "warning")
            errors = sum(1 for l in logs if l.status == "error")
            
            # Determine overall status
            if total == 0:
                status = "unknown"
            elif errors > 0:
                status = "failing"
            elif warnings > total * 0.3:  # More than 30% warnings
                status = "degraded"
            else:
                status = "healthy"
            
            summary[status] += 1
            
            cat_statuses.append(CapabilityStatus(
                capability=cap,
                category=category,
                last_log_time=logs[-1].timestamp if logs else None,
                total_logs=total,
                success_count=success,
                warning_count=warnings,
                error_count=errors,
                status=status
            ))
        
        categories_status[category] = cat_statuses
    
    return CapabilitiesDashboardResponse(
        categories=categories_status,
        summary=summary
    )


@router.get("/list")
async def list_capabilities():
    """List all tracked capabilities organized by category."""
    return {
        "categories": CAPABILITY_CATEGORIES,
        "total_count": len(ALL_CAPABILITIES)
    }


@router.get("/stats")
async def get_statistics():
    """Get overall statistics about capability tracking."""
    total_logs = sum(len(logs) for logs in _capability_logs.values())
    total_analyses = len(_llm_analyses)
    
    logs_by_status = {"executing": 0, "success": 0, "warning": 0, "error": 0}
    for logs in _capability_logs.values():
        for log in logs:
            logs_by_status[log.status] = logs_by_status.get(log.status, 0) + 1
    
    return {
        "total_capabilities_tracked": len(ALL_CAPABILITIES),
        "total_logs": total_logs,
        "total_llm_analyses": total_analyses,
        "logs_by_status": logs_by_status,
        "categories_count": len(CAPABILITY_CATEGORIES)
    }
