import streamlit as st
import math
import pandas as pd

st.set_page_config(
    page_title="Model Calculator",
    layout="wide"
)

# ==========================
# CONFIG
# ==========================

DEFAULT_BANKROLL = 100
DEFAULT_KELLY_FRACTION = 0.25
MAX_EVENTS = 15
MAX_ITER = 200
LAMBDA_TOL = 1e-9


# ==========================
# POISSON HELPERS
# ==========================

def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * lam**k) / math.factorial(k)


def prob_over_05(lam):
    return 1 - math.exp(-lam)


def prob_over_15(lam):
    return 1 - (
        poisson_pmf(0, lam)
        + poisson_pmf(1, lam)
    )


def prob_over_25(lam):
    return 1 - (
        poisson_pmf(0, lam)
        + poisson_pmf(1, lam)
        + poisson_pmf(2, lam)
    )


def prob_over_35(lam):
    return 1 - sum(poisson_pmf(k, lam) for k in range(4))


def prob_over_45(lam):
    return 1 - sum(poisson_pmf(k, lam) for k in range(5))


def prob_over_55(lam):
    return 1 - sum(poisson_pmf(k, lam) for k in range(6))


def prob_over_65(lam):
    return 1 - sum(poisson_pmf(k, lam) for k in range(7))


def prob_over_75(lam):
    return 1 - sum(poisson_pmf(k, lam) for k in range(8))


PROB_FUNCS = {
    0.5: prob_over_05,
    1.5: prob_over_15,
    2.5: prob_over_25,
    3.5: prob_over_35,
    4.5: prob_over_45,
    5.5: prob_over_55,
    6.5: prob_over_65,
    7.5: prob_over_75,
}

OUTPUT_LINES = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]

# Lines available for player inputs in the H2H model
H2H_LINE_OPTIONS = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]


def prob_over_line(lam, line):
    threshold = int(math.floor(line))
    cumulative = sum(poisson_pmf(k, lam) for k in range(threshold + 1))
    return max(0.0, min(1.0, 1.0 - cumulative))


def validate_line(line):
    if abs((line * 2) % 2 - 1) > 1e-9:
        raise ValueError("Line must be X.5, for example 0.5, 1.5, 2.5.")
    if line < 0.5:
        raise ValueError("Minimum accepted line is 0.5.")


# ==========================
# LAMBDA SOLVER
# ==========================

def find_lambda(target_prob, line):
    validate_line(line)

    if not (0.0 < target_prob < 1.0):
        raise ValueError("Target probability must be between 0 and 1.")

    low, high = 0.0001, 50.0

    for _ in range(MAX_ITER):
        mid = (low + high) / 2

        if high - low < LAMBDA_TOL:
            break

        prob = prob_over_line(mid, line)

        if prob > target_prob:
            high = mid
        else:
            low = mid

    return (low + high) / 2


def weighted_lambda_generic(lambda_pairs):
    total_weight = 0.0
    weighted_sum = 0.0

    for lam, line in lambda_pairs:
        weight = line
        weighted_sum += lam * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def resolve_lambda_custom_lines(odds_pairs, label="MODEL"):
    available = [
        (line, odd)
        for line, odd in odds_pairs
        if odd is not None
    ]

    if not available:
        raise ValueError(f"Provide at least one fair odd for {label}.")

    lambda_pairs = []

    for line, odd in available:
        validate_line(line)

        if odd <= 1:
            raise ValueError(f"[{label}] Fair odd for Over {line} must be greater than 1.")

        prob = 1 / odd
        lam = find_lambda(prob, line)
        lambda_pairs.append((lam, line))

    return weighted_lambda_generic(lambda_pairs)


# ==========================
# KELLY
# ==========================

def kelly_fraction(prob, market_odd):
    b = market_odd - 1

    if b <= 0:
        return 0

    q = 1 - prob

    kelly = ((b * prob) - q) / b

    return max(0, kelly)


def kelly_stake(prob, market_odd, bankroll, fraction):
    kelly_full = kelly_fraction(prob, market_odd)

    stake = (
        bankroll
        * kelly_full
        * fraction
    )

    return kelly_full, stake


def value_label(fair_odd, market_odd):
    if market_odd > fair_odd * 1.15:
        return "🔥 HIGH VALUE"

    elif market_odd > fair_odd * 1.05:
        return "✅ Value"

    elif market_odd >= fair_odd * 0.98:
        return "⚖️ Fair"

    else:
        return "❌ No Value"


