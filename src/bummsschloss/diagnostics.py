"""Find out why the game will not start on somebody else's machine.

Run it when the game crashes or refuses to come up::

    bummsschloss --diagnose
    python -m bummsschloss.diagnostics

The game package itself is pure Python; the only machine code involved belongs
to pygame-ce, the SDL libraries and CPython. A crash that kills the process
outright - an illegal instruction on an old CPU, a missing DLL, a video driver
that cannot make a window - therefore leaves no Python traceback, which makes
"it does not work" the only report the user can give.

So every probe runs in its own child process. If a probe takes the process
down with it, the parent survives, decodes the exit status and names the step
that did it. The first failure in the list is the interesting one.
"""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

from bummsschloss import __version__, config

#: Environment variable naming the file a child probe writes its failure to.
_PROBE_LOG = "BUMMSSCHLOSS_PROBE_LOG"

# Exit statuses that mean the child did not die of a Python exception.
# Windows reports an unhandled structured exception as the NTSTATUS itself.
# Depending on how the status travels, Python hands it over either unsigned
# (3221225501) or signed (-1073741795), so both forms must be recognised.
_WINDOWS_STATUS = {
    0xC000001D: "illegal instruction (0xC000001D) - the CPU does not know an "
    "instruction this component was built with",
    0xC000001E: "invalid instruction access (0xC000001E)",
    0xC0000005: "access violation (0xC0000005) - a bad memory access",
    0xC0000135: "missing DLL (0xC0000135) - a dependency could not be loaded",
    0xC0000142: "DLL initialisation failed (0xC0000142)",
    0xC00000FD: "stack overflow (0xC00000FD)",
    0xC0000409: "stack buffer overrun (0xC0000409)",
}

# POSIX reports a fatal signal as a negative signal number.
_SIGNALS = {
    -4: "SIGILL - illegal instruction, the CPU does not know an instruction "
    "this component was built with",
    -11: "SIGSEGV - a bad memory access",
    -6: "SIGABRT - the component aborted",
    -8: "SIGFPE - an arithmetic fault",
}

PROBE_TIMEOUT = 120.0


# -- what the machine can do -------------------------------------------------


def _windows_cpu_features() -> dict[str, bool]:
    """Ask Windows which instruction-set extensions this CPU supports."""
    # PF_* constants from winnt.h, passed to IsProcessorFeaturePresent.
    features = {
        "SSE2": 10,
        "SSE3": 13,
        "SSSE3": 36,
        "SSE4.1": 37,
        "SSE4.2": 38,
        "AVX": 39,
        "AVX2": 40,
        "AVX512F": 41,
    }
    present = ctypes.windll.kernel32.IsProcessorFeaturePresent
    return {name: bool(present(number)) for name, number in features.items()}


def _cpuinfo_flags() -> set[str]:
    """The flag list Linux publishes for the first core."""
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.startswith("flags") or line.startswith("Features"):
                    return set(line.partition(":")[2].split())
    except OSError:
        pass
    return set()


