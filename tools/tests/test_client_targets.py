"""Unit tests for the client target/session helpers (no network, no tkinter).

Covers the part that makes a client able to point at ANY repo/runner: URL
extraction from both session layouts, state normalization, and config
migration from the old single-seat file.
"""
import importlib.util
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parents[2] / "clients" / "desktop" / "nimbus_targets.py"
spec = importlib.util.spec_from_file_location("nimbus_targets", MOD)
nt = importlib.util.module_from_spec(spec)
sys.modules["nimbus_targets"] = nt
spec.loader.exec_module(nt)


def test_extract_url_prefers_url_then_novnc():
    assert nt.extract_url({"url": "https://a/x"}) == "https://a/x"
    assert nt.extract_url({"novncUrl": "https://b/vnc.html"}) == "https://b/vnc.html"
    assert nt.extract_url({"url": "about:blank", "web": "https://c"}) == "https://c"
    assert nt.extract_url({}) is None
    assert nt.extract_url(None) is None


def test_normalize_nimbus_seat_live():
    s = nt.normalize_session({"state": "live", "url": "https://host/nimbus.html?pw=x",
                              "resolution": "1280x720", "fps": 30})
    assert s["live"] is True
    assert s["url"] == "https://host/nimbus.html?pw=x"
    assert s["resolution"] == "1280x720"


def test_normalize_zen_panel_vnc_has_no_state_field():
    # zen-panel's VNC slot publishes url/novncUrl but no `state`.
    s = nt.normalize_session({"kind": "Linux-VNC", "os": "linux",
                              "url": "https://host/vnc.html",
                              "novncUrl": "https://host/vnc.html"})
    assert s["live"] is True
    assert s["kind"] == "Linux-VNC"
    assert s["url"] == "https://host/vnc.html"


def test_ended_is_never_live_even_with_stale_url():
    s = nt.normalize_session({"state": "ended", "url": "https://host/vnc.html"})
    assert s["live"] is False
    assert s["state"] == "ended"


def test_offline_without_url():
    assert nt.normalize_session({"state": "offline"})["live"] is False
    assert nt.normalize_session({})["live"] is False


def test_migrate_legacy_single_seat():
    cfg = nt.migrate_config({"repo": "me/fork", "token": "t"})
    assert cfg["token"] == "t"
    assert len(cfg["targets"]) == 1
    assert cfg["targets"][0]["repo"] == "me/fork"
    assert cfg["targets"][0]["session"]["branch"] == "live"
    assert cfg["active"] == cfg["targets"][0]["name"]


def test_migrate_empty_uses_defaults():
    cfg = nt.migrate_config({})
    names = [t["name"] for t in cfg["targets"]]
    assert "NimbusSeat" in names and "zen-panel screen" in names
    assert cfg["active"] == names[0]


def test_migrate_keeps_existing_targets_and_fixes_active():
    raw = {"token": "t", "active": "nope", "targets": [
        {"name": "A", "repo": "o/a"}, {"name": "B", "repo": "o/b"}]}
    cfg = nt.migrate_config(raw)
    assert [t["name"] for t in cfg["targets"]] == ["A", "B"]
    assert cfg["active"] == "A"          # bad active falls back to the first
    assert cfg["targets"][0]["workflow"] == nt.NIMBUS_WORKFLOW


def test_find_target():
    cfg = nt.migrate_config({"targets": [{"name": "A", "repo": "o/a"},
                                         {"name": "B", "repo": "o/b"}], "active": "B"})
    assert nt.find_target(cfg)["name"] == "B"
    assert nt.find_target(cfg, "A")["name"] == "A"
    assert nt.find_target({"targets": []}) is None
