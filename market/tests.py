from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from market.views import get_yahoo_symbol_candidates


class MarketViewsTests(TestCase):
    @patch('market.views.fetch_yahoo_quote')
    def test_market_summary_endpoint(self, mock_quote):
        mock_quote.side_effect = [
            {"price": 77000.0, "change": 10.0, "changePercent": 0.01, "marketState": "REGULAR", "source": "Yahoo Finance"},
            {"price": 23000.0, "change": 20.0, "changePercent": 0.09, "marketState": "REGULAR", "source": "Yahoo Finance"},
            {"price": 50000.0, "change": -30.0, "changePercent": -0.06, "marketState": "REGULAR", "source": "Yahoo Finance"},
        ]
        response = self.client.get(reverse('market_summary'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('indices', payload)
        self.assertTrue(payload['marketOpen'])
        self.assertEqual(payload['indices'][0]['price'], 77000.0)

    @patch('market.views.fetch_yahoo_quote')
    def test_stock_quote_endpoint(self, mock_quote):
        mock_quote.return_value = {
            "price": 1300.0,
            "change": 5.0,
            "changePercent": 0.39,
            "marketState": "REGULAR",
            "source": "Yahoo Finance",
        }
        response = self.client.get(reverse('stock_quote', args=['aapl']))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['symbol'], 'AAPL')
        self.assertEqual(payload['price'], 1300.0)

    def test_stock_suggestions_endpoint(self):
        with patch('market.views.fetch_yahoo_suggestions', return_value=[]):
            response = self.client.get(reverse('stock_suggestions'), {'query': 'reli'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item['symbol'] == 'RELIANCE' for item in payload))

    @patch('market.views.fetch_yahoo_suggestions')
    def test_stock_suggestions_include_yahoo_matches(self, mock_suggestions):
        mock_suggestions.return_value = [
            {"symbol": "SBIN.NS", "name": "State Bank of India", "exchange": "NSE"},
        ]
        response = self.client.get(reverse('stock_suggestions'), {'query': 'state bank'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item['symbol'] == 'SBIN.NS' for item in payload))

    def test_plain_indian_symbols_try_nse_and_bse(self):
        self.assertEqual(get_yahoo_symbol_candidates('sbin')[:2], ['SBIN.NS', 'SBIN.BO'])
