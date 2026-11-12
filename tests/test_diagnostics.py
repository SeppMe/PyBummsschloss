"""The machine check: it must survive a child process that dies hard."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import subprocess  # noqa: E402
import sys  # noqa: E402

import pytest  # noqa: E402

from bummsschloss import diagnostics  # noqa: E402


def test_every_probe_is_named_and_documented():
    assert diagnostics.PROBES, "there must be something to probe"
    for name, probe in diagnostics.PROBES.items():
        assert callable(probe)
        assert probe.__doc__, f"probe {name} needs a one-line summary for the report"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows exit statuses")
@pytest.mark.parametrize("code", [0xC000001D, 0xC000001D - 0x100000000])
def test_illegal_instruction_is_recognised_signed_or_unsigned(code):
    """Windows hands the NTSTATUS over either way; both must be understood."""
    assert "illegal instruction" in diagnostics.explain_status(code)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows exit statuses")
def test_unknown_fatal_status_is_still_reported_as_a_crash():
    assert "fatal Windows exception" in diagnostics.explain_status(0xC0000374)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_sigill_is_recognised():
    assert "SIGILL" in diagnostics.explain_status(-4)


def test_ordinary_exit_status_is_not_mistaken_for_a_crash():
    assert diagnostics.explain_status(1) == "exit status 1"


def test_unknown_probe_is_rejected_rather_than_crashing():
    assert diagnostics.run_probe("no-such-probe") == 2


def test_a_failing_probe_is_reported_not_raised(monkeypatch, tmp_path):
    def explode() -> None:
        raise RuntimeError("boom")

    log = tmp_path / "probe.txt"
    monkeypatch.setitem(diagnostics.PROBES, "explode", explode)
    monkeypatch.setenv(diagnostics._PROBE_LOG, str(log))

    assert diagnostics.run_probe("explode") == 1
    # The parent reads this file, because a windowed build has no stderr.
    assert "boom" in log.read_text(encoding="utf-8")


def test_the_report_never_imports_pygame_into_its_own_process():
    """The whole point of the child processes.

    If the installed pygame uses an instruction this CPU lacks, importing it
    here would kill the very process that is supposed to write the report -
    which is precisely the machine we are trying to diagnose.
    """
    code = (
        "import sys;"
        "from bummsschloss import diagnostics;"
        "diagnostics.describe_machine();"
        "print('LOADED' if 'pygame' in sys.modules else 'CLEAN')"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=180
    )
    assert done.returncode == 0, done.stderr
    assert "CLEAN" in done.stdout, "describe_machine() must not import pygame in-process"


def test_the_machine_description_survives_a_pygame_that_cannot_load(monkeypatch):
    """A pygame that dies on import must be reported, not propagated."""

    def dead_child(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=-4, stdout="", stderr="")

    monkeypatch.setattr(diagnostics.subprocess, "run", dead_child)
    assert "cannot be imported" in diagnostics._pygame_version()


def test_the_machine_description_mentions_the_cpu_and_python():
    report = "\n".join(diagnostics.describe_machine())
    assert "CPU" in report
    assert "Python" in report


def test_cpu_features_are_believable_if_reported():
    features = diagnostics.cpu_features()
    if not features:
        pytest.skip("this platform will not say")
    # SSE2 is part of the x86-64 ABI, so any 64-bit x86 machine must have it.
    if "64" in os.environ.get("PROCESSOR_ARCHITECTURE", "") or sys.maxsize > 2**32:
        assert features.get("SSE2", True)
