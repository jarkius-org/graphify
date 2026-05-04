"""Tests for watch.py - file watcher helpers (no watchdog required)."""
import json
import time
from pathlib import Path
import pytest

from graphify.watch import _notify_only, _WATCHED_EXTENSIONS


# --- _notify_only ---

def test_notify_only_creates_flag(tmp_path):
    _notify_only(tmp_path)
    flag = tmp_path / "graphify-out" / "needs_update"
    assert flag.exists()
    assert flag.read_text() == "1"

def test_notify_only_creates_flag_dir(tmp_path):
    # graphify-out dir does not exist yet
    assert not (tmp_path / "graphify-out").exists()
    _notify_only(tmp_path)
    assert (tmp_path / "graphify-out").is_dir()

def test_notify_only_idempotent(tmp_path):
    _notify_only(tmp_path)
    _notify_only(tmp_path)
    flag = tmp_path / "graphify-out" / "needs_update"
    assert flag.read_text() == "1"


# --- _WATCHED_EXTENSIONS ---

def test_watched_extensions_includes_code():
    assert ".py" in _WATCHED_EXTENSIONS
    assert ".ts" in _WATCHED_EXTENSIONS
    assert ".go" in _WATCHED_EXTENSIONS
    assert ".rs" in _WATCHED_EXTENSIONS

def test_watched_extensions_includes_docs():
    assert ".md" in _WATCHED_EXTENSIONS
    assert ".txt" in _WATCHED_EXTENSIONS
    assert ".pdf" in _WATCHED_EXTENSIONS

def test_watched_extensions_includes_images():
    assert ".png" in _WATCHED_EXTENSIONS
    assert ".jpg" in _WATCHED_EXTENSIONS

def test_watched_extensions_excludes_noise():
    assert ".json" not in _WATCHED_EXTENSIONS
    assert ".pyc" not in _WATCHED_EXTENSIONS
    assert ".log" not in _WATCHED_EXTENSIONS


# --- watch() import error without watchdog ---

def test_check_update_no_flag_returns_true(tmp_path):
    """check_update returns True and is silent when needs_update flag is absent."""
    from graphify.watch import check_update
    assert check_update(tmp_path) is True


def test_check_update_with_flag_returns_true_and_prints(tmp_path, capsys):
    """check_update returns True and prints notification when flag exists."""
    from graphify.watch import check_update
    flag = tmp_path / "graphify-out" / "needs_update"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("1")
    result = check_update(tmp_path)
    assert result is True
    out = capsys.readouterr().out
    assert "graphify --update" in out


def test_check_update_does_not_clear_flag(tmp_path):
    """check_update never removes the needs_update flag (clearing is LLM's job)."""
    from graphify.watch import check_update
    flag = tmp_path / "graphify-out" / "needs_update"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text("1")
    check_update(tmp_path)
    assert flag.exists()


def test_rebuild_code_drops_stale_code_scoped_nodes(tmp_path):
    from graphify.watch import _rebuild_code

    (tmp_path / "index.php").write_text("<?php echo 'fresh';\n", encoding="utf-8")
    out = tmp_path / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(json.dumps({
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "index_php", "label": "index.php", "file_type": "code", "source_file": "index.php"},
            {
                "id": "page_stale",
                "label": "page:$stale",
                "file_type": "code",
                "source_file": "index.php",
                "runtime_kind": "web_page",
            },
        ],
        "links": [
            {
                "source": "index_php",
                "target": "page_stale",
                "relation": "redirects_to",
                "context": "web_flow",
                "confidence": "EXTRACTED",
                "source_file": "index.php",
                "weight": 1.0,
            }
        ],
    }), encoding="utf-8")

    assert _rebuild_code(tmp_path, force=True) is True

    rebuilt = json.loads((out / "graph.json").read_text(encoding="utf-8"))
    node_ids = {n["id"] for n in rebuilt["nodes"]}
    assert "page_stale" not in node_ids
    assert not any(e.get("target") == "page_stale" for e in rebuilt["links"])


def test_rebuild_code_preserves_non_code_source_nodes(tmp_path):
    from graphify.watch import _rebuild_code

    (tmp_path / "index.php").write_text("<?php echo 'fresh';\n", encoding="utf-8")
    out = tmp_path / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(json.dumps({
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "doc_note", "label": "Note", "file_type": "document", "source_file": "docs/note.md"},
        ],
        "links": [],
    }), encoding="utf-8")

    assert _rebuild_code(tmp_path, force=True) is True

    rebuilt = json.loads((out / "graph.json").read_text(encoding="utf-8"))
    node_ids = {n["id"] for n in rebuilt["nodes"]}
    assert "doc_note" in node_ids


def test_watch_raises_without_watchdog(tmp_path, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "watchdog.observers" or name == "watchdog.events":
            raise ImportError("mocked missing watchdog")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from graphify.watch import watch
    with pytest.raises(ImportError, match="watchdog not installed"):
        watch(tmp_path)