# ==========================
# MODEL
# ==========================

def price_off_target_market(
    odds_over_05=None,
    odds_over_15=None,
    odds_over_25=None,
    off_target_rate=0.4
):

    probs = []

    if odds_over_05:
        probs.append((1 / odds_over_05, 0.5))

    if odds_over_15:
        probs.append((1 / odds_over_15, 1.5))

    if odds_over_25:
        probs.append((1 / odds_over_25, 2.5))

    if not probs:
        raise ValueError(
            "Provide at least one line"
        )

    lambdas = []

    for prob, line in probs:
        lam = find_lambda(prob, line)
        lambdas.append(lam)

    lambda_shots = (
        sum(lambdas) / len(lambdas)
    )

    lambda_off = (
        lambda_shots
        * off_target_rate
    )

    p_over_05 = prob_over_05(lambda_off)
    p_over_15 = prob_over_15(lambda_off)
    p_over_25 = prob_over_25(lambda_off)

    return {
        "lambda_shots": lambda_shots,
        "lambda_off_target": lambda_off,

        "over_0_5_prob": p_over_05,
        "over_0_5_odds": (
            1 / p_over_05
            if p_over_05 > 0
            else None
        ),

        "over_1_5_prob": p_over_15,
        "over_1_5_odds": (
            1 / p_over_15
            if p_over_15 > 0
            else None
        ),

        "over_2_5_prob": p_over_25,
        "over_2_5_odds": (
            1 / p_over_25
            if p_over_25 > 0
            else None
        ),
    }

def prob_to_lambda(prob):
    return -math.log(1 - prob)


def h2h_probs(lambda_a, lambda_b, max_events=15):
    p_a = p_draw = p_b = 0

    probs_a = [poisson_pmf(i, lambda_a) for i in range(max_events + 1)]
    probs_b = [poisson_pmf(j, lambda_b) for j in range(max_events + 1)]

    probs_a[-1] += max(0.0, 1 - sum(probs_a))
    probs_b[-1] += max(0.0, 1 - sum(probs_b))

    for i in range(max_events + 1):
        for j in range(max_events + 1):
            p = probs_a[i] * probs_b[j]

            if i > j:
                p_a += p
            elif i == j:
                p_draw += p
            else:
                p_b += p

    return p_a, p_draw, p_b


def prob_to_odd(prob):
    return 1 / prob if prob > 0 else None

def outside_box_sot_model(
    odds_sot_over_05=None,
    odds_sot_over_15=None,
    outside_box_rate=0.35
):
    probs = []

    if odds_sot_over_05:
        probs.append((1 / odds_sot_over_05, 0.5))

    if odds_sot_over_15:
        probs.append((1 / odds_sot_over_15, 1.5))

    if not probs:
        raise ValueError("Provide at least one fair odd.")

    lambdas = []

    for prob, line in probs:
        lam = find_lambda(prob, line)
        lambdas.append(lam)

    lambda_sot = sum(lambdas) / len(lambdas)
    lambda_outside_sot = lambda_sot * outside_box_rate

    p05 = prob_over_05(lambda_outside_sot)
    p15 = prob_over_15(lambda_outside_sot)

    return {
        "lambda_sot": lambda_sot,
        "lambda_outside_sot": lambda_outside_sot,

        "over_0_5_prob": p05,
        "over_0_5_odd": 1 / p05 if p05 > 0 else None,

        "over_1_5_prob": p15,
        "over_1_5_odd": 1 / p15 if p15 > 0 else None,
    }

def goal_or_assist_model(p_goal_percent, p_assist_percent, market_odd):
    p_goal = p_goal_percent / 100
    p_assist = p_assist_percent / 100

    overlap = min(p_goal, p_assist) * 0.17

    combined_prob = p_goal + p_assist - overlap

    fair_odd = 1 / combined_prob if combined_prob > 0 else None

    ev = combined_prob * market_odd

    kelly_full, stake = kelly_stake(
        combined_prob,
        market_odd,
        DEFAULT_BANKROLL,
        DEFAULT_KELLY_FRACTION
    )

    return {
        "p_goal": p_goal,
        "p_assist": p_assist,
        "overlap": overlap,
        "combined_prob": combined_prob,
        "fair_odd": fair_odd,
        "ev": ev,
        "kelly": kelly_full,
        "stake": stake
    }

