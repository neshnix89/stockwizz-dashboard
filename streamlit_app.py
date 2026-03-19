"""
dashboard.py - Stock Wizz Live Dashboard
==========================================
Run: streamlit run dashboard.py
Deploy: Streamlit Cloud (free) or self-host on VPS

Shows:
- Portfolio overview (equity curve, total P&L)
- Active positions with live P&L
- Per-signal performance stats
- Trade history log
- Signal health monitoring
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Stock Wizz", page_icon="", layout="wide")

# =============================================================================
# PASSWORD PROTECTION
# =============================================================================
def check_password():
    """Simple password gate using Streamlit secrets."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if st.session_state.authenticated:
        return True
    
    st.title("Stock Wizz")
    st.markdown("Enter password to access dashboard.")
    password = st.text_input("Password", type="password")
    
    if password:
        try:
            correct = st.secrets["PASSWORD"]
        except:
            correct = os.getenv("PASSWORD", "stockwizz")
        
        if password == correct:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False

if not check_password():
    st.stop()

# =============================================================================
# SUPABASE CONNECTION
# =============================================================================
@st.cache_resource
def get_supabase():
    try:
        from supabase import create_client
        # Try Streamlit secrets first (cloud), then .env (local)
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        except:
            url = os.getenv('SUPABASE_URL', '')
            key = os.getenv('SUPABASE_KEY', '')
        if url and key:
            return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase connection failed: {e}")
    return None

supabase = get_supabase()

def fetch_table(table_name, order_by=None, limit=500):
    if not supabase:
        return pd.DataFrame()
    try:
        query = supabase.table(table_name).select('*')
        if order_by:
            query = query.order(order_by, desc=True)
        if limit:
            query = query.limit(limit)
        result = query.execute()
        return pd.DataFrame(result.data) if result.data else pd.DataFrame()
    except:
        return pd.DataFrame()


# =============================================================================
# SIDEBAR
# =============================================================================
st.sidebar.title("Stock Wizz")
st.sidebar.markdown("*10-Signal Trading System*")
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Active Positions",
    "Signal Performance",
    "Forward Testing",
    "Trade History",
    "Signal Health",
    "Scanner Log",
])

# Signal color map
SIGNAL_COLORS = {
    'S4_InsiderClusters': '#FF6B6B',
    'S5_VolPriceDivergence': '#4ECDC4',
    'S6_NeglectedFirm': '#45B7D1',
    'S7_CongressCluster': '#96CEB4',
    'S8_Activist13D': '#FFEAA7',
    'S9_8KSevereDip': '#DDA0DD',
    'S12_GovContracts': '#98D8C8',
    'S13_UnusualOptions': '#F7DC6F',
    'S18_ShortCovering': '#BB8FCE',
    'S20_SympathyDip': '#85C1E9',
}


