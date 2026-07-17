# -*- coding: utf-8 -*-
#
# Copyright 2020-2024 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.
"""
Various unicode text utils.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import io
import unicodedata

import six


# We currently  support only control sequence codes, but this has been written
# so it would be easy to expand to reserved (Cn), private-use (Co), and
# surrogate (Cs) code points.
CATEGORY_CONTROL = "Cc"

# Internal module use, could also just be a set of supported category keys
_categories = {CATEGORY_CONTROL: "Control"}


def _replace_category(s, category, new, maxreplace=-1, exclude=None):
    """
    Return a copy of string *s* with characters from the unicode category key
    *category* replaced by *new*.
    """
    if not isinstance(s, six.text_type):
        raise TypeError
    if category not in _categories:
        raise ValueError("Invalid category key: " + repr(category))
    if maxreplace == 0:
        return s
    exclude = set(exclude) if exclude is not None else set()
    buffer = io.StringIO()
    for old in s:
        if (maxreplace != 0
                and old not in exclude
                and unicodedata.category(old) == category):
            if new:
                buffer.write(new)
            maxreplace -= 1
        else:
            buffer.write(old)
    return buffer.getvalue()


def strip_category(s, category, maxstrip=-1, exclude=None):
    """
    Return a copy of string *s* with characters from the unicode category
    *category* omitted.

    :type s: str

    :param str category:
        A unicode category key to replace or strip.

        Only "Cc" (Control characters) is currently supported.

    :param int maxstrip:
        Limit number of characters that are replaced.

        If ``maxreplace < 0`` (the default), all occurrences are removed.
        If `maxreplace>= 0`, then only the first *maxstrip* occurrences are
        removed.

    :param set exclude:
        Individual characters listed in *exclude* will not be replaced or
        stripped.
    """
    return _replace_category(
        s,
        category=category,
        new="",
        maxreplace=maxstrip,
        exclude=exclude,
    )


def strip_control_characters(s, **kwargs):
    """
    Strips non-printable control sequence characters.

    :param int maxstrip: see :func:`.strip_category`
    :param set exclude: see :func:`.replace_category`
    """
    return strip_category(s, CATEGORY_CONTROL, **kwargs)
