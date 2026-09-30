import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import streamlit.components.v1 as components
import os
from dotenv import load_dotenv

load_dotenv()

bets_icon = """
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" stroke="#34d399" stroke-width="2">
  <rect x="3" y="2" width="14" height="18" rx="2"/>
  <line x1="7" y1="6" x2="13" y2="6"/>
  <line x1="7" y1="10" x2="13" y2="10"/>
</svg>
"""

profit_icon = """
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" stroke="#22c55e" stroke-width="2">
  <circle cx="12" cy="12" r="10"/>
  <path d="M12 6v12M9 9h4a2 2 0 0 1 0 4h-2a2 2 0 0 0 0 4h4"/>
</svg>
"""

stake_icon = """
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" stroke="#60a5fa" stroke-width="2">
  <line x1="4" y1="20" x2="4" y2="10"/>
  <line x1="10" y1="20" x2="10" y2="4"/>
  <line x1="16" y1="20" x2="16" y2="14"/>
</svg>
"""

roi_icon = """
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" stroke="#34d399" stroke-width="2">
  <polyline points="4 14 8 10 12 13 18 6"/>
</svg>
"""

hit_icon = """
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="19" y1="5" x2="5" y2="19"/>
  <circle cx="6.5" cy="6.5" r="2.5"/>
  <circle cx="17.5" cy="17.5" r="2.5"/>
</svg>
"""
drawdown_icon = """
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" stroke="#ef4444" stroke-width="2">
  <polyline points="4 6 9 12 13 9 18 16"/>
  <polyline points="14 16 18 16 18 12"/>
</svg>
"""

st.set_page_config(page_title="Analytics", layout="wide")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD")
}

def get_engine():
    connection_string = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    return create_engine(connection_string)

def load_bets(engine):
    query = """
    SELECT
        bet_id,
        date,
        time,
        sport,
        match,
        selection,
        status,
        stake,
        odds,
        sportsbook,
        tipster,
        profit
    FROM bets
    ORDER BY date DESC, time DESC;
    """
    bets_df = pd.read_sql(query, engine)
    bets_df["date"] = pd.to_datetime(bets_df["date"]).dt.date
    return bets_df

def apply_filters(bets_df):
    st.sidebar.header("Filters")

    sport_options = ["All"] + sorted(bets_df["sport"].dropna().unique().tolist())
    sportsbook_options = ["All"] + sorted(bets_df["sportsbook"].dropna().unique().tolist())
    tipster_options = ["All"] + sorted(bets_df["tipster"].dropna().unique().tolist())

    min_date = bets_df["date"].min()
    max_date = bets_df["date"].max()

    sport_filter = st.sidebar.selectbox("Select Sport", sport_options)
    sportsbook_filter = st.sidebar.selectbox("Select Sportsbook", sportsbook_options)
    tipster_filter = st.sidebar.selectbox("Select Tipster", tipster_options)

    odds_ranges_input = st.sidebar.text_input(
        "Odds breakpoints (comma-separated)",
        value="1.50, 2.50",
        help="Ex: 1.50, 2.50 cria as faixas 1.01-1.50, 1.51-2.50 e 2.51+"
    )

    start_date = st.sidebar.date_input("Start Date", min_date)
    end_date = st.sidebar.date_input("End Date", max_date)

    filtered_df = bets_df.copy()

    if sport_filter != "All":
        filtered_df = filtered_df[filtered_df["sport"] == sport_filter]

    if sportsbook_filter != "All":
        filtered_df = filtered_df[filtered_df["sportsbook"] == sportsbook_filter]

    if tipster_filter != "All":
        filtered_df = filtered_df[filtered_df["tipster"] == tipster_filter]

    if start_date > end_date:
        st.sidebar.error("Start Date cannot be after End Date.")
        return bets_df.iloc[0:0]

    filtered_df = filtered_df[
        (filtered_df["date"] >= start_date) &
        (filtered_df["date"] <= end_date)
    ]

    return filtered_df, odds_ranges_input

