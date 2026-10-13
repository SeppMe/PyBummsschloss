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
        "angle": "Winkel",
        "wind": "Wind",
        "turn": "Runde",
        "money": "Taler",
        "armour": "Panzerung",
        "damage": "Schaden",
        "shots": "Schüsse",
        "Player 1": "Spieler 1",
        "Player 2": "Spieler 2",
        "Player 3": "Spieler 3",
        "Player 4": "Spieler 4",
        "defeated": "besiegt",
        "H for help": "H für Hilfe",
        "Not enough money for this weapon.": "Nicht genug Taler für diese Waffe.",
        # -- weapons ----------------------------------------------------
        "Cannonball": "Kanonenkugel",
        "Mortar shell": "Mörsergranate",
        "Balloon bomb": "Ballonbombe",
        "Cluster barrel": "Streufass",
        "Fat Bertha": "Dicke Berta",
        "Molehill": "Maulwurfshügel",
        "Bomblet": "Streuling",
        # -- match events -----------------------------------------------
        "Direct hit!": "Volltreffer!",
        "The ground gives way!": "Der Boden gibt nach!",
        "Ouch - that was your own castle!": "Autsch - das war die eigene Burg!",
        "The cluster barrel bursts open!": "Das Streufass platzt auf!",
        "The shot was lost in the clouds.": "Der Schuss verlor sich in den Wolken.",
        "The shot vanished into the abyss.": "Der Schuss verschwand im Abgrund.",
        "A castle falls to rubble!": "Eine Burg sinkt in Schutt und Asche!",
        "Victory!": "Sieg!",
        "Everyone lost.": "Alle haben verloren.",
        # -- summary screen ---------------------------------------------
        "{player} wins!": "{player} gewinnt!",
        "{turns} turns": "{turns} Runden",
        "Awards": "Auszeichnungen",
        "Nobody distinguished themselves.": "Niemand hat sich hervorgetan.",
        "Enter for a rematch   -   M for the menu   -   Esc to quit":
            "Eingabe für Revanche   -   M für das Menü   -   Esc zum Beenden",
        "shots fired": "Schüsse",
        "hits": "Treffer",
        "hit rate": "Trefferquote",
        "damage dealt": "Schaden ausgeteilt",
        "damage per shot": "Schaden pro Schuss",
        "best single shot": "bester Einzelschuss",
        "collapse damage": "Schaden durch Einsturz",
        "damage to own castle": "Schaden an eigener Burg",
        "castles destroyed": "zerstörte Burgen",
        "money spent": "ausgegebene Taler",
        "earth moved": "bewegte Erde",
        # -- awards -----------------------------------------------------
        "Master Gunner": "Meisterschütze",
        "greatest total damage": "größter Gesamtschaden",
        "Lucky Shot": "Glückstreffer",
        "greatest damage from a single shot": "größter Schaden aus einem Schuss",
        "Model of Efficiency": "Ausbund an Effizienz",
        "greatest average damage per shot": "größter Durchschnittsschaden pro Schuss",
        "Castle Breaker": "Burgenbrecher",
        "most castles destroyed": "meiste zerstörte Burgen",
        "Eagle Eye": "Adlerauge",
        "best hit rate": "beste Trefferquote",
        "Master Sapper": "Meistermineur",
        "most damage from collapsing castles": "größter Schaden durch Einstürze",
        "Landscape Gardener": "Landschaftsgärtner",
        "most earth moved": "meiste bewegte Erde",
        "Cloud Hunter": "Wolkenjäger",
        "most shots that hit nothing": "meiste Schüsse ins Leere",
        "Own Goal": "Eigentor",
        "most damage to one's own castle": "größter Schaden an der eigenen Burg",
        "Thrifty Quartermaster": "Sparsamer Quartiermeister",
        "least money spent per point of damage":
            "wenigste Taler je Schadenspunkt",
        "{:.0f} damage": "{:.0f} Schaden",
        "{:.1f} per shot": "{:.1f} pro Schuss",
        "{:.0f} shovelfuls": "{:.0f} Schaufeln",
        "{:.0f} shots": "{:.0f} Schüsse",
        "{:.0f} coins per point": "{:.0f} Taler je Punkt",
        # -- setup menu --------------------------------------------------
        "Set up the match": "Partie einrichten",
        "players": "Spieler",
        "seat {number}": "Platz {number}",
        "starting money": "Startkapital",
        "income per turn": "Einkommen pro Zug",
        "economy": "Wirtschaft",
        "Start the match": "Partie starten",
        "(unnamed)": "(namenlos)",
        "type to rename, arrows for colour":
            "tippen zum Umbenennen, Pfeile für die Farbe",
        "Everything ready? Then let the cannons speak.":
            "Alles bereit? Dann sollen die Kanonen sprechen.",
        "arrow keys to choose   -   Enter to start   -   Esc to quit":
            "Pfeiltasten zum Wählen   -   Eingabe zum Starten   -   Esc zum Beenden",
        "flat": "fest",
        "rising": "steigend",
        "catch-up": "Aufholjagd",
        "Everybody gets the same amount every turn.":
            "Jeder erhält in jedem Zug denselben Betrag.",
        "The income grows with every round, so later weapons get affordable.":
            "Das Einkommen wächst mit jeder Runde, "
            "so werden teure Waffen später erschwinglich.",
        "The worse your castle looks, the more you are paid.":
            "Je übler die eigene Burg aussieht, desto mehr Taler gibt es.",
        # -- colours ------------------------------------------------------
        "red": "Rot",
        "blue": "Blau",
        "green": "Grün",
        "yellow": "Gelb",
        "purple": "Violett",
        "orange": "Orange",
        # -- controls ---------------------------------------------------
        "mouse": "Maus",
        "click/space": "Klick/Leer",
        "wheel": "Mausrad",
        "left/right": "Links/Rechts",
        "up/down, wheel": "Hoch/Runter, Mausrad",
        "aim": "zielen",
        "fire": "feuern",
        "fine-tune angle": "Winkel feinjustieren",
        "choose weapon": "Waffe wählen",
        "new landscape": "neue Landschaft",
        "back to the menu": "zurück zum Menü",
        "scatter balls": "Kugeln streuen",
        "clear": "leeren",
        "fullscreen": "Vollbild",
        "hide this help": "Hilfe ausblenden",
        "quit": "beenden",
        # -- command line ------------------------------------------------
        "which scene to start in (default: %(default)s)":
            "Szene, in der gestartet wird (Standard: %(default)s)",
        "seed for the random landscape, for reproducible matches":
            "Startwert für die Zufallslandschaft, für wiederholbare Partien",
        "number of players to preselect in the menu (default: %(default)s)":
            "Zahl der im Menü vorgewählten Spieler (Standard: %(default)s)",
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
