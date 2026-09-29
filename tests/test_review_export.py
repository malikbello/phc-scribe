import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_review_app_content_matches_repo():
    spec = importlib.util.spec_from_file_location(
        "export_review_data", ROOT / "scripts" / "export_review_data.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (ROOT / "review-app" / "src" / "data" / "review.json").read_text(encoding="utf-8")
    assert committed == module.build(), "run: python scripts/export_review_data.py"
