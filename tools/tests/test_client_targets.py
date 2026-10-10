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
    assert "NimbusSeat" in names and "zen-panel hub" in names
    hub = [t for t in cfg["targets"] if t["name"] == "zen-panel hub"][0]
    assert hub["session"]["path"] == "live/session-hub-linux.json"
    assert hub["session"]["branch"] == "session-state"
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


def _capture_auth(monkeypatch, token):
    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["auth"] = req.get_header("Authorization")
        raise OSError("stop")

    monkeypatch.setattr(nt.urllib.request, "urlopen", fake_urlopen)
    nt.GitHub(token)._req("GET", "/repos/o/r/contents/x")
    return seen["auth"]


def test_empty_token_sends_no_authorization(monkeypatch):
    # A bare `Authorization: token ` makes GitHub 401 even on public repos,
    # so a tokenless client must not send the header at all.
    assert _capture_auth(monkeypatch, "") is None


def test_token_is_sent_when_present(monkeypatch):
    assert _capture_auth(monkeypatch, "abc") == "token abc"


def test_novnc_url_adds_autoconnect_and_scale():
    # zen-panel publishes a bare vnc.html: without this it shows a dark
    # Connect dialog at 1:1 instead of the desktop.
    assert nt.novnc_url("https://h/vnc.html") == \
        "https://h/vnc.html?autoconnect=1&resize=scale"
    assert nt.novnc_url("https://h/path/vnc_lite.html") == \
        "https://h/path/vnc_lite.html?autoconnect=1&resize=scale"


def test_novnc_url_keeps_existing_query():
    out = nt.novnc_url("https://h/vnc.html?password=secret")
    assert "password=secret" in out
    assert "autoconnect=1" in out and "resize=scale" in out


def test_novnc_url_leaves_non_novnc_untouched():
    assert nt.novnc_url("https://h/nimbus.html?pw=x") == "https://h/nimbus.html?pw=x"
    assert nt.novnc_url(None) is None


def test_novnc_url_adds_hub_gate_for_any_page():
    # A gated hub answers 401 on pages, api and audio unless ?zt= is present.
    assert nt.novnc_url("https://h/m", "tok") == "https://h/m?zt=tok"
    assert nt.novnc_url("https://h/vnc.html", "tok") == \
        "https://h/vnc.html?autoconnect=1&resize=scale&zt=tok"


def test_novnc_url_keeps_existing_gate():
    out = nt.novnc_url("https://h/m?zt=already", "tok")
    assert out == "https://h/m?zt=already"


def test_dispatch_passes_gate_as_token_input(monkeypatch):
    seen = {}

    def fake_req(self, method, path, body=None):
        seen["body"] = body
        seen["path"] = path
        return 204, {}

    monkeypatch.setattr(nt.GitHub, "_req", fake_req)
    nt.GitHub("t").dispatch({
        "repo": "o/r", "workflow": "hub.yml", "inputs": {"os": "linux"},
        "gate": "secret",
    })
    assert seen["path"] == "/repos/o/r/actions/workflows/hub.yml/dispatches"
    assert seen["body"]["inputs"]["token"] == "secret"
    assert seen["body"]["inputs"]["os"] == "linux"


def test_dispatch_leaves_inputs_alone_without_gate(monkeypatch):
    seen = {}

    def fake_req(self, method, path, body=None):
        seen["body"] = body
        return 204, {}

    monkeypatch.setattr(nt.GitHub, "_req", fake_req)
    nt.GitHub("t").dispatch({"repo": "o/r", "workflow": "hub.yml",
                             "inputs": {"os": "linux"}})
    assert "token" not in seen["body"]["inputs"]


def test_mobile_url_wins_over_plain_url():
    assert nt.extract_url({"mobile": "https://h/m", "url": "https://h/"}) == "https://h/m"
