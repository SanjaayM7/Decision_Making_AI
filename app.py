
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from decision_engine import DecisionAPIError, evaluate_options


# -------------------- CONFIG --------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "decision_history.db"

st.set_page_config(
    page_title="Decision AI",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# -------------------- MINIMAL THEME --------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg: #0e1117;
    --panel: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #a78bfa;
}

html, body, [class*="css"] {
    font-family: Inter, sans-serif;
}

.stApp {
    background: var(--bg);
    color: var(--text);
}

[data-testid="stHeader"] {
    background: var(--bg);
}

.block-container {
    max-width: 1100px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

h1, h2, h3 {
    color: var(--text);
    letter-spacing: -0.025em;
}

h1 {
    font-size: 2rem;
    font-weight: 700;
}

h2 {
    font-size: 1.4rem;
}

p, label {
    color: var(--text);
}

[data-testid="stCaptionContainer"] {
    color: var(--muted) !important;
}

/* Inputs */
.stTextArea textarea,
.stTextInput input,
[data-testid="stNumberInput"] input {
    background: var(--panel) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
}

.stTextArea textarea:focus,
.stTextInput input:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}

/* Number controls */
[data-testid="stNumberInput"] button {
    background: var(--panel) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
}

/* Buttons */
.stButton > button,
.stFormSubmitButton > button {
    border-radius: 8px;
    min-height: 40px;
    font-weight: 600;
}

.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background: var(--accent);
    border-color: var(--accent);
    color: #11111b;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-weight: 500;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--accent) !important;
}

/* Simple containers */
[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
}

[data-testid="stMetricLabel"] {
    color: var(--muted) !important;
}

[data-testid="stMetricValue"] {
    color: var(--text) !important;
    font-weight: 700;
    overflow-wrap: anywhere;
}

[data-testid="stExpander"] {
    border: 1px solid var(--border);
    border-radius: 8px;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}

hr {
    border-color: var(--border);
}

.small-note {
    color: var(--muted);
    font-size: 0.85rem;
}


/* Fix text visibility across the dark UI */

/* Main text and labels */
.stApp,
.stApp p,
.stApp label,
.stApp .stMarkdown,
.stApp [data-testid="stMarkdownContainer"] p {
    color: #e6edf3 !important;
}

/* Text-area content */
.stTextArea textarea,
.stTextInput input {
    background-color: #161b22 !important;
    color: #f0f6fc !important;
    -webkit-text-fill-color: #f0f6fc !important;
    border: 1px solid #484f58 !important;
    caret-color: #a78bfa !important;
}

/* Placeholder text */
.stTextArea textarea::placeholder,
.stTextInput input::placeholder {
    color: #8b949e !important;
    -webkit-text-fill-color: #8b949e !important;
    opacity: 1 !important;
}

/* Number-input values */
[data-testid="stNumberInput"] input {
    background-color: #161b22 !important;
    color: #f0f6fc !important;
    -webkit-text-fill-color: #f0f6fc !important;
    border: 1px solid #484f58 !important;
    opacity: 1 !important;
}

/* Number-input buttons */
[data-testid="stNumberInput"] button {
    background-color: #21262d !important;
    color: #f0f6fc !important;
    border-color: #484f58 !important;
}

/* Input labels and captions */
[data-testid="stWidgetLabel"] p,
[data-testid="stCaptionContainer"] p {
    color: #c9d1d9 !important;
}

/* Improve focus visibility */
.stTextArea textarea:focus,
.stTextInput input:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: #a78bfa !important;
    box-shadow: 0 0 0 1px #a78bfa !important;
}

</style>
""", unsafe_allow_html=True)


# -------------------- DATABASE --------------------
def initialize_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT '',
                problem TEXT NOT NULL DEFAULT '',
                results TEXT NOT NULL DEFAULT '[]'
            )
        """)

        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(decisions)"
            ).fetchall()
        }

        if "created_at" not in columns:
            conn.execute(
                "ALTER TABLE decisions ADD COLUMN "
                "created_at TEXT NOT NULL DEFAULT ''"
            )

        if "problem" not in columns:
            conn.execute(
                "ALTER TABLE decisions ADD COLUMN "
                "problem TEXT NOT NULL DEFAULT ''"
            )

        if "results" not in columns:
            conn.execute(
                "ALTER TABLE decisions ADD COLUMN "
                "results TEXT NOT NULL DEFAULT '[]'"
            )

        conn.commit()


def save_decision(problem, results):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO decisions (created_at, problem, results)
            VALUES (?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                problem,
                json.dumps(results),
            ),
        )
        conn.commit()


def load_history():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
            SELECT id, created_at, problem, results
            FROM decisions
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()


initialize_database()


# -------------------- HEADER --------------------
st.title("Decision AI")
st.caption("Compare your options. Prioritize what matters. Decide with clarity.")

workspace_tab, history_tab = st.tabs([
    "Decision workspace",
    "History",
])