def calculate_kpis(filtered_df):
    total_bets = len(filtered_df)
    settled_df = filtered_df[filtered_df["status"].isin(["win", "loss", "void"])]

    total_profit = round(settled_df["profit"].sum(), 2) if not settled_df.empty else 0.0
    total_stake = settled_df["stake"].sum() if not settled_df.empty else 0.0
    roi_percent = round((total_profit / total_stake) * 100, 2) if total_stake > 0 else 0.0

    win_count = (settled_df["status"] == "win").sum()
    hit_rate_percent = round((win_count / len(settled_df)) * 100, 2) if len(settled_df) > 0 else 0.0

    return total_bets, total_profit, total_stake, roi_percent, hit_rate_percent


def build_aggregations(filtered_df):
    settled_df = filtered_df[filtered_df["status"].isin(["win", "loss", "void"])].copy()

    if settled_df.empty:
        sportsbook_analysis = pd.DataFrame(columns=[
            "Sportsbook", "Bets", "Wins", "Hit Rate",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ])
        tipster_analysis = pd.DataFrame(columns=[
            "Tipster", "Bets", "Wins", "Hit Rate",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ])
        sport_analysis = pd.DataFrame(columns=[
            "Sport", "Bets", "Wins", "Hit Rate",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ])
        bankroll_df = pd.DataFrame(columns=["date", "profit", "cumulative_profit"])
        return sportsbook_analysis, tipster_analysis, sport_analysis, bankroll_df

    sportsbook_analysis = (
        settled_df.groupby("sportsbook", as_index=False)
        .agg(
            Bets=("bet_id", "count"),
            Wins=("status", lambda x: (x == "win").sum()),
            Profit=("profit", "sum"),
            Stake=("stake", "sum"),
            Std_Dev=("profit", "std"),
        )
    )

    sportsbook_analysis["Std_Dev"] = sportsbook_analysis["Std_Dev"].fillna(0)

    sportsbook_analysis["Hit Rate"] = (
        (sportsbook_analysis["Wins"] / sportsbook_analysis["Bets"]) * 100
    ).round(2)

    sportsbook_analysis["ROI (%)"] = (
        (sportsbook_analysis["Profit"] / sportsbook_analysis["Stake"]) * 100
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    sportsbook_analysis["Sharpe"] = (
        sportsbook_analysis["Profit"] / sportsbook_analysis["Std_Dev"]
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    sportsbook_analysis = sportsbook_analysis.rename(columns={
        "sportsbook": "Sportsbook",
        "Std_Dev": "Std Dev"
    })

    sportsbook_analysis = sportsbook_analysis[
        [
            "Sportsbook", "Bets", "Wins", "Hit Rate",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ]
    ].sort_values(by="Profit", ascending=False)

    tipster_analysis = (
        settled_df.dropna(subset=["tipster"])
        .groupby("tipster", as_index=False)
        .agg(
            Bets=("bet_id", "count"),
            Wins=("status", lambda x: (x == "win").sum()),
            Profit=("profit", "sum"),
            Stake=("stake", "sum"),
            Std_Dev=("profit", "std"),
        )
    )

    tipster_analysis["Std_Dev"] = tipster_analysis["Std_Dev"].fillna(0)

    tipster_analysis["Hit Rate"] = (
        (tipster_analysis["Wins"] / tipster_analysis["Bets"]) * 100
    ).round(2)

    tipster_analysis["ROI (%)"] = (
        (tipster_analysis["Profit"] / tipster_analysis["Stake"]) * 100
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    tipster_analysis["Sharpe"] = (
        tipster_analysis["Profit"] / tipster_analysis["Std_Dev"]
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    tipster_analysis = tipster_analysis.rename(columns={
        "tipster": "Tipster",
        "Std_Dev": "Std Dev"
    })

    tipster_analysis = tipster_analysis[
        [
            "Tipster", "Bets", "Wins", "Hit Rate",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ]
    ].sort_values(by="Profit", ascending=False)

    sport_analysis = (
        settled_df.dropna(subset=["sport"])
        .groupby("sport", as_index=False)
        .agg(
            Bets=("bet_id", "count"),
            Wins=("status", lambda x: (x == "win").sum()),
            Profit=("profit", "sum"),
            Stake=("stake", "sum"),
            Std_Dev=("profit", "std"),
        )
    )

    sport_analysis["Std_Dev"] = sport_analysis["Std_Dev"].fillna(0)

    sport_analysis["Hit Rate"] = (
        (sport_analysis["Wins"] / sport_analysis["Bets"]) * 100
    ).round(2)

    sport_analysis["ROI (%)"] = (
        (sport_analysis["Profit"] / sport_analysis["Stake"]) * 100
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    sport_analysis["Sharpe"] = (
        sport_analysis["Profit"] / sport_analysis["Std_Dev"]
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    sport_analysis = sport_analysis.rename(columns={
        "sport": "Sport",
        "Std_Dev": "Std Dev"
    })

    sport_analysis = sport_analysis[
        [
            "Sport", "Bets", "Wins", "Hit Rate",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ]
    ].sort_values(by="Profit", ascending=False)

    bankroll_df = (
        settled_df.sort_values(by=["date", "time"])
        .groupby("date", as_index=False)["profit"]
        .sum()
    )
    bankroll_df["cumulative_profit"] = bankroll_df["profit"].cumsum()

    return sportsbook_analysis, tipster_analysis, sport_analysis, bankroll_df

def calculate_drawdown(bankroll_df):
    if bankroll_df.empty:
        return 0.0, 0, True, pd.DataFrame(columns=["date", "drawdown"])

    df = bankroll_df.copy()
    df["running_max"] = df["cumulative_profit"].cummax()
    df["drawdown"] = df["cumulative_profit"] - df["running_max"]

    idx_max_dd = df["drawdown"].idxmin()
    max_drawdown = df.loc[idx_max_dd, "drawdown"]
    peak_value = df.loc[idx_max_dd, "running_max"]

    peak_matches = df[df["cumulative_profit"] == peak_value]
    peak_date = peak_matches["date"].iloc[0] if not peak_matches.empty else df.loc[idx_max_dd, "date"]

    after_peak = df.loc[idx_max_dd:]
    recovered = after_peak[after_peak["cumulative_profit"] >= peak_value]

    if not recovered.empty:
        recovery_date = recovered["date"].iloc[0]
        is_recovered = True
    else:
        recovery_date = df["date"].iloc[-1]
        is_recovered = False

    duration_days = (pd.to_datetime(recovery_date) - pd.to_datetime(peak_date)).days

    return round(max_drawdown, 2), duration_days, is_recovered, df[["date", "drawdown"]]

def plot_multi_line_chart(df, category_col, title):
    if df.empty:
        return None

    grouped = (
        df.groupby(["date", category_col], as_index=False)["profit"]
        .sum()
        .sort_values("date")
    )

    grouped["cumulative_profit"] = grouped.groupby(category_col)["profit"].cumsum()

    # Adiciona um ponto inicial em 0 para cada categoria, um dia antes da primeira aposta dela
    zero_rows = []
    for category, group in grouped.groupby(category_col):
        first_date = pd.to_datetime(group["date"].iloc[0])
        zero_rows.append({
            "date": (first_date - pd.Timedelta(days=1)).date(),
            category_col: category,
            "profit": 0,
            "cumulative_profit": 0
        })

    grouped = pd.concat([pd.DataFrame(zero_rows), grouped], ignore_index=True)
    grouped = grouped.sort_values(["date", category_col])

    premium_palette = [
        "#22c55e", "#60a5fa", "#f59e0b", "#a78bfa",
        "#ef4444", "#2dd4bf", "#f472b6", "#eab308",
        "#818cf8", "#fb923c"
    ]

    fig = px.line(
        grouped,
        x="date",
        y="cumulative_profit",
        color=category_col,
        markers=True,
        color_discrete_sequence=premium_palette,
    )

    fig.update_traces(
        line=dict(width=3, shape="spline", smoothing=0.4),
        marker=dict(size=5, line=dict(color="#0e1117", width=1)),
        hovertemplate="<b>%{fullData.name}</b><br>%{x|%d/%m}: %{y:.2f} u<extra></extra>",
    )

    fig.add_hline(y=0, line_width=1, line_color="rgba(255,255,255,0.25)")

    fig.update_layout(
        height=400,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white", family="Arial, sans-serif"),
        title=None,
        xaxis=dict(
            title=None,
            showgrid=False,
            zeroline=False,
            showline=False,
        ),
        yaxis=dict(
            title="Profit (u)",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
            showline=False,
        ),
        legend=dict(
            title=None,
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11)
        ),
        margin=dict(l=20, r=20, t=30, b=20),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1f2937",
            font_size=12,
            font_color="white",
            bordercolor="rgba(255,255,255,0.1)"
        ),
    )

    return fig

def plot_bankroll_chart(bankroll_df):
    if bankroll_df.empty:
        return None

    is_positive = bankroll_df["cumulative_profit"].iloc[-1] >= 0
    line_color = "#22c55e" if is_positive else "#ef4444"
    fill_color = "rgba(34, 197, 94, 0.18)" if is_positive else "rgba(239, 68, 68, 0.18)"

    # Adiciona um ponto inicial em 0, um dia antes da primeira aposta
    first_date = bankroll_df["date"].iloc[0]
    start_date = pd.to_datetime(first_date) - pd.Timedelta(days=1)

    plot_df = pd.concat([
        pd.DataFrame([{
            "date": start_date.date(),
            "profit": 0,
            "cumulative_profit": 0
        }]),
        bankroll_df
    ], ignore_index=True)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=plot_df["date"],
        y=plot_df["cumulative_profit"],
        mode="lines",
        name="Cumulative Profit",
        line=dict(color=line_color, width=3.5, shape="spline", smoothing=0.4),
        fill="tozeroy",
        fillcolor=fill_color,
        hovertemplate="<b>%{x|%d/%m}</b><br>Cumulative: %{y:.2f} u<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=plot_df["date"],
        y=plot_df["cumulative_profit"],
        mode="markers",
        marker=dict(
            color=line_color,
            size=6,
            line=dict(color="#0e1117", width=1.5)
        ),
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=plot_df["date"],
        y=plot_df["profit"],
        mode="lines+markers",
        name="Daily Profit",
        line=dict(color="#60a5fa", width=1.8, dash="dot"),
        marker=dict(color="#60a5fa", size=4),
        hovertemplate="<b>%{x|%d/%m}</b><br>Daily: %{y:.2f} u<extra></extra>",
    ))

    fig.add_hline(y=0, line_width=1, line_color="rgba(255,255,255,0.25)")

    fig.update_layout(
        height=450,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white", family="Arial, sans-serif"),
        xaxis=dict(
            title=None,
            showgrid=False,
            zeroline=False,
            showline=False,
        ),
        yaxis=dict(
            title="Profit (u)",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
            showline=False,
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=12)
        ),
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1f2937",
            font_size=13,
            font_color="white",
            bordercolor="rgba(255,255,255,0.1)"
        ),
    )

    return fig

