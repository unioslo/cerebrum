# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.password_notifier.notifier` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import locale

import pytest

from Cerebrum.modules.password_notifier import notifier


#
# formatting tests
#


def test_locale_context():
    old_locale = locale.getlocale(locale.LC_CTYPE)
    # Change to a different locale (don't really care which, as long as it's
    # not the default).
    new_locale = (
        "nb_NO" if old_locale[0] == "en_US" else "en_US",
        "ISO8859-1" if old_locale[1] == "UTF-8" else "UTF-8",
    )
    # sanity check our new locale
    assert old_locale != new_locale

    with notifier.locale_context(locale.LC_CTYPE, new_locale):
        # in context, should use our locale
        assert locale.getlocale(locale.LC_CTYPE) == new_locale

    # Back out of context - should reset
    assert locale.getlocale(locale.LC_CTYPE) != old_locale


# a wednesday
DATE = datetime.date(2025, 6, 25)


def test_human_date():
    assert notifier.human_date(DATE) == "2025-06-25"


@pytest.mark.parametrize(
    "date, lang, result",
    [
        pytest.param(DATE, "en_US", "Wednesday, 25 June 2025", id="en_US"),
        pytest.param(DATE, "nb_NO", "onsdag 25. juni 2025", id="nb_NO"),
    ],
)
def test_local_date(date, lang, result):
    assert notifier.local_date(date, lang) == result
