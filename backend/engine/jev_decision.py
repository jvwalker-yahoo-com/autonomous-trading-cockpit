# jev_decision.py
"""Utility module for integrating Jev decision maker.

The Jev model is a structured decision-making system that expects a *state* (context)
and a list of *questions* and returns concrete typed answers (choice, score, or
probability).  This wrapper abstracts the API call so the backtester can ask
whether to open a position.

Implementation details:
- `JEv_API_URL` should be set to the endpoint provided by the Jev service.
- The `evaluate_decision` function sends a JSON payload containing the state and
  questions.  It expects a JSON response with an `answers` field.
- In production you would add authentication, retries, and schema validation.
- For now the function returns a dummy response (`True`) to keep the backtester
  functional without external dependencies.
"""
import json
import os
from typing import Any, Dict, List

# Placeholder URL – replace with the actual Jev endpoint.
JEv_API_URL = os.getenv("JEV_API_URL", "https://api.jev.example/evaluate")


def _call_jev_api(state: Dict[str, Any], questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Make a raw HTTP request to the Jev service.

    This function is deliberately minimal; in a real deployment you would use a
    robust HTTP client (e.g., `httpx`) with proper error handling.
    """
    # Dummy implementation – always approve.
    # Replace this block with an actual HTTP call.
    return {"answers": [{"type": "choice", "value": "APPROVE"}]}


def evaluate_decision(state: Dict[str, Any], questions: List[Dict[str, Any]]) -> bool:
    """Ask Jev to make a decision and return ``True`` if approved.

    Parameters
    ----------
    state:
        Arbitrary context information (e.g., current price, indicator values).
    questions:
        List of question dicts as described in the Jev docs.  Example::

            [{"type": "choice", "question": "Should we open a LONG?", "options": ["APPROVE", "REJECT"]}]

    Returns
    -------
    bool
        ``True`` if Jev's answer is an approving choice, otherwise ``False``.
    """
    response = _call_jev_api(state, questions)
    answers = response.get("answers", [])
    if not answers:
        return False
    # Simple heuristic: any answer with value "APPROVE" is accepted.
    return any(ans.get("value") == "APPROVE" for ans in answers)
