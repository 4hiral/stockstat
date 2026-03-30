import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc
import requests
import pandas as pd
from datetime import datetime, date
import json as _json


API_BASE         = "http://13.235.103.18:3000"
API_ENDPOINT     = f"{API_BASE}/api/scanner/deep-analytics"
REFRESH_INTERVAL = 30_000

SIGNAL_COL = "signalType"
RESULT_COL = "result"
PNL_COL    = "pnl"
ENTRY_COL  = "entryPrice"
QTY_COL    = "quantity"


C = {
    "bg":        "#0d1117",
    "card":      "#161b26",
    "card2":     "#1c2333",
    "border":    "#2a3347",
    "blue":      "#3b82f6",
    "green":     "#22c55e",
    "red":       "#ef4444",
    "amber":     "#f59e0b",
    "muted":     "#94a3b8",
    "text":      "#e2e8f0",
    "btn":       "#2563eb",
    "tag_on":    "#2563eb",
    "tag_off":   "#1e293b",
    "pnl_red":   "#3b0a0a",
    "pnl_green": "#052e16",
}


def fmt(v, prefix=""):
    if v is None: return "—"
    v = float(v)
    sign = "+" if v > 0 else ("-" if v < 0 else "")
    av = abs(v)
    if av >= 1_00_000: return f"{sign}{prefix}{av/1_00_000:.2f}L"
    if av >= 1_000:    return f"{sign}{prefix}{av/1_000:.1f}K"
    return f"{sign}{prefix}{av:.2f}"

def fmt_price(v):
    try: return f"{float(v):,.2f}"
    except: return str(v)

def fmt_pct(v):
    try: return f"{float(v):.1f}%"
    except: return ""


