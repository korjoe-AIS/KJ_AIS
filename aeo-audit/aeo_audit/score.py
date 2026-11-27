"""Step 3: read every pasted answer and work out:
  - did the business come up? (and where in the list)
  - which competitors were recommended, and the reasons the AI gave
  - which websites / directories the AI cited
  - scores: "came up in X of 20" per AI tool, and overall
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from urllib.parse import urlparse

from .collect import answer_path, read_answer
from .config import Audit

# Words that tell us WHY the AI picked a business. Plain-English label -> trigger words.
REASONS = {
    "reviews and ratings": r"\breviews?\b|\brating|\brated\b|\bstars?\b|\b[45]\.\d\b",
    "experience and credentials": r"\byears?\b|experience|board[- ]certified|licensed|certified|credential|since (19|20)\d\d|\bnp\b|\brn\b|nurse|physician|doctor",
    "awards and 'best of' lists": r"award|best of|voted|top[- ]rated|recogni[sz]ed|ranked|winner",
    "specific services offered": r"offers?|specializ|services?|treatments?|procedures?|botox|filler|laser|facial|implant|veneer|repair|install",
    "convenience (hours, location, booking)": r"open|hours|weekend|saturday|same[- ]day|emergency|24/7|location|located|parking|online booking|book online|convenient",
    "price, financing or memberships": r"afford|price|pricing|cost|financ|membership|package|special|discount|insurance",
    "mentioned by other sites or press": r"featured|press|news|magazine|according to|listed on|mentioned",
    "clear website / helpful info": r"website|blog|faq|before[- ]and[- ]after|gallery|transparent",
}

URL_RE = re.compile(r"https?://[^\s)\]>\"']+", re.I)
LIST_ITEM_RE = re.compile(r"^\s*(?:\d{1,2}[.)]|[-*•–])\s+(.*)$")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
SEPARATORS = re.compile(r"\s+[–—-]\s+|:\s|\s\(|\s\|\s|,\s(?=located|which|known|offers|with)")
CORP_TOKENS = {"&", "llc", "llp", "pc", "pllc", "inc", "dds", "dmd"}
STOP_SUFFIX = re.compile(r"\b(llc|llp|pllc|pc|inc|the)\b")


def norm(s: str) -> str:
    s = s.lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def key(name: str) -> str:
    """A loose key so 'The Glow Room, LLC' and 'Glow Room' count as one business."""
    return re.sub(r"\s+", " ", STOP_SUFFIX.sub(" ", norm(name)).replace("'s", "")).strip()


def mentions(text: str, names: list[str], website: str | None = None) -> bool:
    t = " " + norm(text) + " "
    for n in names:
        if n and f" {norm(n)} " in t:
            return True
    if website:
        dom = website.lower().replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
        if dom and dom in text.lower():
            return True
    return False


def clean_name(raw: str) -> str:
    raw = raw.strip().strip("*_#").strip()
    raw = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", raw)  # markdown links -> text
    raw = SEPARATORS.split(raw, maxsplit=1)[0]
    return raw.strip(" .,:;*_\"'").strip()


def looks_like_business(name: str, hints: list[str], directories: list[str]) -> bool:
    words = name.split()
    if not (1 <= len(words) <= 8) or len(name) > 70:
        return False
    if not name[0].isupper() and not name[0].isdigit():
        return False
    low = norm(name)
    if any(low == norm(d) for d in directories):
        return False
    tokens = set(low.split()) | {w.lower().strip(".,") for w in words}
    hint_hit = any(f" {norm(h)} " in f" {low} " for h in hints if norm(h)) or bool(tokens & CORP_TOKENS)
    return hint_hit


def split_items(text: str) -> list[tuple[str, str]]:
    """Splits an answer into (business name candidate, the text that describes it)."""
    items: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        m = LIST_ITEM_RE.match(line)
        bold = BOLD_RE.search(line)
        heading = line.lstrip().startswith("#")
        if m or heading or (bold and line.strip().startswith("**")):
            body = m.group(1) if m else line.lstrip("# ").strip()
            b = BOLD_RE.search(body)
            name = clean_name(b.group(1) or b.group(2)) if b else clean_name(body)
            items.append((name, [body]))
        elif items and line.strip():
            items[-1][1].append(line.strip())
    out = [(n, " ".join(d)) for n, d in items]
    # Also pick up bold names inside normal sentences ("Try **Glow Room** for ...").
    for sent in re.split(r"(?<=[.!?])\s+", text):
        for b in BOLD_RE.finditer(sent):
            out.append((clean_name(b.group(1) or b.group(2)), sent))
    return out


def tidy_snippet(snippet: str, name: str) -> str:
    """Removes markdown, citation numbers and the leading business name, keeping the AI's words."""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", snippet)
    s = re.sub(r"\[\d+\]", "", s).replace("**", "").replace("__", "")
    s = re.sub(r"\s+", " ", s).strip()
    if s.lower().startswith(name.lower()):
        s = s[len(name):].lstrip(" :-–—,.")
    return s[:400]


