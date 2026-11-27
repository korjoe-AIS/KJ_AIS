#!/usr/bin/env python3
"""KJ AIS AI visibility audit. Run  python3 aeo.py --help  to see the steps.

Typical flow (free, manual mode):
  python3 aeo.py new audits/glow-room --business "The Glow Room" --industry med-spa --city Hanover --place "Hanover, MD"
  python3 aeo.py collect audits/glow-room      # makes one paste file per question per AI tool
  ...paste answers...
  python3 aeo.py report audits/glow-room       # scores and writes output/report.pdf
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aeo_audit import apis, collect, config, prompts, report, score  # noqa: E402

AUDIT_TEMPLATE = """# One audit = this folder. Edit these values, then run:  python3 aeo.py prompts {folder} --force
[business]
name = "{business}"
aliases = []                 # other ways people write the name, e.g. ["Glow Room", "Glow Room Med Spa"]
website = ""                 # e.g. "theglowroom.com" (a link to the site counts as a mention)
industry = "{industry}"      # one of: {industries}
city = "{city}"              # used in questions like "... in {{city}}"
place = "{place}"            # used in questions like "... in {{place}}"

[audit]
date = "{today}"
models = ["chatgpt", "perplexity", "gemini", "google_ai_overviews"]
how_run = "Each question was typed into the free consumer app (logged out or a fresh chat) and the full answer was saved."
known_competitors = []       # names you already know, so they are always caught
ignore_names = []            # names the tool wrongly picked up as businesses
# extra_questions = ["Best med spa near Arundel Mills?"]

[api]
enabled = false              # API mode costs money. See README before turning on.
"""

FINDINGS_TEMPLATE = """# What you confirmed by checking their Google profile, website and listings.
# Pick 3-5 gaps. ids: gbp, reviews, faq_pages, service_pages, directories, nap, schema, local_mentions
# "detail" is the one specific fact that makes it personal.

# [[gap]]
# id = "reviews"
# detail = "41 Google reviews vs. 300+ for the three spas AI named."