def fetch(selected_date):
    try:
        r = requests.get(API_ENDPOINT, params={"date": selected_date}, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("trades", []) if isinstance(data, dict) else data
    except Exception as e:
        print(f"API error: {e}")
        return []

def summarize(trades):
    """
    Win rate = (TARGET_HIT + SQUARED_OFF) / closed * 100
    closed   = TARGET_HIT + SL_HIT + SQUARED_OFF  (not OPEN)
    """
    if not trades:
        return dict(invested=0, pnl=0, target=0, sl=0,
                    squared=0, open_=0, total=0, winrate=0.0, buy=0, sell=0)
    df = pd.DataFrame(trades)
    results = df[RESULT_COL].str.upper() if RESULT_COL in df.columns else pd.Series([], dtype=str)
    target  = int((results == "TARGET_HIT").sum())
    sl      = int((results == "SL_HIT").sum())
    squared = int((results == "SQUARED_OFF").sum())
    open_   = int((results == "OPEN").sum())
    closed  = target + sl + squared
    wins    = target + squared
    winrate = (wins / closed * 100) if closed else 0.0
    pnl     = float(df[PNL_COL].sum()) if PNL_COL in df.columns else 0
    invested = float((df[ENTRY_COL] * df[QTY_COL]).sum()) if ENTRY_COL in df.columns and QTY_COL in df.columns else 0
    buy  = int((df[SIGNAL_COL].str.upper() == "BUY").sum())  if SIGNAL_COL in df.columns else 0
    sell = int((df[SIGNAL_COL].str.upper() == "SELL").sum()) if SIGNAL_COL in df.columns else 0
    return dict(invested=invested, pnl=pnl, target=target, sl=sl,
                squared=squared, open_=open_, total=len(trades),
                winrate=winrate, buy=buy, sell=sell)


def tag_btn(label, tid, active, group):
    return html.Button(label,
        id={"type": f"tag-{group}", "index": tid},
        n_clicks=0,
        style={
            "backgroundColor": C["tag_on"] if active else C["tag_off"],
            "color": C["text"],
            "border": "none",
            "borderRadius": "6px",
            "padding": "5px 14px",
            "fontSize": "13px",
            "cursor": "pointer",
            "fontWeight": "600" if active else "400",
        })

def result_badge(result):
    v = str(result).upper()
    if v == "TARGET_HIT":
        return html.Span("● TARGET", style={
            "backgroundColor": "#052e16", "color": C["green"],
            "border": f"1px solid {C['green']}44",
            "borderRadius": "20px", "padding": "3px 12px",
            "fontSize": "12px", "fontWeight": "600",
        })
    if v == "SL_HIT":
        return html.Span("● SL HIT", style={
            "backgroundColor": C["pnl_red"], "color": C["red"],
            "border": f"1px solid {C['red']}44",
            "borderRadius": "20px", "padding": "3px 12px",
            "fontSize": "12px", "fontWeight": "600",
        })
    if v == "SQUARED_OFF":
        return html.Span("● SQUARED", style={
            "backgroundColor": "#0c1a3a", "color": C["blue"],
            "border": f"1px solid {C['blue']}44",
            "borderRadius": "20px", "padding": "3px 12px",
            "fontSize": "12px", "fontWeight": "600",
        })
    if v == "OPEN":
        return html.Span("○ OPEN", style={
            "backgroundColor": "#1e2535", "color": C["muted"],
            "border": f"1px solid {C['muted']}44",
            "borderRadius": "20px", "padding": "3px 12px",
            "fontSize": "12px", "fontWeight": "600",
        })
    return html.Span(result, style={"color": C["muted"], "fontSize": "12px"})

def signal_badge(sig):
    v = str(sig).upper()
    if v == "BUY":
        return html.Span("↗ BUY", style={
            "backgroundColor": "#052e16", "color": C["green"],
            "border": f"1px solid {C['green']}55",
            "borderRadius": "6px", "padding": "2px 10px",
            "fontSize": "12px", "fontWeight": "700",
        })
    return html.Span("↘ SELL", style={
        "backgroundColor": C["pnl_red"], "color": C["red"],
        "border": f"1px solid {C['red']}55",
        "borderRadius": "6px", "padding": "2px 10px",
        "fontSize": "12px", "fontWeight": "700",
    })

def fmt_signal_time(t):
    try:
        dt = datetime.fromisoformat(str(t))
        return dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")
    except:
        return str(t)

def trade_card(trade):
    symbol     = trade.get("symbol", "—")
    name       = trade.get("name", "")
    sig        = trade.get(SIGNAL_COL, "")
    sig_time   = trade.get("signalTime", "")
    entry      = trade.get(ENTRY_COL, 0)
    sl         = trade.get("stopLoss", 0)
    target_p   = trade.get("target", 0)
    qty        = trade.get(QTY_COL, 0)
    result     = trade.get(RESULT_COL, "OPEN")
    exit_price = trade.get("exitPrice", None)
    exit_time  = trade.get("exitTime", None)
    pnl        = trade.get(PNL_COL, 0)
    pnl_pct    = trade.get("pnlPercent", 0)
    ltp        = trade.get("ltp", None)

    
    try:
        sl_pct  = abs((float(sl)     - float(entry)) / float(entry) * 100)
        tgt_pct = abs((float(target_p) - float(entry)) / float(entry) * 100)
    except:
        sl_pct = tgt_pct = 0

    
    pnl_color = C["green"] if float(pnl or 0) >= 0 else C["red"]
    pnl_display = fmt(pnl)
    pnl_pct_display = fmt_pct(float(pnl_pct or 0) * (1 if float(pnl or 0) >= 0 else 1))

    
    exit_row = []
    if exit_price and str(result).upper() != "OPEN":
        try:
            exit_dt = datetime.fromisoformat(str(exit_time)).strftime("%H:%M") if exit_time else ""
        except:
            exit_dt = ""
        exit_row = [
            html.Div([
                html.Div([
                    html.Div("Exit Price", style={"color": C["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                    html.Div(fmt_price(exit_price), style={"fontWeight": "700", "fontSize": "15px"}),
                ], style={"flex": "1"}),
                html.Div([
                    html.Div("Exit Time", style={"color": C["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                    html.Div(exit_dt, style={"fontWeight": "700", "fontSize": "15px"}),
                ], style={"flex": "1"}),
                html.Div([
                    html.Div("P&L", style={"color": C["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                    html.Div(f"{pnl_display} ({pnl_pct_display})",
                             style={"fontWeight": "700", "fontSize": "15px", "color": pnl_color}),
                ], style={"flex": "1"}),
            ], style={
                "display": "flex", "gap": "24px", "flexWrap": "wrap",
                "padding": "14px 16px",
                "borderTop": f"1px solid {C['border']}",
                "backgroundColor": C["card2"],
                "borderRadius": "0 0 10px 10px",
            })
        ]

    return html.Div([
        # Card header
        html.Div([
            html.Div([
                html.Span(symbol, style={"fontWeight": "800", "fontSize": "18px", "marginRight": "10px"}),
                signal_badge(sig),
                html.Span(fmt_signal_time(sig_time), style={
                    "color": C["muted"], "fontSize": "12px", "marginLeft": "12px"
                }),
                html.A("🔗 Chart",
                    href=f"https://www.tradingview.com/chart/?symbol=NSE%3A{symbol}&interval=3",
                    target="_blank",
                    style={
                        "color": C["blue"], "fontSize": "12px", "marginLeft": "12px",
                        "cursor": "pointer", "border": f"1px solid {C['border']}",
                        "padding": "2px 8px", "borderRadius": "6px",
                        "textDecoration": "none", "display": "inline-block",
                    }),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "6px"}),
            result_badge(result),
        ], style={
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "center", "marginBottom": "6px",
            "flexWrap": "wrap", "gap": "8px",
        }),

        
        html.Div(name, style={"color": C["muted"], "fontSize": "13px", "marginBottom": "14px"}),

        
        html.Div([
            html.Div([
                html.Div("Entry Price", style={"color": C["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                html.Div(fmt_price(entry), style={"fontWeight": "700", "fontSize": "15px"}),
            ], style={"flex": "1"}),
            html.Div([
                html.Div(f"Stop Loss ({sl_pct:.1f}%)", style={"color": C["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                html.Div(fmt_price(sl), style={"fontWeight": "700", "fontSize": "15px", "color": C["red"]}),
            ], style={"flex": "1"}),
            html.Div([
                html.Div(f"Target ({tgt_pct:.1f}%)", style={"color": C["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                html.Div(fmt_price(target_p), style={"fontWeight": "700", "fontSize": "15px", "color": C["green"]}),
            ], style={"flex": "1"}),
            html.Div([
                html.Div("Qty", style={"color": C["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                html.Div(str(qty), style={"fontWeight": "700", "fontSize": "15px"}),
            ], style={"flex": "1"}),
            html.Div([
                html.Div("LTP", style={"color": C["muted"], "fontSize": "12px", "marginBottom": "4px"}),
                html.Div(fmt_price(ltp) if ltp else "—", style={"fontWeight": "700", "fontSize": "15px"}),
            ], style={"flex": "1"}) if ltp else html.Div(),
        ], style={"display": "flex", "gap": "24px", "flexWrap": "wrap"}),

        *exit_row,

    ], style={
        "backgroundColor": C["card"],
        "border": f"1px solid {C['border']}",
        "borderRadius": "10px",
        "padding": "16px",
        "marginBottom": "12px",
    })


app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="Deep Analytics - Trade P&L",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server

app.layout = html.Div([
    dcc.Store(id="store-trades", data=[]),
    dcc.Store(id="store-sig",    data="all"),
    dcc.Store(id="store-res",    data="all"),
    dcc.Store(id="store-ar",     data=True),
    dcc.Interval(id="iv", interval=REFRESH_INTERVAL, disabled=False),

    html.Div([

        # ── Header ──
        html.Div([
            html.Div([
                html.Span("📊", style={"fontSize": "28px", "marginRight": "10px"}),
                html.Span("Deep Analytics - Trade P&L",
                          style={"fontSize": "26px", "fontWeight": "800"}),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div("Track trade performance with entry, exit, stop loss and target",
                     style={"color": C["muted"], "fontSize": "14px", "marginTop": "4px"}),
        ], style={"marginBottom": "24px"}),

        # ── Date + Load + Auto-refresh ──
        html.Div([
            html.Div("Select Date", style={"fontWeight": "600", "marginBottom": "10px", "fontSize": "14px"}),
            html.Div([
                dcc.DatePickerSingle(
                    id="dp",
                    date=date.today().strftime("%Y-%m-%d"),
                    display_format="DD-MM-YYYY",
                    style={"flex": "1", "minWidth": "200px"},
                ),
                html.Button([html.Span("🔍 "), "Load Trades"],
                    id="btn-load", n_clicks=0, style={
                        "backgroundColor": C["btn"], "color": "#fff",
                        "border": "none", "borderRadius": "8px",
                        "padding": "10px 24px", "fontSize": "14px",
                        "fontWeight": "600", "cursor": "pointer",
                    }),
            ], style={"display": "flex", "gap": "12px", "alignItems": "center", "flexWrap": "wrap"}),

            html.Div([
                html.Button("🔄 Auto-refresh ON", id="btn-ar", n_clicks=0, style={
                    "backgroundColor": "#14532d", "color": C["green"],
                    "border": f"1px solid {C['green']}", "borderRadius": "20px",
                    "padding": "6px 14px", "fontSize": "13px", "cursor": "pointer", "fontWeight": "600",
                }),
                html.Span("Every 30 seconds", style={"color": C["muted"], "fontSize": "13px"}),
                html.Div(id="refresh-ts", style={
                    "color": C["muted"], "fontSize": "13px", "marginLeft": "auto"
                }),
            ], style={"display": "flex", "gap": "12px", "alignItems": "center",
                      "marginTop": "16px", "flexWrap": "wrap"}),
        ], style={
            "backgroundColor": C["card"], "borderRadius": "12px",
            "padding": "20px", "border": f"1px solid {C['border']}",
            "marginBottom": "20px",
        }),

        
        html.Div([

            # Total Invested
            html.Div([
                html.Div([
                    html.Div("$", style={
                        "width": "40px", "height": "40px", "borderRadius": "50%",
                        "backgroundColor": "#1e3a5f", "color": C["blue"],
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "fontSize": "18px", "fontWeight": "bold",
                    }),
                    html.Div([
                        html.Div("Total Invested", style={"color": C["muted"], "fontSize": "13px"}),
                        html.Div("—", id="v-invested", style={
                            "fontSize": "24px", "fontWeight": "800", "color": C["text"],
                        }),
                    ]),
                ], style={"display": "flex", "gap": "12px", "alignItems": "center"}),
            ], style={
                "backgroundColor": C["card"], "borderRadius": "10px",
                "padding": "16px 20px", "border": f"1px solid {C['border']}", "flex": "1",
            }),

            
            html.Div(id="pnl-card", children=[
                html.Div([
                    html.Div("📈", style={
                        "width": "40px", "height": "40px", "borderRadius": "50%",
                        "backgroundColor": "#052e16", "color": C["green"],
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "fontSize": "18px",
                    }),
                    html.Div([
                        html.Div("Day P&L", style={"color": C["muted"], "fontSize": "13px"}),
                        html.Div("—", id="v-pnl", style={
                            "fontSize": "24px", "fontWeight": "800", "color": C["green"],
                        }),
                    ]),
                ], style={"display": "flex", "gap": "12px", "alignItems": "center"}),
            ], style={
                "backgroundColor": C["pnl_green"], "borderRadius": "10px",
                "padding": "16px 20px", "border": f"1px solid {C['green']}33", "flex": "1",
            }),

            
            html.Div([
                html.Div([
                    html.Div("🎯", style={
                        "width": "40px", "height": "40px", "borderRadius": "50%",
                        "backgroundColor": "#052e16", "color": C["green"],
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "fontSize": "18px",
                    }),
                    html.Div([
                        html.Div("Target Hits", style={"color": C["muted"], "fontSize": "13px"}),
                        html.Div("—", id="v-target", style={
                            "fontSize": "24px", "fontWeight": "800", "color": C["text"],
                        }),
                    ]),
                ], style={"display": "flex", "gap": "12px", "alignItems": "center"}),
            ], style={
                "backgroundColor": C["card"], "borderRadius": "10px",
                "padding": "16px 20px", "border": f"1px solid {C['border']}", "flex": "1",
            }),

            
            html.Div([
                html.Div([
                    html.Div("⚠️", style={
                        "width": "40px", "height": "40px", "borderRadius": "50%",
                        "backgroundColor": "#3b0a0a", "color": C["red"],
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "fontSize": "18px",
                    }),
                    html.Div([
                        html.Div("SL Hits", style={"color": C["muted"], "fontSize": "13px"}),
                        html.Div("—", id="v-sl", style={
                            "fontSize": "24px", "fontWeight": "800", "color": C["red"],
                        }),
                    ]),
                ], style={"display": "flex", "gap": "12px", "alignItems": "center"}),
            ], style={
                "backgroundColor": C["card"], "borderRadius": "10px",
                "padding": "16px 20px", "border": f"1px solid {C['border']}", "flex": "1",
            }),

            
            html.Div([
                html.Div([
                    html.Div("%", style={
                        "width": "40px", "height": "40px", "borderRadius": "50%",
                        "backgroundColor": "#451a03", "color": C["amber"],
                        "display": "flex", "alignItems": "center",
                        "justifyContent": "center", "fontSize": "16px", "fontWeight": "bold",
                    }),
                    html.Div([
                        html.Div("Win Rate", style={"color": C["muted"], "fontSize": "13px"}),
                        html.Div("—", id="v-wr", style={
                            "fontSize": "24px", "fontWeight": "800", "color": C["amber"],
                        }),
                        html.Div("—", id="v-wr-sub", style={
                            "color": C["muted"], "fontSize": "12px", "marginTop": "2px"
                        }),
                    ]),
                ], style={"display": "flex", "gap": "12px", "alignItems": "flex-start"}),
            ], style={
                "backgroundColor": C["card"], "borderRadius": "10px",
                "padding": "16px 20px", "border": f"1px solid {C['border']}", "flex": "1",
            }),

        ], style={
            "display": "flex", "gap": "12px", "marginBottom": "20px", "flexWrap": "wrap",
        }),

        
        html.Div([
            html.Div([
                html.Span("▽ Signal:", style={"color": C["muted"], "fontSize": "13px", "marginRight": "8px"}),
                html.Div(id="sig-tags", style={"display": "flex", "gap": "6px", "flexWrap": "wrap"}),
                html.Span("Result:", style={"color": C["muted"], "fontSize": "13px",
                                           "marginLeft": "20px", "marginRight": "8px"}),
                html.Div(id="res-tags", style={"display": "flex", "gap": "6px", "flexWrap": "wrap"}),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "6px"}),
        ], style={
            "backgroundColor": C["card"], "borderRadius": "10px",
            "padding": "14px 20px", "border": f"1px solid {C['border']}",
            "marginBottom": "20px",
        }),

        
        html.Div(id="trade-cards"),

    ], style={"maxWidth": "1200px", "margin": "0 auto", "padding": "28px 20px"}),

], style={
    "fontFamily": "'Inter','Segoe UI',sans-serif",
    "backgroundColor": C["bg"], "minHeight": "100vh", "color": C["text"],
})




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
    return trades, f"Last refresh: {now}"


@app.callback(
    Output("v-invested", "children"),
    Output("v-pnl",      "children"),
    Output("v-target",   "children"),
    Output("v-sl",       "children"),
    Output("v-wr",       "children"),
    Output("v-wr-sub",   "children"),
    Output("pnl-card",   "style"),
    Input("store-trades","data"),
)
def update_cards(trades):
    s = summarize(trades or [])
    pnl = s["pnl"]
    pnl_positive = pnl >= 0

    
    pnl_style = {
        "backgroundColor": C["pnl_green"] if pnl_positive else C["pnl_red"],
        "borderRadius": "10px", "padding": "16px 20px",
        "border": f"1px solid {(C['green'] if pnl_positive else C['red'])}33",
        "flex": "1",
    }

    wr_sub = f"{s['squared']} squared, {s['open_']} open"
    invested_fmt = fmt(s["invested"])
    # Remove leading + from invested
    if invested_fmt.startswith("+"): invested_fmt = invested_fmt[1:]

    return (
        invested_fmt,
        fmt(pnl),
        str(s["target"]),
        str(s["sl"]),
        f"{s['winrate']:.2f}%",
        wr_sub,
        pnl_style,
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
        tag_btn(f"All ({total})",    "all",  active == "all",  "sig"),
        tag_btn(f"↗ Buy ({buy})",   "buy",  active == "buy",  "sig"),
        tag_btn(f"↘ Sell ({sell})", "sell", active == "sell", "sig"),
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
    total = len(df)
    return [
        tag_btn(f"All",                        "all",     active == "all",     "res"),
        tag_btn(f"Target ({cnt('TARGET_HIT')})", "target", active == "target",  "res"),
        tag_btn(f"SL ({cnt('SL_HIT')})",        "sl",     active == "sl",      "res"),
        tag_btn(f"Squared ({cnt('SQUARED_OFF')})","squared",active == "squared","res"),
        tag_btn(f"Open ({cnt('OPEN')})",         "open",   active == "open",    "res"),
    ]


@app.callback(
    Output("store-sig", "data"),
    Input({"type": "tag-sig", "index": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def set_sig(clicks):
    ctx = callback_context
    if not ctx.triggered: return no_update
    return _json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["index"]


@app.callback(
    Output("store-res", "data"),
    Input({"type": "tag-res", "index": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def set_res(clicks):
    ctx = callback_context
    if not ctx.triggered: return no_update
    return _json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["index"]


@app.callback(
    Output("trade-cards", "children"),
    Input("store-trades", "data"),
    Input("store-sig",    "data"),
    Input("store-res",    "data"),
)
def update_cards_list(trades, sig_f, res_f):
    if not trades:
        return html.Div("No trades found. Select a date and click Load Trades.",
                        style={"color": C["muted"], "textAlign": "center",
                               "padding": "60px", "fontSize": "14px"})
    df = pd.DataFrame(trades)

    
    if sig_f != "all" and SIGNAL_COL in df.columns:
        df = df[df[SIGNAL_COL].str.upper() == sig_f.upper()]

    
    result_map = {"target": "TARGET_HIT", "sl": "SL_HIT",
                  "squared": "SQUARED_OFF", "open": "OPEN"}
    if res_f != "all" and RESULT_COL in df.columns:
        df = df[df[RESULT_COL].str.upper() == result_map.get(res_f, res_f).upper()]

    if df.empty:
        return html.Div("No trades match the selected filters.",
                        style={"color": C["muted"], "textAlign": "center", "padding": "40px"})

    return [trade_card(row.to_dict()) for _, row in df.iterrows()]


@app.callback(
    Output("store-ar", "data"),
    Output("btn-ar",   "children"),
    Output("btn-ar",   "style"),
    Output("iv",       "disabled"),
    Input("btn-ar",    "n_clicks"),
    State("store-ar",  "data"),
    prevent_initial_call=True,
)
def toggle_ar(n, on):
    new = not on
    if new:
        lbl = "🔄 Auto-refresh ON"
        s = {"backgroundColor": "#14532d", "color": C["green"],
             "border": f"1px solid {C['green']}", "borderRadius": "20px",
             "padding": "6px 14px", "fontSize": "13px", "cursor": "pointer", "fontWeight": "600"}
    else:
        lbl = "🔄 Auto-refresh OFF"
        s = {"backgroundColor": "#3b0a0a", "color": C["red"],
             "border": f"1px solid {C['red']}", "borderRadius": "20px",
             "padding": "6px 14px", "fontSize": "13px", "cursor": "pointer", "fontWeight": "600"}
    return new, lbl, s, not new


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