GENERIC_REASON = "specific services offered"


def reason_tags(snippet: str) -> list[str]:
    low = snippet.lower()
    return [label for label, rx in REASONS.items() if re.search(rx, low)]


def sources_in(text: str, directories: list[str]) -> list[str]:
    found = []
    compact = {re.sub(r"[^a-z0-9]", "", d.lower()): d for d in directories if d.lower() != "google"}
    for u in URL_RE.findall(text):
        host = urlparse(u.rstrip(".,")).netloc.lower().replace("www.", "")
        if not host:
            continue
        label = next((d for c, d in compact.items() if c and c in host.replace("-", "")), None)
        if label is None and host.split(".")[0] == "google":
            label = "Google reviews / Maps"
        found.append(label or host)
    low = " " + norm(text) + " "
    for d in directories:
        if d.lower() == "google":
            if re.search(r"google (reviews?|maps|business)", text, re.I):
                found.append("Google reviews / Maps")
        elif f" {norm(d)} " in low:
            found.append(d)
    return list(dict.fromkeys(found))


def analyse_answer(text: str, audit: Audit) -> dict:
    hints = audit.industry.get("name_hints", [])
    dirs = audit.industry.get("directories", [])
    own_keys = {key(n) for n in audit.names()}
    known = audit.audit.get("known_competitors", [])
    ignore = {key(n) for n in audit.audit.get("ignore_names", [])}

    competitors: dict[str, dict] = {}
    order: list[str] = []
    for name, snippet in split_items(text):
        if not name:
            continue
        k = key(name)
        if not k or k in ignore or k in own_keys or any(k in o or o in k for o in own_keys if len(o) > 4):
            continue
        is_known = any(key(c) == k for c in known)
        if not is_known and not looks_like_business(name, hints, dirs):
            continue
        if k not in competitors:
            competitors[k] = {"name": name, "snippet": tidy_snippet(snippet, name), "reasons": reason_tags(snippet)}
            order.append(k)
    # Known competitors written in plain sentences (no list, no bold).
    for c in known:
        k = key(c)
        if k not in competitors and mentions(text, [c]):
            sent = next((s for s in re.split(r"(?<=[.!?])\s+", text) if mentions(s, [c])), "")
            competitors[k] = {"name": c, "snippet": tidy_snippet(sent, c), "reasons": reason_tags(sent)}
            order.append(k)

    is_mentioned = mentions(text, audit.names(), audit.business.get("website"))
    rank = None
    if is_mentioned:
        # Position among the businesses listed (1 = first one named).
        listed = [n for n, _ in split_items(text) if n]
        for idx, n in enumerate(dict.fromkeys(key(x) for x in listed), 1):
            if n in own_keys or any(o in n for o in own_keys if len(o) > 4):
                rank = idx
                break
    return {
        "mentioned": is_mentioned,
        "rank": rank,
        "competitors": [competitors[k] | {"key": k} for k in order],
        "sources": sources_in(text, dirs),
    }