# Optional: write your own quick wins / plan lines instead of the defaults.
# quick_wins = ["...", "...", "..."]
# plan = ["...", "..."]
"""


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def cmd_new(a):
    folder = Path(a.folder)
    if (folder / "audit.toml").exists():
        raise SystemExit(f"{folder}/audit.toml already exists.")
    config.industry(a.industry)  # fail early if unknown
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "audit.toml").write_text(AUDIT_TEMPLATE.format(
        folder=folder, business=a.business, industry=a.industry, city=a.city, place=a.place or a.city,
        today=date.today().isoformat(), industries=", ".join(config.list_industries())), encoding="utf-8")
    (folder / "findings.toml.example").write_text(FINDINGS_TEMPLATE, encoding="utf-8")
    qs = prompts.write_prompts(config.Audit(folder))
    print(f"Made {folder}/ with {len(qs)} questions in prompts.txt.")
    print(f"Next: check prompts.txt, then  python3 aeo.py collect {folder}")


def cmd_prompts(a):
    qs = prompts.write_prompts(config.Audit(a.folder), force=a.force)
    print(f"Wrote {len(qs)} questions to {a.folder}/prompts.txt")
    for i, q in enumerate(qs, 1):
        print(f"  {i:2d}. {q}")


def print_estimate(audit, models):
    est = apis.estimate(models, len(audit.prompts()))
    print("API cost estimate for ONE audit (nothing has been spent):")
    for r in est["rows"]:
        print(f"  {r['model']:<11} {r['api_model']:<18} {r['questions']} questions  "
              f"tokens ${r['token_cost']:.3f} + search fees ${r['search_fees']:.3f} = ${r['cost']:.2f}")
        if r["notes"]:
            print(f"              {r['notes']}")
    print(f"  TOTAL about ${est['total']:.2f} per audit (prices in pricing.toml, checked 2026-11-27).")
    skipped = [m for m in audit.models if m not in apis.API_MODELS]
    if skipped:
        print(f"  Not covered by API (always pasted by hand): {', '.join(skipped)}")
    return est


def cmd_collect(a):
    audit = config.Audit(a.folder)
    if a.api:
        config.load_env()
        models = [m for m in audit.models if m in apis.API_MODELS]
        print_estimate(audit, models)
        problems = apis.check_ready(audit, models)
        if problems:
            print("\nAPI mode will not run:")
            for p in problems:
                print(f"  - {p}")
            return
        if not a.yes_spend:
            print("\nNothing was sent. To spend this and run it, add --yes-spend")
            return
        n = apis.run(audit, models, overwrite=a.overwrite)
        print(f"Made {n} API calls.")
    progress = collect.prepare_manual(audit)
    print(f"Paste files are in {audit.answers_dir}/<ai tool>/NN.txt")
    for m, (done, total) in progress.items():
        print(f"  {audit.model_label(m):<20} {done} of {total} pasted")
    nxt = collect.next_unanswered(audit, limit=3)
    if nxt:
        print("\nNext to paste:")
        for m, i, q, p in nxt:
            print(f"  [{audit.model_label(m)}] Q{i}: {q}\n      -> {p}")
    else:
        print(f"\nAll answers are in. Run:  python3 aeo.py report {a.folder}")


def cmd_estimate(a):
    audit = config.Audit(a.folder)
    print_estimate(audit, [m for m in audit.models if m in apis.API_MODELS])


def run_score(audit):
    result = score.score(audit)
    score.write_outputs(audit, result)
    return result


def cmd_score(a):
    audit = config.Audit(a.folder)
    result = run_score(audit)
    print((audit.output_dir / "summary.md").read_text(encoding="utf-8"))


def cmd_report(a):
    audit = config.Audit(a.folder)
    result = run_score(audit)
    if result["overall"]["answered"] == 0:
        raise SystemExit("No answers pasted yet. Run  python3 aeo.py collect  first.")
    out = audit.output_dir / f"{slug(audit.business['name'])}-ai-visibility-audit.pdf"
    report.build_pdf(audit, result, out)
    o = result["overall"]
    print(f"Score: came up in {o['mentioned']} of {o['answered']} answers.")
    for v in result["per_model"].values():
        print(f"  {v['label']:<20} {v['mentioned']} of {v['questions']}")
    if not audit.findings_path.exists():
        print("! No findings.toml yet, so the gaps on the PDF are marked as a draft.")
    print(f"PDF: {out}")


def main(argv=None):
    p = argparse.ArgumentParser(description="KJ AIS AI visibility audit")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="start a new audit folder")
    s.add_argument("folder")
    s.add_argument("--business", required=True)
    s.add_argument("--industry", required=True, help=f"one of {config.list_industries()}")
    s.add_argument("--city", required=True)
    s.add_argument("--place", help='how the place is written in questions, e.g. "Hanover, MD"')
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("prompts", help="(re)write prompts.txt from the industry template")
    s.add_argument("folder")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_prompts)

    s = sub.add_parser("collect", help="make paste files and show progress (or --api)")
    s.add_argument("folder")
    s.add_argument("--api", action="store_true", help="use paid APIs (off unless enabled in audit.toml)")
    s.add_argument("--yes-spend", action="store_true", help="actually run the paid API calls")
    s.add_argument("--overwrite", action="store_true", help="replace answers already saved")
    s.set_defaults(fn=cmd_collect)

    s = sub.add_parser("estimate", help="show the API cost of one audit without spending anything")
    s.add_argument("folder")
    s.set_defaults(fn=cmd_estimate)

    s = sub.add_parser("score", help="score the answers and write output/summary.md")
    s.add_argument("folder")
    s.set_defaults(fn=cmd_score)

    s = sub.add_parser("report", help="score and build the PDF")
    s.add_argument("folder")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("industries", help="list industry templates")
    s.set_defaults(fn=lambda a: print("\n".join(config.list_industries())))

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
