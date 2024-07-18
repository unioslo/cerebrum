# -*- coding: utf-8 -*-
"""
Test fixtures for :mod:`Cerebrum.modules.pwcheck` fixtures
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import gettext

import pytest

from Cerebrum.modules.pwcheck import checker


#
# translation tests
#
# This sanity checks our basic test setup (conftest)
#


test_message = "Must not contain repeated sequences of characters"


@pytest.mark.parametrize(
    "lang, text",
    [
        ("en", test_message),
        ("nb", "Må ikke inneholde gjentagende sekvenser"),
        ("dk", test_message),  # should use "en"-fallback
    ],
)
def test_translate(cereconf, lang, text):
    tr = gettext.translation(checker.gettext_domain,
                             localedir=checker.locale_dir,
                             languages=[lang, "en"])
    msg = tr.gettext(test_message)
    assert msg == text