def value_diagnosis(fair_odd, market_odd):
    edge = (market_odd / fair_odd - 1) * 100

    if market_odd > fair_odd * 1.20:
        label = "🔥 EXCEPTIONAL VALUE"
    elif market_odd > fair_odd * 1.10:
        label = "✅ HIGH VALUE"
    elif market_odd > fair_odd * 1.05:
        label = "✅ Value"
    elif market_odd >= fair_odd * 0.98:
        label = "⚖️ Fair"
    else:
        label = "❌ No Value"

    return label, edge


def goalkeeper_saves_model(adversario_odds, save_rate):
    if not (0 < save_rate < 1):
        raise ValueError("Save rate must be between 0 and 1.")

    lambda_opponent_sot = resolve_lambda_custom_lines(
        adversario_odds,
        label="Opponent SOT"
    )

    lambda_goalkeeper_saves = lambda_opponent_sot * save_rate

    rows = []

    for line in OUTPUT_LINES:
        prob = PROB_FUNCS[line](lambda_goalkeeper_saves)
        fair_odd = 1 / prob if prob > 0 else None

        rows.append({
            "line": line,
            "prob": prob,
            "fair_odd": fair_odd
        })

    return {
        "lambda_opponent_sot": lambda_opponent_sot,
        "save_rate": save_rate,
        "lambda_goalkeeper_saves": lambda_goalkeeper_saves,
        "lines": rows
    }


# ==========================
# PAGE
# ==========================

st.title("Model Calculator")

model_option = st.selectbox(
    "Select Model",
    [
        "Off Target Shots",
        "H2H",
        "Outside Box Shot on Target",
        "G/A",
        "Goalkeeper Saves",
        "Modelo 2"
    ]
)

if model_option == "Off Target Shots":
    left_col, right_col = st.columns(2)

    with left_col:

        st.subheader("Model Inputs")
        
        st.info(
            "Using fixed settings: "
            "100u bankroll • 25% Kelly"
        )

        odds_05 = st.number_input(
            "Fair Odds Over 0.5 Shots",
            min_value=1.01,
            value=2.00
        )

        odds_15 = st.number_input(
            "Fair Odds Over 1.5 Shots",
            min_value=1.01,
            value=4.00
        )

        odds_25 = st.number_input(
            "Fair Odds Over 2.5 Shots",
            min_value=1.01,
            value=8.00
        )

        off_target_rate = st.number_input(
            "Off Target Rate",
            min_value=0.0,
            max_value=1.0,
            value=0.40
        )

    with right_col:

        st.subheader(
            "Market Odds"
        )

        market_05 = st.number_input(
            "Market Over 0.5",
            min_value=1.01,
            value=2.00
        )

        market_15 = st.number_input(
            "Market Over 1.5",
            min_value=1.01,
            value=4.00
        )

        market_25 = st.number_input(
            "Market Over 2.5",
            min_value=1.01,
            value=8.00
        )

    calculate = st.button(
        "Calculate Model"
    )

    if calculate:

        result = price_off_target_market(
            odds_over_05=odds_05,
            odds_over_15=odds_15,
            odds_over_25=odds_25,
            off_target_rate=off_target_rate
        )

        st.subheader("Model Output")

        metric_col1, metric_col2 = st.columns(2)

        metric_col1.metric(
            "Lambda Shots",
            f"{result['lambda_shots']:.4f}"
        )

        metric_col2.metric(
            "Lambda Off Target",
            f"{result['lambda_off_target']:.4f}"
        )

        rows = []

        market_dict = {
            "0.5": market_05,
            "1.5": market_15,
            "2.5": market_25
        }

        for line in ["0.5", "1.5", "2.5"]:

            prob = result[
                f"over_{line.replace('.', '_')}_prob"
            ]

            fair_odd = result[
                f"over_{line.replace('.', '_')}_odds"
            ]

            market_odd = market_dict[line]

            kelly_full, stake = kelly_stake(
                prob,
                market_odd,
                DEFAULT_BANKROLL,
                DEFAULT_KELLY_FRACTION
            )

            rows.append({
                "Market":
                    f"Over {line}",

                "Probability":
                    f"{prob:.2%}",

                "Fair Odds":
                    round(fair_odd, 2),

                "Market Odds":
                    market_odd,

                "Value":
                    value_label(
                        fair_odd,
                        market_odd
                    ),

                "Kelly":
                    f"{kelly_full:.2%}",

                "Stake":
                    f"{stake:.2f} u"
            })

        result_df = pd.DataFrame(rows)

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True
        )
