"""Step 2: get the AI answers into answers/<model>/NN.txt.

Manual mode (default, free): this makes one empty file per question per AI tool.
You ask the question in the real app and paste the whole answer into the file.
"""
from __future__ import annotations

from pathlib import Path

from .config import Audit

MARKER = "----- paste the full answer below this line (include any links or sources) -----"


def answer_path(audit: Audit, model: str, i: int) -> Path:
    return audit.answers_dir / model / f"{i:02d}.txt"


def file_header(question: str, source: str = "manual") -> str:
    return f"QUESTION: {question}\nSOURCE: {source}\n{MARKER}\n"


def read_answer(path: Path) -> tuple[str | None, str]:
    """Returns (question in file, answer text). Answer is '' if nothing was pasted yet."""
    if not path.exists():
        return None, ""
    text = path.read_text(encoding="utf-8", errors="replace")
    question = None
    for line in text.splitlines()[:3]:
        if line.startswith("QUESTION:"):
            question = line[len("QUESTION:"):].strip()
    if MARKER in text:
        text = text.split(MARKER, 1)[1]
    return question, text.strip()


def prepare_manual(audit: Audit) -> dict[str, tuple[int, int]]:
    """Creates any missing paste files. Never touches a file that already has an answer."""
    prompts = audit.prompts()
    progress = {}
    for model in audit.models:
        done = 0
        for i, q in enumerate(prompts, 1):
            p = answer_path(audit, model, i)
            p.parent.mkdir(parents=True, exist_ok=True)
            existing_q, answer = read_answer(p)
            if answer:
                done += 1
                if existing_q and existing_q != q:
                    print(f"  ! {model}/{p.name}: question in file differs from prompts.txt line {i}. Check it.")
                continue
            p.write_text(file_header(q), encoding="utf-8")
        progress[model] = (done, len(prompts))
    return progress


def next_unanswered(audit: Audit, limit: int = 5) -> list[tuple[str, int, str, Path]]:
    out = []
    prompts = audit.prompts()
    for model in audit.models:
        for i, q in enumerate(prompts, 1):
            p = answer_path(audit, model, i)
            if not read_answer(p)[1]:
                out.append((model, i, q, p))
                if len(out) >= limit:
                    return out
    return out
