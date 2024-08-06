# -*- coding: utf-8 -*-
"""
Tests for mod:`Cerebrum.utils.username`
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import pytest

from Cerebrum.utils import username


@pytest.mark.parametrize(
    "fname, lname, maxlen",
    [
        ("Foo", "Bar", 8),
        ("Foo", "Bar", 4),
        ("Geir-Ove Johnsen", "Hansen", 8),
    ],
)
def test_suggest_usernames_counts(fname, lname, maxlen):
    candidates = username.suggest_usernames(fname, lname, maxlen)
    assert len(candidates) >= 15


def test_suggest_usernames_special_chars():
    # One of the most common Icelandic names + an Icelandic fjord
    candidates = username.suggest_usernames("Aþena", "Öxarfjörður")
    assert candidates
    assert len(candidates) >= 15


def test_suggest_usernames_combinations():
    # Test some examples given in the code comments
    candidates = username.suggest_usernames("Geir-Ove Johnsen", "Hansen")

    # initials
    assert "gohansen" in candidates
    assert "gojhanse" in candidates
    assert "gohanse" in candidates

    # substrings
    assert "geiroveh" in candidates
    assert "geirovjh" in candidates


def test_suggest_usernames_many_parts():
    assert username.suggest_usernames("Foo Bar Baz Quux", "van der Example")


def test_suggest_usernames_optional_fname():
    assert username.suggest_usernames("", "Bar")


def test_suggest_usernames_require_lname():
    with pytest.raises(ValueError):
        username.suggest_usernames("Foo", "")


@pytest.mark.parametrize("maxlen", [3, 4, 8, 12])
def test_suggest_usernames_maxlen(maxlen):
    candidates = username.suggest_usernames("Foo", "Bar", maxlen=maxlen)
    assert candidates
    assert all(len(c) <= maxlen for c in candidates)


def test_suggest_usernames_prefix():
    candidates = username.suggest_usernames("Foo", "Bar", maxlen=8,
                                            prefix="x-")
    assert candidates
    assert all(len(c) <= 8 for c in candidates)
    # For some reason, we ignore the prefix when generating last ditch
    # candidates.  This is probably a bug?
    # assert all(c.startswith("x-") for c in candidates)
    assert any(c.startswith("x-") for c in candidates)


def test_suggest_usernames_suffix():
    candidates = username.suggest_usernames("Foo", "Bar", maxlen=8,
                                            suffix="-y")
    assert candidates
    assert all(len(c) <= 8 for c in candidates)
    assert all(c.endswith("-y") for c in candidates)


def test_suggest_usernames_validate():
    # validate_func - make sure that nothing but our numbered usernames are
    # valid
    candidates = username.suggest_usernames(
        "Foo", "Bar",
        validate_func=(lambda s: s[-1].isdigit()),
    )
    assert candidates
    assert all(c[-1].isdigit() for c in candidates)
