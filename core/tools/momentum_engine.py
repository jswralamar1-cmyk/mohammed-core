from typing import List, Dict
class MomentumEngine:
    def analyze(self, candles: List[Dict]) -> Dict:
        if len(candles) < 21:
            return {"score": 0}
        closes = [c["close"] for c in candles]
        highs = [c["high"] for c in candles]
        lows = [c["low"] for c in candles]
        volumes = [c["volume"] for c in candles]
        score = 0
        direction = None
        # EMA
        ema9 = self._ema(closes, 9)[-1]
        ema21 = self._ema(closes, 21)[-1]
        if ema9 > ema21:
            score += 1
            direction = "LONG"
        elif ema21 > ema9:
            score += 1
            direction = "SHORT"
        # Volume Spike
        avg_volume = sum(volumes[-20:-1]) / 19
        if volumes[-1] > avg_volume * 2.5:
            score += 2
        # Breakout
        recent_high = max(highs[-12:-1])
        recent_low = min(lows[-12:-1])
        last_close = closes[-1]
        # Strong candle body filter
        last_candle = candles[-1]
        body = abs(last_candle["close"] - last_candle["open"])
        range_ = last_candle["high"] - last_candle["low"]
        strong_body = range_ > 0 and (body / range_) > 0.6
        if last_close > recent_high and strong_body:
            score += 3
            direction = "LONG"
        if last_close < recent_low and strong_body:
            score += 3
            direction = "SHORT"
        # 3-candle momentum
        if direction == "LONG" and closes[-1] > closes[-2] > closes[-3]:
            score += 1
        if direction == "SHORT" and closes[-1] < closes[-2] < closes[-3]:
            score += 1
        return {"score": score, "direction": direction}
    def _ema(self, data, period):
        ema = [sum(data[:period]) / period]
        multiplier = 2 / (period + 1)
        for price in data[period:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        return ema
