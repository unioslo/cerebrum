# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
# Copyright 2002-2015 University of Oslo, Norway
"""
Utilities for calculating n-th backoff value.


Examples
========

A basic linear backoff:

>>> get_backoff = Backoff(Linear(), Factor(20), Truncate(100))
>>> [get_backoff(n + 1) for n in range(6)]
[20, 40, 60, 80, 100, 100]


We can use py:class:`datetime.timedelta` as our factor to create a linear
backoff with 10 minute intervals:

>>> from datetime import timedelta
>>> get_backoff = Backoff(Linear(), Factor(timedelta(minutes=10)))
>>> [str(get_backoff(n + 1)) for n in range(6)]
['0:10:00', '0:20:00', '0:30:00', '0:40:00', '0:50:00', '1:00:00']


A truncated binary exponential backoff that starts at 1/16th of an hour, and
truncates at *12 hours*:

>>> get_backoff = Backoff(
...     Exponential(2),
...     Factor(timedelta(hours=1) / 16),
...     Truncate(timedelta(hours=12)))
>>> [str(get_backoff(n + 1)) for n in range(6)]
['0:03:45', '0:07:30', '0:15:00', '0:30:00', '1:00:00', '2:00:00']
>>> [str(get_backoff(n)) for n in (8, 9)]
['8:00:00', '12:00:00']

A truncated base-3 exponential backoff that starts at 2/3rd of a minute, and
truncates after 5 *steps*:

>>> get_backoff = Backoff(
...     Truncate(5),
...     Exponential(3),
...     Factor(timedelta(minutes=2) / 3))
>>> [str(get_backoff(n + 1)) for n in range(6)]
['0:00:40', '0:02:00', '0:06:00', '0:18:00', '0:54:00', '0:54:00']

"""
import functools

from Cerebrum.utils import reprutils


class Linear(reprutils.ReprFieldMixin):
    """ linear (no-op) transform.  """
    repr_id = False
    repr_module = False

    def __call__(self, step):
        # just enforce an absolute min value
        return max(1, step)


class Exponential(reprutils.ReprEvalMixin):
    """ exponential growth transform. """

    repr_module = False
    repr_args = ('base',)

    def __init__(self, base):
        """
        :param base: exponential base
        """
        self.base = base

    def __call__(self, step):
        """
        :param int step: numerical step number

        :returns: base ** (step - 1)
        """
        # steps 1, 2, 3 -> exponent 0, 1, 2
        return self.base ** max(0, step - 1)


class Factor(reprutils.ReprEvalMixin):
    """ factor transform. """
    repr_module = False
    repr_args = ('factor',)

    def __init__(self, factor):
        """
        :param factor: factor to apply to all values
        """
        self.factor = factor

    def __call__(self, value):
        """
        :returns: factor * value
        """
        return self.factor * value


class Truncate(reprutils.ReprEvalMixin):
    """ truncate transform. """
    repr_module = False
    repr_args = ('maxval',)

    def __init__(self, maxval):
        """
        :param maxval: upper bound to truncate values to
        """
        self.maxval = maxval

    def __call__(self, value):
        """
        :returns: value or maximum value
        """
        return min(self.maxval, value)


class Backoff(reprutils.ReprEvalMixin):
    """
    Callable backoff.

    This callable takes a single value — a step number — and calculates an
    appropriate backoff value for this step.
    """
    repr_module = False
    repr_args_attr = 'transforms'

    def __init__(self, *transforms):
        self.transforms = transforms

    def __call__(self, step):
        """
        :param int step: a positive number

        :returns: an appropriate backoff value for the n-th step
        """
        return functools.reduce(
            lambda value, callback: callback(value),
            self.transforms,
            step,
        )


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
