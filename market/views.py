import json
from time import time
from urllib import request as urlopen_request
from urllib.parse import quote, urlencode

from django.http import JsonResponse
from django.shortcuts import render


YAHOO_SYMBOLS = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
}

INDEX_OPTIONS = [
    {"name": "SENSEX", "symbol": "^BSESN"},
    {"name": "NIFTY 50", "symbol": "^NSEI"},
    {"name": "BANK NIFTY", "symbol": "^NSEBANK"},
]

STOCK_OPTIONS = [
    {"symbol": "RELIANCE", "name": "Reliance Industries"},
    {"symbol": "TCS", "name": "Tata Consultancy Services"},
    {"symbol": "INFY", "name": "Infosys Ltd"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank"},
    {"symbol": "SBIN", "name": "State Bank of India"},
    {"symbol": "ITC", "name": "ITC Ltd"},
    {"symbol": "LT", "name": "Larsen & Toubro"},
    {"symbol": "AXISBANK", "name": "Axis Bank"},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel"},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever"},
    {"symbol": "MARUTI", "name": "Maruti Suzuki"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors"},
    {"symbol": "ADANIENT", "name": "Adani Enterprises"},
]


def no_store_json(data, safe=True):
    response = JsonResponse(data, safe=safe)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def get_yahoo_symbol_candidates(symbol):
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return []
    if symbol in YAHOO_SYMBOLS:
        return [YAHOO_SYMBOLS[symbol]]
    if symbol.startswith("^") or "." in symbol:
        return [symbol]

    us_symbols = {"AAPL", "MSFT", "TSLA", "NVDA", "AMZN"}
    if symbol in us_symbols:
        return [symbol]

    if symbol.replace("-", "").isalnum():
        return [f"{symbol}.NS", f"{symbol}.BO", symbol]

    return [symbol]


def fetch_single_yahoo_quote(yahoo_symbol):
    encoded_symbol = quote(yahoo_symbol, safe="")
    cache_buster = int(time() * 1000)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}"
        f"?range=1d&interval=1m&includePrePost=false&_={cache_buster}"
    )
    request = urlopen_request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })

    with urlopen_request.urlopen(request, timeout=10) as response:
        payload = json.load(response)

    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        raise ValueError("Quote unavailable")

    meta = result.get("meta", {})
    price = meta.get("regularMarketPrice")
    previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")

    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    latest_close = next((value for value in reversed(closes) if value is not None), None)
    if price is None:
        price = latest_close
    if previous_close is None:
        previous_close = meta.get("regularMarketPreviousClose")

    if price is None:
        raise ValueError("Quote price unavailable")

    change = 0.0
    change_percent = 0.0
    if previous_close:
        change = float(price) - float(previous_close)
        change_percent = (change / float(previous_close)) * 100

    return {
        "price": round(float(price), 2),
        "change": round(change, 2),
        "changePercent": round(change_percent, 2),
        "marketState": meta.get("marketState", "UNKNOWN"),
        "resolvedSymbol": meta.get("symbol", yahoo_symbol),
        "lastUpdated": meta.get("regularMarketTime"),
        "source": "Yahoo Finance",
    }


def fetch_yahoo_quote(symbol):
    last_error = None
    for yahoo_symbol in get_yahoo_symbol_candidates(symbol):
        try:
            return fetch_single_yahoo_quote(yahoo_symbol)
        except Exception as error:
            last_error = error
    raise last_error or ValueError("Quote unavailable")


def fetch_yahoo_suggestions(query):
    params = urlencode({"q": query, "quotesCount": 12, "newsCount": 0})
    url = f"https://query1.finance.yahoo.com/v1/finance/search?{params}"
    request = urlopen_request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen_request.urlopen(request, timeout=10) as response:
        payload = json.load(response)

    suggestions = []
    seen = set()
    for item in payload.get("quotes", []):
        symbol = (item.get("symbol") or "").upper()
        quote_type = item.get("quoteType")
        if not symbol or symbol in seen or quote_type not in {"EQUITY", "ETF", "INDEX"}:
            continue
        seen.add(symbol)
        suggestions.append({
            "symbol": symbol,
            "name": item.get("shortname") or item.get("longname") or symbol,
            "exchange": item.get("exchDisp") or item.get("exchange") or "",
        })
    return suggestions[:10]


def home(request):
    return render(request, "market/index.html")


def market_summary(request):
    indices = []
    market_open = False

    for index in INDEX_OPTIONS:
        try:
            quote_data = fetch_yahoo_quote(index["symbol"])
            market_open = market_open or quote_data.get("marketState") == "REGULAR"
            indices.append({"name": index["name"], **quote_data})
        except Exception:
            indices.append({
                "name": index["name"],
                "price": 0.0,
                "change": 0.0,
                "changePercent": 0.0,
                "error": "Quote unavailable",
            })

    return no_store_json({
        "marketOpen": market_open,
        "indices": indices,
    })


def stock_suggestions(request):
    query = (request.GET.get("query") or "").strip().upper()
    if not query:
        return no_store_json([], safe=False)

    local_matches = [
        item for item in STOCK_OPTIONS
        if query in item["symbol"] or query in item["name"].upper()
    ][:8]

    try:
        yahoo_matches = fetch_yahoo_suggestions(query)
    except Exception:
        yahoo_matches = []

    matches = []
    seen = set()
    for item in local_matches + yahoo_matches:
        symbol = item["symbol"]
        if symbol in seen:
            continue
        seen.add(symbol)
        matches.append(item)

    if not matches and query.replace("-", "").isalnum():
        matches.append({"symbol": query, "name": f"Search {query} as NSE/BSE symbol"})

    return no_store_json(matches[:10], safe=False)


def stock_quote(request, symbol):
    symbol = (symbol or "AAPL").upper()

    try:
        quote_data = fetch_yahoo_quote(symbol)
    except Exception:
        return no_store_json({
            "symbol": symbol,
            "price": 0.0,
            "change": 0.0,
            "changePercent": 0.0,
            "error": "Quote unavailable",
        })

    return no_store_json({"symbol": symbol, **quote_data})
