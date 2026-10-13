"""Lightweight translation layer.

All user-visible strings go through :func:`_`. Source strings are written in
English and act as the lookup key; the catalogues below provide translations.
German is the default language.

A plain dict keeps the build simple (no .po/.mo compilation step), while the
``_()`` call signature matches gettext, so switching to gettext later would not
touch any call site.
"""

from __future__ import annotations

import locale
import os

DEFAULT_LANGUAGE = "de"

#: Languages the game ships with, in menu order.
AVAILABLE_LANGUAGES: tuple[str, ...] = ("de", "en")

#: ``{language: {source string: translation}}``. English needs no entries -
#: the source strings are already English.
CATALOGUES: dict[str, dict[str, str]] = {
    "en": {},
    "de": {
        # -- window / branding ------------------------------------------
        # The game title itself is a proper name and stays untranslated.
        "engine demo": "Engine-Demo",
        # -- HUD --------------------------------------------------------
        "power": "Kraft",
        "balls": "Kugeln",
        "fps": "Bilder/s",
        # -- controls ---------------------------------------------------
        "mouse": "Maus",
        "click/space": "Klick/Leer",
        "wheel": "Mausrad",
        "aim": "zielen",
        "fire": "feuern",
        "scatter balls": "Kugeln streuen",
        "clear": "leeren",
        "fullscreen": "Vollbild",
        "hide this help": "Hilfe ausblenden",
        "quit": "beenden",
        # -- command line ------------------------------------------------
        "which scene to start in (default: %(default)s)":
            "Szene, in der gestartet wird (Standard: %(default)s)",
        "language of the user interface (default: %(default)s)":
            "Sprache der Benutzeroberfläche (Standard: %(default)s)",
    },
}

_current_language = DEFAULT_LANGUAGE


def detect_language() -> str:
    """Pick a language from ``BUMMSSCHLOSS_LANG`` or the system locale."""
    candidates = [os.environ.get("BUMMSSCHLOSS_LANG", "")]
    try:
        system_locale, _encoding = locale.getlocale()
    except ValueError:  # pragma: no cover - malformed locale setting
        system_locale = None
    candidates.append(system_locale or "")

    for candidate in candidates:
        code = candidate.replace("-", "_").split("_")[0].lower()
        if code in AVAILABLE_LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def set_language(language: str | None) -> str:
    """Set the active language; unknown values fall back to the default."""
    global _current_language
    _current_language = language if language in AVAILABLE_LANGUAGES else DEFAULT_LANGUAGE
    return _current_language


def get_language() -> str:
    """Return the currently active language code."""
    return _current_language


def gettext(message: str) -> str:
    """Translate ``message`` into the active language."""
    return CATALOGUES.get(_current_language, {}).get(message, message)


#: Conventional short alias used at call sites.
_ = gettext