def plot_drawdown_chart(drawdown_df):
    if drawdown_df.empty:
        return None

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=drawdown_df["date"],
        y=drawdown_df["drawdown"],
        mode="lines",
        name="Drawdown",
        line=dict(color="#ef4444", width=3, shape="spline", smoothing=0.4),
        fill="tozeroy",
        fillcolor="rgba(239, 68, 68, 0.18)",
        hovertemplate="<b>%{x|%d/%m}</b><br>Drawdown: %{y:.2f} u<extra></extra>",
    ))

    fig.add_hline(y=0, line_width=1, line_color="rgba(255,255,255,0.25)")

    fig.update_layout(
        height=350,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white", family="Arial, sans-serif"),
        xaxis=dict(title=None, showgrid=False, zeroline=False, showline=False),
        yaxis=dict(
            title="Drawdown (u)",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
            showline=False,
        ),
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#1f2937", font_size=13, font_color="white", bordercolor="rgba(255,255,255,0.1)"),
    )

    return fig

def render_kpi_card(title, value, icon_svg, color="white"):
    icon_svg = icon_svg.replace("<svg", '<svg style="display:block;"', 1)
    html = f"""
    <div style="
        display:flex;
        align-items:center;
        gap:14px;
        padding:6px 4px;
        font-family:Arial, sans-serif;
    ">
        <div style="
            width:60px;
            height:60px;
            background: rgba(255,255,255,0.02);
            border-radius:12px;
            display:flex;
            align-items:center;
            justify-content:center;
            flex-shrink:0;
            overflow:hidden;
        ">
            <div style="display:flex;">{icon_svg}</div>
        </div>

        <div>
            <div style="
                font-size:17px;
                color:#9ca3af;
                margin-bottom:4px;
            ">
                {title}
            </div>

            <div style="
                font-size:25px;
                font-weight:800;
                color:{color};
                line-height:1;
            ">
                {value}
            </div>
        </div>
    </div>
    """

    components.html(html, height=90)

