"""Approval policies. Owner: Cem.

manual: proposal waits for POST /api/proposals/{id}/approve.
batch_policy: overnight run only: auto-approve if the gate passed and turnover <= limit. Always labelled by="batch_policy".
"""
from __future__ import annotations

from typing import Literal

from app.schemas import Mandate


def batch_allows(gate_passed: bool, turnover: float, mandate: Mandate) -> bool:
    return gate_passed and turnover <= mandate.approval.batch_auto_approve_turnover_max


ApprovalMode = Literal["manual", "batch_policy"]
