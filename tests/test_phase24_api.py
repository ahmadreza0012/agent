"""
Unit tests for Phase 24 API.
"""

import sys
sys.path.insert(0, '/workspace')

import unittest
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


class TestHealthRoutes(unittest.TestCase):
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('components', data)
        self.assertEqual(data['status'], 'healthy')
    
    def test_liveness(self):
        """Test liveness probe."""
        response = client.get("/api/v1/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'alive')
    
    def test_readiness(self):
        """Test readiness probe."""
        response = client.get("/api/v1/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ready')


class TestStatusRoutes(unittest.TestCase):
    
    def test_get_status(self):
        """Test get system status."""
        response = client.get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('mode', data)
        self.assertIn('trading_allowed', data)
        self.assertEqual(data['mode'], 'paper')


class TestPortfolioRoutes(unittest.TestCase):
    
    def test_get_portfolio(self):
        """Test get portfolio."""
        response = client.get("/api/v1/portfolio")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_equity', data)
        self.assertIn('cash', data)
        self.assertIn('positions', data)
    
    def test_get_positions(self):
        """Test get positions."""
        response = client.get("/api/v1/portfolio/positions")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
    
    def test_get_portfolio_history(self):
        """Test get portfolio history."""
        response = client.get("/api/v1/portfolio/history?days=7")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('days', data)
        self.assertEqual(data['days'], 7)


class TestOrderRoutes(unittest.TestCase):
    
    def test_create_order(self):
        """Test creating an order (requires auth)."""
        order_data = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "order_type": "market",
            "amount": 0.1
        }
        # Without API key - should fail
        response = client.post("/api/v1/orders", json=order_data)
        self.assertEqual(response.status_code, 401)
        
        # With API key - should succeed (mock)
        response = client.post(
            "/api/v1/orders",
            json=order_data,
            headers={"X-API-Key": "test-key"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('id', data)
        self.assertEqual(data['symbol'], 'BTC/USDT')
    
    def test_get_orders(self):
        """Test get orders."""
        response = client.get("/api/v1/orders")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
    
    def test_get_order_not_found(self):
        """Test get order not found."""
        response = client.get("/api/v1/orders/nonexistent")
        self.assertEqual(response.status_code, 404)


class TestRiskRoutes(unittest.TestCase):
    
    def test_get_risk_limits(self):
        """Test get risk limits."""
        response = client.get("/api/v1/risk/limits")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('max_daily_loss', data)
        self.assertIn('max_total_drawdown', data)
        self.assertIn('is_halted', data)
    
    def test_reset_daily_limits(self):
        """Test reset daily limits (requires auth)."""
        response = client.post("/api/v1/risk/reset-daily")
        self.assertEqual(response.status_code, 401)
        
        response = client.post(
            "/api/v1/risk/reset-daily",
            headers={"X-API-Key": "test-key"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
    
    def test_get_risk_events(self):
        """Test get risk events."""
        response = client.get("/api/v1/risk/events")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('events', data)
        self.assertIn('count', data)


class TestSystemRoutes(unittest.TestCase):
    
    def test_get_config(self):
        """Test get system config."""
        response = client.get("/api/v1/system/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('mode', data)
        self.assertIn('version', data)
        self.assertEqual(data['version'], '2.0.0')
    
    def test_pause_system(self):
        """Test pause system (requires auth)."""
        response = client.post(
            "/api/v1/system/pause",
            json={"reason": "Testing"},
            headers={"X-API-Key": "test-key"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'pause')
    
    def test_resume_system(self):
        """Test resume system (requires auth)."""
        response = client.post(
            "/api/v1/system/resume",
            json={"reason": "Testing"},
            headers={"X-API-Key": "test-key"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'resume')
    
    def test_halt_system(self):
        """Test halt system (requires auth)."""
        response = client.post(
            "/api/v1/system/halt",
            json={"reason": "Testing"},
            headers={"X-API-Key": "test-key"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'halt')
    
    def test_emergency_kill(self):
        """Test emergency kill (requires auth)."""
        response = client.post(
            "/api/v1/system/kill",
            json={"reason": "Testing"},
            headers={"X-API-Key": "test-key"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['action'], 'kill')
    
    def test_rebalance(self):
        """Test trigger rebalance (requires auth)."""
        response = client.post(
            "/api/v1/system/rebalance",
            json={"reason": "Testing"},
            headers={"X-API-Key": "test-key"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])


class TestMetricsRoutes(unittest.TestCase):
    
    def test_get_performance_metrics(self):
        """Test get performance metrics."""
        response = client.get("/api/v1/metrics/performance?days=30")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_return', data)
        self.assertIn('sharpe_ratio', data)
        self.assertIn('num_trades', data)
    
    def test_get_daily_snapshots(self):
        """Test get daily snapshots."""
        response = client.get("/api/v1/metrics/daily?days=7")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)


class TestMiddleware(unittest.TestCase):
    
    def test_rate_limit(self):
        """Test rate limiting doesn't block normal usage."""
        # Make several requests in quick succession
        for _ in range(10):
            response = client.get("/api/v1/health")
            self.assertEqual(response.status_code, 200)
    
    def test_auth_required_for_writes(self):
        """Test authentication required for write operations."""
        # POST without API key should fail
        response = client.post("/api/v1/system/pause", json={"reason": "test"})
        self.assertEqual(response.status_code, 401)
        
        # DELETE without API key should fail
        response = client.delete("/api/v1/orders/test-order")
        self.assertEqual(response.status_code, 401)
    
    def test_auth_not_required_for_reads(self):
        """Test authentication not required for read operations."""
        response = client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        
        response = client.get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        
        response = client.get("/api/v1/portfolio")
        self.assertEqual(response.status_code, 200)


class TestRootEndpoint(unittest.TestCase):
    
    def test_root(self):
        """Test root endpoint."""
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('name', data)
        self.assertIn('version', data)
        self.assertIn('docs', data)


if __name__ == '__main__':
    unittest.main()
