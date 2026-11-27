"""Loads the settings files. Everything a person edits is a plain .toml or .txt file."""
from __future__ import annotations

import os
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - older Python
    import tomli as tomllib  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
INDUSTRIES_DIR = ROOT / "industries"


def load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def settings() -> dict:
    return load_toml(ROOT / "settings.toml")


def pricing() -> dict:
    return load_toml(ROOT / "pricing.toml")


def list_industries() -> list[str]:
    return sorted(p.stem for p in INDUSTRIES_DIR.glob("*.toml"))


def industry(slug: str) -> dict:
    path = INDUSTRIES_DIR / f"{slug}.toml"
    if not path.exists():
        raise SystemExit(
            f"No industry called '{slug}'. Pick one of: {', '.join(list_industries())}\n"
            f"(or copy one of the files in {INDUSTRIES_DIR} to make a new one)"
        )
    data = load_toml(path)
    data["slug"] = slug
    return data


class Audit:
    """One audit = one folder with audit.toml, prompts.txt, answers/ and output/."""

    def __init__(self, folder: str | Path):
        self.dir = Path(folder).resolve()
        cfg_path = self.dir / "audit.toml"
        if not cfg_path.exists():
            raise SystemExit(f"No audit.toml in {self.dir}. Start one with:  python3 aeo.py new {folder} ...")
        self.cfg = load_toml(cfg_path)
        self.business = self.cfg["business"]
        self.audit = self.cfg.get("audit", {})
        self.api = self.cfg.get("api", {})
        self.settings = settings()
        self.industry = industry(self.business["industry"])

    # --- paths -------------------------------------------------------
    @property
    def prompts_path(self) -> Path:
        return self.dir / "prompts.txt"

    @property
    def answers_dir(self) -> Path:
        return self.dir / "answers"

    @property
    def output_dir(self) -> Path:
        d = self.dir / "output"
        d.mkdir(exist_ok=True)
        return d

    @property
    def findings_path(self) -> Path:
        return self.dir / "findings.toml"

    # --- values ------------------------------------------------------
    @property
    def models(self) -> list[str]:
        all_models = list(self.settings["models"].keys())
        chosen = self.audit.get("models", all_models)
        unknown = [m for m in chosen if m not in all_models]
        if unknown:
            raise SystemExit(f"Unknown model(s) {unknown} in audit.toml. Known: {all_models}")
        return chosen

    def model_label(self, model: str) -> str:
        return self.settings["models"][model]["label"]

    def model_short(self, model: str) -> str:
        m = self.settings["models"][model]
        return m.get("short", m["label"])

    def names(self) -> list[str]:
        """The business name plus any other ways people write it."""
        return [self.business["name"], *self.business.get("aliases", [])]

    def prompts(self) -> list[str]:
        if not self.prompts_path.exists():
            raise SystemExit(f"No prompts.txt yet. Run:  python3 aeo.py prompts {self.dir}")
        lines = self.prompts_path.read_text(encoding="utf-8").splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def load_env(path: Path | None = None) -> None:
    """Reads KEY=value lines from aeo-audit/.env into the environment (no extra library needed)."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value and key.strip() not in os.environ:
            os.environ[key.strip()] = value
