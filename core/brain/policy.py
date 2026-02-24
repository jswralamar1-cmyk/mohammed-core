DEFAULT_POLICY = {
    "system": {
        "name": "Mohammed Core",
        "mode": "AUTO",              # AUTO | ADVISE | LOCKDOWN
        "market": "USDTM_FUTURES_ALL",
        "margin_mode": "ISOLATED"
    },
    "risk": {
        "risk_per_trade_default": 0.025,    # 2.5%
        "max_leverage": 12,
        "daily_loss_limit": 0.15,           # 15% Kill Switch
        "max_open_positions": 5,
        "max_trades_per_day": 200,
        "sl_required": True
    },
    
    "turbo": {
      "enabled": True,
      "max_orders_per_tick": 3,
      "max_new_risk_per_cycle": 0.07 # 7%
    },
    "adaptive_controls": {
        "reduce_size_at_loss_10": True,
        "shift_to_advise_at_loss_15": True,
        "lockdown_at_loss_20": True
    },
    "language_map": {
        "قوية": {"risk_per_trade": 0.04},
        "خفيفة": {"risk_per_trade": 0.015},
        "مخبل": {"aggression_multiplier": 1.4}
    }
}
# --- Global Safety Switch ---
LIVE_TRADING = True