# =============================================================================
# PAGE: OVERVIEW
# =============================================================================
if page == "Overview":
    st.title("Portfolio Overview")

    # Key metrics row
    trades_df = fetch_table('trades', 'closed_at')
    positions_df = fetch_table('positions')
    equity_df = fetch_table('equity_snapshots', 'snapshot_date')

    open_pos = positions_df[positions_df['status'] == 'open'] if len(positions_df) > 0 else pd.DataFrame()

    col1, col2, col3, col4, col5 = st.columns(5)

    total_pnl = trades_df['net_pnl'].sum() if len(trades_df) > 0 else 0
    total_trades = len(trades_df)
    win_rate = (trades_df['return_pct'] > 0).mean() * 100 if len(trades_df) > 0 else 0
    open_count = len(open_pos)
    unrealized = open_pos['unrealized_pnl'].sum() if len(open_pos) > 0 and 'unrealized_pnl' in open_pos.columns else 0

    col1.metric("Total P&L", f"${total_pnl:+,.2f}", delta=f"{total_trades} trades")
    col2.metric("Win Rate", f"{win_rate:.1f}%")
    col3.metric("Open Positions", f"{open_count}")
    col4.metric("Unrealized P&L", f"${unrealized:+,.2f}")
    col5.metric("Total (Realized + Open)", f"${total_pnl + unrealized:+,.2f}")

    # Equity curve
    if len(equity_df) > 0:
        st.subheader("Equity Curve")
        equity_df['snapshot_date'] = pd.to_datetime(equity_df['snapshot_date'])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=equity_df['snapshot_date'],
            y=equity_df['total_equity'],
            mode='lines+markers',
            name='Equity',
            line=dict(color='#4ECDC4', width=2),
            fill='tozeroy',
            fillcolor='rgba(78, 205, 196, 0.1)',
        ))
        fig.update_layout(height=400, template='plotly_dark',
                         xaxis_title='Date', yaxis_title='Equity ($)')
        st.plotly_chart(fig, use_container_width=True)

    # Cumulative P&L by signal
    if len(trades_df) > 0:
        st.subheader("P&L by Signal")
        signal_pnl = trades_df.groupby('signal_name')['net_pnl'].sum().sort_values(ascending=False)
        fig = px.bar(
            x=signal_pnl.index,
            y=signal_pnl.values,
            color=signal_pnl.values,
            color_continuous_scale=['#FF6B6B', '#FFEAA7', '#4ECDC4'],
            labels={'x': 'Signal', 'y': 'Net P&L ($)'},
        )
        fig.update_layout(height=350, template='plotly_dark', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Monthly P&L
    if len(trades_df) > 0:
        st.subheader("Monthly P&L")
        trades_df['month'] = pd.to_datetime(trades_df['closed_at']).dt.to_period('M').astype(str)
        monthly = trades_df.groupby('month')['net_pnl'].sum()
        colors = ['#4ECDC4' if v >= 0 else '#FF6B6B' for v in monthly.values]
        fig = go.Figure(go.Bar(x=monthly.index, y=monthly.values, marker_color=colors))
        fig.update_layout(height=300, template='plotly_dark',
                         xaxis_title='Month', yaxis_title='P&L ($)')
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# PAGE: ACTIVE POSITIONS
# =============================================================================
elif page == "Active Positions":
    st.title("Active Positions")

    positions_df = fetch_table('positions')
    open_pos = positions_df[positions_df['status'] == 'open'] if len(positions_df) > 0 else pd.DataFrame()

    if len(open_pos) == 0:
        st.info("No open positions.")
    else:
        for _, pos in open_pos.iterrows():
            entry = pos.get('entry_price', 0)
            current = pos.get('current_price', entry)
            pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            pnl_dollar = (current - entry) * pos.get('shares', 0)
            days_left = (pd.to_datetime(pos.get('target_exit_date', datetime.now())) - pd.Timestamp(datetime.now())).days

            color = "#4ECDC4" if pnl_pct >= 0 else "#FF6B6B"

            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                col1.markdown(f"**{pos.get('ticker', '?')}**")
                col2.markdown(f"*{pos.get('signal_name', '')}*")
                col3.markdown(f"Entry: ${entry:.2f}")
                col4.markdown(f"Current: ${current:.2f}")
                col5.markdown(f"<span style='color:{color}'>{pnl_pct:+.1f}% (${pnl_dollar:+.2f})</span>",
                             unsafe_allow_html=True)
                col6.markdown(f"{days_left}d left")
                st.divider()


# =============================================================================
# PAGE: SIGNAL PERFORMANCE
# =============================================================================
elif page == "Signal Performance":
    st.title("Signal Performance")

    stats_df = fetch_table('strategy_stats')
    trades_df = fetch_table('trades', 'closed_at')

    if len(stats_df) > 0:
        st.subheader("Per-Signal Statistics")

        for _, row in stats_df.iterrows():
            signal = row.get('signal_name', '')
            color = SIGNAL_COLORS.get(signal, '#888888')

            with st.expander(f"{signal} — PF: {row.get('profit_factor', 0):.2f} | "
                            f"Trades: {row.get('total_trades', 0)} | "
                            f"P&L: ${row.get('total_pnl', 0):+,.2f}"):

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Live PF", f"{row.get('profit_factor', 0):.2f}",
                           delta=f"Backtest: {row.get('backtest_pf', 0):.2f}")
                col2.metric("Hit Rate", f"{row.get('hit_rate', 0):.1f}%",
                           delta=f"Backtest: {row.get('backtest_hit_rate', 0):.1f}%")
                col3.metric("Expectancy", f"{row.get('expectancy_pct', 0):+.2f}%",
                           delta=f"Backtest: {row.get('backtest_expectancy', 0):+.2f}%")
                col4.metric("Total P&L", f"${row.get('total_pnl', 0):+,.2f}")

                # Signal trade history
                if len(trades_df) > 0:
                    sig_trades = trades_df[trades_df['signal_name'] == signal]
                    if len(sig_trades) > 0:
                        sig_trades['closed_at'] = pd.to_datetime(sig_trades['closed_at'])
                        fig = go.Figure()
                        cum_pnl = sig_trades.sort_values('closed_at')['net_pnl'].cumsum()
                        fig.add_trace(go.Scatter(
                            x=sig_trades.sort_values('closed_at')['closed_at'],
                            y=cum_pnl,
                            mode='lines',
                            line=dict(color=color, width=2),
                            fill='tozeroy',
                        ))
                        fig.update_layout(height=200, template='plotly_dark',
                                         margin=dict(l=0, r=0, t=0, b=0))
                        st.plotly_chart(fig, use_container_width=True)

                health = "Healthy" if row.get('is_healthy', True) else "UNHEALTHY"
                st.markdown(f"Status: **{health}** | "
                           f"Last trade: {row.get('last_trade_at', 'Never')}")


