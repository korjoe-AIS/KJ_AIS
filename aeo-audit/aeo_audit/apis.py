"""Optional API mode. OFF by default and it costs money.

It only runs when ALL of these are true:
  1. the audit's audit.toml has  [api] enabled = true
  2. the key is in aeo-audit/.env (never in GitHub)
  3. you pass --yes-spend on the command line, after seeing the cost estimate

Honest caveat: API answers are not the same as what a customer sees in the app.
The apps add location, chat history and their own instructions. For a sales audit,
the manual paste from the real apps is the more truthful view. API mode is for
re-measuring the same questions every month without the copy-paste work.

Uses only Python's built-in urllib, so there are no SDKs to install.
"""
from __future__ import annotations

import json
import os
import urllib.request

from .config import pricing

API_MODELS = ("chatgpt", "perplexity", "gemini")
KEY_NAMES = {"chatgpt": "OPENAI_API_KEY", "perplexity": "PERPLEXITY_API_KEY", "gemini": "GEMINI_API_KEY"}


def estimate(models: list[str], n_questions: int, prices: dict | None = None) -> dict:
    prices = prices or pricing()
    a = prices["assumptions"]
    rows, total = [], 0.0
    for m in models:
        if m not in API_MODELS:
            continue
        p = prices[m]
        tokens = n_questions * (a["input_tokens_per_question"] * p["input_per_million"]
                                + a["output_tokens_per_question"] * p["output_per_million"]) / 1_000_000
        fees = n_questions * p["per_call_fee"]
        cost = tokens + fees
        total += cost
        rows.append({"model": m, "api_model": p["model"], "questions": n_questions,
                     "token_cost": round(tokens, 4), "search_fees": round(fees, 4),
                     "cost": round(cost, 4), "notes": p.get("notes", "")})
    return {"rows": rows, "total": round(total, 4)}


def check_ready(audit, models: list[str]) -> list[str]:
    """Returns a list of reasons API mode can't run. Empty list = ready."""
    problems = []
    if not audit.api.get("enabled", False):
        problems.append("API mode is off. Set  [api] enabled = true  in audit.toml to turn it on.")
    for m in models:
        if m not in API_MODELS:
            continue
        if not os.environ.get(KEY_NAMES[m]):
            problems.append(f"{KEY_NAMES[m]} is missing from aeo-audit/.env")
    return problems


def _post(url: str, body: dict, headers: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https URLs
        return json.loads(resp.read().decode())


def _with_sources(text: str, urls: list[str]) -> str:
    urls = list(dict.fromkeys(u for u in urls if u))
    if urls:
        text += "\n\nSources:\n" + "\n".join(f"- {u}" for u in urls)
    return text


def ask_chatgpt(question: str, model: str) -> str:
    data = _post("https://api.openai.com/v1/responses",
                 {"model": model, "tools": [{"type": "web_search_preview"}], "input": question},
                 {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    texts, urls = [], []
    for item in data.get("output", []):
        for c in item.get("content", []) or []:
            if c.get("type") == "output_text":
                texts.append(c.get("text", ""))
                urls += [a.get("url") for a in c.get("annotations", []) if a.get("type") == "url_citation"]
    return _with_sources("\n".join(texts), urls)


def ask_perplexity(question: str, model: str) -> str:
    data = _post("https://api.perplexity.ai/chat/completions",
                 {"model": model, "messages": [{"role": "user", "content": question}]},
                 {"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}"})
    text = data["choices"][0]["message"]["content"]
    urls = list(data.get("citations", [])) + [r.get("url") for r in data.get("search_results", [])]
    return _with_sources(text, urls)


def ask_gemini(question: str, model: str) -> str:
    data = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                 {"contents": [{"parts": [{"text": question}]}], "tools": [{"google_search": {}}]},
                 {"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    cand = data["candidates"][0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
    urls = [c.get("web", {}).get("uri") for c in chunks]
    return _with_sources(text, urls)


ASKERS = {"chatgpt": ask_chatgpt, "perplexity": ask_perplexity, "gemini": ask_gemini}


def run(audit, models: list[str], overwrite: bool = False) -> int:
    """Asks each question through the APIs and saves answers. Returns number of calls made."""
    from datetime import date

    from .collect import answer_path, file_header, read_answer

    prices = pricing()
    calls = 0
    for m in models:
        if m not in API_MODELS:
            continue
        api_model = prices[m]["model"]
        for i, q in enumerate(audit.prompts(), 1):
            p = answer_path(audit, m, i)
            if read_answer(p)[1] and not overwrite:
                continue
            answer = ASKERS[m](q, api_model)
            calls += 1
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(file_header(q, f"api {api_model} {date.today().isoformat()}") + answer + "\n", encoding="utf-8")
            print(f"  saved {m}/{p.name}")
    return calls
