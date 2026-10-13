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
        "Dud": "Blindgänger",
        "Cannonball": "Kanonenkugel",
        "Mortar shell": "Mörsergranate",
        "Balloon bomb": "Ballonbombe",
        "Mole": "Maulwurf",
        "Cluster barrel": "Streufass",
        "Earthquake": "Erdbeben",
        "Laser": "Laser",
        "Fat Bertha": "Dicke Berta",
        "Bomblet": "Streuling",
        # -- weapon descriptions ----------------------------------------
        "Free, and about as dangerous as a thrown bread roll.":
            "Kostenlos und etwa so gefährlich wie ein geworfenes Brötchen.",
        "Cheap, heavy and barely troubled by the wind.":
            "Billig, schwer und kaum vom Wind zu beirren.",
        "Falls steeply - good for targets tucked behind a hill.":
            "Fällt steil - gut für Ziele hinter einem Hügel.",
        "Never falls. Rides the wind until it bumps into something.":
            "Fällt nie. Reitet auf dem Wind, bis es irgendwo anstößt.",
        "Burrows into the hill and back out. Spares the castle that fired it.":
            "Gräbt sich in den Hügel und wieder heraus. Verschont die eigene Burg.",
        "Bursts at the top of its arc into five little bomblets.":
            "Platzt am Scheitel der Flugbahn in fünf Streulinge.",
        "Shakes the whole world. Every castle takes the same - yours too.":
            "Erschüttert die ganze Welt. Jede Burg nimmt gleich viel - auch die eigene.",
        "Flies dead straight: no gravity, no wind, no excuses.":
            "Fliegt schnurgerade: keine Schwerkraft, kein Wind, keine Ausreden.",
        "A huge crater. Expensive, slow, and worth every taler.":
            "Ein gewaltiger Krater. Teuer, träge und jeden Taler wert.",
        # -- arsenal readout --------------------------------------------
        "Arsenal": "Arsenal",
        "reach": "Reichweite",
        "gravity": "Schwerkraft",
        "everyone": "alle",
        "W to close": "W zum Schließen",
        "show the arsenal": "Arsenal zeigen",
        "H for help, W for the arsenal": "H für Hilfe, W für das Arsenal",
        # -- match events -----------------------------------------------
        "Direct hit!": "Volltreffer!",
        "The ground gives way!": "Der Boden gibt nach!",
        "Ouch - that was your own castle!": "Autsch - das war die eigene Burg!",
        "The cluster barrel bursts open!": "Das Streufass platzt auf!",
        "The mole goes off underground!": "Der Maulwurf geht unter Tage hoch!",
        "The earth shakes - nobody is spared!":
            "Die Erde bebt - niemand bleibt verschont!",
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
        # -- network play -------------------------------------------------
        "game type": "Spielart",
        "hotseat": "Hotseat",
        "network": "Netzwerk",
        "role": "Rolle",
        "host": "Gastgeber",
        "join": "beitreten",
        "room code": "Raumcode",
        "your name": "dein Name",
        "type to rename": "tippen zum Umbenennen",
        "Open the room": "Raum eröffnen",
        "Join the room": "Raum betreten",
        "Everybody at one keyboard, passing it around.":
            "Alle an einer Tastatur, die herumgereicht wird.",
        "Everyone plays at their own machine, over the internet.":
            "Jeder spielt am eigenen Rechner, über das Internet.",
        "You open the room and start the match.":
            "Du eröffnest den Raum und startest die Partie.",
        "Enter the code your host read out to you.":
            "Gib den Code ein, den dir der Gastgeber vorgelesen hat.",
        "Five characters. Arrow keys roll a fresh code.":
            "Fünf Zeichen. Pfeiltasten würfeln einen neuen Code.",
        "No port forwarding needed - everybody dials out.":
            "Keine Portfreigabe nötig - alle wählen sich hinaus.",
        # -- waiting room ---------------------------------------------------
        "Waiting room": "Warteraum",
        "Read this code out to the others.": "Lies diesen Code den anderen vor.",
        "you": "du",
        "Connecting to the broker...": "Verbinde mit dem Vermittler...",
        "Nobody here yet.": "Noch niemand da.",
        "No connection: {reason}": "Keine Verbindung: {reason}",
        "Enter starts the match": "Eingabe startet die Partie",
        "At least one more player is needed.":
            "Es fehlt noch mindestens ein Mitspieler.",
        "Waiting for the host to start...":
            "Warte auf den Gastgeber...",
        "Esc to leave the room": "Esc verlässt den Raum",
        "lost the connection to the broker":
            "Verbindung zum Vermittler verloren",
        "Your move.": "Du bist dran.",
        "Waiting for {player}...": "Warte auf {player}...",
        "resynced {count}x": "{count}x neu abgeglichen",
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
        "message broker for network games (default: %(default)s)":
            "Vermittler für Netzwerkspiele (Standard: %(default)s)",
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
