# -*- coding: utf-8 -*-

# Copyright 2020 University of Oslo, Norway
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

"""Unicode string manipulation routines."""

import six
import unicodedata


# we currently  support only control sequence codes,
# but this has been written so it would be easy to expand
# to reserved (0x01), PUA (0x04), and surrogate (0x05) code points.
control = 0x03
_categories = {control: "Cc"}


def replace_category(s, category, new, maxreplace=-1, exclude=None):
    """
    Return a copy of string `s` with occurrences associated with
    the Unicode code point label `category` replaced by `new`.

    If the optional argument `maxreplace` is given, the first
    `maxreplace` occurrences are replaced.  If `maxreplace` < 0,
    there is no limit on the number of code points replaced.

    Individual code points whose Unicode code point label matches
    `category` and are listed in `exclude` will not be replaced.
    """
    if not isinstance(s, six.text_type):
        raise TypeError
    if category not in _categories:
        raise ValueError("Invalid code point label: {!r}".format(category))
    if maxreplace == 0:
        return s
    exclude = set(list(exclude)) if exclude is not None else set()
    rv = []
    for old in s:
        if (
            maxreplace != 0
            and unicodedata.category(old) == _categories[category]
            and old not in exclude
        ):
            if len(new) > 0:
                rv.append(new)
            maxreplace -= 1
        else:
            rv.append(old)
    return "".join(rv)


def strip_category(s, category, maxstrip=-1, exclude=None):
    """
    Return a copy of string `s` with occurrences associated with
    the Unicode code point label `category` left omitted.

    If the optional argument `maxstrip` is given, the first `maxstrip`
    occurrences are omitted.  If `maxstrip` < 0, there is no limit
    on the number of code points omitted.

    Individual code points whose Unicode code point label matches
    `category` and are listed in `exclude` will not be omitted.
    """
    return replace_category(s, category, "",  maxreplace=maxstrip, exclude=exclude)


def strip_control_characters(s, **kwargs):
    """
    Strips non-printable control sequence characters.
    If `maxstrip` < 0, there is no limit on the number of characters stripped.
    Individual control characters listed in `exclude` will not be omitted.
    """
    return strip_category(s, control, **kwargs)
