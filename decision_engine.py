
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


# ==================================================
# CONFIGURATION
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent
ENV_FILE = PROJECT_DIR / ".env"

API_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "respan/span-01-lite:free"


class DecisionAPIError(RuntimeError):
    """Raised when the OpenRouter Decisions API fails."""


# ==================================================
# AUTHENTICATION
# ==================================================

def get_api_key():
    load_dotenv(ENV_FILE, override=True)

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    if (
        len(api_key) >= 2
        and api_key[0] == api_key[-1]
        and api_key[0] in ("'", '"')
    ):
        api_key = api_key[1:-1].strip()

    if not api_key:
        raise DecisionAPIError(
            f"API key not found. Check your .env file: {ENV_FILE}"
        )

    return api_key


# ==================================================
# RESPONSE PARSING
# ==================================================

def parse_probability(answer):
    """Extract the NOUL probability that a condition is true."""

    if not isinstance(answer, dict):
        return None

    value = answer.get("noul")

    if isinstance(value, (int, float)):
        value = float(value)

        if 0 <= value <= 1:
            return value

    return None


# ==================================================
# DECISION ENGINE
# ==================================================

def evaluate_options(problem, options, criteria, weights):
    """
    Evaluate alternatives using Span-01 Lite.

    Each API question evaluates one option against one criterion.
    Because Span-01 Lite supports at most 8 questions per request,
    this implementation limits each evaluation to 8 comparisons.
    """

    api_key = get_api_key()

    problem = str(problem).strip()

    options = [
        str(x).strip()
        for x in options
        if str(x).strip()
    ]

    criteria = [
        str(x).strip()
        for x in criteria
        if str(x).strip()
    ]

    # --------------------------------------------------
    # INPUT VALIDATION
    # --------------------------------------------------

    if not problem:
        raise ValueError("Enter a decision problem.")

    if len(options) < 2:
        raise ValueError("Enter at least two options.")

    if not criteria:
        raise ValueError("Enter at least one criterion.")

    if len(weights) != len(criteria):
        raise ValueError(
            "Provide one weight for every criterion."
        )

    try:
        weights = [float(w) for w in weights]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Criterion weights must be numeric."
        ) from exc

    if any(w < 0 for w in weights):
        raise ValueError("Weights cannot be negative.")

    if sum(weights) <= 0:
        raise ValueError(
            "At least one criterion weight must be positive."
        )

    comparisons = [
        (option, criterion, weights[index])
        for option in options
        for index, criterion in enumerate(criteria)
    ]

    if len(comparisons) > 8:
        raise ValueError(
            f"This model allows at most 8 questions per request. "
            f"You entered {len(comparisons)} option-criterion comparisons. "
            "Reduce the number of options or criteria so their product "
            "is no greater than 8."
        )

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    options_text = "\n".join(
        f"- {option}" for option in options
    )

    criteria_text = "\n".join(
        f"- {criterion}: importance {weights[i]}/5"
        for i, criterion in enumerate(criteria)
    )

    user_content = (
        f"Decision problem:\n{problem}\n\n"
        f"Options:\n{options_text}\n\n"
        f"Criteria:\n{criteria_text}\n\n"
        "Assess whether each proposed option meets its stated "
        "criterion using only the information provided. "
        "Do not invent evidence. Missing information should "
        "not be treated as proof that a condition is satisfied."
    )

    state = {
        "input": [
            {
                "role": "user",
                "content": user_content,
            }
        ],
        "output": {
            "role": "assistant",
            "content": "Structured option evaluation.",
        },
    }

    # --------------------------------------------------
    # QUESTIONS
    # --------------------------------------------------

    questions = {}
    question_map = {}

    for index, (option, criterion, weight) in enumerate(
        comparisons, start=1
    ):
        question_id = f"comparison_{index}"

        questions[question_id] = {
            "type": "noul",
            "instructions": (
                f"Does the available information support the claim "
                f"that option '{option}' meets the criterion "
                f"'{criterion}' for the stated decision?"
            ),
            "criteria": {
                "true": (
                    "The supplied information supports the option "
                    "meeting this criterion."
                ),
                "false": (
                    "The supplied information does not support the "
                    "option meeting this criterion, or evidence is "
                    "insufficient."
                ),
            },
        }

        question_map[question_id] = {
            "option": option,
            "criterion": criterion,
            "weight": weight,
        }

    payload = {
        "model": MODEL,
        "state": state,
        "questions": questions,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": "Decision Making AI",
    }

    # --------------------------------------------------
    # API REQUEST
    # --------------------------------------------------

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as exc:
        raise DecisionAPIError(
            f"OpenRouter connection failed: {exc}"
        ) from exc

    if not response.ok:
        try:
            details = response.json()
        except ValueError:
            details = response.text

        raise DecisionAPIError(
            f"OpenRouter HTTP {response.status_code}: {details}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise DecisionAPIError(
            "OpenRouter returned invalid JSON."
        ) from exc

    answers = data.get("answers")

    if not isinstance(answers, dict):
        raise DecisionAPIError(
            f"Unexpected API response: {data}"
        )

    # --------------------------------------------------
    # WEIGHTED SCORING
    # --------------------------------------------------

    results = []

    for option in options:
        weighted_total = 0.0
        total_weight = 0.0
        criterion_scores = {}

        for question_id, comparison in question_map.items():
            if comparison["option"] != option:
                continue

            probability = parse_probability(
                answers.get(question_id)
            )

            criterion = comparison["criterion"]
            weight = comparison["weight"]

            criterion_scores[criterion] = (
                probability * 5
                if probability is not None
                else None
            )

            if probability is not None and weight > 0:
                weighted_total += probability * 5 * weight
                total_weight += weight

        final_score = (
            weighted_total / total_weight
            if total_weight > 0
            else None
        )

        results.append({
            "option": option,
            "score": final_score,
            "criterion_scores": criterion_scores,
        })

    results.sort(
        key=lambda item: (
            item["score"]
            if item["score"] is not None
            else -1
        ),
        reverse=True,
    )

    return {
        "model": MODEL,
        "rows": results,
        "raw_response": data,
    }
