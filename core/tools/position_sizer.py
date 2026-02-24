import math

class PositionSizer:

    def __init__(self, policy: dict):
        self.policy = policy

    def calculate(self, balance: float, sl_percentage: float) -> dict:
        risk_per_trade = self.policy.get("risk_per_trade", 0.02)
        leverage = self.policy.get("leverage", 10)
        risk_amount = balance * risk_per_trade
        position_size_usd = (risk_amount / sl_percentage) * leverage
        return {
            "position_size_usd": position_size_usd,
            "leverage": leverage,
            "risk_amount_usd": risk_amount
        }

    def calculate_quantity(self, symbol: str, entry_price: float, sl_pct: float, risk_override: float = None) -> float:
        """
        Calculate order quantity based on account balance and risk parameters.
        Returns quantity in base asset units (e.g., BTC for BTCUSDT).
        """
        try:
            from core.tools.binance_futures import BinanceFutures
            client = BinanceFutures(
                self.policy.get('binance_api_key'),
                self.policy.get('binance_api_secret')
            )
            # Get futures account balance
            account = client._get("/fapi/v2/account", signed=True)
            if not account:
                print("[PositionSizer] Could not fetch account balance, using default $100", flush=True)
                balance = 100.0
            else:
                # Find USDT balance
                balance = 0.0
                for asset in account.get('assets', []):
                    if asset.get('asset') == 'USDT':
                        balance = float(asset.get('availableBalance', 0))
                        break
                if balance == 0:
                    balance = float(account.get('totalWalletBalance', 100))

            print(f"[PositionSizer] Available balance: ${balance:.2f}", flush=True)

            risk_pct = risk_override if risk_override else self.policy.get('risk_per_trade', 0.02)
            leverage = self.policy.get('leverage', 10)

            if sl_pct <= 0:
                sl_pct = 0.012  # default 1.2%

            # Risk amount in USDT
            risk_amount = balance * risk_pct
            # Position size in USDT (notional)
            notional = (risk_amount / sl_pct) * leverage
            # Quantity in base asset
            quantity = notional / entry_price

            # Get exchange info for precision
            exchange_info = client._get("/fapi/v1/exchangeInfo")
            if exchange_info:
                for s in exchange_info.get('symbols', []):
                    if s['symbol'] == symbol:
                        for f in s.get('filters', []):
                            if f['filterType'] == 'LOT_SIZE':
                                step = float(f['stepSize'])
                                precision = len(str(step).rstrip('0').split('.')[-1]) if '.' in str(step) else 0
                                quantity = math.floor(quantity / step) * step
                                quantity = round(quantity, precision)
                                break
                        break

            print(f"[PositionSizer] Quantity: {quantity} {symbol} (notional: ${notional:.2f})", flush=True)
            return quantity

        except Exception as e:
            print(f"[PositionSizer] Error: {e}", flush=True)
            return 0.0