def score(audit: Audit) -> dict:
    prompts = audit.prompts()
    per_model, per_question = {}, []
    comp_hits: dict[str, dict] = {}
    source_count: Counter = Counter()
    comp_sources: dict[str, Counter] = defaultdict(Counter)

    grid = {m: [] for m in audit.models}
    for m in audit.models:
        mentioned = answered = 0
        for i, q in enumerate(prompts, 1):
            _, text = read_answer(answer_path(audit, m, i))
            if not text:
                grid[m].append(None)
                continue
            answered += 1
            a = analyse_answer(text, audit)
            grid[m].append({"mentioned": a["mentioned"], "rank": a["rank"],
                            "competitors": [c["name"] for c in a["competitors"]], "sources": a["sources"]})
            mentioned += a["mentioned"]
            source_count.update(a["sources"])
            for c in a["competitors"]:
                h = comp_hits.setdefault(c["key"], {"name": c["name"], "answers": 0, "models": set(),
                                                    "reasons": Counter(), "snippets": []})
                h["answers"] += 1
                h["models"].add(m)
                h["reasons"].update(c["reasons"])
                if len(h["snippets"]) < 3 and c["snippet"]:
                    h["snippets"].append(c["snippet"])
                comp_sources[c["key"]].update(a["sources"])
        per_model[m] = {"label": audit.model_label(m), "mentioned": mentioned, "answered": answered,
                        "questions": len(prompts)}

    for i, q in enumerate(prompts):
        cells = {m: grid[m][i] for m in audit.models}
        per_question.append({"n": i + 1, "question": q,
                             "mentioned_in": [m for m, c in cells.items() if c and c["mentioned"]],
                             "answered_in": [m for m, c in cells.items() if c]})

    total_answered = sum(v["answered"] for v in per_model.values())
    total_mentioned = sum(v["mentioned"] for v in per_model.values())
    any_q = sum(1 for q in per_question if q["mentioned_in"])

    competitors = sorted(comp_hits.values(), key=lambda h: (-h["answers"], -len(h["models"]), h["name"]))
    comp_out = []
    for h in competitors:
        k = key(h["name"])
        comp_out.append({"name": h["name"], "answers": h["answers"],
                         "models": sorted(h["models"], key=audit.models.index),
                         "top_reasons": [r for r, _ in sorted(h["reasons"].items(),
                                                              key=lambda kv: (kv[0] == GENERIC_REASON, -kv[1]))][:3],
                         "snippets": h["snippets"],
                         "sources_seen_with": [s for s, _ in comp_sources[k].most_common(5)]})

    return {
        "business": audit.business["name"],
        "industry": audit.industry["name"],
        "place": audit.business.get("place", audit.business["city"]),
        "date": str(audit.audit.get("date", "")),
        "models": audit.models,
        "per_model": per_model,
        "overall": {"mentioned": total_mentioned, "answered": total_answered,
                    "questions": len(prompts), "questions_with_any_mention": any_q},
        "questions": per_question,
        "competitors": comp_out,
        "sources": source_count.most_common(),
        "suggested_gaps": suggest_gaps(comp_out, source_count, total_mentioned, total_answered),
    }


def suggest_gaps(competitors: list[dict], sources: Counter, mentioned: int, answered: int) -> list[str]:
    """Gap ids to CHECK, based on what the AI said about competitors. You confirm them in findings.toml."""
    top = competitors[:5]
    reason_counts = Counter(r for c in top for r in c["top_reasons"])
    out = []
    if reason_counts["reviews and ratings"] >= 1:
        out.append("reviews")
    if sources:
        out.append("directories")
    if reason_counts["specific services offered"] >= 2:
        out.append("service_pages")
    if reason_counts["clear website / helpful info"] >= 1 or answered and mentioned / answered < 0.25:
        out.append("faq_pages")
    out += ["gbp", "nap", "schema"]
    return list(dict.fromkeys(out))


def write_outputs(audit: Audit, result: dict) -> None:
    out = audit.output_dir
    (out / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with open(out / "competitors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["competitor", "answers_it_came_up_in", "ai_tools", "top_reasons", "sources_seen_with"])
        for c in result["competitors"]:
            w.writerow([c["name"], c["answers"], " / ".join(c["models"]), "; ".join(c["top_reasons"]),
                        "; ".join(c["sources_seen_with"])])
    lines = [f"# AI visibility score: {result['business']}", "",
             f"{result['industry']} in {result['place']}, checked {result['date']}", "",
             "| AI tool | Came up in | Answers pasted |", "| --- | --- | --- |"]
    for m, v in result["per_model"].items():
        lines.append(f"| {v['label']} | {v['mentioned']} of {v['questions']} | {v['answered']} |")
    o = result["overall"]
    lines += ["", f"**Overall:** came up in {o['mentioned']} of {o['answered']} answers. "
              f"At least once in {o['questions_with_any_mention']} of {o['questions']} questions.", "",
              "## Who AI recommends instead", ""]
    for c in result["competitors"][:10]:
        lines.append(f"- **{c['name']}**: {c['answers']} answers ({', '.join(c['models'])}). "
                     f"Reasons: {', '.join(c['top_reasons']) or 'none stated'}")
    lines += ["", "## Sites the AI cited", ""] + [f"- {s}: {n}" for s, n in result["sources"][:15]]
    lines += ["", "## Gaps worth checking (confirm in findings.toml)", ""] + [f"- {g}" for g in result["suggested_gaps"]]
    lines += ["", "Check `competitors.csv`. If a name there is not a real business, add it to",
              "`ignore_names` in audit.toml. If a competitor is missed, add it to `known_competitors`."]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
