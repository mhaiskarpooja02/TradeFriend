# TradeFriend Algo Trading System

TradeFriend is a **rule-based swing trading system** built in Python with a **Tkinter dashboard**, SQLite persistence, and a clean multi-stage trading pipeline.

This project is designed for **paper trading first**, with strict separation of:
- Scan
- Plan
- Decide
- Execute
- Monitor

---

## 🔁 High-Level Flow

```
Daily Scan
   ↓
Watchlist (DB)
   ↓
Swing Trade Plans (PLANNED)
   ↓
Morning Confirmation
   ↓
Live Trades (OPEN / PARTIAL)
   ↓
Trade Monitor
   ↓
EXIT (TARGET / SL / TRAIL)
```

---

## 🧠 Core Philosophy

- **Planning > Prediction**
- **Risk-first position sizing**
- **No emotional execution**
- **DB is the single source of truth**
- **Each class owns its own database**
- **Dashboard only triggers orchestration**

---

## 📁 Project Structure

```
tradefriend/
│
├── core/
│   ├── watchlist_engine.py
│   ├── TradeFriendDecisionRunner.py
│   ├── TradeFriendSwingTradeMonitor.py
│   ├── TradeFriendPositionSizer.py
│   └── TradeFriendDataProvider.py
│
├── strategy/
│   ├── TradeFriendScanner.py
│   ├── TradeFriendSwingEntryPlanner.py
│   ├── TradeFriendSwingEntry.py
│   └── TradeFriendScoring.py
│
├── db/
│   ├── TradeFriendWatchlistRepo.py
│   ├── TradeFriendSwingPlanRepo.py
│   ├── TradeFriendTradeRepo.py
│   └── TradeFriendDatabase.py
│
├── ui/
│   └── TradeFriendDashboard.py
│
├── utils/
│   ├── TradeFriendManager.py
│   └── logger.py
│
├── config/
│   └── TradeFriendConfig.py
│
└── dbdata/
    └── *.db
```

---

## 🧩 Key Components

### 1️⃣ WatchlistEngine
- Fetches daily data
- Runs scanner logic
- Saves qualified symbols into `tradefriend_watchlist`
- Builds **swing trade plans**

Triggered by:
- Dashboard → **Run Daily Scan**

---

### 2️⃣ TradeFriendSwingPlanRepo
- Stores PLANNED swing trades
- Handles:
  - Expiry
  - Triggered state
  - Cancellation

---

### 3️⃣ TradeFriendDecisionRunner
- Runs **morning confirmation**
- Converts PLANNED plans → LIVE trades
- Uses:
  - LTP confirmation
  - Position sizing
  - Risk checks

Triggered by:
- Dashboard → **Run Morning Confirmation**

---

### 4️⃣ TradeFriendTradeRepo
- Manages executed trades
- Supports:
  - Partial booking
  - Hold mode
  - Trailing SL
  - Emergency exits
- Used by:
  - DecisionRunner
  - TradeMonitor
  - Dashboard

---

### 5️⃣ TradeFriendSwingTradeMonitor
- Monitors OPEN / PARTIAL trades
- Handles:
  - SL
  - Partial @ 1R
  - ATR-based trailing SL
  - Final target
- Designed for **paper trading**

Triggered by:
- Scheduler or manual call

---

### 6️⃣ TradeFriendDashboard (Tkinter)
Buttons:
- **Run Daily Scan**
- **Run Morning Confirmation**
- **Refresh Tables**

Tabs:
- 📋 Watchlist
- 📈 Trades

Dashboard responsibilities:
- Trigger flows
- Display DB state
- Never contain trading logic

---

## 🗄️ Databases Used

| DB | Purpose |
|----|--------|
| tradefriend_watchlist.db | Daily scan results |
| tradefriend_swing_plans.db | Planned swing trades |
| tradefriend_trades.db | Executed trades |

---

## ⚙️ Configuration

All strategy & risk parameters are controlled from:

```
config/TradeFriendConfig.py
```

Examples:
- Capital
- Risk per trade
- Partial booking rules
- ATR trailing multiple

---

## 🚀 How to Run (Paper Trading)

1. Run dashboard
2. Click **Run Daily Scan**
3. Review Watchlist
4. Click **Run Morning Confirmation**
5. (Optional) Run Trade Monitor periodically
6. Observe trade lifecycle in Trades tab

---

## 🛡️ Safety Notes

- Paper trade only
- No broker order placement
- No live money risk
- SQLite auto-migrates safely

---

## 🧭 Roadmap

- [ ] Scheduler (cron / APScheduler)
- [ ] Live broker integration
- [ ] Strategy plug-in system
- [ ] Equity curve & analytics
- [ ] Export reports

---

## 📌 Final Note

> TradeFriend is built to **think like a trader, not a gambler**.

Plan the trade.
Trade the plan.
Let the system execute.

---

Happy Trading 🚀
