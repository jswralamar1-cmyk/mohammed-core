DEFAULT_BRAIN_CONFIG = {
    # ============================
    # 🔢 Strategy Weights
    # ============================
    "weights": {
        "momentum": 1.0,        # المرحلة 3 engine
        "rsi": 0.7,
        "funding_oi": 0.6,
        "patterns": 0.8
    },
    # ============================
    # 🎯 Entry Threshold
    # ============================
    "entry_threshold": 3.0,
    # ============================
    # ⚖️ Conflict Handling
    # ============================
    "conflict_policy": "dominant",  
    # options:
    # "dominant" → الأعلى مجموع يفوز
    # "strict"   → إذا تعارض، لا دخول
    # "bias_long"  → LONG يفوز إذا متقارب
    # "bias_short" → SHORT يفوز إذا متقارب
    # ============================
    # 📉 Adaptive Limits (مرحلة 5 لاحقاً)
    # ============================
    "min_confidence": 0.4,
    "max_confidence": 1.0
}
_