elif model_option == "H2H":
    st.subheader("H2H Calculator")

    st.info("Using fixed settings: 100u bankroll • 25% Kelly")

    input_col1, input_col2 = st.columns(2)

    with input_col1:
        st.subheader("Player A")

        name_a = st.text_input("Player A Name", value="Player A")
        market_odd_a = st.number_input(
            "Market Odd Player A",
            min_value=1.01,
            value=2.00
        )
        prob_a_percent = st.number_input(
            "Probability Player A Over 0.5 (%)",
            min_value=0.01,
            max_value=99.99,
            value=50.00
        )

    with input_col2:
        st.subheader("Player B")

        name_b = st.text_input("Player B Name", value="Player B")
        market_odd_b = st.number_input(
            "Market Odd Player B",
            min_value=1.01,
            value=2.00
        )
        prob_b_percent = st.number_input(
            "Probability Player B Over 0.5 (%)",
            min_value=0.01,
            max_value=99.99,
            value=50.00
        )

    market_odd_draw = st.number_input(
        "Market Odd Draw",
        min_value=1.01,
        value=3.00
    )
        
    calculate_h2h = st.button("Calculate H2H")

    if calculate_h2h:
        prob_a = prob_a_percent / 100
        prob_b = prob_b_percent / 100

        lambda_a = prob_to_lambda(prob_a)
        lambda_b = prob_to_lambda(prob_b)

        p_a, p_draw, p_b = h2h_probs(
            lambda_a,
            lambda_b,
            max_events=MAX_EVENTS
        )

        fair_a = prob_to_odd(p_a)
        fair_draw = prob_to_odd(p_draw)
        fair_b = prob_to_odd(p_b)

        k_a, stake_a = kelly_stake(
            p_a,
            market_odd_a,
            DEFAULT_BANKROLL,
            DEFAULT_KELLY_FRACTION
        )

        k_draw, stake_draw = kelly_stake(
            p_draw,
            market_odd_draw,
            DEFAULT_BANKROLL,
            DEFAULT_KELLY_FRACTION
        )

        k_b, stake_b = kelly_stake(
            p_b,
            market_odd_b,
            DEFAULT_BANKROLL,
            DEFAULT_KELLY_FRACTION
        )

        st.subheader("Model Output")

        metric_col1, metric_col2 = st.columns(2)

        metric_col1.metric(f"Lambda {name_a}", f"{lambda_a:.4f}")
        metric_col2.metric(f"Lambda {name_b}", f"{lambda_b:.4f}")

        result_df = pd.DataFrame([
            {
                "Outcome": name_a,
                "Probability": f"{p_a:.2%}",
                "Fair Odds": round(fair_a, 2),
                "Market Odds": market_odd_a,
                "Value": value_label(fair_a, market_odd_a),
                "Kelly": f"{k_a:.2%}",
                "Stake": f"{stake_a:.2f} u"
            },
            {
                "Outcome": "Draw",
                "Probability": f"{p_draw:.2%}",
                "Fair Odds": round(fair_draw, 2),
                "Market Odds": market_odd_draw,
                "Value": value_label(fair_draw, market_odd_draw),
                "Kelly": f"{k_draw:.2%}",
                "Stake": f"{stake_draw:.2f} u"
            },
            {
                "Outcome": name_b,
                "Probability": f"{p_b:.2%}",
                "Fair Odds": round(fair_b, 2),
                "Market Odds": market_odd_b,
                "Value": value_label(fair_b, market_odd_b),
                "Kelly": f"{k_b:.2%}",
                "Stake": f"{stake_b:.2f} u"
            },
        ])

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True
        )

