import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import time

load_dotenv()

st.set_page_config(page_title="Bet Management", layout="wide")

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

def show_feedback_message():
    if "feedback_message" in st.session_state and "feedback_type" in st.session_state:
        message = st.session_state.pop("feedback_message")
        message_type = st.session_state.pop("feedback_type")

        placeholder = st.empty()

        with placeholder.container():
            if message_type == "success":
                st.success(message)
            elif message_type == "warning":
                st.warning(message)
            elif message_type == "error":
                st.error(message)
            elif message_type == "info":
                st.info(message)

        time.sleep(2.5)
        placeholder.empty()

def set_feedback(message, message_type="success"):
    st.session_state["feedback_message"] = message
    st.session_state["feedback_type"] = message_type

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
    bets_df["time"] = pd.to_datetime(
        bets_df["time"].astype(str),
        format="%H:%M:%S",
        errors="coerce"
    ).dt.time

    bets_df["date_display"] = pd.to_datetime(bets_df["date"]).dt.strftime("%d/%m")
    bets_df["time_display"] = pd.to_datetime(
        bets_df["time"].astype(str),
        format="%H:%M:%S",
        errors="coerce"
    ).dt.strftime("%H:%M")

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
         status, stake, odds, sportsbook, tipster, profit
    )
    VALUES (
        :date, :time, :sport, :match, :selection,
         :status, :stake, :odds, :sportsbook, :tipster, :profit
    )
    """)

    with engine.begin() as conn:
        conn.execute(query, bet_data)

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


def update_bet(engine, bet_id, updated_data):
    query = text("""
        UPDATE bets
        SET
            date = :date,
            time = :time,
            sport = :sport,
            match = :match,
            selection = :selection,
            stake = :stake,
            odds = :odds,
            sportsbook = :sportsbook,
            tipster = :tipster,
            status = :status,
            profit = :profit
        WHERE bet_id = :bet_id
    """)

    with engine.begin() as conn:
        conn.execute(query, {**updated_data, "bet_id": bet_id})


def delete_bet(engine, bet_id):
    query = text("""
        DELETE FROM bets
        WHERE bet_id = :bet_id
    """)

    with engine.begin() as conn:
        conn.execute(query, {"bet_id": bet_id})


@st.dialog("Edit Bet")
def edit_bet_dialog(bet_id, bets_df, engine):
    selected_row = bets_df[bets_df["bet_id"] == bet_id].iloc[0]

    col1, col2 = st.columns(2)

    with col1:
        edit_date = st.date_input("Date", value=selected_row["date"])
        edit_time = st.time_input("Time", value=selected_row["time"])

        base_sport_options = ["Football", "Basketball", "Tennis", "Volleyball", "MMA", "eSports"]
        db_sport_options = bets_df["sport"].dropna().unique().tolist()
        edit_sport_options = sorted(set(base_sport_options) | set(db_sport_options)) + ["Other"]
        current_sport = selected_row["sport"]

        if current_sport in edit_sport_options:
            default_sport_index = edit_sport_options.index(current_sport)
        else:
            default_sport_index = edit_sport_options.index("Other")

        edit_sport_choice = st.selectbox(
            "Sport",
            edit_sport_options,
            index=default_sport_index
        )

        if edit_sport_choice == "Other":
            edit_sport = st.text_input("Enter new sport", value=current_sport if current_sport not in edit_sport_options else "")
        else:
            edit_sport = edit_sport_choice

        edit_match = st.text_input("Match", value=selected_row["match"])
        edit_selection = st.text_input("Selection", value=selected_row["selection"])

    with col2:
        edit_stake = st.number_input("Stake", min_value=0.0, value=float(selected_row["stake"]))
        edit_odds = st.number_input("Odds", min_value=1.01, value=float(selected_row["odds"]))

        edit_tipster_options = sorted(bets_df["tipster"].dropna().unique().tolist())
        current_tipster = selected_row["tipster"] if pd.notna(selected_row["tipster"]) else ""

        if current_tipster and current_tipster not in edit_tipster_options:
            edit_tipster_options.append(current_tipster)
            edit_tipster_options = sorted(edit_tipster_options)

        edit_tipster_select_options = [""] + edit_tipster_options + ["Other"]

        if current_tipster in edit_tipster_options:
            default_tipster_index = edit_tipster_select_options.index(current_tipster)
        elif current_tipster == "":
            default_tipster_index = 0
        else:
            default_tipster_index = edit_tipster_select_options.index("Other")

        edit_tipster_choice = st.selectbox(
            "Tipster",
            edit_tipster_select_options,
            index=default_tipster_index
        )

        if edit_tipster_choice == "Other":
            edit_tipster = st.text_input("Enter new tipster", value=current_tipster if current_tipster not in edit_tipster_options else "")
        elif edit_tipster_choice == "":
            edit_tipster = ""
        else:
            edit_tipster = edit_tipster_choice

        edit_sportsbook_options = sorted(bets_df["sportsbook"].dropna().unique().tolist())
        current_sportsbook = selected_row["sportsbook"]

        if current_sportsbook and current_sportsbook not in edit_sportsbook_options:
            edit_sportsbook_options.append(current_sportsbook)
            edit_sportsbook_options = sorted(edit_sportsbook_options)

        edit_sportsbook_select_options = edit_sportsbook_options + ["Other"]

        if current_sportsbook in edit_sportsbook_options:
            default_sportsbook_index = edit_sportsbook_select_options.index(current_sportsbook)
        else:
            default_sportsbook_index = edit_sportsbook_select_options.index("Other")

        edit_sportsbook_choice = st.selectbox(
            "Sportsbook",
            edit_sportsbook_select_options,
            index=default_sportsbook_index
        )

        if edit_sportsbook_choice == "Other":
            edit_sportsbook = st.text_input("Enter new sportsbook", value=current_sportsbook)
        else:
            edit_sportsbook = edit_sportsbook_choice

        edit_status = st.selectbox(
            "Status",
            ["pending", "win", "loss", "void"],
            index=["pending", "win", "loss", "void"].index(selected_row["status"])
        )

    save_col, delete_col = st.columns(2)

    with save_col:
        if st.button("Update Bet", use_container_width=True):
            if not edit_match.strip() or not edit_selection.strip() or not edit_sportsbook.strip() or not edit_sport.strip():
                st.error("Please fill in all required fields.")
            elif edit_stake <= 0:
                st.error("Stake must be greater than 0.")
            elif edit_odds <= 1:
                st.error("Odds must be greater than 1.")
            else:
                try:
                    profit = calculate_profit(edit_status, edit_odds, edit_stake)

                    updated_data = {
                        "date": edit_date,
                        "time": edit_time,
                        "sport": edit_sport.strip(),
                        "match": edit_match.strip(),
                        "selection": edit_selection.strip(),
                        "stake": edit_stake,
                        "odds": edit_odds,
                        "sportsbook": edit_sportsbook.strip(),
                        "tipster": edit_tipster.strip() if edit_tipster.strip() else None,
                        "status": edit_status,
                        "profit": profit,
                    }

                    update_bet(engine, bet_id, updated_data)
                    set_feedback("Bet updated successfully!", "success")
                    st.rerun()

                except Exception as e:
                    st.error(f"Error updating bet: {e}")

    st.markdown("---")
    st.caption("Delete this bet")

    confirm_delete = st.checkbox("I confirm deletion")

    with delete_col:
        if st.button("Delete Bet", use_container_width=True, type="primary"):
            if not confirm_delete:
                st.warning("Please confirm deletion first.")
            else:
                try:
                    delete_bet(engine, bet_id)
                    set_feedback("Bet deleted successfully!", "warning")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting bet: {e}")


def main():

    st.title("Bet Management")
    st.markdown("""
            <style>
            div[class*="st-key-edit_btn_"] button {
                background: rgba(255,255,255,0.02);
                border-radius: 12px;
                border: none;
                width: 44px;
                height: 44px;
                padding: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.15s ease;
            }
            div[class*="st-key-edit_btn_"] button:hover {
                background: rgba(255,255,255,0.08);
                border: none;
            }
            div[class*="st-key-edit_btn_"] button p {
                font-size: 20px;
                margin: 0;
            }
            </style>
        """, unsafe_allow_html=True)
    show_feedback_message()

    try:
        engine = get_engine()
        bets_df = load_bets(engine)

        st.sidebar.header("Filters")

        status_filter = st.sidebar.selectbox(
            "Status",
            ["All"] + sorted(bets_df["status"].dropna().unique().tolist())
        )

        sportsbook_filter = st.sidebar.selectbox(
            "Sportsbook",
            ["All"] + sorted(bets_df["sportsbook"].dropna().unique().tolist())
        )

        filtered_bets_df = bets_df.copy()

        if status_filter != "All":
            filtered_bets_df = filtered_bets_df[filtered_bets_df["status"] == status_filter]

        if sportsbook_filter != "All":
            filtered_bets_df = filtered_bets_df[filtered_bets_df["sportsbook"] == sportsbook_filter]

        st.subheader("Add New Bet")

        with st.form("bet_form"):
            col1, col2 = st.columns(2)

            with col1:
                date = st.date_input("Date")
                time = st.time_input("Time")
                base_sport_options = ["Football", "Basketball", "Tennis", "Volleyball", "MMA", "eSports"]
                db_sport_options = bets_df["sport"].dropna().unique().tolist()
                sport_options = sorted(set(base_sport_options) | set(db_sport_options)) + ["Other"]

                sport_choice = st.selectbox(
                    "Sport",
                    sport_options
                )

                if sport_choice == "Other":
                    sport = st.text_input("Enter new sport")
                else:
                    sport = sport_choice
                match = st.text_input("Match")
                selection = st.text_input("Selection")

            with col2:

                tipster_options = sorted(bets_df["tipster"].dropna().unique().tolist())
                tipster_choice = st.selectbox(
                    "Tipster (optional)",
                    [""] + tipster_options + ["Other"]
                )

                if tipster_choice == "Other":
                    tipster = st.text_input("Enter new tipster")
                elif tipster_choice == "":
                    tipster = ""
                else:
                    tipster = tipster_choice

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
                if not match.strip() or not selection.strip() or not sportsbook.strip() or not sport.strip():
                    st.error("Please fill in all required fields.")
                elif stake <= 0:
                    st.error("Stake must be greater than 0.")
                elif odds <= 1:
                    st.error("Odds must be greater than 1.")
                elif tipster_choice == "Other" and not tipster.strip():
                    st.error("Please enter a tipster.")
                else:
                    profit = calculate_profit(status, odds, stake)

                    bet_data = {
                        "date": date,
                        "time": time,
                        "sport": sport,
                        "match": match.strip(),
                        "selection": selection.strip(),
                        "status": status,
                        "stake": stake,
                        "odds": odds,
                        "sportsbook": sportsbook.strip(),
                        "tipster": tipster.strip() if tipster.strip() else None,
                        "profit": profit,
                    }

                    insert_bet(engine, bet_data)
                    set_feedback("Bet added successfully!", "success")
                    st.rerun()

            except Exception as e:
                st.error(f"Error inserting bet: {e}")

        pending_df = bets_df[bets_df["status"] == "pending"]

        pending_count = len(pending_df)
        pending_units = pending_df["stake"].sum() if not pending_df.empty else 0.0

        col1, col2 = st.columns(2)

        col1.metric("Pending Bets", pending_count)
        col2.metric("Pending Units", f"{pending_units:.2f} u")

        st.subheader("All Bets")

        bets_limit = st.selectbox(
            "Number of bets to display",
            options=[10, 25, 50, 100, 200],
            index=2
        )

        if status_filter == "pending":
            display_bets_df = filtered_bets_df
        else:
            display_bets_df = filtered_bets_df.head(bets_limit)

        status_map = {
            "Not settled": "pending",
            "Won": "win",
            "Lost": "loss",
            "Void": "void",
        }

        reverse_status_map = {v: k for k, v in status_map.items()}

        if not display_bets_df.empty:
            for _, row in display_bets_df.iterrows():
                with st.container(border=True):
                    cols = st.columns([1.0, 1.0, 1.2, 2.0, 1.6, 1.1, 1.1, 0.8, 0.8, 1.2, 0.9, 0.5])

                    cols[0].markdown(f"**Date**<br>{row['date_display']}", unsafe_allow_html=True)
                    cols[1].markdown(f"**Time**<br>{row['time_display']}", unsafe_allow_html=True)
                    cols[2].markdown(f"**Sport**<br>{row['sport']}", unsafe_allow_html=True)
                    cols[3].markdown(f"**Match**<br>{row['match']}", unsafe_allow_html=True)
                    cols[4].markdown(f"**Selection**<br>{row['selection']}", unsafe_allow_html=True)
                    cols[5].markdown(f"**Sportsbook**<br>{row['sportsbook']}", unsafe_allow_html=True)
                    cols[6].markdown(f"**Tipster**<br>{row['tipster'] if pd.notna(row['tipster']) else '-'}", unsafe_allow_html=True)
                    cols[7].markdown(f"**Stake**<br>{row['stake']:.2f} u", unsafe_allow_html=True)
                    cols[8].markdown(f"**Odds**<br>{row['odds']:.2f}", unsafe_allow_html=True)

                    current_status_label = reverse_status_map.get(row["status"], "Not settled")

                    selected_status_label = cols[9].selectbox(
                        "Status",
                        options=list(status_map.keys()),
                        index=list(status_map.keys()).index(current_status_label),
                        key=f"all_status_{row['bet_id']}",
                        label_visibility="collapsed"
                    )

                    selected_status = status_map[selected_status_label]

                    if selected_status != row["status"]:
                        try:
                            update_bet_status(engine, row["bet_id"], selected_status)
                            set_feedback("Bet status updated successfully!", "success")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating bet: {e}")

                    profit = row["profit"]

                    if pd.isna(profit):
                        cols[10].markdown("**Profit**<br><span style='color:gray'>Pending</span>", unsafe_allow_html=True)
                    elif profit > 0:
                        cols[10].markdown(
                            f"**Profit**<br><span style='color:#22c55e'>{profit:.2f}</span>",
                            unsafe_allow_html=True
                        )
                    elif profit < 0:
                        cols[10].markdown(
                            f"**Profit**<br><span style='color:#ef4444'>{profit:.2f}</span>",
                            unsafe_allow_html=True
                        )
                    else:
                        cols[10].markdown(
                            f"**Profit**<br><span style='color:#9ca3af'>{profit:.2f}</span>",
                            unsafe_allow_html=True
                        )

                    if cols[11].button(":material/edit:", key=f"edit_btn_{row['bet_id']}", help="Edit this bet"):
                        edit_bet_dialog(row["bet_id"], bets_df, engine)
        else:
            st.info("No bets found.")

    except Exception as e:
        st.error(f"Error loading page: {e}")

if __name__ == "__main__":
    main()