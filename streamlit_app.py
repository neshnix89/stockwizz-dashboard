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
