import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "betting_analytics",
    "user": "postgres",
    "password": "your_postgre_password"
}


def get_engine():
    connection_string = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    return create_engine(connection_string)


def load_bets(engine):
    query = """
    SELECT *
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

    total_profit = round(filtered_df["profit"].sum(), 2) if not filtered_df.empty else 0.0
    total_stake = filtered_df["stake"].sum() if not filtered_df.empty else 0.0

    roi_percent = round((total_profit / total_stake) * 100, 2) if total_stake > 0 else 0.0

    resolved_bets = filtered_df[filtered_df["status"].isin(["win", "loss", "void"])]
    win_count = (resolved_bets["status"] == "win").sum()
    hit_rate_percent = round((win_count / len(resolved_bets)) * 100, 2) if len(resolved_bets) > 0 else 0.0

    return total_bets, total_profit, total_stake, roi_percent, hit_rate_percent


def build_aggregations(filtered_df):
    if filtered_df.empty:
        profit_by_sport = pd.DataFrame(columns=["sport", "profit"])
        profit_by_sportsbook = pd.DataFrame(columns=["sportsbook", "profit"])
        profit_by_tag = pd.DataFrame(columns=["tag", "profit"])
        roi_by_sport = pd.DataFrame(columns=["sport", "profit", "stake", "roi_percent"])
        roi_by_sportsbook = pd.DataFrame(columns=["sportsbook", "profit", "stake", "roi_percent"])
        bankroll_df = pd.DataFrame(columns=["date", "cumulative_profit"])

        return (
            profit_by_sport,
            profit_by_sportsbook,
            profit_by_tag,
            roi_by_sport,
            roi_by_sportsbook,
            bankroll_df,
        )

    profit_by_sport = (
        filtered_df.groupby("sport", as_index=False)["profit"]
        .sum()
        .sort_values(by="profit", ascending=False)
    )

    profit_by_sportsbook = (
        filtered_df.groupby("sportsbook", as_index=False)["profit"]
        .sum()
        .sort_values(by="profit", ascending=False)
    )

    profit_by_tag = (
        filtered_df.dropna(subset=["tag"])
        .groupby("tag", as_index=False)["profit"]
        .sum()
        .sort_values(by="profit", ascending=False)
    )

    roi_by_sport = (
        filtered_df.groupby("sport", as_index=False)
        .agg({"profit": "sum", "stake": "sum"})
    )
    roi_by_sport["roi_percent"] = (
        (roi_by_sport["profit"] / roi_by_sport["stake"]) * 100
    ).round(2)
    roi_by_sport = roi_by_sport.sort_values(by="roi_percent", ascending=False)

    roi_by_sportsbook = (
        filtered_df.groupby("sportsbook", as_index=False)
        .agg({"profit": "sum", "stake": "sum"})
    )
    roi_by_sportsbook["roi_percent"] = (
        (roi_by_sportsbook["profit"] / roi_by_sportsbook["stake"]) * 100
    ).round(2)
    roi_by_sportsbook = roi_by_sportsbook.sort_values(by="roi_percent", ascending=False)

    bankroll_df = (
        filtered_df.sort_values(by=["date", "time"])
        .groupby("date", as_index=False)["profit"]
        .sum()
    )
    bankroll_df["cumulative_profit"] = bankroll_df["profit"].cumsum()

    return (
        profit_by_sport,
        profit_by_sportsbook,
        profit_by_tag,
        roi_by_sport,
        roi_by_sportsbook,
        bankroll_df,
    )

def main():
    st.set_page_config(page_title="Betting Analytics Dashboard", layout="wide")
    st.title("Betting Analytics Dashboard")

    try:
        engine = get_engine()
        bets_df = load_bets(engine)

        filtered_df = apply_filters(bets_df)

        total_bets, total_profit, total_stake, roi_percent, hit_rate_percent = calculate_kpis(filtered_df)
        
        profit_by_sport, profit_by_sportsbook, profit_by_tag, roi_by_sport, roi_by_sportsbook, bankroll_df, = build_aggregations(filtered_df)
        
        st.caption(f"Showing {len(filtered_df)} filtered bets")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Bets", total_bets)
        col2.metric("Total Profit", f"{total_profit:.2f}")
        col3.metric("Total Stake", f"{total_stake:.2f}")
        col4.metric("ROI (%)", f"{roi_percent:.2f}")
        col5.metric("Hit Rate (%)", f"{hit_rate_percent:.2f}")

        st.subheader("Charts")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.subheader("Profit by Sport")
            if not profit_by_sport.empty:
                st.bar_chart(profit_by_sport.set_index("sport")["profit"])
            else:
                st.info("No data available for the selected filters.")

        with chart_col2:
            st.subheader("Profit by Tag")
            if not profit_by_tag.empty:
                st.bar_chart(profit_by_tag.set_index("tag")["profit"])
            else:
                st.info("No tag data available for the selected filters.")

        st.subheader("Bankroll Over Time")
        if not bankroll_df.empty:
            st.line_chart(bankroll_df.set_index("date")["cumulative_profit"])
        else:
            st.info("No data available for the selected filters.")

        table_col1, table_col2 = st.columns(2)

        with table_col1:
            st.subheader("Profit by Sportsbook")
            st.dataframe(profit_by_sportsbook, use_container_width=True)

        with table_col2:
            st.subheader("Profit by Tag")
            st.dataframe(profit_by_tag, use_container_width=True)

        st.subheader("All Bets")
        st.dataframe(filtered_df, use_container_width=True)

        st.subheader("ROI Analysis")

        roi_col1, roi_col2 = st.columns(2)

        with roi_col1:
            st.subheader("ROI by Sport")
            st.dataframe(roi_by_sport, use_container_width=True)

        with roi_col2:
            st.subheader("ROI by Sportsbook")
            st.dataframe(roi_by_sportsbook, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading dashboard: {e}")


if __name__ == "__main__":
    main()
