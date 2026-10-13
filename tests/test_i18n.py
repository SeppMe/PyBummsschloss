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