elif model_option == "Outside Box Shot on Target":
    st.subheader("Outside Box Shot on Target Calculator")

    st.info("Using fixed settings: 100u bankroll • 25% Kelly")

    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("Model Inputs")

        odds_sot_05 = st.number_input(
            "Fair Odds Over 0.5 Shot on Target",
            min_value=1.01,
            value=2.00
        )

        odds_sot_15 = st.number_input(
            "Fair Odds Over 1.5 Shots on Target",
            min_value=1.01,
            value=4.00
        )

        outside_box_rate = st.number_input(
            "Outside Box Rate",
            min_value=0.0,
            max_value=1.0,
            value=0.35
        )

    with right_col:
        st.subheader("Market Odds")

        market_05 = st.number_input(
            "Market Over 0.5 Outside Box SOT",
            min_value=1.01,
            value=2.00
        )

        market_15 = st.number_input(
            "Market Over 1.5 Outside Box SOT",
            min_value=1.01,
            value=4.00
        )

    calculate_outside_sot = st.button("Calculate Outside Box SOT")

    if calculate_outside_sot:
        result = outside_box_sot_model(
            odds_sot_over_05=odds_sot_05,
            odds_sot_over_15=odds_sot_15,
            outside_box_rate=outside_box_rate
        )

        st.subheader("Model Output")

        metric_col1, metric_col2 = st.columns(2)

        metric_col1.metric(
            "Lambda SOT",
            f"{result['lambda_sot']:.4f}"
        )

        metric_col2.metric(
            "Lambda Outside Box SOT",
            f"{result['lambda_outside_sot']:.4f}"
        )

        rows = []

        market_dict = {
            "0.5": market_05,
            "1.5": market_15
        }

        for line in ["0.5", "1.5"]:
            prob = result[f"over_{line.replace('.', '_')}_prob"]
            fair_odd = result[f"over_{line.replace('.', '_')}_odd"]
            market_odd = market_dict[line]

            kelly_full, stake = kelly_stake(
                prob,
                market_odd,
                DEFAULT_BANKROLL,
                DEFAULT_KELLY_FRACTION
            )

            rows.append({
                "Market": f"Over {line}",
                "Probability": f"{prob:.2%}",
                "Fair Odds": round(fair_odd, 2),
                "Market Odds": market_odd,
                "Value": value_label(fair_odd, market_odd),
                "Kelly": f"{kelly_full:.2%}",
                "Stake": f"{stake:.2f} u"
            })

        result_df = pd.DataFrame(rows)

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True
        )
elif model_option == "G/A":
    st.subheader("Goal or Assist Calculator")

    st.info("Using fixed settings: 100u bankroll • 25% Kelly")

    col1, col2, col3 = st.columns(3)

    with col1:
        p_goal = st.number_input(
            "Goal Probability (%)",
            min_value=0.01,
            max_value=100.0,
            value=30.0
        )

    with col2:
        p_assist = st.number_input(
            "Assist Probability (%)",
            min_value=0.01,
            max_value=100.0,
            value=20.0
        )

    with col3:
        market_odd = st.number_input(
            "Market Odd",
            min_value=1.01,
            value=2.00
        )

    calculate_goal_assist = st.button("Calculate Goal or Assist")

    if calculate_goal_assist:
        result = goal_or_assist_model(
            p_goal,
            p_assist,
            market_odd
        )

        st.subheader("Model Output")

        metric_col1, metric_col2, metric_col3 = st.columns(3)

        metric_col1.metric(
            "Combined Probability",
            f"{result['combined_prob']:.2%}"
        )

        metric_col2.metric(
            "Fair Odd",
            f"{result['fair_odd']:.2f}"
        )

        metric_col3.metric(
            "EV",
            f"{result['ev']:.3f}"
        )

        result_df = pd.DataFrame([
            {
                "Market": "Goal or Assist",
                "Goal Probability": f"{result['p_goal']:.2%}",
                "Assist Probability": f"{result['p_assist']:.2%}",
                "Overlap": f"{result['overlap']:.2%}",
                "Combined Probability": f"{result['combined_prob']:.2%}",
                "Fair Odds": round(result["fair_odd"], 2),
                "Market Odds": market_odd,
                "Value": value_label(result["fair_odd"], market_odd),
                "Kelly": f"{result['kelly']:.2%}",
                "Stake": f"{result['stake']:.2f} u"
            }
        ])

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True
        )


