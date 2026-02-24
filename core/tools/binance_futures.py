import hmac
import hashlib
import time
import requests


class BinanceFutures:
    def __init__(self, api_key: str, secret_key: str):
        self.base_url = "https://fapi.binance.com"
        self.api_key = api_key
        self.secret_key = secret_key

    def _get_timestamp(self):
        return int(time.time() * 1000)

    def _sign(self, query_string: str) -> str:
        return hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method, endpoint, params=None, signed=False):
        if params is None:
            params = {}
        if signed:
            params["timestamp"] = self._get_timestamp()
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            params["signature"] = self._sign(query_string)
        headers = {"X-MBX-APIKEY": self.api_key}
        try:
            res = requests.request(
                method,
                self.base_url + endpoint,
                params=params,
                headers=headers,
                timeout=10
            )
            if not res.ok:
                print(f"[Binance API Error] {res.status_code}: {res.text[:200]}", flush=True)
                return None
            return res.json()
        except requests.exceptions.RequestException as e:
            print(f"[Binance API Error] {e}", flush=True)
            return None

    def _get(self, endpoint, params=None, signed=False):
        return self._request("GET", endpoint, params, signed)

    def _post(self, endpoint, params=None, signed=False):
        return self._request("POST", endpoint, params, signed)

    def get_all_tickers(self):
        return self._get('/fapi/v1/ticker/price')

    def get_candles(self, symbol: str, interval: str = '15m', limit: int = 100):
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        klines = self._get('/fapi/v1/klines', params)
        if not klines:
            return []
        candles = []
        for k in klines:
            candles.append({
                'open_time': k[0],
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5]),
                'close_time': k[6],
            })
        return candles

    def get_ticker(self, symbol: str):
        return self._get('/fapi/v1/ticker/price', {'symbol': symbol})

    def place_market_order(self, symbol: str, side: str, quantity: float):
        params = {'symbol': symbol, 'side': side, 'type': 'MARKET', 'quantity': quantity}
        return self._post('/fapi/v1/order', params, signed=True)

    def get_avg_price(self, symbol: str):
        data = self._get('/fapi/v1/avgPrice', {'symbol': symbol})
        return float(data['price']) if data else None
