# Deep Analytics - Trade P&L Dashboard
### Python replica of http://13.235.103.18:3000/dashboard/scanner/deep-analytics

---

## Setup

```bash
# 1. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux / Mac
venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python app.py
```

Then open your browser at: **http://localhost:8050**

---

## Configuration

In `app.py`, line 14–15, update these if your API path differs:

```python
API_BASE     = "http://13.235.103.18:3000"
API_ENDPOINT = f"{API_BASE}/api/scanner/deep-analytics"   # ← adjust if needed
```

**To find the exact API endpoint:**
1. Open the original URL in Chrome
2. Press `F12` → Network tab → reload the page
3. Click on the `deep-analytics?date=...` request
4. Copy the full **Request URL** from the Headers tab
5. Replace `API_ENDPOINT` with that URL (without the `?date=...` part)

---

## What's included

| Feature | Status |
|---|---|
| Dark theme (matches original) | ✅ |
| Date picker | ✅ |
| Load Trades button | ✅ |
| Auto-refresh every 30s | ✅ |
| Toggle Auto-refresh ON/OFF | ✅ |
| Last refresh timestamp | ✅ |
| Total Invested card | ✅ |
| Day P&L card (red for negative) | ✅ |
| Target Hits card | ✅ |
| SL Hits card | ✅ |
| Win Rate card | ✅ |
| Signal filter (All / Buy / Sell) | ✅ |
| Result filter (All / Target / SL / Squared / Open) | ✅ |
| Trades table with color-coded rows | ✅ |
| Live counts in filter tabs | ✅ |

---

## Flexible column mapping

The app automatically detects these common column names from your API response:

| Data | Tried column names |
|---|---|
| Signal/Direction | `signal`, `Signal`, `type`, `direction` |
| Result/Status | `result`, `Result`, `status`, `Status` |
| Invested amount | `invested`, `Invested`, `capital`, `amount` |
| P&L | `pnl`, `PnL`, `profit`, `pl`, `P&L` |

If your API uses different names, update the `col()` helper inside `compute_summary()` and `build_table()`.

---

## Tech stack

- **Dash** — Python reactive web framework (built on Flask + React)
- **Dash Bootstrap Components** — layout utilities
- **Pandas** — trade data processing
- **Requests** — HTTP calls to your existing API