elif model_option == "Goalkeeper Saves":
    st.subheader("Goalkeeper Saves Calculator")

    st.info("Using fixed settings: 100u bankroll • 25% Kelly")

    input_col, market_col = st.columns(2)

    with input_col:
        st.subheader("Opponent Shots on Target Fair Odds")

        st.caption("Choose up to 3 opponent SOT lines. At least one line is required.")

        line_options = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5]

        use_line_1 = st.checkbox("Use opponent line #1", value=True)
        if use_line_1:
            opponent_line_1 = st.selectbox(
                "Opponent SOT Line #1",
                line_options,
                index=2,
                key="gk_line_1"
            )
            opponent_odd_1 = st.number_input(
                f"Fair Odd Over {opponent_line_1} Opponent SOT",
                min_value=1.01,
                value=2.00,
                key="gk_odd_1"
            )
        else:
            opponent_line_1 = None
            opponent_odd_1 = None

        use_line_2 = st.checkbox("Use opponent line #2", value=False)
        if use_line_2:
            opponent_line_2 = st.selectbox(
                "Opponent SOT Line #2",
                line_options,
                index=3,
                key="gk_line_2"
            )
            opponent_odd_2 = st.number_input(
                f"Fair Odd Over {opponent_line_2} Opponent SOT",
                min_value=1.01,
                value=3.00,
                key="gk_odd_2"
            )
        else:
            opponent_line_2 = None
            opponent_odd_2 = None

        use_line_3 = st.checkbox("Use opponent line #3", value=False)
        if use_line_3:
            opponent_line_3 = st.selectbox(
                "Opponent SOT Line #3",
                line_options,
                index=4,
                key="gk_line_3"
            )
            opponent_odd_3 = st.number_input(
                f"Fair Odd Over {opponent_line_3} Opponent SOT",
                min_value=1.01,
                value=5.00,
                key="gk_odd_3"
            )
        else:
            opponent_line_3 = None
            opponent_odd_3 = None

        save_rate = st.number_input(
            "Goalkeeper Save Rate",
            min_value=0.01,
            max_value=0.99,
            value=0.70,
            step=0.01
        )

    with market_col:
        st.subheader("Market Odds - Goalkeeper Saves")

        st.caption("Optional. Enable only the lines you want to compare.")

        market_odds = {}

        for line in OUTPUT_LINES:
            use_market_line = st.checkbox(
                f"Compare Over {line}",
                value=line in [2.5, 3.5, 4.5],
                key=f"gk_use_market_{line}"
            )

            if use_market_line:
                market_odds[line] = st.number_input(
                    f"Market Odd Over {line} Saves",
                    min_value=1.01,
                    value=2.00,
                    key=f"gk_market_{line}"
                )
            else:
                market_odds[line] = None

    calculate_gk = st.button("Calculate Goalkeeper Saves")

    if calculate_gk:
        adversario_odds = []

        if opponent_line_1 is not None:
            adversario_odds.append((opponent_line_1, opponent_odd_1))

        if opponent_line_2 is not None:
            adversario_odds.append((opponent_line_2, opponent_odd_2))

        if opponent_line_3 is not None:
            adversario_odds.append((opponent_line_3, opponent_odd_3))

        if not adversario_odds:
            st.error("Please provide at least one opponent SOT line.")
        else:
            try:
                result = goalkeeper_saves_model(
                    adversario_odds=adversario_odds,
                    save_rate=save_rate
                )

                st.subheader("Model Output")

                metric_col1, metric_col2, metric_col3 = st.columns(3)

                metric_col1.metric(
                    "Opponent SOT λ",
                    f"{result['lambda_opponent_sot']:.4f}"
                )

                metric_col2.metric(
                    "Save Rate",
                    f"{result['save_rate']:.2%}"
                )

                metric_col3.metric(
                    "Goalkeeper Saves λ",
                    f"{result['lambda_goalkeeper_saves']:.4f}"
                )

                rows = []

                for item in result["lines"]:
                    line = item["line"]
                    prob = item["prob"]
                    fair_odd = item["fair_odd"]
                    market_odd = market_odds.get(line)

                    row = {
                        "Market": f"Over {line}",
                        "Probability": f"{prob:.2%}",
                        "Fair Odds": round(fair_odd, 2),
                        "Market Odds": "-",
                        "Edge": "-",
                        "Value": "-",
                        "Kelly": "-",
                        "Stake": "-"
                    }

                    if market_odd:
                        value, edge = value_diagnosis(fair_odd, market_odd)

                        kelly_full, stake = kelly_stake(
                            prob,
                            market_odd,
                            DEFAULT_BANKROLL,
                            DEFAULT_KELLY_FRACTION
                        )

                        row.update({
                            "Market Odds": market_odd,
                            "Edge": f"{edge:+.1f}%",
                            "Value": value,
                            "Kelly": f"{kelly_full:.2%}",
                            "Stake": f"{stake:.2f} u" if stake > 0 else "No bet"
                        })

                    rows.append(row)

                result_df = pd.DataFrame(rows)

                st.dataframe(
                    result_df,
                    use_container_width=True,
                    hide_index=True
                )

            except Exception as e:
                st.error(f"Error calculating model: {e}")

