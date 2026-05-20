import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import streamlit.components.v1 as components

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
<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="none" stroke="#f59e0b" stroke-width="2">
  <circle cx="12" cy="12" r="10"/>
  <circle cx="12" cy="12" r="4"/>
</svg>
"""

st.set_page_config(page_title="Analytics", layout="wide")

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "betting_analytics",
    "user": "postgres",
    "password": "8017"
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
        tag,
        status,
        stake,
        odds,
        sportsbook,
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
    status_options = ["All"] + sorted(bets_df["status"].dropna().unique().tolist())
    tag_options = ["All"] + sorted(bets_df["tag"].dropna().unique().tolist())

    min_date = bets_df["date"].min()
    max_date = bets_df["date"].max()

    sport_filter = st.sidebar.selectbox("Select Sport", sport_options)
    sportsbook_filter = st.sidebar.selectbox("Select Sportsbook", sportsbook_options)
    status_filter = st.sidebar.selectbox("Select Status", status_options)
    tag_filter = st.sidebar.selectbox("Select Tag", tag_options)

    start_date = st.sidebar.date_input("Start Date", min_date)
    end_date = st.sidebar.date_input("End Date", max_date)

    filtered_df = bets_df.copy()

    if sport_filter != "All":
        filtered_df = filtered_df[filtered_df["sport"] == sport_filter]

    if sportsbook_filter != "All":
        filtered_df = filtered_df[filtered_df["sportsbook"] == sportsbook_filter]

    if status_filter != "All":
        filtered_df = filtered_df[filtered_df["status"] == status_filter]

    if tag_filter != "All":
        filtered_df = filtered_df[filtered_df["tag"] == tag_filter]

    if start_date > end_date:
        st.sidebar.error("Start Date cannot be after End Date.")
        return bets_df.iloc[0:0]

    filtered_df = filtered_df[
        (filtered_df["date"] >= start_date) &
        (filtered_df["date"] <= end_date)
    ]

    return filtered_df


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
            "Sportsbook", "Bets", "Wins", "Hit Rate (%)",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ])
        tag_analysis = pd.DataFrame(columns=[
            "Tag", "Bets", "Wins", "Hit Rate (%)",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ])
        bankroll_df = pd.DataFrame(columns=["date", "profit", "cumulative_profit"])
        return sportsbook_analysis, tag_analysis, bankroll_df

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

    sportsbook_analysis["Hit Rate (%)"] = (
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
            "Sportsbook", "Bets", "Wins", "Hit Rate (%)",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ]
    ].sort_values(by="Profit", ascending=False)

    tag_analysis = (
        settled_df.dropna(subset=["tag"])
        .groupby("tag", as_index=False)
        .agg(
            Bets=("bet_id", "count"),
            Wins=("status", lambda x: (x == "win").sum()),
            Profit=("profit", "sum"),
            Stake=("stake", "sum"),
            Std_Dev=("profit", "std"),
        )
    )

    tag_analysis["Std_Dev"] = tag_analysis["Std_Dev"].fillna(0)

    tag_analysis["Hit Rate (%)"] = (
        (tag_analysis["Wins"] / tag_analysis["Bets"]) * 100
    ).round(2)

    tag_analysis["ROI (%)"] = (
        (tag_analysis["Profit"] / tag_analysis["Stake"]) * 100
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    tag_analysis["Sharpe"] = (
        tag_analysis["Profit"] / tag_analysis["Std_Dev"]
    ).replace([np.inf, -np.inf], 0).fillna(0).round(2)

    tag_analysis = tag_analysis.rename(columns={
        "tag": "Tag",
        "Std_Dev": "Std Dev"
    })

    tag_analysis = tag_analysis[
        [
            "Tag", "Bets", "Wins", "Hit Rate (%)",
            "Profit", "Stake", "ROI (%)", "Std Dev", "Sharpe"
        ]
    ].sort_values(by="Profit", ascending=False)

    bankroll_df = (
        settled_df.sort_values(by=["date", "time"])
        .groupby("date", as_index=False)["profit"]
        .sum()
    )
    bankroll_df["cumulative_profit"] = bankroll_df["profit"].cumsum()

    return sportsbook_analysis, tag_analysis, bankroll_df


def plot_risk_analysis(df, label_col, title):
    if df.empty:
        return None

    risk_df = df.copy()

    fig = px.scatter(
        risk_df,
        x="Std Dev",
        y="ROI (%)",
        size="Bets",
        color="Profit",
        hover_name=label_col,
        text=label_col,
        title=title,
        color_continuous_scale="RdYlGn",
    )

    fig.update_traces(textposition="top center")

    fig.add_hline(y=0, line_width=1, line_color="gray")

    fig.update_layout(
        height=500,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white"),
        xaxis_title="Volatility (Std Dev)",
        yaxis_title="ROI (%)",
        margin=dict(l=20, r=20, t=50, b=20),
    )

    return fig

def plot_multi_line_chart(df, category_col, title):
    if df.empty:
        return None

    grouped = (
        df.groupby(["date", category_col], as_index=False)["profit"]
        .sum()
        .sort_values("date")
    )

    grouped["cumulative_profit"] = grouped.groupby(category_col)["profit"].cumsum()

    fig = px.line(
        grouped,
        x="date",
        y="cumulative_profit",
        color=category_col,
        title=title,
        markers=True
    )

    fig.update_layout(
        height=400,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white"),
        xaxis_title="Date",
        yaxis_title="Profit",
        legend_title=category_col,
        margin=dict(l=20, r=20, t=50, b=20),
    )

    return fig


def plot_bankroll_chart(bankroll_df):
    if bankroll_df.empty:
        return None

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=bankroll_df["date"],
        y=bankroll_df["cumulative_profit"],
        mode="lines+markers",
        name="Cumulative Profit",
        line=dict(color="#22c55e", width=3)
    ))

    fig.add_trace(go.Scatter(
        x=bankroll_df["date"],
        y=bankroll_df["profit"],
        mode="lines+markers",
        name="Daily Profit",
        line=dict(color="#60a5fa", width=2, dash="dot")
    ))

    fig.add_hline(y=0, line_width=1, line_color="gray")

    fig.update_layout(
        height=450,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white"),
        xaxis_title="Date",
        yaxis_title="Profit",
        legend=dict(title=""),
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified"
    )

    return fig

def render_kpi_card(title, value, icon_svg, color="white"):
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
        ">
            {icon_svg}
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
        hit_rate = row["Hit Rate (%)"]
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

    # ROI diário
    daily_df["daily_roi"] = np.where(
        daily_df["stake"] > 0,
        (daily_df["profit"] / daily_df["stake"]) * 100,
        0
    )

    # ROI acumulado
    daily_df["cumulative_profit"] = daily_df["profit"].cumsum()
    daily_df["cumulative_stake"] = daily_df["stake"].cumsum()

    daily_df["cumulative_roi"] = np.where(
        daily_df["cumulative_stake"] > 0,
        (daily_df["cumulative_profit"] / daily_df["cumulative_stake"]) * 100,
        0
    )

    # Volatilidade rolling
    daily_df["rolling_std"] = (
        daily_df["profit"]
        .rolling(window=7, min_periods=1)
        .std()
        .fillna(0)
    )

    fig = go.Figure()

    # ROI
    fig.add_trace(go.Scatter(
        x=daily_df["date"],
        y=daily_df["cumulative_roi"],
        mode="lines",
        name="Cumulative ROI (%)",
        line=dict(color="#22c55e", width=3)
    ))

    # Volatilidade
    fig.add_trace(go.Scatter(
        x=daily_df["date"],
        y=daily_df["rolling_std"],
        mode="lines",
        name="Rolling Volatility",
        line=dict(color="#ef4444", width=2, dash="dot")
    ))

    fig.update_layout(
        height=500,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font=dict(color="white"),
        xaxis_title="Date",
        yaxis_title="Value",
        legend=dict(title=""),
        margin=dict(l=20, r=20, t=40, b=20),
        hovermode="x unified"
    )

    return fig

def plot_tag_risk_line_chart(filtered_df, selected_tag):
    tag_df = filtered_df[
        (filtered_df["tag"] == selected_tag) &
        (filtered_df["status"].isin(["win", "loss", "void"]))
    ].copy()

    if tag_df.empty:
        return None

    tag_df = tag_df.sort_values(by=["date", "time"])

    daily_df = (
        tag_df.groupby("date", as_index=False)
        .agg(
            profit=("profit", "sum"),
            stake=("stake", "sum")
        )
    )

    # ROI diário
    daily_df["daily_roi"] = np.where(
        daily_df["stake"] > 0,
        (daily_df["profit"] / daily_df["stake"]) * 100,
        0
    )

    # ROI acumulado
    daily_df["cumulative_profit"] = daily_df["profit"].cumsum()
    daily_df["cumulative_stake"] = daily_df["stake"].cumsum()

    daily_df["cumulative_roi"] = np.where(
        daily_df["cumulative_stake"] > 0,
        (daily_df["cumulative_profit"] / daily_df["cumulative_stake"]) * 100,
        0
    )

    # Volatilidade rolling
    daily_df["rolling_std"] = (
        daily_df["profit"]
        .rolling(window=7, min_periods=1)
        .std()
        .fillna(0)
    )

    fig = go.Figure()

    # ROI
    fig.add_trace(go.Scatter(
        x=daily_df["date"],
        y=daily_df["cumulative_roi"],
        mode="lines",
        name="Cumulative ROI (%)",
        line=dict(color="#22c55e", width=3)
    ))

    # Volatilidade
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
        title=f"Risk Analysis - {selected_tag}"
    )

    return fig

def main():
    st.title("Analytics")

    try:
        engine = get_engine()
        bets_df = load_bets(engine)

        filtered_df = apply_filters(bets_df)

        total_bets, total_profit, total_stake, roi_percent, hit_rate_percent = calculate_kpis(filtered_df)

        (
            sportsbook_analysis,
            tag_analysis,
            bankroll_df,
        ) = build_aggregations(filtered_df)

        total_risk_analysis = build_total_risk_analysis(filtered_df)

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
            render_kpi_card("Hit Rate (%)", f"{hit_rate_percent:.2f}%", hit_icon, hit_rate_color)

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
            st.subheader("Profit Over Time by Tag")
            if not filtered_df.empty:
                fig_tag = plot_multi_line_chart(
                    filtered_df,
                    "tag",
                    "Profit Over Time by Tag"
                )
                st.plotly_chart(fig_tag, use_container_width=True)
            else:
                st.info("No data available.")

        st.subheader("Bankroll Over Time")

        if not bankroll_df.empty:
            fig = plot_bankroll_chart(bankroll_df)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No settled data available for the selected filters.")

        st.subheader("Risk Analysis")

        risk_col1, risk_col2 = st.columns(2)

        with risk_col1:
            st.subheader("Total Risk vs Return")
            if not total_risk_analysis.empty:
                fig_risk_total = plot_total_risk_line_chart(filtered_df)
                st.plotly_chart(fig_risk_total, use_container_width=True)
            else:
                st.info("No total risk data available.")

        with risk_col2:
            st.subheader("Tag Risk vs Return")
            if not tag_analysis.empty:
                fig_risk_tag = plot_risk_analysis(
                    tag_analysis,
                    "Tag",
                    "Risk vs Return by Tag"
                )
                st.plotly_chart(fig_risk_tag, use_container_width=True)
            else:
                st.info("No tag data available.")

        st.subheader("Tag Risk Analysis")

        available_tags = sorted(
            filtered_df["tag"]
            .dropna()
            .unique()
            .tolist()
        )

        selected_tag_risk = st.selectbox(
            "Select Tag",
            available_tags
        )

        fig_tag_risk = plot_tag_risk_line_chart(
            filtered_df,
            selected_tag_risk
        )

        if fig_tag_risk:
            st.plotly_chart(fig_tag_risk, use_container_width=True)
        else:
            st.info("No data available for selected tag.")

        st.subheader("Analysis Overview")

        st.subheader("Sportsbook Analysis")
        render_analysis_rows(sportsbook_analysis, "Sportsbook")

        st.markdown("<div style='margin: 20px 0;'></div>", unsafe_allow_html=True)

        st.subheader("Tag Analysis")
        render_analysis_rows(tag_analysis, "Tag")

    except Exception as e:
        st.error(f"Error loading analytics page: {e}")


if __name__ == "__main__":
    main()