def get_value_color(value):
    if pd.isna(value):
        return "gray"
    if value > 0:
        return "green"
    if value < 0:
        return "red"
    return "gray"

def render_analysis_rows(df, title_col):
    if df.empty:
        st.info("No data available.")
        return

    df = df.sort_values(by="Bets", ascending=False)

    header = st.columns([2.2, 0.8, 1.4, 1.3, 1.3, 1.1, 1.1, 1.0])

    header[0].markdown("**Name**")
    header[1].markdown("**Bets**")
    header[2].markdown("**Won**")
    header[3].markdown("**Staked**")
    header[4].markdown("**Profit**")
    header[5].markdown("**ROI**")
    header[6].markdown("**Std Dev**")
    header[7].markdown("**Sharpe**")

    for _, row in df.iterrows():
        cols = st.columns([2.2, 0.8, 1.4, 1.3, 1.3, 1.1, 1.1, 1.0])

        bets = int(row["Bets"])
        wins = int(row["Wins"])
        hit_rate = row["Hit Rate"]
        stake = row["Stake"]
        profit = row["Profit"]
        roi = row["ROI (%)"]
        std_dev = row["Std Dev"]
        sharpe = row["Sharpe"]

        profit_color = "#22c55e" if profit > 0 else "#ef4444" if profit < 0 else "#9ca3af"
        roi_color = "#22c55e" if roi > 0 else "#ef4444" if roi < 0 else "#9ca3af"
        sharpe_color = "#22c55e" if sharpe > 0 else "#ef4444" if sharpe < 0 else "#9ca3af"

        cols[0].markdown(f"**{row[title_col]}**")
        cols[1].markdown(f"{bets}")
        cols[2].markdown(f"{wins} ({hit_rate:.2f}%)")
        cols[3].markdown(f"{stake:.2f} u")

        cols[4].markdown(
            f"<span style='color:{profit_color}; font-weight:700;'>{'+' if profit > 0 else ''}{profit:.2f} u</span>",
            unsafe_allow_html=True
        )

        cols[5].markdown(
            f"<span style='color:{roi_color}; font-weight:700;'>{'+' if roi > 0 else ''}{roi:.2f}%</span>",
            unsafe_allow_html=True
        )

        cols[6].markdown(f"{std_dev:.2f}")

        cols[7].markdown(
            f"<span style='color:{sharpe_color}; font-weight:700;'>{sharpe:.2f}</span>",
            unsafe_allow_html=True
        )

        st.markdown("<hr style='margin:6px 0; border-color:#1f2937;'>", unsafe_allow_html=True)

