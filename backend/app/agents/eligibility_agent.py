"""EligibilityAgent — evaluates each opportunity against the user's profile.

Combines the existing rule-based engine with LLM-powered reasoning for
nuanced edge cases. Produces explainable verdicts with confidence scores.
"""
from __future__ import annotations

import json
import logging
from datetime import date

from app.agents.base import BaseAgent
from app.agents.state import AgentState
from app.services import eligibility as elig_engine

STATUS_RANK = {"eligible": 0, "partial": 1, "needs_review": 2, "closed": 3}


def _days_left(deadline: str | None) -> int | None:
    if not deadline:
        return None
    try:
        return (date.fromisoformat(deadline) - date.today()).days
    except (TypeError, ValueError):
        return None


def match_sort_key(m: dict):
    """Eligible first (soonest open deadline first), then partial matches
    (closest match first), then needs-review, then closed."""
    rank = STATUS_RANK.get(m.get("status"), 9)
    days = _days_left(m.get("deadline"))
    days = days if days is not None and days >= 0 else 9999
    if rank == 0:
        return (rank, days, -m.get("score", 0))
    return (rank, -m.get("score", 0), days)


logger = logging.getLogger("lifepilot.agents.eligibility")

_ELIGIBILITY_PROMPT = """You are LifePilot's Eligibility Agent. Evaluate whether this citizen qualifies for the scheme.

## Citizen Profile:
{profile_json}

## Scheme Details:
- Title: {title}
- Description: {description}
- Criteria: {criteria_json}

## Rule-Based Result:
- Eligible: {rule_eligible}
- Score: {rule_score}
- Reasons met: {reasons}
- Unmet criteria: {unmet}

## Your Task:
Review the rule-based result and provide your assessment. Consider edge cases
the rules might miss (e.g., "engineering" matches "technical education").
Respond with JSON:
```json
{{
  "eligible": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of your assessment",
  "additional_reasons": ["any extra reasons the rules missed"],
  "additional_gaps": ["any extra gaps the rules missed"]
}}
```"""


class EligibilityAgent(BaseAgent):
    name = "EligibilityAgent"
    description = "Evaluates eligibility using rules + LLM reasoning"

    def execute(self, state: AgentState) -> AgentState:
        profile = state.profile
        opportunities = state.raw_opportunities
        matches: list[dict] = []

        for opp in opportunities:
            # Step 1: Rule-based evaluation. This is the source of truth for
            # eligibility: it is deterministic and every verdict has reasons.
            elig = elig_engine.evaluate(profile, opp)

            # Step 2: optional LLM notes. The LLM may point out things the rules
            # missed, but it never changes the verdict (eligibility is a legal rule).
            notes: list[str] = []
            if self.llm.name != "mock" and opp.get("criteria") and not state.is_simulation:
                try:
                    llm_result = self._llm_evaluate(profile, opp, elig)
                    if llm_result:
                        notes.extend(str(n) for n in (llm_result.get("additional_reasons") or []))
                        notes.extend(f"Check: {g}" for g in (llm_result.get("additional_gaps") or []))
                except Exception as e:
                    logger.warning(f"LLM eligibility check failed for {opp.get('id')}: {e}")

            days = _days_left(opp.get("deadline"))
            status = "closed" if days is not None and days < 0 else elig.status

            matches.append({
                "opportunity_id": opp.get("id", opp.get("title", "unknown")),
                "title": opp.get("title", "Unknown Scheme"),
                "provider": opp.get("provider"),
                "url": opp.get("url"),
                "amount": opp.get("amount"),
                "deadline": opp.get("deadline"),
                "deadline_note": opp.get("deadline_note"),
                "category": opp.get("category"),
                "description": opp.get("description"),
                "eligible": elig.eligible,
                "status": status,
                "score": elig.score,
                "confidence": elig.confidence,
                "reasons": elig.reasons,
                "unmet": elig.unmet,
                "notes": notes,
                "documents": opp.get("documents", []),
                "roadmap": [],
                "source": opp.get("source", "curated"),
                "criteria": opp.get("criteria") or {},
            })

        matches.sort(key=match_sort_key)
        state.matches = matches

        eligible_count = sum(1 for m in matches if m["status"] == "eligible")
        closed_count = sum(1 for m in matches if m["status"] == "closed")
        review_count = sum(1 for m in matches if m["status"] == "needs_review")
        avg_conf = round(sum(m["confidence"] for m in matches) / max(len(matches), 1), 2)
        state.add_log(
            agent=self.name,
            message=f"Evaluated {len(matches)} opportunities: {eligible_count} eligible and open, "
                    f"{len(matches) - eligible_count - closed_count - review_count} partial, "
                    f"{review_count} need manual review, {closed_count} closed. "
                    f"Average confidence: {avg_conf}.",
            confidence=avg_conf,
        )
        return state

    def _llm_evaluate(self, profile: dict, opp: dict, elig) -> dict | None:
        prompt = _ELIGIBILITY_PROMPT.format(
            profile_json=json.dumps(profile, indent=2, default=str),
            title=opp.get("title", ""),
            description=opp.get("description", ""),
            criteria_json=json.dumps(opp.get("criteria", {}), indent=2),
            rule_eligible=elig.eligible,
            rule_score=elig.score,
            reasons="; ".join(elig.reasons[:3]),
            unmet="; ".join(elig.unmet[:3]),
        )
        return self.llm.generate_json(
            prompt,
            system="You are a government scheme eligibility expert. Respond only with valid JSON."
        )
