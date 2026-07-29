"""
Flask Web Server for Crypto Portfolio Optimization System
==========================================================
This module converts the main trading pipeline into a web server that:
1. Stays running continuously on Railway
2. Exposes endpoints for health checks and running the trading pipeline
3. Implements sleep mode to stay within free tier limits
4. Responds to UptimeRobot monitors

Endpoints:
- GET /health : Health check endpoint (returns 200 OK)
- POST /run   : Run the full trading pipeline
- GET  /status: Get current system status
- POST /wake  : Wake up from sleep mode

Usage:
    python app.py
    
Environment Variables:
    PORT          : Port to run on (default: 8000)
    GROQ_API_KEY  : Optional, for real sentiment analysis
    SLEEP_MODE    : Set to "true" to enable sleep mode (default: false)
"""

import os
import logging
import sys
import json
import threading
import time
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
from flask import Flask, jsonify, request

# Import the main system components
from main import CryptoPortfolioSystem, print_final_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('portfolio_backtest.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global state
system_state = {
    'status': 'idle',
    'last_run': None,
    'last_result': None,
    'is_running': False,
    'start_time': datetime.now().isoformat(),
    'total_runs': 0,
    'successful_runs': 0,
    'failed_runs': 0,
}

# Thread lock for preventing concurrent runs
run_lock = threading.Lock()


def get_sleep_mode_enabled() -> bool:
    """Check if sleep mode is enabled via environment variable."""
    return os.getenv('SLEEP_MODE', 'false').lower() == 'true'


def should_allow_request() -> bool:
    """
    In sleep mode, only allow health checks and wake calls.
    Block expensive operations unless explicitly woken up.
    """
    if not get_sleep_mode_enabled():
        return True
    
    # In sleep mode, allow requests only if recently woken up
    last_wake = system_state.get('last_wake_time')
    if last_wake:
        wake_dt = datetime.fromisoformat(last_wake)
        # Allow operations for 1 hour after wake
        if (datetime.now() - wake_dt).total_seconds() < 3600:
            return True
    
    return False


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for Railway and UptimeRobot.
    Returns 200 OK with basic status information.
    """
    logger.info("Health check requested")
    
    response_data = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'uptime_since': system_state['start_time'],
        'sleep_mode': get_sleep_mode_enabled(),
        'version': '2.0'
    }
    
    return jsonify(response_data), 200


@app.route('/wake', methods=['POST'])
def wake_up():
    """
    Wake up the system from sleep mode.
    This allows expensive operations for a limited time window.
    """
    logger.info("Wake-up signal received")
    
    system_state['last_wake_time'] = datetime.now().isoformat()
    system_state['status'] = 'awake'
    
    response_data = {
        'status': 'awake',
        'message': 'System awakened. Operations allowed for 1 hour.',
        'wake_time': system_state['last_wake_time'],
        'expires_at': (datetime.now().replace(hour=datetime.now().hour) + 
                      pd.Timedelta(hours=1)).isoformat()
    }
    
    return jsonify(response_data), 200


@app.route('/status', methods=['GET'])
def get_status():
    """
    Get current system status and statistics.
    """
    logger.info("Status requested")
    
    # Calculate uptime
    start_dt = datetime.fromisoformat(system_state['start_time'])
    uptime_seconds = (datetime.now() - start_dt).total_seconds()
    uptime_hours = uptime_seconds / 3600
    
    response_data = {
        'status': system_state['status'],
        'is_running': system_state['is_running'],
        'last_run': system_state['last_run'],
        'total_runs': system_state['total_runs'],
        'successful_runs': system_state['successful_runs'],
        'failed_runs': system_state['failed_runs'],
        'success_rate': (system_state['successful_runs'] / system_state['total_runs'] * 100 
                        if system_state['total_runs'] > 0 else 0),
        'uptime_hours': round(uptime_hours, 2),
        'sleep_mode': get_sleep_mode_enabled(),
        'last_wake_time': system_state.get('last_wake_time'),
    }
    
    return jsonify(response_data), 200


@app.route('/run', methods=['POST'])
def run_pipeline():
    """
    Run the full crypto portfolio optimization pipeline.
    
    Expected JSON payload (optional):
    {
        "since_days": 365,
        "n_folds": 1,
        "use_auto_selection": true,
        "symbols": ["BTC/USDT", "ETH/USDT", ...]
    }
    """
    logger.info("=" * 60)
    logger.info("Pipeline execution requested via /run endpoint")
    logger.info("=" * 60)
    
    # Check if we should allow this request
    if get_sleep_mode_enabled() and not should_allow_request():
        logger.warning("Request blocked: system in sleep mode. Send POST /wake first.")
        return jsonify({
            'error': 'System in sleep mode',
            'message': 'Send POST /wake to activate the system for 1 hour',
            'status': 'sleeping'
        }), 503
    
    # Check if already running
    if system_state['is_running']:
        logger.warning("Pipeline already running, rejecting concurrent request")
        return jsonify({
            'error': 'Pipeline already running',
            'status': 'busy'
        }), 409
    
    # Acquire lock
    with run_lock:
        system_state['is_running'] = True
        system_state['status'] = 'running'
        start_time = datetime.now()
        
        try:
            # Parse request parameters
            data = request.get_json(silent=True) or {}
            since_days = data.get('since_days', 365)
            n_folds = data.get('n_folds', 1)
            use_auto_selection = data.get('use_auto_selection', True)
            symbols = data.get('symbols', ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'])
            
            logger.info(f"Running pipeline with: since_days={since_days}, n_folds={n_folds}, "
                       f"symbols={len(symbols)} assets")
            
            # Initialize and run the system
            system = CryptoPortfolioSystem(
                symbols=symbols,
                initial_capital=100000,
            )
            
            results = system.run_full_pipeline(
                since_days=since_days,
                n_folds=n_folds,
                use_auto_selection=use_auto_selection
            )
            
            # Process evaluation results
            evaluation = results.get('evaluation', {})
            if evaluation:
                summary = {
                    'mean_monthly_return': evaluation.get('mean_monthly_return', 0),
                    'median_monthly_return': evaluation.get('median_monthly_return', 0),
                    'worst_monthly_return': evaluation.get('worst_monthly_return', 0),
                    'pct_months_positive': evaluation.get('pct_months_positive', 0),
                    'worst_max_drawdown': evaluation.get('worst_max_drawdown', 0),
                    'mean_sharpe': evaluation.get('mean_sharpe', 0),
                    'target_achieved_on_average': evaluation.get('target_achieved_on_average', False),
                    'target_achieved_every_month': evaluation.get('target_achieved_every_month', False),
                    'drawdown_within_limit': evaluation.get('drawdown_within_limit', False),
                    'n_calendar_months_observed': evaluation.get('n_calendar_months_observed', 0),
                }
            else:
                summary = {'error': 'No evaluation results'}
            
            # Update state
            end_time = datetime.now()
            duration_seconds = (end_time - start_time).total_seconds()
            
            system_state['last_run'] = end_time.isoformat()
            system_state['last_result'] = summary
            system_state['total_runs'] += 1
            system_state['successful_runs'] += 1
            system_state['status'] = 'completed'
            
            logger.info(f"Pipeline completed successfully in {duration_seconds:.2f} seconds")
            
            response_data = {
                'status': 'success',
                'message': 'Pipeline executed successfully',
                'duration_seconds': round(duration_seconds, 2),
                'timestamp': end_time.isoformat(),
                'results': summary,
                'data_points': len(results.get('prices', [])),
                'warning': evaluation.get('n_calendar_months_observed', 0) < 6
            }
            
            return jsonify(response_data), 200
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            
            # Update state
            end_time = datetime.now()
            duration_seconds = (end_time - start_time).total_seconds()
            
            system_state['total_runs'] += 1
            system_state['failed_runs'] += 1
            system_state['status'] = 'failed'
            
            response_data = {
                'status': 'error',
                'message': str(e),
                'duration_seconds': round(duration_seconds, 2),
                'timestamp': end_time.isoformat(),
                'error_type': type(e).__name__
            }
            
            return jsonify(response_data), 500
            
        finally:
            system_state['is_running'] = False


@app.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Get detailed metrics about system performance.
    Useful for monitoring dashboards.
    """
    logger.info("Metrics requested")
    
    start_dt = datetime.fromisoformat(system_state['start_time'])
    uptime_seconds = (datetime.now() - start_dt).total_seconds()
    
    metrics = {
        'uptime': {
            'seconds': int(uptime_seconds),
            'hours': round(uptime_seconds / 3600, 2),
            'days': round(uptime_seconds / 86400, 2)
        },
        'runs': {
            'total': system_state['total_runs'],
            'successful': system_state['successful_runs'],
            'failed': system_state['failed_runs'],
            'success_rate': round(system_state['successful_runs'] / max(system_state['total_runs'], 1) * 100, 2)
        },
        'current_status': {
            'is_running': system_state['is_running'],
            'status': system_state['status'],
            'last_run': system_state['last_run']
        },
        'configuration': {
            'sleep_mode': get_sleep_mode_enabled(),
            'last_wake_time': system_state.get('last_wake_time')
        }
    }
    
    return jsonify(metrics), 200


@app.route('/', methods=['GET'])
def index():
    """
    Root endpoint with API documentation.
    """
    docs = {
        'name': 'Crypto Portfolio Optimization API',
        'version': '2.0',
        'description': 'Automated crypto portfolio optimization with AI sentiment analysis',
        'endpoints': {
            'GET /': 'This documentation',
            'GET /health': 'Health check for UptimeBot/Railway',
            'POST /wake': 'Wake up from sleep mode (enables operations for 1 hour)',
            'GET /status': 'Get current system status',
            'POST /run': 'Run the trading pipeline',
            'GET /metrics': 'Get detailed system metrics'
        },
        'example_usage': {
            'health_check': 'curl https://your-app.railway.app/health',
            'wake_up': 'curl -X POST https://your-app.railway.app/wake',
            'run_pipeline': 'curl -X POST -H "Content-Type: application/json" -d \'{"since_days": 365, "n_folds": 1}\' https://your-app.railway.app/run',
            'get_status': 'curl https://your-app.railway.app/status'
        },
        'current_status': {
            'uptime_since': system_state['start_time'],
            'total_runs': system_state['total_runs'],
            'sleep_mode': get_sleep_mode_enabled()
        }
    }
    
    return jsonify(docs), 200


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405


def main():
    """
    Main entry point for the Flask application.
    """
    # Get port from environment variable (Railway sets this automatically)
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info("=" * 60)
    logger.info("Starting Crypto Portfolio Optimization Web Server")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Sleep mode: {get_sleep_mode_enabled()}")
    logger.info("=" * 60)
    
    # Run the Flask app
    # Note: In production, use gunicorn instead of Flask's built-in server
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()
