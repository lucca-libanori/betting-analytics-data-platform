import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

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

    pending_count = (filtered_df["status"] == "pending").sum()

    return total_bets, total_profit, total_stake, roi_percent, hit_rate_percent, pending_count


def build_aggregations(filtered_df):
    settled_df = filtered_df[filtered_df["status"].isin(["win", "loss", "void"])].copy()

    if settled_df.empty:
        sportsbook_analysis = pd.DataFrame(
            columns=["Sportsbook", "Bets", "Wins", "Hit Rate (%)", "Profit", "Stake", "ROI (%)"]
        )
        tag_analysis = pd.DataFrame(
            columns=["Tag", "Bets", "Wins", "Hit Rate (%)", "Profit", "Stake", "ROI (%)"]
        )
        bankroll_df = pd.DataFrame(columns=["date", "cumulative_profit"])

        return (
            sportsbook_analysis,
            tag_analysis,
            bankroll_df,
        )

    # -------------------------
    # Sportsbook analysis
    # -------------------------
    sportsbook_analysis = (
        settled_df.groupby("sportsbook", as_index=False)
        .agg(
            Bets=("bet_id", "count"),
            Wins=("status", lambda x: (x == "win").sum()),
            Profit=("profit", "sum"),
            Stake=("stake", "sum"),
        )
    )

    sportsbook_analysis["Hit Rate (%)"] = (
        (sportsbook_analysis["Wins"] / sportsbook_analysis["Bets"]) * 100
    ).round(2)

    sportsbook_analysis["ROI (%)"] = (
        (sportsbook_analysis["Profit"] / sportsbook_analysis["Stake"]) * 100
    ).round(2)

    sportsbook_analysis = sportsbook_analysis.rename(columns={
        "sportsbook": "Sportsbook"
    })

    sportsbook_analysis = sportsbook_analysis[
        ["Sportsbook", "Bets", "Wins", "Hit Rate (%)", "Profit", "Stake", "ROI (%)"]
    ].sort_values(by="Profit", ascending=False)

    # -------------------------
    # Tag analysis
    # -------------------------
    tag_analysis = (
        settled_df.dropna(subset=["tag"])
        .groupby("tag", as_index=False)
        .agg(
            Bets=("bet_id", "count"),
            Wins=("status", lambda x: (x == "win").sum()),
            Profit=("profit", "sum"),
            Stake=("stake", "sum"),
        )
    )

    tag_analysis["Hit Rate (%)"] = (
        (tag_analysis["Wins"] / tag_analysis["Bets"]) * 100
    ).round(2)

    tag_analysis["ROI (%)"] = (
        (tag_analysis["Profit"] / tag_analysis["Stake"]) * 100
    ).round(2)

    tag_analysis = tag_analysis.rename(columns={
        "tag": "Tag"
    })

    tag_analysis = tag_analysis[
        ["Tag", "Bets", "Wins", "Hit Rate (%)", "Profit", "Stake", "ROI (%)"]
    ].sort_values(by="Profit", ascending=False)

    # -------------------------
    # Bankroll
    # -------------------------
    bankroll_df = (
        settled_df.sort_values(by=["date", "time"])
        .groupby("date", as_index=False)["profit"]
        .sum()
    )
    bankroll_df["cumulative_profit"] = bankroll_df["profit"].cumsum()

    return (
        sportsbook_analysis,
        tag_analysis,
        bankroll_df,
    )


def main():
    st.title("Analytics")

    try:
        engine = get_engine()
        bets_df = load_bets(engine)

        filtered_df = apply_filters(bets_df)

        total_bets, total_profit, total_stake, roi_percent, hit_rate_percent, pending_count = calculate_kpis(filtered_df)

        (
            sportsbook_analysis,
            tag_analysis,
            bankroll_df,
        ) = build_aggregations(filtered_df)

        st.caption(f"Showing {len(filtered_df)} filtered bets")

        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Total Bets", total_bets)
        col2.metric("Pending Bets", pending_count)
        col3.metric("Total Profit", f"{total_profit:.2f}")
        col4.metric("Total Stake", f"{total_stake:.2f}")
        col5.metric("ROI (%)", f"{roi_percent:.2f}")
        col6.metric("Hit Rate (%)", f"{hit_rate_percent:.2f}")

        st.subheader("Charts")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Profit by Sportsbook")
            if not sportsbook_analysis.empty:
                st.bar_chart(sportsbook_analysis.set_index("Sportsbook")["Profit"])
            else:
                st.info("No settled data available for the selected filters.")

        with chart_col2:
            st.subheader("Profit by Tag")
            if not tag_analysis.empty:
                st.bar_chart(tag_analysis.set_index("Tag")["Profit"])
            else:
                st.info("No tag data available for the selected filters.")

        st.subheader("Bankroll Over Time")
        if not bankroll_df.empty:
            st.line_chart(bankroll_df.set_index("date")["cumulative_profit"])
        else:
            st.info("No settled data available for the selected filters.")

        st.subheader("Analysis Tables")

        table_col1, table_col2 = st.columns(2)

        with table_col1:
            st.subheader("Sportsbook Analysis")
            st.dataframe(sportsbook_analysis, use_container_width=True, hide_index=True)

        with table_col2:
            st.subheader("Tag Analysis")
            st.dataframe(tag_analysis, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error loading analytics page: {e}")


if __name__ == "__main__":
    main()