elif model_option == "Modelo 2":
    st.subheader("Modelo 2 — Chutes / Faltas (H2H)")

    st.info("Using fixed settings: 100u bankroll • 25% Kelly")

    mercado = st.text_input("Tipo de mercado (chutes / faltas)", value="chutes")

    linha = st.selectbox(
        "Linha usada para os dois jogadores",
        [1.5, 2.5],
        index=0,
        key="modelo2_linha"
    )

    input_col1, input_col2 = st.columns(2)

    with input_col1:
        st.subheader("Jogador A")

        nome_a = st.text_input("Nome do Jogador A", value="Player A", key="modelo2_nome_a")
        odd_a_mercado = st.number_input(
            "Odd de mercado Jogador A",
            min_value=1.01,
            value=2.00,
            key="modelo2_odd_a_mercado"
        )
        odd_a_over = st.number_input(
            f"Odd justa Over {linha} Jogador A",
            min_value=1.01,
            value=2.00,
            key="modelo2_odd_a_over"
        )

    with input_col2:
        st.subheader("Jogador B")

        nome_b = st.text_input("Nome do Jogador B", value="Player B", key="modelo2_nome_b")
        odd_b_mercado = st.number_input(
            "Odd de mercado Jogador B",
            min_value=1.01,
            value=2.00,
            key="modelo2_odd_b_mercado"
        )
        odd_b_over = st.number_input(
            f"Odd justa Over {linha} Jogador B",
            min_value=1.01,
            value=2.00,
            key="modelo2_odd_b_over"
        )

    odd_empate_mercado = st.number_input(
        "Odd de mercado Empate",
        min_value=1.01,
        value=3.00,
        key="modelo2_odd_empate"
    )

    calculate_modelo2 = st.button("Calcular Modelo 2")

    if calculate_modelo2:
        prob_a_over = 1 / odd_a_over
        prob_b_over = 1 / odd_b_over

        lambda_a = find_lambda(prob_a_over, linha)
        lambda_b = find_lambda(prob_b_over, linha)

        p_a, p_draw, p_b = h2h_probs(lambda_a, lambda_b, max_events=MAX_EVENTS)

        fair_a = prob_to_odd(p_a)
        fair_draw = prob_to_odd(p_draw)
        fair_b = prob_to_odd(p_b)

        k_a, stake_a = kelly_stake(p_a, odd_a_mercado, DEFAULT_BANKROLL, DEFAULT_KELLY_FRACTION)
        k_draw, stake_draw = kelly_stake(p_draw, odd_empate_mercado, DEFAULT_BANKROLL, DEFAULT_KELLY_FRACTION)
        k_b, stake_b = kelly_stake(p_b, odd_b_mercado, DEFAULT_BANKROLL, DEFAULT_KELLY_FRACTION)

        st.subheader(f"Model Output | {mercado.upper()}")

        metric_col1, metric_col2 = st.columns(2)

        metric_col1.metric(f"Lambda {nome_a}", f"{lambda_a:.4f}")
        metric_col2.metric(f"Lambda {nome_b}", f"{lambda_b:.4f}")

        result_df = pd.DataFrame([
            {
                "Outcome": nome_a,
                "Probability": f"{p_a:.2%}",
                "Fair Odds": round(fair_a, 2),
                "Market Odds": odd_a_mercado,
                "Value": value_label(fair_a, odd_a_mercado),
                "Kelly": f"{k_a:.2%}",
                "Stake": f"{stake_a:.2f} u"
            },
            {
                "Outcome": "Empate",
                "Probability": f"{p_draw:.2%}",
                "Fair Odds": round(fair_draw, 2),
                "Market Odds": odd_empate_mercado,
                "Value": value_label(fair_draw, odd_empate_mercado),
                "Kelly": f"{k_draw:.2%}",
                "Stake": f"{stake_draw:.2f} u"
            },
            {
                "Outcome": nome_b,
                "Probability": f"{p_b:.2%}",
                "Fair Odds": round(fair_b, 2),
                "Market Odds": odd_b_mercado,
                "Value": value_label(fair_b, odd_b_mercado),
                "Kelly": f"{k_b:.2%}",
                "Stake": f"{stake_b:.2f} u"
            },
        ])

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True
        )