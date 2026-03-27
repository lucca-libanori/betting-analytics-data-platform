import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Bet Management", layout="wide")

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


def calculate_profit(status, odds, stake):
    if status == "win":
        return round((odds - 1) * stake, 2)
    elif status == "loss":
        return round(-stake, 2)
    elif status == "void":
        return 0.0
    elif status == "pending":
        return None
    return None


def insert_bet(engine, bet_data):
    query = text("""
    INSERT INTO bets (
        date, time, sport, match, selection,
        tag, status, stake, odds, sportsbook, profit
    )
    VALUES (
        :date, :time, :sport, :match, :selection,
        :tag, :status, :stake, :odds, :sportsbook, :profit
    )
    """)

    with engine.begin() as conn:
        conn.execute(query, bet_data)


def load_pending_bets(engine):
    query = """
    SELECT
        bet_id,
        date,
        time,
        match,
        selection,
        odds,
        stake,
        sportsbook
    FROM bets
    WHERE status = 'pending'
    ORDER BY date ASC, time ASC;
    """
    pending_df = pd.read_sql(query, engine)
    pending_df["date"] = pd.to_datetime(pending_df["date"]).dt.date
    return pending_df


def update_bet_status(engine, bet_id, new_status):
    get_bet_query = text("""
    SELECT odds, stake
    FROM bets
    WHERE bet_id = :bet_id
    """)

    update_query = text("""
    UPDATE bets
    SET status = :status,
        profit = :profit
    WHERE bet_id = :bet_id
    """)

    with engine.begin() as conn:
        result = conn.execute(get_bet_query, {"bet_id": bet_id}).fetchone()

        if result is None:
            raise ValueError("Bet not found.")

        odds = result[0]
        stake = result[1]
        profit = calculate_profit(new_status, odds, stake)

        conn.execute(update_query, {
            "status": new_status,
            "profit": profit,
            "bet_id": bet_id
        })


def main():
    st.title("Bet Management")

    try:
        engine = get_engine()
        bets_df = load_bets(engine)

        st.subheader("Add New Bet")

        with st.form("bet_form"):
            col1, col2 = st.columns(2)

            with col1:
                date = st.date_input("Date")
                time = st.time_input("Time")
                st.text_input("Sport", value="Football", disabled=True)
                sport = "Football"
                match = st.text_input("Match")
                selection = st.text_input("Selection")

            with col2:
                tag = st.text_input("Tag (optional)")
                status = st.selectbox(
                    "Status",
                    ["pending", "win", "loss", "void"],
                    index=0
                )
                stake = st.number_input("Stake", min_value=0.0)
                odds = st.number_input("Odds", min_value=1.01)

                sportsbook_options = sorted(bets_df["sportsbook"].dropna().unique().tolist())
                sportsbook_choice = st.selectbox(
                    "Sportsbook",
                    sportsbook_options + ["Other"]
                )

                if sportsbook_choice == "Other":
                    sportsbook = st.text_input("Enter new sportsbook")
                else:
                    sportsbook = sportsbook_choice

            submitted = st.form_submit_button("Save Bet")

        if submitted:
            try:
                if not match.strip() or not selection.strip() or not sportsbook.strip():
                    st.error("Please fill in all required fields.")
                elif stake <= 0:
                    st.error("Stake must be greater than 0.")
                elif odds <= 1:
                    st.error("Odds must be greater than 1.")
                else:
                    profit = calculate_profit(status, odds, stake)

                    bet_data = {
                        "date": date,
                        "time": time,
                        "sport": sport,
                        "match": match.strip(),
                        "selection": selection.strip(),
                        "tag": tag.strip() if tag.strip() else None,
                        "status": status,
                        "stake": stake,
                        "odds": odds,
                        "sportsbook": sportsbook.strip(),
                        "profit": profit,
                    }

                    insert_bet(engine, bet_data)
                    st.success("Bet added successfully!")
                    st.rerun()

            except Exception as e:
                st.error(f"Error inserting bet: {e}")

        pending_bets_df = load_pending_bets(engine)

        st.subheader("Settle Pending Bets")

        if not pending_bets_df.empty:
            pending_options = {
                f"{row['bet_id']} | {row['date']} {row['time']} | {row['match']} | {row['selection']} | {row['sportsbook']}": row["bet_id"]
                for _, row in pending_bets_df.iterrows()
            }

            selected_bet_label = st.selectbox(
                "Select Pending Bet",
                list(pending_options.keys())
            )

            new_status = st.selectbox(
                "New Status",
                ["win", "loss", "void"]
            )

            if st.button("Update Bet Status"):
                try:
                    selected_bet_id = pending_options[selected_bet_label]
                    update_bet_status(engine, selected_bet_id, new_status)
                    st.success("Bet status updated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error updating bet: {e}")
        else:
            st.info("No pending bets found.")

        management_display_df = bets_df[
    ["bet_id", "date", "time", "match", "selection", "tag", "status", "stake", "odds", "sportsbook", "profit"]
]
        st.subheader("All Bets")
        st.dataframe(management_display_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error loading page: {e}")


if __name__ == "__main__":
    main()