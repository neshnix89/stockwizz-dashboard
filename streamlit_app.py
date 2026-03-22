"""
Stock Wizz Dashboard v2
========================
Clear split: Forward Testing vs Live Trading
Rich charts and visual analytics
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

st.set_page_config(page_title="Stock Wizz", page_icon="📊", layout="wide")

# =============================================================================
# PASSWORD
# =============================================================================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated:
        return True
    st.title("📊 Stock Wizz")
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
# SUPABASE
# =============================================================================
@st.cache_resource
def get_supabase():
    try:
        from supabase import create_client
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

# Debug connection
if supabase:
    st.sidebar.success("DB Connected")
    try:
        test = supabase.table('signals').select('id').limit(1).execute()
        st.sidebar.info(f"Signals rows: {len(test.data)}")
    except Exception as e:
        st.sidebar.error(f"Query error: {e}")
else:
    st.sidebar.error("DB Not Connected")

def fetch_table(table_name, order_by=None, limit=2000):
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
# CONSTANTS
# =============================================================================
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

SIGNAL_DESCRIPTIONS = {
    'S4_InsiderClusters': 'Company insiders (CEO, CFO, directors) buying stock with their own money. 2+ insiders buying within 14 days = they know something good is coming.',
    'S5_VolPriceDivergence': 'Trading volume rising 1.5x+ while stock price stays flat. Someone is quietly accumulating shares before a move. Blocked in bear markets.',
    'S6_NeglectedFirm': 'Stocks with 2 or fewer analysts covering them. Less coverage = less efficient pricing = more opportunity. Blocked in bear markets.',
    'S7_CongressCluster': '2+ US politicians buying the same stock within 14 days. Politicians have access to non-public policy information that affects stock prices.',
    'S8_Activist13D': 'An activist investor files SEC 13D (5%+ ownership stake). They plan to push for changes that unlock value. Quick 5-day trade on the announcement pop.',
    'S9_8KSevereDip': 'Company files an 8-K (material event) AND stock drops >10%. Market overreacts to bad news — mean reversion trade.',
    'S12_GovContracts': 'Company wins a government contract >$10M. Government contracts = guaranteed revenue with zero credit risk. Stock drifts higher for weeks.',
    'S13_UnusualOptions': 'Stock volume spikes 2x+ above normal with a positive close. Smart money is positioning before a move.',
    'S18_ShortCovering': 'Stock down 15%+ from high, then suddenly volume spikes 2x with a green candle. Short sellers are covering = forced buying = reversal.',
    'S20_SympathyDip': 'One stock in a sector crashes >10%, peers drop 3-8% in sympathy even though the bad news doesnt affect them. Buy the innocent bystanders.',
}

BACKTEST = {
    'S4_InsiderClusters':    {'pf': 3.32, 'hit': 59.3, 'exp': 9.90, 'hold': 40, 'trades': 27},
    'S5_VolPriceDivergence': {'pf': 1.71, 'hit': 53.5, 'exp': 1.98, 'hold': 10, 'trades': 318},
    'S6_NeglectedFirm':     {'pf': 1.71, 'hit': 47.2, 'exp': 7.18, 'hold': 60, 'trades': 339},
    'S7_CongressCluster':    {'pf': 2.46, 'hit': 63.0, 'exp': 4.66, 'hold': 40, 'trades': 1350},
    'S8_Activist13D':        {'pf': 2.07, 'hit': 53.3, 'exp': 3.11, 'hold': 5, 'trades': 105},
    'S9_8KSevereDip':        {'pf': 1.62, 'hit': 49.8, 'exp': 2.89, 'hold': 10, 'trades': 99},
    'S12_GovContracts':      {'pf': 2.80, 'hit': 65.2, 'exp': 4.92, 'hold': 40, 'trades': 1070},
    'S13_UnusualOptions':    {'pf': 1.31, 'hit': 52.2, 'exp': 1.58, 'hold': 20, 'trades': 312},
    'S18_ShortCovering':     {'pf': 1.77, 'hit': 53.0, 'exp': 2.91, 'hold': 10, 'trades': 132},
    'S20_SympathyDip':       {'pf': 1.59, 'hit': 55.4, 'exp': 2.34, 'hold': 10, 'trades': 408},
}

# =============================================================================
# HELPER
# =============================================================================
def calc_pf(returns):
    winners = returns[returns > 0]
    losers = returns[returns <= 0]
    gp = winners.sum() if len(winners) > 0 else 0
    gl = abs(losers.sum()) if len(losers) > 0 else 0.001
    return round(gp / gl, 2)

# =============================================================================
# SIDEBAR
# =============================================================================
st.sidebar.title("📊 Stock Wizz")

mode = st.sidebar.radio("Mode", ["Forward Testing", "Live Trading"])
st.sidebar.markdown("---")

if mode == "Forward Testing":
    page = st.sidebar.radio("Navigate", [
        "FT Dashboard",
        "FT Signal Scorecard",
        "FT Signal Deep Dive",
        "FT Trade Log",
        "FT Convergence Analysis",
        "Scanner Log",
    ])
else:
    page = st.sidebar.radio("Navigate", [
        "Live Dashboard",
        "Live Positions",
        "Live Trade History",
        "Live Signal Performance",
    ])

st.sidebar.markdown("---")
st.sidebar.markdown(f"Updated: {datetime.now().strftime('%H:%M:%S')}")
st.sidebar.markdown("[Refresh](/)")


# =============================================================================
# FORWARD TESTING: DASHBOARD
# =============================================================================
if page == "FT Dashboard":
    st.title("📋 Forward Testing Dashboard")
    st.markdown("*Tracking all signals in paper mode to validate backtest results.*")

    trades_df = fetch_table('trades', 'closed_at')
    positions_df = fetch_table('positions')
    signals_df = fetch_table('signals', 'detected_at')

    open_pos = positions_df[positions_df['status'] == 'open'] if len(positions_df) > 0 else pd.DataFrame()

    # Key metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    total_signals = len(signals_df) if len(signals_df) > 0 else 0
    total_trades = len(trades_df) if len(trades_df) > 0 else 0
    open_count = len(open_pos)
    total_pnl = trades_df['net_pnl'].sum() if len(trades_df) > 0 else 0
    win_rate = (trades_df['return_pct'] > 0).mean() * 100 if len(trades_df) > 0 else 0
    live_pf = calc_pf(trades_df['return_pct']) if len(trades_df) > 0 else 0

    col1.metric("Signals Detected", total_signals)
    col2.metric("Trades Closed", total_trades)
    col3.metric("Open Positions", open_count)
    col4.metric("Paper P&L", f"${total_pnl:+,.2f}")
    col5.metric("Win Rate", f"{win_rate:.1f}%")
    col6.metric("Live PF", f"{live_pf:.2f}")

    # Validation progress
    st.subheader("Validation Progress")
    min_trades = 20
    if len(trades_df) > 0:
        validated = sum(
            1 for s in BACKTEST
            if len(trades_df[trades_df['signal_name'] == s]) >= min_trades
        )
    else:
        validated = 0
    st.progress(validated / len(BACKTEST),
                text=f"{validated}/{len(BACKTEST)} signals have {min_trades}+ trades (statistically significant)")

    # Signal distribution pie chart
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Signals Detected by Type")
        if len(signals_df) > 0 and 'signal_name' in signals_df.columns:
            sig_counts = signals_df['signal_name'].value_counts()
            colors = [SIGNAL_COLORS.get(s, '#888') for s in sig_counts.index]
            fig = go.Figure(go.Pie(
                labels=sig_counts.index,
                values=sig_counts.values,
                marker=dict(colors=colors),
                hole=0.4,
                textinfo='label+value',
            ))
            fig.update_layout(height=350, template='plotly_dark', showlegend=False,
                              margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No signals detected yet.")

    with col_right:
        st.subheader("Open Positions by Signal")
        if len(open_pos) > 0 and 'signal_name' in open_pos.columns:
            pos_counts = open_pos['signal_name'].value_counts()
            colors = [SIGNAL_COLORS.get(s, '#888') for s in pos_counts.index]
            fig = go.Figure(go.Pie(
                labels=pos_counts.index,
                values=pos_counts.values,
                marker=dict(colors=colors),
                hole=0.4,
                textinfo='label+value',
            ))
            fig.update_layout(height=350, template='plotly_dark', showlegend=False,
                              margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No open positions.")

    # P&L by signal (bar chart)
    if len(trades_df) > 0:
        st.subheader("Paper P&L by Signal")
        signal_pnl = trades_df.groupby('signal_name').agg(
            pnl=('net_pnl', 'sum'),
            trades=('net_pnl', 'count'),
            avg_ret=('return_pct', 'mean'),
        ).sort_values('pnl', ascending=False)

        colors = ['#4ECDC4' if v >= 0 else '#FF6B6B' for v in signal_pnl['pnl']]
        fig = go.Figure(go.Bar(
            x=signal_pnl.index,
            y=signal_pnl['pnl'],
            marker_color=colors,
            text=[f"${v:+,.0f}<br>{int(t)} trades" for v, t in zip(signal_pnl['pnl'], signal_pnl['trades'])],
            textposition='outside',
        ))
        fig.update_layout(height=400, template='plotly_dark',
                          xaxis_title='Signal', yaxis_title='Paper P&L ($)')
        st.plotly_chart(fig, use_container_width=True)

    # Cumulative P&L over time
    if len(trades_df) > 0 and 'closed_at' in trades_df.columns:
        st.subheader("Cumulative Paper P&L Over Time")
        trades_df['closed_at'] = pd.to_datetime(trades_df['closed_at'])
        sorted_trades = trades_df.sort_values('closed_at')
        sorted_trades['cum_pnl'] = sorted_trades['net_pnl'].cumsum()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sorted_trades['closed_at'], y=sorted_trades['cum_pnl'],
            mode='lines', line=dict(color='#4ECDC4', width=2),
            fill='tozeroy', fillcolor='rgba(78,205,196,0.1)',
            name='Cumulative P&L',
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=350, template='plotly_dark',
                          xaxis_title='Date', yaxis_title='P&L ($)')
        st.plotly_chart(fig, use_container_width=True)

    # Recent activity
    st.subheader("Recent Positions")
    if len(open_pos) > 0:
        display_cols = ['signal_name', 'ticker', 'entry_price', 'shares',
                       'entry_date', 'target_exit_date', 'allocation_pct']
        available = [c for c in display_cols if c in open_pos.columns]
        st.dataframe(open_pos[available].head(20), use_container_width=True)
    else:
        st.info("No open positions.")


# =============================================================================
# FORWARD TESTING: SIGNAL SCORECARD
# =============================================================================
elif page == "FT Signal Scorecard":
    st.title("📊 Signal Scorecard — Live vs Backtest")
    st.markdown("*Side-by-side comparison of every signal's forward test results against backtest.*")

    with st.expander("📖 What does each signal mean?"):
        for sig, desc in SIGNAL_DESCRIPTIONS.items():
            color = SIGNAL_COLORS.get(sig, '#888')
            st.markdown(f"**{sig}** — {desc}")
    
    trades_df = fetch_table('trades', 'closed_at')

    # Build scorecard
    scorecard = []
    for signal_name, bt in BACKTEST.items():
        if len(trades_df) > 0:
            sig = trades_df[trades_df['signal_name'] == signal_name]
            live_count = len(sig)
            if live_count > 0:
                live_pf = calc_pf(sig['return_pct'])
                live_hit = round((sig['return_pct'] > 0).mean() * 100, 1)
                live_exp = round(sig['return_pct'].mean(), 2)
                live_pnl = round(sig['net_pnl'].sum(), 2)
            else:
                live_pf = live_hit = live_exp = live_pnl = 0
        else:
            live_count = live_pf = live_hit = live_exp = live_pnl = 0

        pf_ratio = round(live_pf / bt['pf'] * 100) if bt['pf'] > 0 and live_pf > 0 else 0

        if live_count == 0:
            grade = '⏳'
        elif live_count < 20:
            grade = '🔄'
        elif live_pf >= bt['pf'] * 0.7:
            grade = '✅'
        elif live_pf >= 1.0:
            grade = '⚠️'
        else:
            grade = '🚫'

        scorecard.append({
            'Signal': signal_name,
            'Grade': grade,
            'BT PF': bt['pf'],
            'Live PF': live_pf,
            'PF Match': f"{pf_ratio}%",
            'BT Hit%': f"{bt['hit']}%",
            'Live Hit%': f"{live_hit}%",
            'BT Exp': f"{bt['exp']:+.2f}%",
            'Live Exp': f"{live_exp:+.2f}%",
            'Trades': f"{live_count}/20",
            'P&L': f"${live_pnl:+,.2f}",
        })

    sc_df = pd.DataFrame(scorecard)
    st.dataframe(sc_df, use_container_width=True, height=450)

    # Visual comparison: backtest vs live PF
    st.subheader("Profit Factor: Backtest vs Live")
    fig = go.Figure()
    signals = [s['Signal'] for s in scorecard]
    bt_pfs = [s['BT PF'] for s in scorecard]
    live_pfs = [s['Live PF'] for s in scorecard]

    fig.add_trace(go.Bar(name='Backtest PF', x=signals, y=bt_pfs,
                         marker_color='rgba(78,205,196,0.5)'))
    fig.add_trace(go.Bar(name='Live PF', x=signals, y=live_pfs,
                         marker_color='#4ECDC4'))
    fig.add_hline(y=1.0, line_dash="dash", line_color="red",
                  annotation_text="Breakeven (PF=1.0)")
    fig.update_layout(barmode='group', height=400, template='plotly_dark',
                      xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    # Visual comparison: backtest vs live hit rate
    st.subheader("Hit Rate: Backtest vs Live")
    bt_hits = [BACKTEST[s['Signal']]['hit'] for s in scorecard]
    live_hits_raw = []
    for s in scorecard:
        try:
            live_hits_raw.append(float(s['Live Hit%'].replace('%', '')))
        except:
            live_hits_raw.append(0)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name='Backtest Hit%', x=signals, y=bt_hits,
                          marker_color='rgba(150,206,180,0.5)'))
    fig2.add_trace(go.Bar(name='Live Hit%', x=signals, y=live_hits_raw,
                          marker_color='#96CEB4'))
    fig2.add_hline(y=50, line_dash="dash", line_color="yellow",
                   annotation_text="50% baseline")
    fig2.update_layout(barmode='group', height=400, template='plotly_dark',
                       xaxis_tickangle=-45)
    st.plotly_chart(fig2, use_container_width=True)

    # Summary
    st.subheader("Summary")
    grades = [s['Grade'] for s in scorecard]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Passing", grades.count('✅'))
    col2.metric("🔄 Collecting", grades.count('🔄'))
    col3.metric("⏳ Waiting", grades.count('⏳'))
    col4.metric("⚠️🚫 Review", grades.count('⚠️') + grades.count('🚫'))


# =============================================================================
# FORWARD TESTING: SIGNAL DEEP DIVE
# =============================================================================
elif page == "FT Signal Deep Dive":
    st.title("🔬 Signal Deep Dive")

    trades_df = fetch_table('trades', 'closed_at')
    positions_df = fetch_table('positions')

    signal_choice = st.selectbox("Select Signal", sorted(BACKTEST.keys()))
    st.info(SIGNAL_DESCRIPTIONS.get(signal_choice, ''))
    bt = BACKTEST[signal_choice]
    color = SIGNAL_COLORS.get(signal_choice, '#888')

    # Backtest reference
    st.subheader(f"Backtest Reference")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Backtest PF", bt['pf'])
    col2.metric("Backtest Hit%", f"{bt['hit']}%")
    col3.metric("Backtest Exp", f"{bt['exp']:+.2f}%")
    col4.metric("Hold Period", f"{bt['hold']}d")
    col5.metric("BT Trades (3yr)", bt['trades'])

    # Live stats
    st.subheader("Forward Test Results")
    if len(trades_df) > 0:
        sig_trades = trades_df[trades_df['signal_name'] == signal_choice]
    else:
        sig_trades = pd.DataFrame()

    if len(sig_trades) == 0:
        st.info(f"No closed trades yet for {signal_choice}. Collecting data...")
    else:
        sig_trades['closed_at'] = pd.to_datetime(sig_trades['closed_at'])
        winners = sig_trades[sig_trades['return_pct'] > 0]
        losers = sig_trades[sig_trades['return_pct'] <= 0]

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Live PF", calc_pf(sig_trades['return_pct']),
                     delta=f"BT: {bt['pf']}")
        col2.metric("Live Hit%", f"{len(winners)/len(sig_trades)*100:.1f}%",
                     delta=f"BT: {bt['hit']}%")
        col3.metric("Expectancy", f"{sig_trades['return_pct'].mean():+.2f}%",
                     delta=f"BT: {bt['exp']:+.2f}%")
        col4.metric("Trades", len(sig_trades),
                     delta=f"Need 20" if len(sig_trades) < 20 else "✅ Sufficient")
        col5.metric("Paper P&L", f"${sig_trades['net_pnl'].sum():+,.2f}")

        # Cumulative P&L
        st.subheader("Cumulative P&L")
        sorted_sig = sig_trades.sort_values('closed_at')
        sorted_sig['cum_pnl'] = sorted_sig['net_pnl'].cumsum()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sorted_sig['closed_at'], y=sorted_sig['cum_pnl'],
            mode='lines+markers', line=dict(color=color, width=2),
            fill='tozeroy',
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(height=300, template='plotly_dark',
                          margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # Return distribution histogram
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("Return Distribution")
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=sig_trades['return_pct'],
                nbinsx=30,
                marker_color=color,
                opacity=0.7,
            ))
            fig.add_vline(x=0, line_dash="dash", line_color="red")
            fig.add_vline(x=sig_trades['return_pct'].mean(), line_dash="dash",
                         line_color="yellow", annotation_text="Mean")
            fig.update_layout(height=300, template='plotly_dark',
                              xaxis_title='Return %', yaxis_title='Count',
                              margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.subheader("Win/Loss Breakdown")
            fig = go.Figure(go.Pie(
                labels=['Winners', 'Losers'],
                values=[len(winners), len(losers)],
                marker=dict(colors=['#4ECDC4', '#FF6B6B']),
                hole=0.5,
                textinfo='label+percent',
            ))
            fig.update_layout(height=300, template='plotly_dark',
                              margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, use_container_width=True)

        # Trade-by-trade table
        st.subheader("Trade Log")
        log_cols = ['closed_at', 'ticker', 'entry_price', 'exit_price',
                   'return_pct', 'net_pnl', 'hold_days']
        available = [c for c in log_cols if c in sig_trades.columns]
        st.dataframe(
            sig_trades[available].sort_values('closed_at', ascending=False),
            use_container_width=True, height=300,
        )

    # Current open positions for this signal
    if len(positions_df) > 0:
        sig_pos = positions_df[
            (positions_df['signal_name'] == signal_choice) &
            (positions_df['status'] == 'open')
        ]
        if len(sig_pos) > 0:
            st.subheader(f"Open Positions ({len(sig_pos)})")
            pos_cols = ['ticker', 'entry_price', 'shares', 'entry_date', 'target_exit_date']
            available = [c for c in pos_cols if c in sig_pos.columns]
            st.dataframe(sig_pos[available], use_container_width=True)


# =============================================================================
# FORWARD TESTING: TRADE LOG
# =============================================================================
elif page == "FT Trade Log":
    st.title("📒 Forward Test Trade Log")

    trades_df = fetch_table('trades', 'closed_at')

    if len(trades_df) == 0:
        st.info("No closed trades yet. Scanner needs to run daily and positions need to reach their exit dates.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        sig_options = ['All'] + sorted(trades_df['signal_name'].unique().tolist())
        selected_sig = col1.selectbox("Signal", sig_options)
        selected_result = col2.selectbox("Result", ['All', 'Winners', 'Losers'])
        selected_ticker = col3.text_input("Ticker (optional)")

        filtered = trades_df.copy()
        if selected_sig != 'All':
            filtered = filtered[filtered['signal_name'] == selected_sig]
        if selected_result == 'Winners':
            filtered = filtered[filtered['return_pct'] > 0]
        elif selected_result == 'Losers':
            filtered = filtered[filtered['return_pct'] <= 0]
        if selected_ticker:
            filtered = filtered[filtered['ticker'].str.contains(selected_ticker.upper())]

        # Summary
        if len(filtered) > 0:
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Trades", len(filtered))
            col2.metric("Win Rate", f"{(filtered['return_pct'] > 0).mean()*100:.1f}%")
            col3.metric("Avg Return", f"{filtered['return_pct'].mean():+.2f}%")
            col4.metric("PF", calc_pf(filtered['return_pct']))
            col5.metric("Total P&L", f"${filtered['net_pnl'].sum():+,.2f}")

        # Table
        display_cols = ['closed_at', 'signal_name', 'ticker', 'entry_price',
                       'exit_price', 'return_pct', 'net_pnl', 'hold_days']
        available = [c for c in display_cols if c in filtered.columns]
        st.dataframe(
            filtered[available].sort_values('closed_at', ascending=False),
            use_container_width=True, height=500,
        )


# =============================================================================
# FORWARD TESTING: CONVERGENCE ANALYSIS
# =============================================================================
elif page == "FT Convergence Analysis":
    st.title("🔗 Convergence Analysis")
    st.markdown("*Stocks where 2+ signals fire simultaneously. Higher conviction = better returns?*")

    signals_df = fetch_table('signals', 'detected_at')
    trades_df = fetch_table('trades', 'closed_at')

    if len(signals_df) == 0:
        st.info("No signal data yet.")
    else:
        # Find convergence events
        if 'confidence' in signals_df.columns:
            convergent = signals_df[signals_df['confidence'] >= 2]
            single = signals_df[signals_df['confidence'] < 2]

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Signals", len(signals_df))
            col2.metric("Convergence Signals", len(convergent))
            col3.metric("Convergence Rate",
                        f"{len(convergent)/max(len(signals_df),1)*100:.1f}%")

            # Convergence tickers
            if len(convergent) > 0:
                st.subheader("Convergence Events")
                conv_display = ['detected_at', 'signal_name', 'ticker', 'confidence', 'status']
                available = [c for c in conv_display if c in convergent.columns]
                st.dataframe(
                    convergent[available].sort_values('detected_at', ascending=False),
                    use_container_width=True, height=300,
                )

            # Compare returns: convergence vs single
            if len(trades_df) > 0:
                st.subheader("Returns: Convergence vs Single Signal")

                # Match trades to their signal confidence
                if 'signal_id' in trades_df.columns and 'id' in signals_df.columns:
                    merged = trades_df.merge(
                        signals_df[['id', 'confidence']].rename(columns={'id': 'signal_id'}),
                        on='signal_id', how='left'
                    )
                    conv_trades = merged[merged['confidence'] >= 2]
                    single_trades = merged[merged['confidence'] < 2]

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Convergence Trades**")
                        if len(conv_trades) > 0:
                            st.metric("Trades", len(conv_trades))
                            st.metric("PF", calc_pf(conv_trades['return_pct']))
                            st.metric("Avg Return", f"{conv_trades['return_pct'].mean():+.2f}%")
                        else:
                            st.info("No convergence trades closed yet")

                    with col2:
                        st.markdown("**Single Signal Trades**")
                        if len(single_trades) > 0:
                            st.metric("Trades", len(single_trades))
                            st.metric("PF", calc_pf(single_trades['return_pct']))
                            st.metric("Avg Return", f"{single_trades['return_pct'].mean():+.2f}%")
                        else:
                            st.info("No single signal trades closed yet")
        else:
            st.info("No confidence data in signals. Run latest scanner version.")


# =============================================================================
# SCANNER LOG
# =============================================================================
elif page == "Scanner Log":
    st.title("🖥️ Scanner Run Log")

    runs_df = fetch_table('scanner_runs', 'run_at')

    if len(runs_df) == 0:
        st.info("No scanner runs logged yet.")
    else:
        # Key stats
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Runs", len(runs_df))
        col2.metric("Avg Signals/Run",
                     f"{runs_df['signals_found'].mean():.1f}" if 'signals_found' in runs_df.columns else "—")
        col3.metric("Avg Duration",
                     f"{runs_df['duration_seconds'].mean():.0f}s" if 'duration_seconds' in runs_df.columns else "—")
        latest_regime = runs_df.iloc[0].get('spy_regime', '—') if len(runs_df) > 0 else '—'
        col4.metric("Current Regime", latest_regime)

        # Signals over time
        if 'run_at' in runs_df.columns and 'signals_found' in runs_df.columns:
            st.subheader("Signals Found Per Run")
            runs_df['run_at'] = pd.to_datetime(runs_df['run_at'])
            fig = px.line(runs_df.sort_values('run_at'), x='run_at', y='signals_found',
                         markers=True)
            fig.update_layout(template='plotly_dark', height=300)
            st.plotly_chart(fig, use_container_width=True)

        # Regime history
        if 'spy_regime' in runs_df.columns:
            st.subheader("Market Regime History")
            regime_counts = runs_df['spy_regime'].value_counts()
            colors = {'bull': '#4ECDC4', 'bear': '#FF6B6B', 'sideways': '#FFEAA7', 'unknown': '#888'}
            fig = go.Figure(go.Pie(
                labels=regime_counts.index,
                values=regime_counts.values,
                marker=dict(colors=[colors.get(r, '#888') for r in regime_counts.index]),
                hole=0.4,
            ))
            fig.update_layout(height=300, template='plotly_dark')
            st.plotly_chart(fig, use_container_width=True)

        # Raw log
        st.subheader("Run History")
        st.dataframe(runs_df, use_container_width=True, height=400)


# =============================================================================
# LIVE TRADING PAGES (placeholder for when IBKR is connected)
# =============================================================================
elif page == "Live Dashboard":
    st.title("💰 Live Trading Dashboard")
    st.warning("Live trading not yet active. Complete forward testing first, "
               "then connect IBKR to switch to live mode.")
    st.markdown("""
    **To activate live trading:**
    1. Forward test for 4-6 weeks
    2. Verify signals match backtest on the Forward Testing pages
    3. Set up IBKR paper account
    4. Connect IB Gateway on VPS
    5. Switch `TRADING_MODE=live` in `.env`
    
    **Status:** Forward Testing in progress...
    """)

elif page == "Live Positions":
    st.title("📈 Live Positions")
    st.warning("Live trading not yet active.")

elif page == "Live Trade History":
    st.title("📜 Live Trade History")
    st.warning("Live trading not yet active.")

elif page == "Live Signal Performance":
    st.title("📊 Live Signal Performance")
    st.warning("Live trading not yet active.")