def _sysctl(name: str) -> str:
    try:
        return subprocess.run(
            ["sysctl", "-n", name], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def cpu_features() -> dict[str, bool]:
    """Map instruction-set extension -> whether this CPU has it.

    Returns an empty mapping when the platform will not say.
    """
    if sys.platform == "win32":
        try:
            return _windows_cpu_features()
        except (AttributeError, OSError):
            return {}
    if sys.platform == "darwin":
        reported = _sysctl("machdep.cpu.features") + " " + _sysctl("machdep.cpu.leaf7_features")
        words = {word.lower() for word in reported.split()}
        if not words:
            return {}
        return {
            "SSE2": "sse2" in words,
            "SSE3": "sse3" in words,
            "SSSE3": "ssse3" in words,
            "SSE4.1": "sse4.1" in words,
            "SSE4.2": "sse4.2" in words,
            "AVX": "avx1.0" in words or "avx" in words,
            "AVX2": "avx2" in words,
            "AVX512F": "avx512f" in words,
        }
    flags = _cpuinfo_flags()
    if not flags:
        return {}
    return {
        "CMOV": "cmov" in flags,
        "MMX": "mmx" in flags,
        "SSE": "sse" in flags,
        "SSE2": "sse2" in flags,
        "SSE3": "pni" in flags or "sse3" in flags,
        "SSSE3": "ssse3" in flags,
        "SSE4.1": "sse4_1" in flags,
        "SSE4.2": "sse4_2" in flags,
        "AVX": "avx" in flags,
        "AVX2": "avx2" in flags,
        "AVX512F": "avx512f" in flags,
    }


def cpu_name() -> str:
    """A human-readable processor name, as far as the platform offers one."""
    if sys.platform == "win32":
        try:
            import winreg

            key = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
                return str(winreg.QueryValueEx(handle, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    elif sys.platform == "darwin":
        name = _sysctl("machdep.cpu.brand_string")
        if name:
            return name
    else:
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.startswith("model name"):
                        return line.partition(":")[2].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine() or "unknown"


def is_32bit_x86() -> bool:
    """True on a 32-bit x86 build, where SSE2 is *not* guaranteed.

    This distinction matters: every x86-64 chip has SSE2 because it is part of
    the ABI, so 64-bit builds may use it unconditionally. On 32-bit x86 it is
    optional, and a pre-Pentium-4 processor does not have it.
    """
    return sys.maxsize <= 2**32 and platform.machine().lower() in {
        "i386",
        "i486",
        "i586",
        "i686",
        "x86",
    }


def _child_environment(**extra: str) -> dict[str, str]:
    """The environment for a child process, without pygame's greeting."""
    return dict(os.environ, PYGAME_HIDE_SUPPORT_PROMPT="1", **extra)


def _pygame_version() -> str:
    """Ask a *child* process which pygame is installed.

    Importing pygame here would be fatal: if the installed build uses an
    instruction this CPU does not have, the import takes the whole process
    down - and this process is the one writing the report.
    """
    code = (
        "import pygame;"
        "print(pygame.version.ver, '.'.join(map(str, pygame.version.SDL)))"
    )
    try:
        done = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            env=_child_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"could not be asked: {exc}"
    if done.returncode != 0:
        return f"cannot be imported - {explain_status(done.returncode)}"
    # pygame greets stdout on import, so only the last line is ours.
    spoken = [line for line in done.stdout.splitlines() if line.strip()]
    if not spoken:
        return "imported, but would not say which version"
    version, _, sdl = spoken[-1].strip().partition(" ")
    return f"{version} (SDL {sdl})"


def describe_machine() -> list[str]:
    """The lines of the report header: what this machine actually is."""
    lines = [
        f"CPU            {cpu_name()}",
        f"Architecture   {platform.machine()} ({64 if sys.maxsize > 2**32 else 32}-bit Python)",
        f"System         {platform.platform()}",
        f"Python         {platform.python_version()} ({platform.python_implementation()})",
        f"               {sys.executable}",
        f"Build          {platform.python_compiler()}",
    ]

    features = cpu_features()
    if features:
        have = [name for name, yes in features.items() if yes]
        missing = [name for name, yes in features.items() if not yes]
        lines.append(f"CPU supports   {', '.join(have) or 'nothing we asked about'}")
        lines.append(f"CPU lacks      {', '.join(missing) or 'nothing we asked about'}")
        if is_32bit_x86() and not features.get("SSE2", True):
            lines.append(
                "               ^ a 32-bit x86 CPU without SSE2. Prebuilt wheels are "
                "rarely tested this far back; this alone can explain an illegal "
                "instruction."
            )
    else:
        lines.append("CPU supports   (this platform will not say)")

    lines.append(f"pygame-ce      {_pygame_version()}")

    for variable in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "SDL_RENDER_DRIVER"):
        if os.environ.get(variable):
            lines.append(f"{variable:<14} {os.environ[variable]}")
    return lines


# -- the probes --------------------------------------------------------------
#
# Each one is a little heavier than the last, so that the first failure points
# at the component to blame. They deliberately exercise the hand-written SIMD
# paths in pygame-ce (blits, fills, transforms), because those are what an old
# CPU would choke on.


def _hidden_window():
    import pygame

    pygame.init()
    return pygame.display.set_mode((64, 48), pygame.HIDDEN)


def _bundled_files(kind: str) -> list[Path]:
    """Real asset files of one kind, ignoring placeholders such as .gitkeep."""
    from bummsschloss import resources

    root = resources.assets_root() / kind
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() != ".txt"
    )


def probe_python() -> None:
    """Python and the rules engine alone - no pygame, no SDL involved."""
    from bummsschloss.match import Match
    from bummsschloss.matchsetup import MatchSetup

    match = Match(setup=MatchSetup.default(2), seed=7)
    match.state_hash()


def probe_import() -> None:
    """Import pygame - loads SDL2 and every extension module."""
    import pygame  # noqa: F401


def probe_init() -> None:
    """pygame.init() - starts up the SDL subsystems."""
    import pygame

    pygame.init()
    pygame.quit()


def probe_display() -> None:
    """Open a window - needs a video driver and, often, a GPU driver."""
    import pygame

    _hidden_window()
    pygame.display.flip()
    pygame.quit()


def probe_blit() -> None:
    """Alpha and blend-mode blits - pygame-ce's AVX2/SSE2 blitters."""
    import pygame

    _hidden_window()
    destination = pygame.Surface((320, 240)).convert()
    source = pygame.Surface((320, 240), pygame.SRCALPHA).convert_alpha()
    source.fill((10, 20, 30, 128))
    destination.blit(source, (0, 0))
    for flag in (
        pygame.BLEND_RGBA_ADD,
        pygame.BLEND_RGBA_SUB,
        pygame.BLEND_RGBA_MULT,
        pygame.BLEND_RGBA_MIN,
        pygame.BLEND_RGBA_MAX,
        pygame.BLEND_RGB_ADD,
        pygame.BLEND_RGB_MULT,
        pygame.BLEND_PREMULTIPLIED,
    ):
        destination.blit(source, (0, 0), special_flags=flag)
    pygame.quit()


def probe_fill() -> None:
    """Blend-mode fills - pygame-ce's AVX2/SSE2 surface fillers."""
    import pygame

    _hidden_window()
    surface = pygame.Surface((320, 240), pygame.SRCALPHA).convert_alpha()
    for flag in (
        0,
        pygame.BLEND_RGBA_ADD,
        pygame.BLEND_RGBA_SUB,
        pygame.BLEND_RGBA_MULT,
        pygame.BLEND_RGBA_MIN,
        pygame.BLEND_RGBA_MAX,
    ):
        surface.fill((40, 50, 60, 70), special_flags=flag)
    pygame.quit()


def probe_transform() -> None:
    """Scaling, greyscale and invert - pygame-ce's AVX2/SSE2 transforms."""
    import pygame

    _hidden_window()
    surface = pygame.Surface((320, 240), pygame.SRCALPHA).convert_alpha()
    surface.fill((90, 120, 150, 200))
    pygame.transform.scale(surface, (640, 480))
    pygame.transform.smoothscale(surface, (160, 120))
    pygame.transform.rotozoom(surface, 25.0, 1.5)
    pygame.transform.grayscale(surface)
    pygame.transform.invert(surface)
    pygame.quit()


def probe_draw() -> None:
    """Draw shapes - the coordinate helpers in pygame's base module.

    Converting Python numbers to C doubles is where pygame-ce's 32-bit x86
    wheels reach for SSE2, and nothing in that module tests for it first.
    """
    import pygame

    _hidden_window()
    surface = pygame.Surface((320, 240), pygame.SRCALPHA).convert_alpha()
    pygame.draw.line(surface, (200, 30, 30), (0.0, 0.0), (319.0, 239.0), 3)
    pygame.draw.rect(surface, (30, 200, 30), pygame.Rect(10, 10, 80, 40), 2)
    pygame.draw.circle(surface, (30, 30, 200), (160.5, 120.5), 37.5)
    pygame.draw.polygon(surface, (200, 200, 30), [(5, 5), (80.5, 9.5), (40, 70)])
    pygame.draw.aaline(surface, (10, 10, 10), (3.5, 4.5), (200.25, 150.75))
    pygame.quit()


def probe_math() -> None:
    """Vector arithmetic and colour conversion - heavy double-precision code."""
    import pygame

    first = pygame.math.Vector2(3.5, -2.25)
    second = pygame.math.Vector3(1.5, 2.5, -3.5)
    first.rotate(37.5)
    first.normalize()
    first.distance_to(pygame.math.Vector2(-9.75, 4.5))
    second.cross(pygame.math.Vector3(0.5, -1.25, 2.0))
    second.reflect(pygame.math.Vector3(0.0, 1.0, 0.0))
    colour = pygame.Color(10, 200, 100, 255)
    colour.hsla = (180.0, 50.0, 50.0, 100.0)
    colour.hsva = (200.0, 40.0, 60.0, 100.0)
    colour.correct_gamma(1.8)


def probe_images() -> None:
    """Encode and decode images - exercises libpng, libjpeg and SDL2_image."""
    import pygame

    _hidden_window()
    picture = pygame.Surface((64, 64), pygame.SRCALPHA).convert_alpha()
    for x in range(64):
        for y in range(0, 64, 8):
            picture.set_at((x, y), (x * 4 % 256, y * 4 % 256, 128, 255))

    # The game draws everything procedurally, so there may be no bundled
    # pictures at all; round-tripping through a file still exercises the codecs.
    with tempfile.TemporaryDirectory(prefix="bummsschloss-img-") as scratch:
        for suffix in (".png", ".bmp", ".jpg", ".tga"):
            path = Path(scratch) / f"probe{suffix}"
            pygame.image.save(picture, str(path))
            pygame.image.load(str(path)).convert_alpha()

    for path in _bundled_files("images"):
        pygame.image.load(path).convert_alpha()
    pygame.quit()


def probe_font() -> None:
    """Render text - exercises SDL2_ttf and FreeType."""
    import pygame

    from bummsschloss import resources

    pygame.init()
    resources.load_font(20).render("Bummsschloss", True, (255, 255, 255))
    pygame.quit()


def probe_mixer() -> None:
    """Start the audio device and build a sound - exercises SDL2_mixer."""
    import array

    import pygame

    pygame.init()
    pygame.mixer.init()
    # A short square wave, so the probe does not need a bundled sound file.
    frequency, _format, channels = pygame.mixer.get_init()
    samples = array.array("h", [(8000 if (i // 40) % 2 else -8000) for i in range(frequency // 10)])
    if channels > 1:
        samples = array.array("h", [value for value in samples for _ in range(channels)])
    pygame.mixer.Sound(buffer=samples.tobytes())

    for path in _bundled_files("sounds"):
        pygame.mixer.Sound(path)
    pygame.mixer.quit()
    pygame.quit()


def probe_game() -> None:
    """Build the real window and draw one frame of the real menu."""
    from bummsschloss.app import App
    from bummsschloss.matchsetup import MatchSetup
    from bummsschloss.scenes.setup import SetupScene

    app = App(headless=True)
    app.push_scene(SetupScene(app, MatchSetup.default(2, seed=1)))
    app.running = True
    app.step(1.0 / 60.0)
    app.quit()


#: Ordered, cheapest first. The first failure is the one worth reporting.
PROBES: dict[str, Callable[[], None]] = {
    "python": probe_python,
    "import": probe_import,
    "init": probe_init,
    "math": probe_math,
    "display": probe_display,
    "blit": probe_blit,
    "fill": probe_fill,
    "draw": probe_draw,
    "transform": probe_transform,
    "images": probe_images,
    "font": probe_font,
    "mixer": probe_mixer,
    "game": probe_game,
}


# -- running them ------------------------------------------------------------


def _child_command(name: str) -> list[str]:
    """How to re-invoke ourselves for a single probe, frozen or not."""
    if getattr(sys, "frozen", False):  # PyInstaller build: the exe is the entry point
        return [sys.executable, "--diagnose", "--probe", name]
    return [sys.executable, "-m", "bummsschloss", "--diagnose", "--probe", name]


def explain_status(code: int) -> str:
    """Turn a child exit status into something a human can act on."""
    if sys.platform == "win32":
        status = code & 0xFFFFFFFF
        known = _WINDOWS_STATUS.get(status)
        if known:
            return known
        if status >= 0xC0000000:
            return f"fatal Windows exception {status:#010x} - the process was killed"
        return f"exit status {code}"
    if code in _SIGNALS:
        return _SIGNALS[code]
    if code < 0:
        return f"killed by signal {-code}"
    return f"exit status {code}"


def _import_trace() -> str:
    """The import-by-import trail of ``import pygame``.

    ``-X importtime`` reports every module *as it finishes* loading, so when
    the process is killed part-way the trail still names the last extension
    that loaded cleanly - and the culprit is the one that would have come
    next. That is as close to a stack trace as a dead process gets.
    """
    try:
        done = subprocess.run(
            [sys.executable, "-X", "importtime", "-c", "import pygame"],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            env=_child_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    trail = [line for line in done.stderr.splitlines() if "|" in line]
    if not trail:
        return ""
    return "\n".join(["last modules that loaded before it died:", *trail[-12:]])


def run_probe(name: str) -> int:
    """Child mode: run one probe, leaving any exception where the parent finds it."""
    probe = PROBES.get(name)
    if probe is None:
        _record_failure(f"unknown probe {name!r}; known: {', '.join(PROBES)}")
        return 2
    try:
        probe()
    except BaseException as exc:  # noqa: BLE001 - a diagnostic reports anything
        import traceback

        _record_failure(f"{traceback.format_exc()}\nFAILED {type(exc).__name__}: {exc}")
        return 1
    return 0


def _record_failure(text: str) -> None:
    """Hand a failure back to the parent.

    A windowed (``console=False``) PyInstaller build has no stderr to inherit,
    so the pipe the parent captures would stay empty. The parent therefore
    nominates a file through the environment and we write there as well.
    """
    print(text, file=sys.stderr)
    path = os.environ.get(_PROBE_LOG)
    if not path:
        return
    try:
        Path(path).write_text(text, encoding="utf-8", errors="replace")
    except OSError:
        pass


def _probe_results() -> Iterator[tuple[str, str, str, str]]:
    """Yield ``(name, summary, outcome, details)`` for every probe, in order.

    ``outcome`` is the empty string when the probe passed.
    """
    with tempfile.TemporaryDirectory(prefix="bummsschloss-diag-") as scratch:
        log = Path(scratch) / "probe.txt"
        for name, probe in PROBES.items():
            summary = (probe.__doc__ or "").splitlines()[0]
            environment = _child_environment(**{_PROBE_LOG: str(log)})
            log.unlink(missing_ok=True)
            try:
                done = subprocess.run(
                    _child_command(name),
                    capture_output=True,
                    text=True,
                    timeout=PROBE_TIMEOUT,
                    env=environment,
                )
            except subprocess.TimeoutExpired:
                yield name, summary, f"HUNG (no answer within {PROBE_TIMEOUT:.0f}s)", ""
                continue
            except OSError as exc:
                yield name, summary, f"could not even be started ({exc})", ""
                continue

            if done.returncode == 0:
                yield name, summary, "", ""
                continue

            details = ""
            if log.exists():
                details = log.read_text(encoding="utf-8", errors="replace").strip()
            if not details:
                details = (done.stderr or "").strip()
            if name == "import":
                # A hard crash inside `import pygame` leaves no traceback, so
                # work out how far the import actually got.
                trace = _import_trace()
                details = f"{details}\n\n{trace}".strip() if trace else details
            yield name, summary, explain_status(done.returncode), details


def _report_path() -> Path:
    """Where to leave a copy of the report, for a build with no console."""
    for candidate in (Path.home(), Path(tempfile.gettempdir())):
        try:
            if candidate.is_dir():
                return candidate / "bummsschloss-diagnose.txt"
        except OSError:
            continue
    return Path("bummsschloss-diagnose.txt")


def run_report() -> int:
    """Parent mode: describe the machine, then run every probe in a child."""
    lines: list[str] = []

    def say(text: str = "") -> None:
        lines.append(text)
        print(text)

    say(f"{config.GAME_TITLE} {__version__} - machine check")
    say()
    for line in describe_machine():
        say(line)
    say()

    first_failure: tuple[str, str, str] | None = None
    for name, summary, outcome, details in _probe_results():
        say(f"{name:<10} {summary:<62} {outcome or 'ok'}")
        if outcome and first_failure is None:
            first_failure = (name, outcome, details)

    say()
    if first_failure is None:
        say("Everything works on this machine. If the game still misbehaves, the")
        say("instruction set is not the problem - run it from a terminal and send")
        say("whatever it prints.")
    else:
        name, reason, details = first_failure
        say(f"First thing that broke: {name} - {reason}")
        if details:
            say()
            say("What the child process said:")
            for line in details.splitlines():
                say(f"    {line}")
        say()
        say("Send this report along; it names the component to blame.")

    report = _report_path()
    try:
        report.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="replace")
        print(f"\nA copy of this report is in {report}")
    except OSError as exc:
        print(f"\n(could not save a copy of this report: {exc})")
    return 1 if first_failure else 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["--probe"] and len(arguments) > 1:
        return run_probe(arguments[1])
    return run_report()


if __name__ == "__main__":
    sys.exit(main())
