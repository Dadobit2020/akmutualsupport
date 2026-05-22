"""
Deterministic fuzzy-matching engine for reconciliation.

Each incoming transaction is scored against all active members.
The output is a confidence score (0–100) and a human-readable explanation.

NO auto-apply happens here — the service layer decides what to do based on thresholds.
"""
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz

from apps.membership.models import Member, MemberStatus
from apps.obligations.models import Obligation, ObligationStatus


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


@dataclass
class MatchCandidate:
    member: Member
    score: int
    explanation: list[str] = field(default_factory=list)
    matched_obligation: Optional[object] = None

    @property
    def explanation_text(self) -> str:
        return "; ".join(self.explanation)


def score_transaction_against_member(
    *,
    payer_name: str,
    amount_cents: int,
    memo: str,
    transaction_date,
    member: Member,
    open_obligations: list,
) -> MatchCandidate:
    score = 0
    explanation = []
    matched_obligation = None

    norm_payer = _normalize(payer_name)

    # 1. Payment reference in memo (very strong signal — ~40 pts)
    if member.payment_reference and member.payment_reference.lower() in memo.lower():
        score += 40
        explanation.append(f"Payment reference '{member.payment_reference}' found in memo")

    # 2. Name matching
    best_name_score = 0
    best_name_variant = ""
    for name_variant in member.display_names:
        norm_variant = _normalize(name_variant)
        ratio = fuzz.token_sort_ratio(norm_payer, norm_variant)
        if ratio > best_name_score:
            best_name_score = ratio
            best_name_variant = name_variant

    if best_name_score == 100:
        score += 30
        explanation.append(f"Exact name match on '{best_name_variant}'")
    elif best_name_score >= 85:
        pts = int((best_name_score - 85) / 15 * 20) + 10  # 10–30
        score += pts
        explanation.append(f"Fuzzy name match {best_name_score}% on '{best_name_variant}'")
    elif best_name_score >= 60:
        pts = int((best_name_score - 60) / 25 * 10)  # 0–10
        score += pts
        explanation.append(f"Weak name match {best_name_score}% on '{best_name_variant}'")

    # 3. Amount matching against open obligations (strong — up to 25 pts)
    for obligation in open_obligations:
        if obligation.outstanding_cents == amount_cents:
            score += 25
            explanation.append(f"Exact amount match for obligation {obligation.id} (outstanding={amount_cents}¢)")
            matched_obligation = obligation
            break
        elif abs(obligation.outstanding_cents - amount_cents) <= 100:  # within $1
            score += 15
            explanation.append(f"Near amount match for obligation (diff={abs(obligation.outstanding_cents - amount_cents)}¢)")
            if matched_obligation is None:
                matched_obligation = obligation

    # 4. Email in memo (moderate)
    if member.email and member.email.lower() in memo.lower():
        score += 10
        explanation.append("Member email found in memo")

    score = min(score, 100)
    return MatchCandidate(
        member=member,
        score=score,
        explanation=explanation,
        matched_obligation=matched_obligation,
    )


def find_best_match(
    *,
    organization,
    payer_name: str,
    amount_cents: int,
    memo: str,
    transaction_date,
    auto_apply_threshold: int = 90,
    review_threshold: int = 60,
) -> Optional[MatchCandidate]:
    """
    Run the matching engine across all active members.
    Returns the best candidate (or None if below review_threshold).
    """
    active_members = Member.objects.filter(
        organization=organization,
        status=MemberStatus.ACTIVE,
    ).prefetch_related("obligations")

    best: Optional[MatchCandidate] = None

    for member in active_members:
        open_obligations = list(
            Obligation.objects.filter(
                member=member,
                status__in=[ObligationStatus.OPEN, ObligationStatus.PARTIALLY_PAID],
            ).order_by("due_date")
        )
        candidate = score_transaction_against_member(
            payer_name=payer_name,
            amount_cents=amount_cents,
            memo=memo,
            transaction_date=transaction_date,
            member=member,
            open_obligations=open_obligations,
        )
        if best is None or candidate.score > best.score:
            best = candidate

    if best and best.score >= review_threshold:
        return best
    return None