def build_total_risk_analysis(filtered_df):
    settled_df = filtered_df[filtered_df["status"].isin(["win", "loss", "void"])].copy()

    if settled_df.empty:
        return pd.DataFrame(columns=["Name", "Bets", "Wins", "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"])

    bets = len(settled_df)
    wins = (settled_df["status"] == "win").sum()
    profit = settled_df["profit"].sum()
    stake = settled_df["stake"].sum()
    roi = (profit / stake) * 100 if stake > 0 else 0
    std_dev = settled_df["profit"].std()
    std_dev = 0 if pd.isna(std_dev) else std_dev
    sharpe = profit / std_dev if std_dev > 0 else 0

    return pd.DataFrame([{
        "Name": "Total",
        "Bets": bets,
        "Wins": wins,
        "Profit": profit,
        "Stake": stake,
        "ROI (%)": roi,
        "Std Dev": std_dev,
        "Sharpe": sharpe
    }])

def build_odds_range_analysis(filtered_df, bins):
    settled_df = filtered_df[filtered_df["status"].isin(["win", "loss", "void"])].copy()

    if settled_df.empty or len(bins) < 2:
        return pd.DataFrame(columns=[
            "Odds Range", "Bets", "Wins", "Hit Rate",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ])

    labels = [
        f"{bins[i]:.2f} - {bins[i+1]:.2f}" if bins[i+1] != float("inf") else f"{bins[i]:.2f}+"
        for i in range(len(bins) - 1)
    ]

    settled_df["odds_range"] = pd.cut(settled_df["odds"], bins=bins, labels=labels)

    odds_analysis = (
        settled_df.groupby("odds_range", as_index=False, observed=True)
        .agg(
            Bets=("bet_id", "count"),
            Wins=("status", lambda x: (x == "win").sum()),
            Profit=("profit", "sum"),
            Stake=("stake", "sum"),
            Std_Dev=("profit", "std"),
        )
    )

    odds_analysis["Std_Dev"] = odds_analysis["Std_Dev"].fillna(0)

    odds_analysis["Hit Rate"] = (
        (odds_analysis["Wins"] / odds_analysis["Bets"]) * 100
    ).round(2)

    odds_analysis["ROI (%)"] = (
        (odds_analysis["Profit"] / odds_analysis["Stake"]) * 100
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    odds_analysis["Sharpe"] = (
        odds_analysis["Profit"] / odds_analysis["Std_Dev"]
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    odds_analysis = odds_analysis.rename(columns={
        "odds_range": "Odds Range",
        "Std_Dev": "Std Dev"
    })

    odds_analysis = odds_analysis[
        [
            "Odds Range", "Bets", "Wins", "Hit Rate",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ]
    ]

    return odds_analysis

def plot_total_risk_line_chart(filtered_df):
    settled_df = filtered_df[
        filtered_df["status"].isin(["win", "loss", "void"])
    ].copy()

    if settled_df.empty:
        return None

    settled_df = settled_df.sort_values(by=["date", "time"])

    daily_df = (
        settled_df.groupby("date", as_index=False)
        .agg(
            profit=("profit", "sum"),
            stake=("stake", "sum")
        )
    )

    daily_df["daily_roi"] = np.where(
        daily_df["stake"] > 0,
        (daily_df["profit"] / daily_df["stake"]) * 100,
        0
    )

    daily_df["cumulative_profit"] = daily_df["profit"].cumsum()
    daily_df["cumulative_stake"] = daily_df["stake"].cumsum()

    daily_df["cumulative_roi"] = np.where(
        daily_df["cumulative_stake"] > 0,
        (daily_df["cumulative_profit"] / daily_df["cumulative_stake"]) * 100,
        0
    )

    daily_df["rolling_std"] = (
        daily_df["profit"]
        .rolling(window=7, min_periods=1)
        .std()
        .fillna(0)
    )

    # Ponto inicial em zero, um dia antes da primeira aposta
    first_date = pd.to_datetime(daily_df["date"].iloc[0])
    start_row = pd.DataFrame([{
        "date": (first_date - pd.Timedelta(days=1)).date(),
        "cumulative_roi": 0,
        "rolling_std": daily_df["rolling_std"].iloc[0]
    }])

    plot_df = pd.concat([start_row, daily_df], ignore_index=True)

    is_positive = daily_df["cumulative_roi"].iloc[-1] >= 0
    line_color = "#22c55e" if is_positive else "#ef4444"
    fill_color = "rgba(34, 197, 94, 0.18)" if is_positive else "rgba(239, 68, 68, 0.18)"

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=plot_df["date"],
        y=plot_df["cumulative_roi"],
        mode="lines",
        name="Cumulative ROI (%)",
        line=dict(color=line_color, width=3.5, shape="spline", smoothing=0.4),
        fill="tozeroy",
        fillcolor=fill_color,
        hovertemplate="<b>%{x|%d/%m}</b><br>ROI: %{y:.2f}%<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=plot_df["date"],
        y=plot_df["cumulative_roi"],
        mode="markers",
        marker=dict(
            color=line_color,
            size=6,
            line=dict(color="#0e1117", width=1.5)
        ),
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=plot_df["date"],
        y=plot_df["rolling_std"],
        mode="lines",
        name="Rolling Volatility",
        line=dict(color="#ff0404", width=1.8, dash="dot"),
        hovertemplate="<b>%{x|%d/%m}</b><br>Volatility: %{y:.2f}<extra></extra>",
    ))

    fig.add_hline(y=0, line_width=1, line_color="rgba(255,255,255,0.25)")

    fig.update_layout(
        height=450,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white", family="Arial, sans-serif"),
        xaxis=dict(
            title=None,
            showgrid=False,
            zeroline=False,
            showline=False,
        ),
        yaxis=dict(
            title="Value",
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
            showline=False,
        ),
        legend=dict(
            title=None,
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=12)
        ),
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1f2937",
            font_size=13,
            font_color="white",
            bordercolor="rgba(255,255,255,0.1)"
        ),
    )

    return fig

