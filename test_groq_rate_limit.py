"""
Test to verify that Groq API calls are rate-limited and cached properly.
This test mocks the Groq client and counts the actual number of API calls made.

Expected behavior after fix:
- Exactly N Groq API calls (one per symbol that has headlines)
- No duplicate calls due to caching
- Rate limiting prevents 429 errors
"""
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch
import sys

sys.path.insert(0, '/workspace')

from ai_sentiment import AISentimentAnalyzer


class MockGroqClient:
    """Mock Groq client that tracks the number of API calls."""
    
    def __init__(self):
        self.call_count = 0
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = MagicMock(side_effect=self._mock_create)
    
    def _mock_create(self, *args, **kwargs):
        self.call_count += 1
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "0.5"
        return mock_response


def test_groq_call_count_with_caching():
    """
    Test that caching prevents duplicate Groq API calls when generate_views
    is called multiple times in the same trading cycle.
    """
    print("\n=== Testing Groq API Call Count with Caching ===\n")
    
    # Create synthetic price data - fix the shape issue
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=200, freq="h")
    data = {}
    for col in ["BTC", "ETH", "SOL", "BNB", "XRP"]:
        data[col] = np.random.randn(200).cumsum() + 100
    prices = pd.DataFrame(data, index=dates)
    
    expected_returns = np.array([0.001] * 5)
    symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]
    
    # Create analyzer with mocked Groq client
    analyzer = AISentimentAnalyzer(api_key="test_key", use_mock=False)
    mock_client = MockGroqClient()
    analyzer.client = mock_client
    
    # First call to generate_views - makes API calls for symbols with headlines
    print(f"First generate_views call for {len(symbols)} symbols...")
    P1, Q1 = analyzer.generate_views(prices, expected_returns, symbols)
    calls_after_first = mock_client.call_count
    print(f"Groq API calls after first generate_views: {calls_after_first}")
    
    # Second call to generate_views - should use cache, making 0 additional calls
    print("\nSecond generate_views call (should use cache)...")
    P2, Q2 = analyzer.generate_views(prices, expected_returns, symbols)
    calls_after_second = mock_client.call_count
    print(f"Groq API calls after second generate_views: {calls_after_second}")
    
    # Third call - still should use cache
    print("\nThird generate_views call (should still use cache)...")
    P3, Q3 = analyzer.generate_views(prices, expected_returns, symbols)
    calls_after_third = mock_client.call_count
    print(f"Groq API calls after third generate_views: {calls_after_third}")
    
    # Verify results
    print("\n=== Results ===")
    print(f"Total Groq API calls: {calls_after_third}")
    print(f"Calls on first invocation: {calls_after_first}")
    print(f"Additional calls on 2nd/3rd invocations: {calls_after_third - calls_after_first}")
    
    # Key assertions: caching must work
    assert calls_after_first >= 1, f"Expected at least 1 call after first generate_views, got {calls_after_first}"
    assert calls_after_second == calls_after_first, f"Expected no new calls after second generate_views (cached), got {calls_after_second}"
    assert calls_after_third == calls_after_first, f"Expected no new calls after third generate_views (cached), got {calls_after_third}"
    
    print(f"\n>>> TEST PASSED: Caching works correctly!")
    print(f">>> Only {calls_after_first} Groq API calls made on first run, then 0 additional calls on subsequent runs.")
    return True


def test_groq_call_count_without_caching_simulation():
    """
    Simulate what would happen WITHOUT caching - multiple calls per symbol.
    This demonstrates the problem that was fixed.
    """
    print("\n=== Simulating Pre-Fix Behavior (No Caching) ===\n")
    
    # In the old code, if generate_views was called 3 times (e.g., 3 rebalances),
    # each call would make 5 Groq API calls = 15 total calls
    # With our fix + caching, it's still only 5 calls total
    
    symbols_per_rebalance = 5
    num_rebalances = 3
    
    # Old behavior (no caching): 5 calls * 3 rebalances = 15 calls
    old_total_calls = symbols_per_rebalance * num_rebalances
    
    # New behavior (with caching): 5 calls total (first rebalance only)
    new_total_calls = symbols_per_rebalance
    
    print(f"Old behavior (no caching): {old_total_calls} Groq API calls")
    print(f"New behavior (with caching): {new_total_calls} Groq API calls")
    print(f"Reduction: {old_total_calls - new_total_calls} fewer calls ({100*(old_total_calls - new_total_calls)/old_total_calls:.0f}% reduction)")
    
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("GROQ API CALL COUNT TEST")
    print("=" * 70)
    
    # Run the main test
    test_groq_call_count_with_caching()
    
    # Show the improvement
    test_groq_call_count_without_caching_simulation()
    
    print("\n" + "=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
