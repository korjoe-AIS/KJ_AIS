"""Run with:  python3 -m pytest tests -q   (from the aeo-audit folder)"""
import shutil
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import aeo  # noqa: E402
from aeo_audit import apis, collect, config, prompts, score  # noqa: E402

DEMO = ROOT / "examples" / "demo-med-spa"


@pytest.fixture
def demo(tmp_path):
    d = tmp_path / "demo"
    shutil.copytree(DEMO, d, ignore=shutil.ignore_patterns("output"))
    return config.Audit(d)


@pytest.mark.parametrize("slug", config.list_industries())
def test_every_industry_makes_20_filled_questions(slug):
    qs = prompts.build_prompts(config.industry(slug), "Hanover", "Hanover, MD")
    assert len(qs) == 20
    assert all("{" not in q and "Hanover" in q for q in qs)


def test_mention_matching_uses_aliases_and_website():
    names = ["Lumen Demo Aesthetics", "Lumen Aesthetics"]
    assert score.mentions("Try **Lumen Aesthetics** for Botox.", names)
    assert score.mentions("See lumen-demo-aesthetics.example/botox", names, "lumen-demo-aesthetics.example")
    assert not score.mentions("Luminous Skin is great.", names)


def test_competitor_extraction_from_list(demo):
    text = ("Here are options:\n1. **Halcyon Demo Med Spa** - 4.9 stars with 600 reviews.\n"
            "2. **Lumen Demo Aesthetics** - newer.\n3. Ember Demo Injectables: great lip filler.\n"
            "Sources: https://www.realself.com/x https://www.yelp.com/y")
    a = score.analyse_answer(text, demo)
    names = [c["name"] for c in a["competitors"]]
    assert names == ["Halcyon Demo Med Spa", "Ember Demo Injectables"]
    assert a["mentioned"] and a["rank"] == 2
    assert "reviews and ratings" in a["competitors"][0]["reasons"]
    assert {"RealSelf", "Yelp"} <= set(a["sources"])


def test_demo_scores(demo):
    r = score.score(demo)
    assert {m: v["mentioned"] for m, v in r["per_model"].items()} == \
        {"chatgpt": 2, "perplexity": 5, "gemini": 2, "google_ai_overviews": 1}
    assert r["overall"]["mentioned"] == 10 and r["overall"]["answered"] == 80
    assert all("Demo" in c["name"] for c in r["competitors"])
    assert all(c["name"] != "Lumen Demo Aesthetics" for c in r["competitors"])


def test_report_builds_two_page_pdf(demo):
    aeo.main(["report", str(demo.dir)])
    pdf = next((demo.dir / "output").glob("*.pdf"))
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF") and b"/Count 2" in data  # front + back


def test_empty_answers_count_as_not_asked(demo):
    p = demo.answers_dir / "chatgpt" / "01.txt"
    q, _ = collect.read_answer(p)
    p.write_text(f"QUESTION: {q}\nSOURCE: manual\n{collect.MARKER}\n")
    r = score.score(demo)
    assert r["per_model"]["chatgpt"]["answered"] == 19


def test_api_mode_never_calls_network_unless_enabled(demo, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("network was called")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    for k in apis.KEY_NAMES.values():
        monkeypatch.setenv(k, "test-key")
    # enabled = false in the demo audit.toml -> refuses even with keys and --yes-spend
    aeo.main(["collect", str(demo.dir), "--api", "--yes-spend"])
    assert "API mode is off" in capsys.readouterr().out


def test_api_mode_needs_yes_spend(demo, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("network was called")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    for k in apis.KEY_NAMES.values():
        monkeypatch.setenv(k, "test-key")
    demo.api["enabled"] = True
    assert apis.check_ready(demo, ["chatgpt", "perplexity", "gemini"]) == []
    cfg = demo.dir / "audit.toml"
    cfg.write_text(cfg.read_text().replace("enabled = false", "enabled = true"))
    aeo.main(["collect", str(demo.dir), "--api"])
    assert "Nothing was sent" in capsys.readouterr().out


def test_cost_estimate_is_under_two_dollars():
    est = apis.estimate(["chatgpt", "perplexity", "gemini"], 20)
    assert 0 < est["total"] < 2


def test_switching_industry_is_one_line(tmp_path):
    d = tmp_path / "hvac"
    aeo.main(["new", str(d), "--business", "Demo Air", "--industry", "hvac", "--city", "Columbia", "--place", "Columbia, MD"])
    assert "HVAC company in Columbia, MD" in (d / "prompts.txt").read_text()
