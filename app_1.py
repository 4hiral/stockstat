"""
Deep Analytics - Trade P&L Dashboard
Full Python implementation using Dash + Flask backend
Replicates: http://13.235.103.18:3000/dashboard/scanner/deep-analytics
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc
import requests
import pandas as pd
from datetime import datetime, date

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE          = "http://13.235.103.18:3000"
API_ENDPOINT      = f"{API_BASE}/api/scanner/deep-analytics"
REFRESH_INTERVAL  = 30_000   # milliseconds

# ── Exact field names from your API ──────────────────────────────────────────
# {"signalType":"BUY","result":"SL_HIT","pnl":-1465,"entryPrice":...}
SIGNAL_COL  = "signalType"   # values: BUY, SELL
RESULT_COL  = "result"       # values: SL_HIT, TARGET_HIT, SQUARED_OFF, OPEN
PNL_COL     = "pnl"
ENTRY_COL   = "entryPrice"
QTY_COL     = "quantity"

# ── App ───────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Deep Analytics - Trade P&L",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server

# ── Colors ────────────────────────────────────────────────────────────────────
C = {
    "bg":         "#0d0f14",
    "card":       "#161b26",
    "card2":      "#1c2333",
    "border":     "#2a3347",
    "blue":       "#3b82f6",
    "green":      "#22c55e",
    "red":        "#ef4444",
    "amber":      "#f59e0b",
    "muted":      "#94a3b8",
    "text":       "#e2e8f0",
    "btn":        "#2563eb",
    "tag_on":     "#2563eb",
    "tag_off":    "#1e2535",
    "pnl_bg":     "#3b0a0a",
    "target_bg":  "#052e16",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def card(children, extra_style=None):
    s = {"backgroundColor": C["card"], "borderRadius": "12px",
         "padding": "20px", "border": f"1px solid {C['border']}"}
    if extra_style:
        s.update(extra_style)
    return html.Div(children, style=s)


def stat_card(icon, icon_color, label, vid, bg=None, val_color=None, sub=None):
    return html.Div([
        html.Div([
            html.Div(icon, style={
                "width": "42px", "height": "42px", "borderRadius": "50%",
                "backgroundColor": icon_color + "22", "color": icon_color,
                "display": "flex", "alignItems": "center",
                "justifyContent": "center", "fontSize": "18px", "flexShrink": "0",
            }),
            html.Div([
                html.Div(label, style={"color": C["muted"], "fontSize": "13px", "marginBottom": "4px"}),
                html.Div("—", id=vid, style={
                    "fontSize": "28px", "fontWeight": "700",
                    "color": val_color or C["text"],
                }),
                html.Div(sub, id=vid + "-sub",
                         style={"color": C["muted"], "fontSize": "12px", "marginTop": "2px"}) if sub is not None else None,
            ], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "14px", "alignItems": "flex-start"}),
    ], style={
        "backgroundColor": bg or C["card"],
        "borderRadius": "12px", "padding": "20px",
        "border": f"1px solid {C['border']}", "flex": "1", "minWidth": "240px",
    })


def tag(label, tid, active, group):
    return html.Button(label, id={"type": f"tag-{group}", "index": tid}, n_clicks=0, style={
        "backgroundColor": C["tag_on"] if active else C["tag_off"],
        "color": C["text"], "border": "none", "borderRadius": "20px",
        "padding": "6px 14px", "fontSize": "13px", "cursor": "pointer",
        "fontWeight": "600" if active else "400",
    })


def fmt(v, prefix="₹"):
    """Format number → K / L notation."""
    if v is None: return "—"
    v = float(v)
    sign = "-" if v < 0 else ""
    av = abs(v)
    if av >= 1_00_000: return f"{sign}{prefix}{av/1_00_000:.2f}L"
    if av >= 1_000:    return f"{sign}{prefix}{av/1_000:.1f}K"
    return f"{sign}{prefix}{av:.2f}"


# ── API call ──────────────────────────────────────────────────────────────────
def fetch(selected_date):
    try:
        r = requests.get(API_ENDPOINT, params={"date": selected_date}, timeout=15)
        r.raise_for_status()
        data = r.json()
        trades = data.get("trades", []) if isinstance(data, dict) else data
        return trades
    except Exception as e:
        print(f"API error: {e}")
        return []


def summarize(trades):
    if not trades:
        return dict(invested=0, pnl=0, target=0, sl=0, squared=0, open_=0, total=0, winrate=0.0)
    df = pd.DataFrame(trades)
    results = df[RESULT_COL].str.upper() if RESULT_COL in df.columns else pd.Series([])
    target  = int((results == "TARGET_HIT").sum())
    sl      = int((results == "SL_HIT").sum())
    squared = int((results == "SQUARED_OFF").sum())
    open_   = int((results == "OPEN").sum())
    closed  = target + sl + squared
    winrate = (target / closed * 100) if closed else 0.0
    pnl     = float(df[PNL_COL].sum()) if PNL_COL in df.columns else 0
    # Total invested = sum(entryPrice * quantity)
    if ENTRY_COL in df.columns and QTY_COL in df.columns:
        invested = float((df[ENTRY_COL] * df[QTY_COL]).sum())
    else:
        invested = 0
    return dict(invested=invested, pnl=pnl, target=target, sl=sl,
                squared=squared, open_=open_, total=len(trades), winrate=winrate)


def build_table(trades, sig_f, res_f):
    if not trades:
        return html.Div("No trades found.", style={"color": C["muted"], "textAlign": "center", "padding": "40px"})

    df = pd.DataFrame(trades)

    # Apply signal filter
    if sig_f != "all" and SIGNAL_COL in df.columns:
        df = df[df[SIGNAL_COL].str.upper() == sig_f.upper()]

    # Apply result filter
    result_map = {"target": "TARGET_HIT", "sl": "SL_HIT", "squared": "SQUARED_OFF", "open": "OPEN"}
    if res_f != "all" and RESULT_COL in df.columns:
        df = df[df[RESULT_COL].str.upper() == result_map.get(res_f, res_f).upper()]

    if df.empty:
        return html.Div("No trades match the filters.", style={"color": C["muted"], "textAlign": "center", "padding": "30px"})

    # Clean up columns for display
    display_cols = [c for c in [
        "symbol", "name", "signalType", "entryPrice", "exitPrice",
        "stopLoss", "target", "quantity", "pnl", "pnlPercent", "result", "ltp",
        "signalTime", "exitTime"
    ] if c in df.columns]

    col_labels = {
        "symbol": "Symbol", "name": "Name", "signalType": "Signal",
        "entryPrice": "Entry", "exitPrice": "Exit", "stopLoss": "SL",
        "target": "Target", "quantity": "Qty", "pnl": "P&L",
        "pnlPercent": "P&L %", "result": "Result", "ltp": "LTP",
        "signalTime": "Signal Time", "exitTime": "Exit Time",
    }

    th_s = {
        "padding": "10px 12px", "textAlign": "left", "color": C["muted"],
        "fontSize": "12px", "fontWeight": "600", "textTransform": "uppercase",
        "letterSpacing": "0.5px", "borderBottom": f"1px solid {C['border']}",
        "whiteSpace": "nowrap",
    }
    td_s = {"padding": "10px 12px", "fontSize": "13px",
            "borderBottom": f"1px solid {C['border']}22", "whiteSpace": "nowrap"}

    def result_badge(val):
        v = str(val).upper()
        if v == "TARGET_HIT":  return ("TARGET", C["green"],  C["target_bg"])
        if v == "SL_HIT":      return ("SL HIT",  C["red"],   C["pnl_bg"])
        if v == "SQUARED_OFF": return ("SQUARED", C["blue"],  "#0c1a3a")
        if v == "OPEN":        return ("OPEN",    C["amber"], "#2a1f00")
        return (val, C["text"], "transparent")

    def cell(col, val):
        v = val
        color = C["text"]
        bg = "transparent"
        display = str(val)

        if col == "result":
            label, color, bg = result_badge(val)
            return html.Td(html.Span(label, style={
                "backgroundColor": bg, "color": color,
                "borderRadius": "12px", "padding": "2px 10px",
                "fontSize": "11px", "fontWeight": "600",
                "border": f"1px solid {color}44",
            }), style={**td_s})

        if col == "signalType":
            color = C["green"] if str(val).upper() == "BUY" else C["red"]

        if col == "pnl":
            try:
                fv = float(val)
                color = C["green"] if fv >= 0 else C["red"]
                display = fmt(fv, prefix="₹")
            except: pass

        if col == "pnlPercent":
            try:
                fv = float(val)
                color = C["green"] if fv >= 0 else C["red"]
                display = f"{fv:.2f}%"
            except: pass

        if col in ("entryPrice", "exitPrice", "stopLoss", "target", "ltp"):
            try: display = f"₹{float(val):,.2f}"
            except: pass

        if col in ("signalTime", "exitTime"):
            try:
                dt = datetime.fromisoformat(str(val))
                display = dt.strftime("%H:%M")
            except: pass

        return html.Td(display, style={**td_s, "color": color})

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        row_bg = C["card2"] if i % 2 == 0 else C["card"]
        cells = [cell(c, row[c]) for c in display_cols]
        rows.append(html.Tr(cells, style={"backgroundColor": row_bg}))

    return html.Table([
        html.Thead(html.Tr([html.Th(col_labels.get(c, c), style=th_s) for c in display_cols])),
        html.Tbody(rows),
    ], style={"width": "100%", "borderCollapse": "collapse"})


# ── Layout ────────────────────────────────────────────────────────────────────
app.layout = html.Div([
    dcc.Store(id="store-trades", data=[]),
    dcc.Store(id="store-sig",    data="all"),
    dcc.Store(id="store-res",    data="all"),
    dcc.Store(id="store-ar",     data=True),
    dcc.Interval(id="iv", interval=REFRESH_INTERVAL, disabled=False),

    html.Div([

        # Header
        html.Div([
            html.Div([
                html.Span("📊", style={"fontSize": "26px"}),
                html.Span(" Deep Analytics - Trade P&L",
                          style={"fontSize": "24px", "fontWeight": "700", "marginLeft": "10px"}),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div("Track trade performance with entry, exit, stop loss and target",
                     style={"color": C["muted"], "fontSize": "14px", "marginTop": "6px"}),
        ], style={"marginBottom": "24px"}),

        # Controls
        card([
            html.Div("Select Date", style={"fontWeight": "600", "marginBottom": "12px"}),
            html.Div([
                dcc.DatePickerSingle(
                    id="dp", date=date.today().strftime("%Y-%m-%d"),
                    display_format="DD-MM-YYYY",
                    style={"flex": "1"},
                ),
                html.Button([html.Span("🔍 "), "Load Trades"],
                    id="btn-load", n_clicks=0, style={
                        "backgroundColor": C["btn"], "color": "#fff",
                        "border": "none", "borderRadius": "8px",
                        "padding": "10px 22px", "fontSize": "14px",
                        "fontWeight": "600", "cursor": "pointer",
                    }),
            ], style={"display": "flex", "gap": "12px", "alignItems": "center", "flexWrap": "wrap"}),

            html.Div([
                html.Button("🔄 Auto-refresh ON", id="btn-ar", n_clicks=0, style={
                    "backgroundColor": "#14532d", "color": C["green"],
                    "border": f"1px solid {C['green']}", "borderRadius": "20px",
                    "padding": "6px 14px", "fontSize": "13px", "cursor": "pointer",
                }),
                html.Span("Every 30 seconds", style={"color": C["muted"], "fontSize": "13px"}),
                html.Div(id="refresh-ts", style={"color": C["blue"], "fontSize": "13px", "marginLeft": "auto"}),
            ], style={"display": "flex", "gap": "12px", "alignItems": "center",
                      "marginTop": "16px", "flexWrap": "wrap"}),
        ], extra_style={"marginBottom": "20px"}),

        # Stat cards row 1
        html.Div([
            stat_card("$",  C["blue"],  "Total Invested", "v-invested"),
            stat_card("📉", C["red"],   "Day P&L",        "v-pnl",
                      bg=C["pnl_bg"], val_color=C["red"]),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px", "flexWrap": "wrap"}),

        # Stat cards row 2
        html.Div([
            stat_card("🎯", C["green"], "Target Hits", "v-target", bg=C["target_bg"], val_color=C["green"]),
            stat_card("⚠️", C["red"],  "SL Hits",     "v-sl"),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "16px", "flexWrap": "wrap"}),

        # Stat cards row 3
        html.Div([
            stat_card("%",  C["amber"], "Win Rate", "v-wr",
                      val_color=C["amber"], sub=""),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "20px", "flexWrap": "wrap"}),

        # Filter bar
        card([
            html.Div([
                html.Span("▽ Signal:", style={"color": C["muted"], "fontSize": "13px"}),
                html.Div(id="sig-tags", style={"display": "flex", "gap": "8px", "flexWrap": "wrap"}),
                html.Span("Result:", style={"color": C["muted"], "fontSize": "13px", "marginLeft": "12px"}),
                html.Div(id="res-tags", style={"display": "flex", "gap": "8px", "flexWrap": "wrap"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px", "flexWrap": "wrap"}),
        ], extra_style={"marginBottom": "20px", "padding": "14px 20px"}),

        # Table
        card([
            html.Div(id="tbl-summary", style={"color": C["muted"], "fontSize": "13px", "marginBottom": "12px"}),
            html.Div(id="tbl", style={"overflowX": "auto"}),
        ]),

    ], style={"maxWidth": "1300px", "margin": "0 auto", "padding": "28px 20px"}),

], style={"fontFamily": "'Inter','Segoe UI',sans-serif",
          "backgroundColor": C["bg"], "minHeight": "100vh", "color": C["text"]})


# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("store-trades", "data"),
    Output("refresh-ts",   "children"),
    Input("btn-load",      "n_clicks"),
    Input("iv",            "n_intervals"),
    State("dp",            "date"),
    State("store-ar",      "data"),
    prevent_initial_call=False,
)
def load(n, ni, dt, ar):
    ctx = callback_context
    trig = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
    if "iv" in trig and not ar:
        return no_update, no_update
    d = dt or date.today().strftime("%Y-%m-%d")
    trades = fetch(d)
    now = datetime.now().strftime("%I:%M:%S %p").lower()
    return trades, f"🔄 Last refresh: {now}"


@app.callback(
    Output("v-invested", "children"),
    Output("v-pnl",      "children"),
    Output("v-target",   "children"),
    Output("v-sl",       "children"),
    Output("v-wr",       "children"),
    Output("v-wr-sub",   "children"),
    Input("store-trades","data"),
)
def update_cards(trades):
    s = summarize(trades or [])
    wr_sub = f"{s['target']} target / {s['sl']} SL / {s['squared']} squared / {s['open_']} open"
    pnl_val = fmt(s["pnl"], prefix="")
    return (
        fmt(s["invested"]),
        pnl_val,
        str(s["target"]),
        str(s["sl"]),
        f"{s['winrate']:.2f}%",
        wr_sub,
    )


@app.callback(
    Output("sig-tags", "children"),
    Input("store-trades", "data"),
    Input("store-sig",    "data"),
)
def sig_tags(trades, active):
    df = pd.DataFrame(trades or [])
    total = len(df)
    buy  = int((df[SIGNAL_COL].str.upper() == "BUY").sum())  if not df.empty and SIGNAL_COL in df.columns else 0
    sell = int((df[SIGNAL_COL].str.upper() == "SELL").sum()) if not df.empty and SIGNAL_COL in df.columns else 0
    return [
        tag(f"All ({total})", "all",  active == "all",  "sig"),
        tag(f"↗ Buy ({buy})",  "buy",  active == "buy",  "sig"),
        tag(f"↘ Sell ({sell})", "sell", active == "sell", "sig"),
    ]


@app.callback(
    Output("res-tags", "children"),
    Input("store-trades", "data"),
    Input("store-res",    "data"),
)
def res_tags(trades, active):
    df = pd.DataFrame(trades or [])
    def cnt(v):
        if df.empty or RESULT_COL not in df.columns: return 0
        return int((df[RESULT_COL].str.upper() == v).sum())
    total   = len(df)
    target  = cnt("TARGET_HIT")
    sl      = cnt("SL_HIT")
    squared = cnt("SQUARED_OFF")
    open_   = cnt("OPEN")
    return [
        tag(f"All ({total})",      "all",     active == "all",     "res"),
        tag(f"Target ({target})",  "target",  active == "target",  "res"),
        tag(f"SL ({sl})",          "sl",      active == "sl",      "res"),
        tag(f"Squared ({squared})","squared", active == "squared", "res"),
        tag(f"Open ({open_})",     "open",    active == "open",    "res"),
    ]


@app.callback(
    Output("store-sig", "data"),
    Input({"type": "tag-sig", "index": dash.ALL}, "n_clicks"),
    State({"type": "tag-sig", "index": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def set_sig(clicks, ids):
    ctx = callback_context
    if not ctx.triggered: return no_update
    btn = ctx.triggered[0]["prop_id"].split(".")[0]
    import json as _j
    return _j.loads(btn)["index"]


@app.callback(
    Output("store-res", "data"),
    Input({"type": "tag-res", "index": dash.ALL}, "n_clicks"),
    State({"type": "tag-res", "index": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def set_res(clicks, ids):
    ctx = callback_context
    if not ctx.triggered: return no_update
    btn = ctx.triggered[0]["prop_id"].split(".")[0]
    import json as _j
    return _j.loads(btn)["index"]


@app.callback(
    Output("tbl",         "children"),
    Output("tbl-summary", "children"),
    Input("store-trades", "data"),
    Input("store-sig",    "data"),
    Input("store-res",    "data"),
)
def update_table(trades, sig, res):
    t = build_table(trades or [], sig, res)
    n = len(trades) if trades else 0
    return t, f"Showing {n} trade(s)"


@app.callback(
    Output("store-ar",  "data"),
    Output("btn-ar",    "children"),
    Output("btn-ar",    "style"),
    Output("iv",        "disabled"),
    Input("btn-ar",     "n_clicks"),
    State("store-ar",   "data"),
    prevent_initial_call=True,
)
def toggle_ar(n, on):
    new = not on
    if new:
        lbl = "🔄 Auto-refresh ON"
        s = {"backgroundColor": "#14532d", "color": C["green"],
             "border": f"1px solid {C['green']}", "borderRadius": "20px",
             "padding": "6px 14px", "fontSize": "13px", "cursor": "pointer"}
    else:
        lbl = "🔄 Auto-refresh OFF"
        s = {"backgroundColor": "#3b0a0a", "color": C["red"],
             "border": f"1px solid {C['red']}", "borderRadius": "20px",
             "padding": "6px 14px", "fontSize": "13px", "cursor": "pointer"}
    return new, lbl, s, not new


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