def plot_tipster_risk_line_chart(filtered_df, selected_tipster):
    tipster_df = filtered_df[
        (filtered_df["tipster"] == selected_tipster) &
        (filtered_df["status"].isin(["win", "loss", "void"]))
    ].copy()

    if tipster_df.empty:
        return None

    tipster_df = tipster_df.sort_values(by=["date", "time"])

    daily_df = (
        tipster_df.groupby("date", as_index=False)
        .agg(
            profit=("profit", "sum"),
            stake=("stake", "sum")
        )
    )

    daily_df["daily_roi"] = np.where(
        daily_df["stake"] > 0,
        (daily_df["profit"] / daily_df["stake"]) * 100,
        0
    )

    daily_df["cumulative_profit"] = daily_df["profit"].cumsum()
    daily_df["cumulative_stake"] = daily_df["stake"].cumsum()

    daily_df["cumulative_roi"] = np.where(
        daily_df["cumulative_stake"] > 0,
        (daily_df["cumulative_profit"] / daily_df["cumulative_stake"]) * 100,
        0
    )

    daily_df["rolling_std"] = (
        daily_df["profit"]
        .rolling(window=7, min_periods=1)
        .std()
        .fillna(0)
    )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=daily_df["date"],
        y=daily_df["cumulative_roi"],
        mode="lines",
        name="Cumulative ROI (%)",
        line=dict(color="#22c55e", width=3)
    ))

    fig.add_trace(go.Scatter(
        x=daily_df["date"],
        y=daily_df["rolling_std"],
        mode="lines",
        name="Rolling Volatility",
        line=dict(color="#ef4444", width=2, dash="dot")
    ))

    fig.add_hline(y=0, line_width=1, line_color="gray")

    fig.update_layout(
        height=500,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white"),
        xaxis_title="Date",
        yaxis_title="Value",
        legend=dict(title=""),
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified",
        title=f"Risk Analysis - {selected_tipster}"
    )

    return fig