# =============================================================================
# PAGE: FORWARD TESTING
# =============================================================================
elif page == "Forward Testing":
    st.title("Forward Testing — Live vs Backtest")
    st.markdown("*Tracking every signal's real-world performance against backtest expectations.*")

    trades_df = fetch_table('trades', 'closed_at', limit=2000)
    stats_df = fetch_table('strategy_stats')
    signals_df = fetch_table('signals', 'detected_at', limit=2000)
    positions_df = fetch_table('positions')

    # Backtest benchmarks
    BACKTEST = {
        'S4_InsiderClusters':    {'pf': 3.32, 'hit': 59.3, 'exp': 9.90, 'trades_3yr': 27},
        'S5_VolPriceDivergence': {'pf': 1.71, 'hit': 53.5, 'exp': 1.98, 'trades_3yr': 318},
        'S6_NeglectedFirm':     {'pf': 1.71, 'hit': 47.2, 'exp': 7.18, 'trades_3yr': 339},
        'S7_CongressCluster':    {'pf': 2.46, 'hit': 63.0, 'exp': 4.66, 'trades_3yr': 1350},
        'S8_Activist13D':        {'pf': 2.07, 'hit': 53.3, 'exp': 3.11, 'trades_3yr': 105},
        'S9_8KSevereDip':        {'pf': 1.62, 'hit': 49.8, 'exp': 2.89, 'trades_3yr': 99},
        'S12_GovContracts':      {'pf': 2.80, 'hit': 65.2, 'exp': 4.92, 'trades_3yr': 1070},
        'S13_UnusualOptions':    {'pf': 1.31, 'hit': 52.2, 'exp': 1.58, 'trades_3yr': 312},
        'S18_ShortCovering':     {'pf': 1.77, 'hit': 53.0, 'exp': 2.91, 'trades_3yr': 132},
        'S20_SympathyDip':       {'pf': 1.59, 'hit': 55.4, 'exp': 2.34, 'trades_3yr': 408},
    }

    # --- Overall Forward Test Summary ---
    st.subheader("Overall Forward Test Progress")

    if len(trades_df) > 0:
        total_live_trades = len(trades_df)
        total_live_pnl = trades_df['net_pnl'].sum()
        live_win_rate = (trades_df['return_pct'] > 0).mean() * 100
        live_winners = trades_df[trades_df['return_pct'] > 0]
        live_losers = trades_df[trades_df['return_pct'] <= 0]
        live_gross_profit = live_winners['return_pct'].sum() if len(live_winners) > 0 else 0
        live_gross_loss = abs(live_losers['return_pct'].sum()) if len(live_losers) > 0 else 0.001
        live_pf = round(live_gross_profit / live_gross_loss, 2)

        days_testing = 0
        if 'closed_at' in trades_df.columns:
            trades_df['closed_at'] = pd.to_datetime(trades_df['closed_at'])
            days_testing = (trades_df['closed_at'].max() - trades_df['closed_at'].min()).days

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Days Testing", f"{days_testing}")
        col2.metric("Live Trades", f"{total_live_trades}")
        col3.metric("Live PF", f"{live_pf}")
        col4.metric("Live Win Rate", f"{live_win_rate:.1f}%")
        col5.metric("Live P&L", f"${total_live_pnl:+,.2f}")

        # Progress bar: need 20 trades per signal for statistical significance
        min_trades_needed = 20
        signals_with_enough = sum(
            1 for s in BACKTEST.keys()
            if len(trades_df[trades_df['signal_name'] == s]) >= min_trades_needed
        )
        st.progress(signals_with_enough / len(BACKTEST),
                    text=f"Signals validated: {signals_with_enough}/{len(BACKTEST)} "
                         f"(need {min_trades_needed}+ trades each)")
    else:
        st.info("No closed trades yet. Run the scanner daily to start building forward test data.")

    # --- Per-Signal Forward Test Cards ---
    st.subheader("Per-Signal Comparison: Live vs Backtest")

    # Signal selector
    signal_filter = st.selectbox("Filter Signal",
                                  ["All Signals"] + sorted(BACKTEST.keys()))

    signals_to_show = [signal_filter] if signal_filter != "All Signals" else sorted(BACKTEST.keys())

    for signal_name in signals_to_show:
        bt = BACKTEST.get(signal_name, {})
        color = SIGNAL_COLORS.get(signal_name, '#888888')

        # Live stats for this signal
        if len(trades_df) > 0:
            sig_trades = trades_df[trades_df['signal_name'] == signal_name]
        else:
            sig_trades = pd.DataFrame()

        live_count = len(sig_trades)
        if live_count > 0:
            live_winners = sig_trades[sig_trades['return_pct'] > 0]
            live_losers = sig_trades[sig_trades['return_pct'] <= 0]
            live_hit = round(len(live_winners) / live_count * 100, 1)
            live_gp = live_winners['return_pct'].sum() if len(live_winners) > 0 else 0
            live_gl = abs(live_losers['return_pct'].sum()) if len(live_losers) > 0 else 0.001
            live_pf = round(live_gp / live_gl, 2)
            live_exp = round(sig_trades['return_pct'].mean(), 2)
            live_total_pnl = round(sig_trades['net_pnl'].sum(), 2)
            live_avg_win = round(live_winners['return_pct'].mean(), 2) if len(live_winners) > 0 else 0
            live_avg_loss = round(live_losers['return_pct'].mean(), 2) if len(live_losers) > 0 else 0
        else:
            live_hit = live_pf = live_exp = live_total_pnl = 0
            live_avg_win = live_avg_loss = 0

        # Open positions count
        open_count = 0
        if len(positions_df) > 0:
            open_count = len(positions_df[
                (positions_df['signal_name'] == signal_name) &
                (positions_df['status'] == 'open')
            ])

        # Signals detected (including non-executed)
        detected_count = 0
        if len(signals_df) > 0:
            detected_count = len(signals_df[signals_df['signal_name'] == signal_name])

        # Status determination
        if live_count == 0:
            status_emoji = "⏳"
            status_text = "Waiting for data"
        elif live_count < 20:
            status_emoji = "🔄"
            status_text = f"Collecting ({live_count}/20 trades)"
        elif live_pf >= bt.get('pf', 1.0) * 0.7:
            status_emoji = "✅"
            status_text = "Performing as expected"
        elif live_pf >= 1.0:
            status_emoji = "⚠️"
            status_text = "Below backtest but profitable"
        else:
            status_emoji = "🚫"
            status_text = "UNDERPERFORMING — review needed"

        with st.expander(
            f"{status_emoji} {signal_name} — "
            f"Live PF: {live_pf} vs Backtest PF: {bt.get('pf', '?')} | "
            f"Trades: {live_count} | P&L: ${live_total_pnl:+,.2f}"
        ):
            # Comparison table
            comp_data = {
                'Metric': ['Profit Factor', 'Hit Rate', 'Expectancy/Trade', 
                          'Avg Win', 'Avg Loss', 'Total Trades', 'Total P&L'],
                'Backtest': [
                    f"{bt.get('pf', 0):.2f}",
                    f"{bt.get('hit', 0):.1f}%",
                    f"{bt.get('exp', 0):+.2f}%",
                    '—',
                    '—',
                    f"{bt.get('trades_3yr', 0)} (3yr)",
                    '—',
                ],
                'Live': [
                    f"{live_pf:.2f}",
                    f"{live_hit:.1f}%",
                    f"{live_exp:+.2f}%",
                    f"{live_avg_win:+.2f}%",
                    f"{live_avg_loss:+.2f}%",
                    f"{live_count}",
                    f"${live_total_pnl:+,.2f}",
                ],
                'Status': [
                    "✅" if live_count < 5 or live_pf >= bt.get('pf', 1) * 0.7 else "⚠️",
                    "✅" if live_count < 5 or live_hit >= bt.get('hit', 50) * 0.8 else "⚠️",
                    "✅" if live_count < 5 or live_exp >= 0 else "🚫",
                    "—",
                    "—",
                    f"{'✅' if live_count >= 20 else f'{live_count}/20'}",
                    "✅" if live_total_pnl >= 0 else "⚠️",
                ],
            }
            st.table(pd.DataFrame(comp_data))

            # Additional stats
            col1, col2, col3 = st.columns(3)
            col1.metric("Open Positions", open_count)
            col2.metric("Signals Detected", detected_count)
            col3.markdown(f"**Verdict:** {status_text}")

            # Trade-by-trade log for this signal
            if live_count > 0:
                st.markdown("**Trade Log:**")
                log_cols = ['closed_at', 'ticker', 'entry_price', 'exit_price',
                           'return_pct', 'net_pnl', 'hold_days']
                available = [c for c in log_cols if c in sig_trades.columns]
                st.dataframe(
                    sig_trades[available].sort_values('closed_at', ascending=False),
                    use_container_width=True,
                    height=min(len(sig_trades) * 40 + 40, 300),
                )

                # Cumulative P&L chart
                sig_sorted = sig_trades.sort_values('closed_at')
                cum_pnl = sig_sorted['net_pnl'].cumsum()
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=sig_sorted['closed_at'],
                    y=cum_pnl,
                    mode='lines+markers',
                    line=dict(color=color, width=2),
                    fill='tozeroy',
                    fillcolor=f'rgba{tuple(list(int(color.lstrip("#")[i:i+2], 16) for i in (0,2,4)) + [0.1])}',
                    name='Cumulative P&L',
                ))
                fig.add_hline(y=0, line_dash="dash", line_color="gray")
                fig.update_layout(
                    height=250, template='plotly_dark',
                    margin=dict(l=0, r=0, t=30, b=0),
                    title=f'{signal_name} Cumulative P&L',
                    yaxis_title='P&L ($)',
                )
                st.plotly_chart(fig, use_container_width=True)

    # --- Forward Test Scorecard ---
    st.subheader("Forward Test Scorecard")
    st.markdown("*How each signal compares to its backtest after live trading.*")

    scorecard = []
    for signal_name, bt in BACKTEST.items():
        if len(trades_df) > 0:
            sig_trades = trades_df[trades_df['signal_name'] == signal_name]
            live_count = len(sig_trades)
            if live_count > 0:
                live_w = sig_trades[sig_trades['return_pct'] > 0]
                live_l = sig_trades[sig_trades['return_pct'] <= 0]
                gp = live_w['return_pct'].sum() if len(live_w) > 0 else 0
                gl = abs(live_l['return_pct'].sum()) if len(live_l) > 0 else 0.001
                live_pf = round(gp / gl, 2)
                live_hit = round(len(live_w) / live_count * 100, 1)
                pnl = round(sig_trades['net_pnl'].sum(), 2)
            else:
                live_pf = live_hit = pnl = 0
        else:
            live_count = 0
            live_pf = live_hit = pnl = 0

        pf_ratio = round(live_pf / bt['pf'] * 100, 0) if bt['pf'] > 0 and live_pf > 0 else 0

        scorecard.append({
            'Signal': signal_name,
            'BT PF': bt['pf'],
            'Live PF': live_pf,
            'PF Ratio': f"{pf_ratio:.0f}%",
            'BT Hit%': f"{bt['hit']:.1f}%",
            'Live Hit%': f"{live_hit:.1f}%",
            'Live Trades': live_count,
            'P&L': f"${pnl:+,.2f}",
            'Grade': '✅' if live_count < 10 or live_pf >= bt['pf'] * 0.7
                     else ('⚠️' if live_pf >= 1.0 else '🚫'),
        })

    sc_df = pd.DataFrame(scorecard)
    st.dataframe(sc_df, use_container_width=True, height=450)

    # Summary stats
    if len(trades_df) > 0:
        st.subheader("Forward Test Summary")
        col1, col2, col3, col4 = st.columns(4)

        passing = sum(1 for s in scorecard if s['Grade'] == '✅')
        warning = sum(1 for s in scorecard if s['Grade'] == '⚠️')
        failing = sum(1 for s in scorecard if s['Grade'] == '🚫')

        col1.metric("Passing", f"{passing}/10", delta="signals on track")
        col2.metric("Warning", f"{warning}/10",
                    delta="below backtest" if warning > 0 else None,
                    delta_color="off")
        col3.metric("Failing", f"{failing}/10",
                    delta="need review" if failing > 0 else None,
                    delta_color="inverse")

        total_fwd_pnl = trades_df['net_pnl'].sum()
        col4.metric("Total Forward P&L", f"${total_fwd_pnl:+,.2f}")


