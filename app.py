
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from decision_engine import DecisionAPIError, evaluate_options


# ==================================================
# CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "decision_history.db"

st.set_page_config(
    page_title="Decision AI",
    page_icon="🧭",
    layout="wide",
)


# ==================================================
# DATABASE
# ==================================================

def initialize_database():
    """Create or safely migrate the decision history table."""
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
    """Save an evaluated decision to SQLite."""
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
    """Return the 50 most recent decisions."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("""
            SELECT id, created_at, problem, results
            FROM decisions
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()


initialize_database()


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def parse_lines(text):
    """Convert multiline input into a list of non-empty strings."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def display_score(score):
    """Format a score without assuming the model returned one."""
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        return round(score, 2)

    return "Unavailable"


# ==================================================
# APPLICATION HEADER
# ==================================================

st.title("🧭 Decision AI")

st.write(
    "Compare alternatives, evaluate important criteria, "
    "and make more informed decisions."
)

st.divider()


# ==================================================
# NAVIGATION
# ==================================================

workspace_tab, history_tab = st.tabs([
    "Decision Workspace",
    "Decision History",
])


# ==================================================
# DECISION WORKSPACE
# ==================================================

with workspace_tab:

    st.header("Define your decision")

    with st.form("decision_form"):

        problem = st.text_area(
            "Decision problem",
            placeholder=(
                "Describe what you need to decide and "
                "include any relevant constraints."
            ),
            height=100,
        )

        col1, col2 = st.columns(2)

        with col1:
            options_text = st.text_area(
                "Options",
                placeholder=(
                    "Build a RAG system\n"
                    "Fine-tune an LLM\n"
                    "Use prompt engineering"
                ),
                height=150,
                help="Enter one option per line.",
            )

        with col2:
            criteria_text = st.text_area(
                "Evaluation criteria",
                value=(
                    "Cost efficiency\n"
                    "Ease of implementation\n"
                    "Expected accuracy\n"
                    "Development time"
                ),
                height=150,
                help="Enter one criterion per line.",
            )

        criteria = parse_lines(criteria_text)

        st.subheader("Criterion weights")

        st.caption(
            "Set each criterion's importance from 0 "
            "(not important) to 5 (very important)."
        )

        weights = []

        if criteria:
            weight_columns = st.columns(min(4, len(criteria)))

            for index, criterion in enumerate(criteria):
                with weight_columns[index % len(weight_columns)]:
                    weight = st.number_input(
                        criterion,
                        min_value=0,
                        max_value=5,
                        value=3,
                        step=1,
                        key=f"weight_{index}_{criterion}",
                    )
                    weights.append(weight)

        submitted = st.form_submit_button(
            "Evaluate Options",
            type="primary",
            use_container_width=True,
        )

    # --------------------------------------------------
    # VALIDATE AND EVALUATE
    # --------------------------------------------------

    if submitted:

        options = parse_lines(options_text)
        criteria = parse_lines(criteria_text)

        if not problem.strip():
            st.error("Please enter a decision problem.")

        elif len(options) < 2:
            st.error("Please enter at least two options.")

        elif not criteria:
            st.error("Please enter at least one criterion.")

        elif len(weights) != len(criteria):
            st.error(
                "The number of weights must match "
                "the number of criteria."
            )

        elif sum(weights) <= 0:
            st.error(
                "At least one criterion must have "
                "a weight greater than zero."
            )

        elif len(options) * len(criteria) > 8:
            st.error(
                "This model supports at most 8 "
                "option-criterion questions per request. "
                "Reduce the number of options or criteria."
            )

        else:
            try:
                with st.spinner("Evaluating your options..."):

                    result = evaluate_options(
                        problem=problem,
                        options=options,
                        criteria=criteria,
                        weights=weights,
                    )

                if not isinstance(result, dict):
                    raise ValueError(
                        "The decision engine returned "
                        "an unexpected result format."
                    )

                rows = result.get("rows", [])

                st.session_state["latest_result"] = result

                save_decision(problem, rows)

                st.success(
                    "Evaluation completed and saved to history."
                )

            except (ValueError, DecisionAPIError) as exc:
                st.error(str(exc))

            except Exception as exc:
                st.error("An unexpected error occurred.")

                with st.expander("Technical details"):
                    st.code(str(exc))

    # --------------------------------------------------
    # DISPLAY RESULTS
    # --------------------------------------------------

    result = st.session_state.get("latest_result")

    if result:

        st.divider()
        st.header("Evaluation Results")

        rows = result.get("rows", [])

        scored_rows = [
            row for row in rows
            if isinstance(row.get("score"), (int, float))
            and not isinstance(row.get("score"), bool)
        ]

        scored_rows.sort(
            key=lambda row: row["score"],
            reverse=True,
        )

        if scored_rows:

            best_option = scored_rows[0]

            metric1, metric2, metric3 = st.columns(3)

            metric1.metric(
                "Top-ranked option",
                str(best_option.get("option", "Unavailable")),
            )

            metric1.caption("Highest calculated weighted score")

            metric2.metric(
                "Weighted score",
                f'{best_option["score"]:.2f} / 5',
            )

            metric3.metric(
                "Options evaluated",
                len(rows),
            )

            st.subheader("Option ranking")

            ranking_data = []

            for rank, row in enumerate(scored_rows, start=1):
                ranking_data.append({
                    "Rank": rank,
                    "Option": row.get("option", ""),
                    "Weighted Score / 5": round(
                        row["score"], 2
                    ),
                })

            st.dataframe(
                pd.DataFrame(ranking_data),
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Score comparison")

            chart_data = pd.DataFrame([
                {
                    "Option": row.get("option", "Option"),
                    "Score": row["score"],
                }
                for row in scored_rows
            ]).set_index("Option")

            st.bar_chart(
                chart_data,
                use_container_width=True,
            )

            st.subheader("Criterion breakdown")

            detail_data = []

            for row in rows:
                item = {
                    "Option": row.get("option", ""),
                    "Weighted Score / 5": display_score(
                        row.get("score")
                    ),
                }

                criterion_scores = row.get(
                    "criterion_scores", {}
                )

                if isinstance(criterion_scores, dict):
                    for criterion, score in criterion_scores.items():
                        item[criterion] = display_score(score)

                detail_data.append(item)

            st.dataframe(
                pd.DataFrame(detail_data),
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

        with st.expander("Technical details: Raw API response"):
            st.json(result.get("raw_response", {}))

        st.caption(
            "AI-generated estimates are not verified facts. "
            "Check important decisions against reliable evidence."
        )


# ==================================================
# DECISION HISTORY
# ==================================================

with history_tab:

    st.header("Decision History")

    st.caption(
        "Your 50 most recent saved decisions are stored locally."
    )

    history = load_history()

    if not history:

        st.info(
            "No saved decisions yet. Evaluate your first decision "
            "in the Decision Workspace."
        )

    else:

        for (
            decision_id,
            created_at,
            saved_problem,
            results_json,
        ) in history:

            label = (
                f"Decision #{decision_id} | "
                f"{created_at or 'Earlier record'}"
            )

            with st.expander(label):

                st.markdown("**Decision problem**")
                st.write(saved_problem or "No description available.")

                try:
                    saved_results = json.loads(
                        results_json or "[]"
                    )

                    if isinstance(saved_results, list) and saved_results:

                        history_data = []

                        for item in saved_results:
                            history_data.append({
                                "Option": item.get("option", ""),
                                "Weighted Score / 5": display_score(
                                    item.get("score")
                                ),
                            })

                        st.markdown("**Saved results**")

                        st.dataframe(
                            pd.DataFrame(history_data),
                            use_container_width=True,
                            hide_index=True,
                        )

                    elif isinstance(saved_results, dict):
                        st.json(saved_results)

                    else:
                        st.caption("No result details were saved.")

                except (ValueError, TypeError):
                    st.warning(
                        "This saved record could not be read."
                    )


# ==================================================
# FOOTER
# ==================================================

st.divider()

st.caption("Decision AI · Built with Streamlit, Python and SQLite")
