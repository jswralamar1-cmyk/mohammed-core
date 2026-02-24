# Mohammed Core — نظام التداول الذكي

نظام تداول متكامل مبني على Python يعمل على Binance USDT-M Futures، مع دعم كامل للغة العربية في التحليل واتخاذ القرار.

---

## الهيكل البرمجي

```
mohammed_core/
├── core/
│   ├── brain/
│   │   ├── memory.py           # نظام الذاكرة والحالة
│   │   ├── policy.py           # سياسة التداول الافتراضية
│   │   └── brain_config.py     # إعدادات الدماغ الاستراتيجي
│   ├── tools/
│   │   ├── binance_futures.py  # واجهة Binance API
│   │   ├── market_scan.py      # ماسح السوق
│   │   ├── momentum_engine.py  # محرك الزخم
│   │   ├── momentum_strategy.py# استراتيجية الزخم
│   │   ├── pattern_strategy.py # استراتيجية الأنماط
│   │   ├── patterns_engine.py  # محرك الأنماط
│   │   ├── weighted_brain.py   # الدماغ الموزون
│   │   ├── risk_governor.py    # حاكم المخاطر
│   │   ├── execution_guard.py  # حارس التنفيذ
│   │   ├── order_router.py     # موجه الأوامر
│   │   ├── position_sizer.py   # محسب حجم المركز
│   │   ├── sl_tp_manager.py    # مدير SL/TP
│   │   ├── trade_logger.py     # مسجل الصفقات
│   │   ├── trade_monitor.py    # مراقب الصفقات
│   │   ├── strategy_scores.py  # هيكل بيانات النتائج
│   │   └── performance_tracker.py # متتبع الأداء
│   └── worker/
│       └── runner.py           # الحلقة الرئيسية للعمل
├── storage/
│   ├── policy.json             # إعدادات السياسة
│   ├── state.json              # الحالة الحالية
│   └── trade_history.csv       # سجل الصفقات
└── tests/
    ├── test_core.py            # اختبارات الوحدة
    └── test_integration.py     # اختبارات التكامل
```

---

## الإعداد والتشغيل

### 1. تثبيت المتطلبات

```bash
sudo pip3 install python-binance pandas
```

### 2. إعداد ملف السياسة

عدّل ملف `storage/policy.json` وأضف مفاتيح API الخاصة بك:

```json
{
  "binance_api_key": "YOUR_API_KEY",
  "binance_api_secret": "YOUR_API_SECRET",
  "leverage": 15,
  "risk_per_trade": 0.04,
  "max_daily_loss": 0.15,
  "max_open_positions": 3,
  "default_sl": 0.012,
  "default_tp": 0.02,
  "trailing_callback": 0.003,
  "scanner": {
    "scan_interval_seconds": 300,
    "entry_threshold": 3.5
  },
  "conflict_policy": "dominant",
  "strategy_weights": {
    "momentum": 1.5,
    "patterns": 1.0,
    "volume": 1.0
  }
}
```

### 3. تشغيل الاختبارات

```bash
cd mohammed_core
python3.11 tests/test_core.py
python3.11 tests/test_integration.py
```

### 4. تشغيل النظام (Dry Run)

```bash
cd mohammed_core
python3.11 -m core.worker.runner
```

### 5. التشغيل الحقيقي

لتفعيل التداول الحقيقي، عدّل `core/brain/policy.py`:

```python
LIVE_TRADING = True
```

---

## معلمات المخاطرة

| المعلمة | القيمة | الوصف |
|---------|--------|-------|
| `leverage` | 15x | الرافعة المالية |
| `risk_per_trade` | 4% | المخاطرة لكل صفقة |
| `max_daily_loss` | 15% | حد الخسارة اليومية (Kill Switch) |
| `max_open_positions` | 3 | أقصى عدد من الصفقات المفتوحة |
| `default_sl` | 1.2% | وقف الخسارة الافتراضي |
| `default_tp` | 2.0% | جني الأرباح الافتراضي |

---

## نتائج الاختبارات

### اختبارات الوحدة (12/12 نجاح)
- ✓ test_add_position
- ✓ test_initial_state
- ✓ test_pnl_update
- ✓ test_remove_position
- ✓ test_downtrend
- ✓ test_uptrend
- ✓ test_long_signal
- ✓ test_short_signal
- ✓ test_approve_trade
- ✓ test_reject_daily_loss
- ✓ test_reject_low_strength
- ✓ test_reject_max_positions

### اختبارات التكامل (7/7 نجاح)
- ✓ Test 1: Single Trade Lifecycle
- ✓ Test 2: Multiple Sequential Trades
- ✓ Test 3: Max Positions Enforcement
- ✓ Test 4: Daily Loss Kill Switch
- ✓ Test 5: Duplicate Position Prevention
- ✓ Test 6: Memory Persistence
- ✓ Test 7: SL/TP Calculation

---

## ملاحظات مهمة

1. **الاختبار أولاً**: استخدم دائماً Testnet قبل التداول الحقيقي.
2. **مفاتيح API**: لا تشارك مفاتيح API مع أحد.
3. **VPS**: يُنصح بتشغيل النظام على VPS مستقر مع مزامنة NTP.
4. **المراقبة**: راقب سجل `storage/trade_history.csv` بانتظام.