# =============================================================================
# PAGE: TRADE HISTORY
# =============================================================================
elif page == "Trade History":
    st.title("Trade History")

    trades_df = fetch_table('trades', 'closed_at')

    if len(trades_df) == 0:
        st.info("No closed trades yet.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        signals = ['All'] + sorted(trades_df['signal_name'].unique().tolist())
        selected_signal = col1.selectbox("Signal", signals)
        selected_result = col2.selectbox("Result", ['All', 'Winners', 'Losers'])

        if selected_signal != 'All':
            trades_df = trades_df[trades_df['signal_name'] == selected_signal]
        if selected_result == 'Winners':
            trades_df = trades_df[trades_df['return_pct'] > 0]
        elif selected_result == 'Losers':
            trades_df = trades_df[trades_df['return_pct'] <= 0]

        # Summary metrics
        if len(trades_df) > 0:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Trades", len(trades_df))
            col2.metric("Win Rate", f"{(trades_df['return_pct'] > 0).mean()*100:.1f}%")
            col3.metric("Avg Return", f"{trades_df['return_pct'].mean():+.2f}%")
            col4.metric("Total P&L", f"${trades_df['net_pnl'].sum():+,.2f}")

        # Table
        display_cols = ['closed_at', 'signal_name', 'ticker', 'entry_price',
                       'exit_price', 'return_pct', 'net_pnl', 'hold_days']
        available_cols = [c for c in display_cols if c in trades_df.columns]
        st.dataframe(
            trades_df[available_cols].sort_values('closed_at', ascending=False),
            use_container_width=True,
            height=500,
        )


# =============================================================================
# PAGE: SIGNAL HEALTH
# =============================================================================
elif page == "Signal Health":
    st.title("Signal Health Monitor")
    st.markdown("*Compares live performance vs backtest. Flags signals that have degraded.*")

    stats_df = fetch_table('strategy_stats')

    if len(stats_df) == 0:
        st.info("No strategy stats yet. Run the scanner to populate.")
    else:
        for _, row in stats_df.iterrows():
            signal = row.get('signal_name', '')
            live_pf = row.get('profit_factor', 0)
            bt_pf = row.get('backtest_pf', 1)
            is_healthy = row.get('is_healthy', True)
            total_trades = row.get('total_trades', 0)

            pf_ratio = (live_pf / bt_pf * 100) if bt_pf > 0 else 0

            if not is_healthy:
                st.error(f"**{signal}** — DEGRADED | Live PF: {live_pf:.2f} vs "
                        f"Backtest PF: {bt_pf:.2f} ({pf_ratio:.0f}%) | "
                        f"Trades: {total_trades}")
            elif total_trades < 10:
                st.warning(f"**{signal}** — INSUFFICIENT DATA | "
                          f"Trades: {total_trades} (need 20+)")
            else:
                st.success(f"**{signal}** — HEALTHY | Live PF: {live_pf:.2f} vs "
                          f"Backtest PF: {bt_pf:.2f} ({pf_ratio:.0f}%) | "
                          f"Trades: {total_trades}")


# =============================================================================
# PAGE: SCANNER LOG
# =============================================================================
elif page == "Scanner Log":
    st.title("Scanner Run Log")

    runs_df = fetch_table('scanner_runs', 'run_at')

    if len(runs_df) == 0:
        st.info("No scanner runs logged yet.")
    else:
        st.dataframe(runs_df, use_container_width=True, height=500)

        # Signals found over time
        if 'run_at' in runs_df.columns:
            runs_df['run_at'] = pd.to_datetime(runs_df['run_at'])
            fig = px.line(runs_df, x='run_at', y='signals_found',
                         title='Signals Found Per Run')
            fig.update_layout(template='plotly_dark')
            st.plotly_chart(fig, use_container_width=True)


# Footer
st.sidebar.markdown("---")
st.sidebar.markdown(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.markdown(f"[Refresh](/) to update data")
