"""Unit tests for the OpenBB feed wrapper.
These tests verify that the wrapper functions are callable and return data structures
compatible with the rest of the cockpit. They intentionally avoid asserting on exact
values because the data is live; instead they check that the return type is a dict
or list and that expected top‑level keys exist.
"""
import unittest
from src.openbb_feed import (
    get_macro_data,
    get_equity_fundamentals,
    get_equity_market_depth,
    get_equity_price_history,
    get_news,
    get_crypto_price,
)

class TestOpenBBFeed(unittest.TestCase):
    def test_macro_data(self):
        result = get_macro_data()
        self.assertIsInstance(result, dict)
        self.assertIn("data", result)
        # Should be a list of dicts even if empty
        self.assertIsInstance(result["data"], list)

    def test_equity_fundamentals(self):
        result = get_equity_fundamentals("AAPL")
        self.assertIsInstance(result, dict)
        self.assertIn("fundamentals", result)
        self.assertIsInstance(result["fundamentals"], list)

    def test_equity_market_depth(self):
        # Depth may be empty if provider lacks data; ensure we get a dict
        result = get_equity_market_depth("AAPL")
        self.assertIsInstance(result, dict)
        self.assertIn("depth", result)

    def test_equity_price_history(self):
        result = get_equity_price_history("AAPL", start_date="2024-01-01")
        self.assertIsInstance(result, dict)
        self.assertIn("prices", result)
        self.assertIsInstance(result["prices"], list)

    def test_news(self):
        result = get_news(limit=5)
        self.assertIsInstance(result, list)
        # Each entry should be a dict with at least a title if available
        if result:
            self.assertIsInstance(result[0], dict)
            self.assertTrue(any(k in result[0] for k in ("title", "headline", "source")))

    def test_crypto_price(self):
        result = get_crypto_price("BTC-USD", start_date="2024-01-01")
        self.assertIsInstance(result, dict)
        self.assertIn("prices", result)
        self.assertIsInstance(result["prices"], list)

if __name__ == "__main__":
    unittest.main()