# -------------------- DECISION WORKSPACE --------------------
with workspace_tab:
    st.subheader("Your decision")

    problem = st.text_area(
        "What are you trying to decide?",
        placeholder="Describe your decision and relevant constraints...",
        height=90,
        key="problem_input",
    )

    option_col, criteria_col = st.columns(2)

    with option_col:
        options_text = st.text_area(
            "Options",
            placeholder=(
                "Build a RAG system\n"
                "Fine-tune an LLM\n"
                "Use prompt engineering"
            ),
            height=140,
            key="options_input",
            help="Enter one option per line.",
        )

    with criteria_col:
        criteria_text = st.text_area(
            "Criteria",
            value=(
                "Cost efficiency\n"
                "Development time"
            ),
            height=140,
            key="criteria_input",
            help="Enter one criterion per line.",
        )

    criteria = [
        item.strip()
        for item in criteria_text.splitlines()
        if item.strip()
    ]

    st.subheader("Criterion weights")
    st.caption("Set importance from 0 (not important) to 5 (very important).")

    weights = []

    if criteria:
        weight_columns = st.columns(min(4, len(criteria)))

        for i, criterion in enumerate(criteria):
            with weight_columns[i % len(weight_columns)]:
                weights.append(
                    st.number_input(
                        criterion,
                        min_value=0,
                        max_value=5,
                        value=3,
                        step=1,
                        key=f"weight_{i}_{criterion}",
                    )
                )

    submitted = st.button(
        "Evaluate options",
        type="primary",
        use_container_width=True,
    )

    if submitted:
        options = [
            item.strip()
            for item in options_text.splitlines()
            if item.strip()
        ]

        criteria = [
            item.strip()
            for item in criteria_text.splitlines()
            if item.strip()
        ]

        if not problem.strip():
            st.error("Enter a decision problem.")

        elif len(options) < 2:
            st.error("Enter at least two options.")

        elif not criteria:
            st.error("Enter at least one criterion.")

        elif len(weights) != len(criteria):
            st.error("The number of weights must match the criteria.")

        elif sum(weights) <= 0:
            st.error("At least one criterion must have a positive weight.")

        elif len(options) * len(criteria) > 8:
            st.error(
                "This model supports at most 8 option-criterion "
                "questions per request. Reduce your options or criteria."
            )

        else:
            try:
                with st.spinner("Evaluating your options..."):
                    result = evaluate_options(
                        problem,
                        options,
                        criteria,
                        weights,
                    )

                st.session_state["latest_result"] = result

                save_decision(
                    problem,
                    result.get("rows", []),
                )

                st.success("Evaluation completed and saved.")

            except (ValueError, DecisionAPIError) as exc:
                st.error(str(exc))

            except Exception as exc:
                st.error("An unexpected error occurred.")
                with st.expander("Technical details"):
                    st.code(str(exc))


# -------------------- RESULTS --------------------
with workspace_tab:
    result = st.session_state.get("latest_result")

    if result:
        st.divider()
        st.subheader("Results")

        rows = result.get("rows", [])

        scored_rows = [
            row for row in rows
            if isinstance(row.get("score"), (int, float))
        ]

        scored_rows.sort(
            key=lambda row: row["score"],
            reverse=True,
        )

        if scored_rows:
            best = scored_rows[0]

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Top-ranked option",
                str(best.get("option", "Unavailable")),
            )

            col2.metric(
                "Weighted score",
                f'{best["score"]:.2f} / 5',
            )

            col3.metric(
                "Options compared",
                len(rows),
            )

            st.markdown("#### Ranking")

            ranking_data = []

            for index, row in enumerate(scored_rows, start=1):
                ranking_data.append({
                    "Rank": index,
                    "Option": row.get("option", ""),
                    "Weighted score / 5": round(row["score"], 2),
                })

            st.dataframe(
                pd.DataFrame(ranking_data),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("#### Score comparison")

            chart_data = pd.DataFrame([
                {
                    "Option": row.get("option", "Option"),
                    "Score": row["score"],
                }
                for row in scored_rows
            ]).set_index("Option")

            st.bar_chart(chart_data, use_container_width=True)

            detail_rows = []

            for row in rows:
                item = {
                    "Option": row.get("option", ""),
                    "Weighted score / 5": (
                        round(row["score"], 2)
                        if isinstance(row.get("score"), (int, float))
                        else "Unavailable"
                    ),
                }

                for criterion, score in row.get(
                    "criterion_scores", {}
                ).items():
                    item[criterion] = (
                        round(score, 2)
                        if isinstance(score, (int, float))
                        else "Unavailable"
                    )

                detail_rows.append(item)

            st.markdown("#### Criterion breakdown")

            st.dataframe(
                pd.DataFrame(detail_rows),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                result.get(
                    "note",
                    "The model did not return numeric scores.",
                )
            )

            if rows:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Option": row.get("option", ""),
                            "Score": "Unavailable",
                        }
                        for row in rows
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )

        with st.expander("Raw API response"):
            st.json(result.get("raw_response", {}))

        st.caption(
            "AI-generated scores are estimates. Verify important "
            "decisions with reliable evidence."
        )


# -------------------- HISTORY --------------------
with history_tab:
    st.subheader("Saved decisions")
    st.caption("Your 50 most recent decisions, stored locally.")

    history = load_history()

    if not history:
        st.info("No saved decisions yet. Evaluate an option to get started.")

    else:
        for row_id, created_at, problem_text, results_json in history:
            label = (
                f"#{row_id} · {created_at or 'Earlier record'} · "
                f"{(problem_text or '')[:70]}"
            )

            with st.expander(label):
                st.write(problem_text or "No problem description")

                try:
                    parsed = json.loads(results_json or "[]")

                    if isinstance(parsed, list):
                        history_data = []

                        for item in parsed:
                            score = item.get("score")

                            history_data.append({
                                "Option": item.get("option", ""),
                                "Weighted score / 5": (
                                    round(score, 2)
                                    if isinstance(score, (int, float))
                                    else "Unavailable"
                                ),
                            })

                        if history_data:
                            st.dataframe(
                                pd.DataFrame(history_data),
                                use_container_width=True,
                                hide_index=True,
                            )
                    else:
                        st.json(parsed)

                except (ValueError, TypeError):
                    st.warning("This history record could not be parsed.")


# -------------------- FOOTER --------------------
st.divider()
st.caption("Decision AI · Simple decision support")
