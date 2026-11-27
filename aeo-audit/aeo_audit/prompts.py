"""Step 1: turn an industry template + a place into ~20 customer-style questions."""
from __future__ import annotations

from .config import Audit


def build_prompts(industry: dict, city: str, place: str, extra: list[str] | None = None) -> list[str]:
    questions = [q.format(city=city, place=place) for q in industry["questions"]]
    for q in extra or []:
        questions.append(q.format(city=city, place=place))
    # Keep order, drop duplicates.
    seen, out = set(), []
    for q in questions:
        if q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def write_prompts(audit: Audit, force: bool = False) -> list[str]:
    if audit.prompts_path.exists() and not force:
        raise SystemExit(
            f"{audit.prompts_path} already exists (you may have edited it).\n"
            "Add --force to replace it with a fresh set from the industry template."
        )
    b = audit.business
    prompts = build_prompts(audit.industry, b["city"], b.get("place", b["city"]), audit.audit.get("extra_questions"))
    header = (
        f"# Questions for {b['name']} ({audit.industry['name']}, {b.get('place', b['city'])}).\n"
        "# One question per line. Edit, add or remove lines freely. Lines starting with # are ignored.\n"
        "# Keep the SAME questions month to month so scores are comparable.\n"
    )
    audit.prompts_path.write_text(header + "\n".join(prompts) + "\n", encoding="utf-8")
    return prompts
