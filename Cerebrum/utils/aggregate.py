# -*- coding: utf-8 -*-
#
# Copyright 2020-2021 University of Oslo, Norway
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
Utilities for grouping items in iterables.
"""
import operator


def unique(seq, key=None):
    """ Strip duplicates from a sequence.

    :type seq: iterable
    :param seq: a sequence of hashable items

    :type key: callable
    :param key:
        Function to extract a comparison key for each item in the sequence.
        The default (``None``) compares items directly.


    :rtype: generator
    :return:
        a sequence of unique items

        The generator yields items in the same order as the input sequence, but
        only yields the first encounter of each item.

    >>> a = ['foo', 1, 'bar', 'foo', 2, 1]
    >>> list(unique(a))
    ['foo', 1, 'bar', 2]
    """
    get_key = key or (lambda x: x)
    seen = set()
    for item in seq:
        k = get_key(item)
        if k in seen:
            continue
        seen.add(k)
        yield item


def _dict_with_collection(iterable, ctype, add):
    d = {}
    for key, value in iterable:
        if key not in d:
            d[key] = ctype()
        add(d[key], value)
    return d


def dict_collect_sets(seq):
    """ Collect key, value pairs into a dict with sets.

    >>> dict_collect_sets([('foo', 1), ('foo', 2), ('bar', 2)])
    {'foo': set([1, 2]), 'bar': set([2])}

    :type seq: iterable
    :param seq: a sequence of (key, value) pairs

    :rtype: dict
    :returns: A dict with sets

    """
    return _dict_with_collection(seq, set, set.add)


def dict_collect_lists(seq):
    """ Collect key, value pairs into a dict with lists.

    >>> dict_collect_lists([('foo', 1), ('foo', 2), ('bar', 2)])
    {'foo': [1, 2], 'bar': [2]}

    :type seq: iterable
    :param seq: a sequence of (key, value) pairs

    :rtype: dict
    :returns: A dict with lists
    """
    return _dict_with_collection(seq, list, list.append)


def dict_collect_first(seq):
    """ Collect key, value pairs into a dict, keeping the first occurance.

    When initializing a dict with a list of tuples, any duplicate key will
    replace the previous occurance:
    >>> dict([('foo', 1), ('foo', 3), ('foo', 2)])
    {'foo': 2}

    This function keeps the first occurance of a key, and ignores any latter
    duplicates:
    >>> dict_collect_first([('foo', 1), ('foo', 3), ('foo', 3)])
    {'foo': 1}

    :type seq: iterable
    :param seq: a sequence of (key, value) pairs

    :rtype: dict
    :returns: A dict with lists
    """
    return dict(unique(seq, key=operator.itemgetter(0)))