def main():
    st.title("Analytics")

    try:
        engine = get_engine()
        bets_df = load_bets(engine)

        filtered_df, odds_ranges_input = apply_filters(bets_df)

        total_bets, total_profit, total_stake, roi_percent, hit_rate_percent = calculate_kpis(filtered_df)

        (
            sportsbook_analysis,
            tipster_analysis,
            sport_analysis,
            bankroll_df,
        ) = build_aggregations(filtered_df)

        total_risk_analysis = build_total_risk_analysis(filtered_df)
        max_drawdown, dd_duration, dd_recovered, drawdown_df = calculate_drawdown(bankroll_df)

        profit_color = "#22c55e" if total_profit > 0 else "#ef4444" if total_profit < 0 else "#9ca3af"
        roi_color = "#22c55e" if roi_percent > 0 else "#ef4444" if roi_percent < 0 else "#9ca3af"
        hit_rate_color = "#22c55e" if hit_rate_percent >= 50 else "#f59e0b"

        kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5, gap="large")

        with kpi_col1:
            render_kpi_card("Total Bets", f"{total_bets}", bets_icon)

        with kpi_col2:
            render_kpi_card("Total Profit", f"{total_profit:.2f}", profit_icon, profit_color)

        with kpi_col3:
            render_kpi_card("Total Stake", f"{total_stake:.2f}", stake_icon)

        with kpi_col4:
            render_kpi_card("ROI (%)", f"{roi_percent:.2f}%", roi_icon, roi_color)

        with kpi_col5:
            render_kpi_card("Hit Rate", f"{hit_rate_percent:.2f}%", hit_icon, hit_rate_color)


        st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)

        kpi_col6, kpi_col7 = st.columns(2, gap="large")

        with kpi_col6:
            render_kpi_card("Max Drawdown", f"{max_drawdown:.2f} u", drawdown_icon, "#ef4444")

        with kpi_col7:
            duration_label = f"{dd_duration}d" if dd_recovered else f"{dd_duration}d (ongoing)"
            duration_color = "#22c55e" if dd_recovered else "#f59e0b"
            render_kpi_card("Drawdown Duration", duration_label, drawdown_icon, duration_color)

        st.markdown("<div style='margin-bottom: 18px;'></div>", unsafe_allow_html=True)

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Profit Over Time by Sportsbook")
            if not filtered_df.empty:
                fig_sportsbook = plot_multi_line_chart(
                    filtered_df,
                    "sportsbook",
                    "Profit Over Time by Sportsbook"
                )
                st.plotly_chart(fig_sportsbook, use_container_width=True)
            else:
                st.info("No data available.")

        with chart_col2:
            st.subheader("Profit Over Time by Tipster")
            if not filtered_df.empty:
                fig_tipster = plot_multi_line_chart(
                    filtered_df,
                    "tipster",
                    "Profit Over Time by Tipster"
                )
                st.plotly_chart(fig_tipster, use_container_width=True)
            else:
                st.info("No data available.")

        st.subheader("Bankroll Over Time")

        if not bankroll_df.empty:
            fig = plot_bankroll_chart(bankroll_df)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No settled data available for the selected filters.")

        st.subheader("Total Risk vs Return")
        if not total_risk_analysis.empty:
            fig_risk_total = plot_total_risk_line_chart(filtered_df)
            st.plotly_chart(fig_risk_total, use_container_width=True)
        else:
            st.info("No total risk data available.")

        st.subheader("Drawdown")

        if not drawdown_df.empty:
            fig_drawdown = plot_drawdown_chart(drawdown_df)
            st.plotly_chart(fig_drawdown, use_container_width=True)
        else:
            st.info("No drawdown data available.")

        st.subheader("Analysis Overview")

        st.subheader("Sportsbook Analysis")
        render_analysis_rows(sportsbook_analysis, "Sportsbook")

        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

        st.subheader("Tipster Analysis")
        render_analysis_rows(tipster_analysis, "Tipster")

        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

        st.subheader("Sport Analysis")
        render_analysis_rows(sport_analysis, "Sport")

        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)
        st.subheader("Odds Range Analysis")

        try:
            breakpoints = sorted(set(
                float(x.strip()) for x in odds_ranges_input.split(",") if x.strip()
            ))
            bins = [1.0] + breakpoints + [float("inf")]

            odds_analysis = build_odds_range_analysis(filtered_df, bins)
            render_analysis_rows(odds_analysis, "Odds Range")

        except ValueError:
            st.error("Formato inválido. Use números separados por vírgula, ex: 1.50, 2.50")

    except Exception as e:
        st.error(f"Error loading analytics page: {e}")


if __name__ == "__main__":
    main()
