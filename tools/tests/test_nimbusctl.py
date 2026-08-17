"""Smoke tests for nimbusctl CLI (no network)."""
import subprocess
import sys
from pathlib import Path

CTL = Path(__file__).resolve().parent.parent / "nimbusctl.py"


def run(*args):
    return subprocess.run([sys.executable, str(CTL), *args],
                          capture_output=True, text=True)


def test_help():
    r = run("--help")
    assert r.returncode == 0
    assert "start" in r.stdout and "migrate" in r.stdout


def test_requires_repo_token():
    r = run("status")
    assert r.returncode != 0
    assert "NIMBUS_REPO" in (r.stdout + r.stderr)
