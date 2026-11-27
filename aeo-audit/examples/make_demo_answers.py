#!/usr/bin/env python3
"""Writes FAKE answers for the demo audit so the whole pipeline can be tested for free.

Every business here is made up (they all have "Demo" in the name and .example websites).
The answers copy the *shape* of real AI answers (numbered lists, bold names, sources) so the
scorer is tested on realistic text. Re-run any time:  python3 examples/make_demo_answers.py
"""
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from aeo_audit.collect import answer_path, file_header  # noqa: E402
from aeo_audit.config import Audit  # noqa: E402

COMPETITORS = {
    "Halcyon Demo Med Spa": [
        "rated 4.9 stars with over 600 Google reviews, nurse injectors with 10+ years of experience",
        "voted Best Med Spa by a local magazine; offers Botox, filler and laser treatments",
        "known for natural-looking filler and clear pricing on its website",
    ],
    "Bayview Demo Skin Studio": [
        "4.8 stars on Yelp and RealSelf, specializes in HydraFacials, peels and microneedling",
        "open Saturdays with online booking; popular membership plans",
        "frequently recommended in local Facebook groups for laser hair removal",
    ],
    "Northstar Demo Aesthetics": [
        "physician-owned, board-certified medical director on site",
        "offers CoolSculpting, IPL photofacials and medical weight loss",
        "has a detailed FAQ and before-and-after gallery on its website",
    ],
    "Willowmere Demo Wellness": [
        "offers semaglutide weight loss programs and IV therapy",
        "affordable packages and monthly specials",
    ],
    "Ember Demo Injectables": [
        "a boutique injector studio with 4.9 stars from 210 reviews",
        "known for lip filler and first-time Botox consultations",
    ],
}
OURS = ("Lumen Demo Aesthetics", "a newer spa offering Botox and facials; fewer reviews so far")
# Which questions mention the demo business, per AI tool.
OUR_HITS = {"chatgpt": {4, 14}, "perplexity": {1, 4, 7, 13, 16}, "gemini": {4, 10}, "google_ai_overviews": {7}}
SOURCES = ["https://www.yelp.com/search?find_desc=med+spa&find_loc=Hanover%2C+MD",
           "https://www.realself.com/find/Maryland/Hanover",
           "https://www.google.com/maps/search/med+spa+hanover+md",
           "https://halcyon-demo-medspa.example/botox",
           "https://bayview-demo-skin.example/memberships",
           "https://www.facebook.com/groups/demo-hanover-moms"]


def pick(rng, q_no, model):
    names = list(COMPETITORS)
    weights = [9, 7, 6, 3, 3]
    chosen = []
    while len(chosen) < rng.randint(3, 4):
        n = rng.choices(names, weights)[0]
        if n not in chosen:
            chosen.append(n)
    items = [(n, rng.choice(COMPETITORS[n])) for n in chosen]
    if q_no in OUR_HITS[model]:
        items.insert(rng.randint(1, len(items)), OURS)
    return items


def chatgpt(q, items, rng):
    lines = ["Here are some well-regarded options in the Hanover, MD area:", ""]
    for i, (n, why) in enumerate(items, 1):
        lines.append(f"{i}. **{n}** - {why[0].upper() + why[1:]}.")
    lines += ["", "Tip: book a consultation first and ask who will do your treatment."]
    return "\n".join(lines)


def perplexity(q, items, rng):
    lines = ["Several med spas near Hanover, MD stand out based on reviews and services [1][2].", ""]
    for n, why in items:
        lines.append(f"## {n}")
        lines.append(f"- {why[0].upper() + why[1:]} [{rng.randint(1, 3)}].")
        lines.append("")
    lines.append("Sources:")
    lines += [f"[{i}] {u}" for i, u in enumerate(rng.sample(SOURCES, 3), 1)]
    return "\n".join(lines)


def gemini(q, items, rng):
    lines = ["Based on Google reviews and local listings, here are a few places to consider:", ""]
    for n, why in items:
        lines.append(f"* **{n}:** {why[0].upper() + why[1:]}.")
    lines += ["", "Check each provider's Google Business Profile for current hours and pricing."]
    return "\n".join(lines)


def ai_overview(q, items, rng):
    first = items[0][0]
    lines = [f"{first} is frequently mentioned for this in Hanover, MD. Other options include:"]
    for n, why in items[1:]:
        lines.append(f"- {n}: {why}")
    lines += ["", "Sources: " + ", ".join(rng.sample(SOURCES[:3], 2))]
    return "\n".join(lines)


WRITERS = {"chatgpt": chatgpt, "perplexity": perplexity, "gemini": gemini, "google_ai_overviews": ai_overview}


def main():
    audit = Audit(HERE / "demo-med-spa")
    rng = random.Random(42)
    for model in audit.models:
        for i, q in enumerate(audit.prompts(), 1):
            text = WRITERS[model](q, pick(rng, i, model), rng)
            p = answer_path(audit, model, i)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(file_header(q, "DEMO (fake answer, made by make_demo_answers.py)") + text + "\n", encoding="utf-8")
    print(f"Wrote demo answers to {audit.answers_dir}")


if __name__ == "__main__":
    main()
