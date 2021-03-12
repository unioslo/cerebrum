# -*- coding: utf-8 -*-
#
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
""" Utilities related to sorting or ordering sequences.  """


def unique(seq):
    """
    Strip duplicates from a sequence.

    :type seq: iterable
    :param seq: a sequence of hashable items

    :rtype: generator
    :return:
        a sequence of unique items

        The generator yields items in the same order as the input sequence, but
        only yields the first encounter of each item.

    >>> a = ['foo', 1, 'bar', 'foo', 2, 1]
    >>> list(unique(a))
    ['foo', 1, 'bar', 2]
    """
    seen = set()
    for item in seq:
        if item not in seen:
            yield item
            seen.add(item)


def make_priority_lookup(lookup_order, invert=False):
    """
    Make a priority lookup function.

    For each value in the given lookup order, the resulting lookup function
    will return a unique numerical value. The first value in the lookup order
    (highest priority) will get the lowest number.

    Any values not defined in the lookup order will be assigned the lowest
    priority by the resulting lookup function.

    :param lookup_order:
        A sequence of unique, ordered values.

    :param invert:
        Invert the priority values from the lookup function. The first item
        will get the highest value.

    :rtype: callable
    :returns: a priority lookup function.

    >>> p = make_priority_lookup(('pri', 'sec'))
    >>> p('pri'), p('sec'), p('undefined')
    (0, 1, 2)

    >>> p = make_priority_lookup(('pri', 'sec'), invert=True)
    >>> p('pri'), p('sec'), p('undefined')
    (2, 1, 0)
    """
    if invert:
        # N items gets weighted N..1
        init_sequence = enumerate(reversed(lookup_order), 1)
        default = 0
    else:
        # N items gets weighted 0..N-1
        init_sequence = enumerate(lookup_order, 0)
        default = len(lookup_order)

    # Build the lookup table and lookup function
    lut = dict()
    for priority, value in init_sequence:
        if value in lut:
            raise ValueError('Duplicate value %r in sequence' % (value,))
        lut[value] = priority

    def get_priority(value):
        return lut.get(value, default)

    return get_priority
