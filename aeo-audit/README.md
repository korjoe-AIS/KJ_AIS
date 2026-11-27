# AI visibility audit (AEO)

This tool makes the free "door-opener" audit for a local business:
**"We asked AI 20 questions your customers actually ask. You came up in X of them. Here's who AI picks instead, and why."**

It checks ChatGPT, Perplexity, Gemini and Google AI Overviews, scores the answers, and builds a
two-sided, one-page PDF: findings on the front, the exact questions and method on the back.

Open the demo to see the end result:
[`examples/demo-med-spa/output/lumen-demo-aesthetics-ai-visibility-audit.pdf`](examples/demo-med-spa/output/lumen-demo-aesthetics-ai-visibility-audit.pdf)
(every business in it is made up).

## Important: this repo is public

- **Real client audits never go in git.** Make them inside `aeo-audit/audits/`, which git ignores.
- **API keys never go in git.** They live in `aeo-audit/.env`, which git ignores.
- Only the fictional demo (`examples/demo-med-spa`) is committed.

## One-time setup (5 minutes)

On your Mac, in Terminal:

```bash
cd "path/to/KJ_AIS/aeo-audit"
python3 -m pip install -r requirements.txt     # installs reportlab (free), for the PDF
python3 -m pytest tests -q                     # optional: should say "passed"
```

Needs Python 3.9 or newer (check with `python3 --version`).

## Making an audit (free, about 60-90 minutes the first time)

**1. Start the audit folder.** One folder per business.

```bash
python3 aeo.py new audits/glow-room --business "The Glow Room" --industry med-spa --city Hanover --place "Hanover, MD"
```

Then open `audits/glow-room/audit.toml` and fill in:
- `aliases`: other ways people write the name ("Glow Room", "Glow Room Med Spa")
- `website`: their domain (a link to their site counts as a mention)

**2. Check the 20 questions** in `audits/glow-room/prompts.txt`. One question per line. Edit freely,
but keep them the same from month to month so scores compare fairly.

**3. Make the paste files.**

```bash
python3 aeo.py collect audits/glow-room
```

This makes `answers/chatgpt/01.txt` through `answers/google_ai_overviews/20.txt`. Each file shows the
question at the top. Type that question into the real app, copy the *whole* answer (including links
and sources) and paste it below the line. Run `collect` again any time to see what's left.

Tips so your results are fair:
- Use a fresh chat (or a logged-out / private window) for each question.
- For Google AI Overviews, search the question on google.com and paste the AI Overview box. If no box shows, leave the file empty: it counts as "not asked", not as a miss.

**4. Check their basics by hand (about 20 minutes).** Look at their Google Business Profile, review
count, website, Yelp/RealSelf listings and whether their name/address/phone match. Copy
`findings.toml.example` to `findings.toml` and pick 3-5 gaps, each with one specific fact, like
`detail = "41 Google reviews vs. 300+ for the three spas AI named."`
Without this file the PDF still builds, but the gaps are marked as a draft.

**5. Score and build the PDF.**

```bash
python3 aeo.py report audits/glow-room
```

You get, in `audits/glow-room/output/`:
- the PDF
- `summary.md`: the scores, every competitor found, every site cited, and suggested gaps
- `competitors.csv`: check this. If something there isn't a real business, add it to `ignore_names`
  in `audit.toml`. If a competitor was missed, add it to `known_competitors`. Then run `report` again.

## Switching industry or area

Industries are templates in `industries/`: `med-spa`, `dentist`, `hvac`, `roofer`, `law-firm`.
Each has 20 questions using `{place}` ("Hanover, MD") and `{city}` ("Hanover").

- **Different area:** change `city` and `place` in `audit.toml`, then `python3 aeo.py prompts audits/glow-room --force`.
- **Different industry:** change `industry` in `audit.toml`, then the same `prompts --force` command.
- **New industry:** copy any file in `industries/`, rename it, change the questions, name hints and directories.
- **Nearby areas** (Arundel Mills, Columbia, Glen Burnie...): add lines to `extra_questions` in `audit.toml`.

## How the scoring works (and its limits)

- **Mentioned** = the business name, an alias, or its website appears anywhere in the answer.
- **Score** = per AI tool, "came up in X of 20". Overall = "X of 80 answers", plus how many of the 20
  questions got at least one mention.
- **Competitors** = businesses named in list items or in bold, whose names look like the industry
  ("Med Spa", "Aesthetics", "Skin"...). This is a rule of thumb, so always glance at `competitors.csv`.
- **Reasons** = the words the AI used about each competitor, grouped into plain labels such as
  "reviews and ratings" or "price, financing or memberships".
- **Sources** = links and directory names (Yelp, RealSelf, Google...) the answers cite.

AI answers change by day, location and account. The PDF says so on the back, and it never promises
placement. What we sell is the measurement (same questions every month) and the fixes.

## Optional API mode (OFF, costs money)

Instead of pasting, the tool can ask ChatGPT, Perplexity and Gemini through their APIs. Google AI
Overviews has no official API, so it is always pasted by hand.

**Estimated cost: about $0.97 per audit** (20 questions x 3 tools, prices checked 2026-11-27):

| Tool | Model | Cost per audit | Mostly from |
| --- | --- | --- | --- |
| ChatGPT | gpt-6-luna + web search | about $0.50 | $25 per 1,000 web searches |
| Perplexity | sonar | about $0.14 | per-request search fee (not confirmed, high end assumed) |
| Gemini | gemini-3.6-flash + Google Search | about $0.33, or $0.05 inside the 5,000 free searches a month | $14 per 1,000 searches after the free 5,000 |

See the numbers any time without spending: `python3 aeo.py estimate audits/glow-room`.

It only runs when **all three** are true:
1. `[api] enabled = true` in that audit's `audit.toml`
2. the keys are in `aeo-audit/.env` (copy `.env.example`)
3. you add `--yes-spend`: `python3 aeo.py collect audits/glow-room --api --yes-spend`

Two honest caveats: API answers are not exactly what a customer sees in the app (the apps add
location and their own settings), so for the first sales audits the manual paste is more truthful.
And prices change: check `pricing.toml` against the links in it before turning this on. Gemini's
search grounding also needs a billing-enabled key. Turning API mode on needs your approval first.

## The demo

`examples/demo-med-spa` is a full audit of **Lumen Demo Aesthetics**, a made-up med spa in Hanover, MD,
with made-up competitors (all with "Demo" in the name). The answers were generated by
`examples/make_demo_answers.py` to look like real AI answers. Rebuild it with:

```bash
python3 examples/make_demo_answers.py
python3 aeo.py report examples/demo-med-spa
```

## Files

| Path | What it is |
| --- | --- |
| `aeo.py` | The command you run (`new`, `prompts`, `collect`, `estimate`, `score`, `report`, `industries`) |
| `industries/*.toml` | Question templates per industry |
| `settings.toml` | Your brand, contact line on the PDF, which AI tools to check |
| `pricing.toml` | API prices used for the cost estimate |
| `aeo_audit/` | The code: prompts, collect, apis (off), score, gaps, report |
| `examples/demo-med-spa/` | The fictional demo audit |
| `tests/` | `python3 -m pytest tests -q` |
