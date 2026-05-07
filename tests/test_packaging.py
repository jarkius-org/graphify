from __future__ import annotations

import tomllib
from pathlib import Path


def test_optional_dependencies_include_direct_llm_backends():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]

    assert "openai" in extras["kimi"]
    assert "anthropic" in extras["claude"]
    assert "openai" in extras["llm"]
    assert "anthropic" in extras["llm"]


def test_dashboard_assets_are_packaged():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "graphify.web" in data["tool"]["setuptools"]["packages"]
    assert set(data["tool"]["setuptools"]["package-data"]["graphify.web"]) == {
        "index.html",
        "app.js",
        "styles.css",
    }
