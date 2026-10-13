"""Tests for the translation layer."""

from __future__ import annotations

import pytest

from bummsschloss import i18n


@pytest.fixture(autouse=True)
def restore_language():
    previous = i18n.get_language()
    yield
    i18n.set_language(previous)


def test_german_is_the_default():
    assert i18n.DEFAULT_LANGUAGE == "de"
    assert i18n.get_language() == "de"


def test_known_string_is_translated():
    i18n.set_language("de")
    assert i18n.gettext("fire") == "feuern"


def test_english_returns_the_source_string():
    i18n.set_language("en")
    assert i18n.gettext("fire") == "fire"


def test_unknown_string_falls_back_to_the_source():
    i18n.set_language("de")
    assert i18n.gettext("no such message") == "no such message"


def test_unknown_language_falls_back_to_the_default():
    assert i18n.set_language("klingon") == i18n.DEFAULT_LANGUAGE
    assert i18n.set_language(None) == i18n.DEFAULT_LANGUAGE


def test_detect_language_honours_the_environment(monkeypatch):
    monkeypatch.setenv("BUMMSSCHLOSS_LANG", "en_GB")
    assert i18n.detect_language() == "en"


def test_every_catalogue_key_exists_in_every_language():
    keys = {key for catalogue in i18n.CATALOGUES.values() for key in catalogue}
    for language in i18n.AVAILABLE_LANGUAGES:
        assert language in i18n.CATALOGUES
    missing = keys - set(i18n.CATALOGUES["de"])
    assert not missing, f"untranslated in German: {sorted(missing)}"


def test_all_award_strings_are_translated():
    """Award titles, descriptions and their unit suffixes must be German."""
    import re

    from bummsschloss.stats import AWARDS

    german = i18n.CATALOGUES["de"]
    missing = []
    for award in AWARDS:
        for text in (award.title, award.description, award.fmt):
            words = re.sub(r"\{[^}]*\}", "", text)
            if not any(char.isalpha() for char in words):
                continue  # a bare number format carries no words to translate
            if text not in german:
                missing.append(text)
    assert not missing, f"untranslated award strings: {missing}"


def test_all_weapon_names_are_translated():
    from bummsschloss.weapons import ARSENAL, HIDDEN_WEAPONS

    german = i18n.CATALOGUES["de"]
    missing = [w.name for w in ARSENAL + HIDDEN_WEAPONS if w.name not in german]
    assert not missing, f"untranslated weapons: {missing}"


def test_every_selectable_weapon_explains_itself_in_german():
    from bummsschloss.weapons import ARSENAL

    german = i18n.CATALOGUES["de"]
    missing = [w.key for w in ARSENAL if not w.description or w.description not in german]
    assert not missing, f"weapons without a German description: {missing}"


def test_all_summary_table_labels_are_translated():
    from bummsschloss.scenes.summary import STAT_ROWS

    german = i18n.CATALOGUES["de"]
    missing = [label for label, _template, _better in STAT_ROWS if label not in german]
    assert not missing, f"untranslated table labels: {missing}"


def test_all_income_models_are_translated():
    from bummsschloss.matchsetup import IncomeModel

    german = i18n.CATALOGUES["de"]
    missing = [
        text
        for model in IncomeModel
        for text in (model.label, model.description)
        if text not in german
    ]
    assert not missing, f"untranslated economy strings: {missing}"


def test_all_palette_colour_names_are_translated():
    from bummsschloss import config

    german = i18n.CATALOGUES["de"]
    missing = [name for name, _rgb in config.PLAYER_PALETTE if name not in german]
    assert not missing, f"untranslated colours: {missing}"


def test_all_default_seat_names_are_translated():
    from bummsschloss.matchsetup import DEFAULT_NAMES

    german = i18n.CATALOGUES["de"]
    missing = [name for name in DEFAULT_NAMES if name not in german]
    assert not missing, f"untranslated seat names: {missing}"
