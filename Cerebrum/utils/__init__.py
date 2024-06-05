# encoding: utf-8
#
# Copyright 2015-2024 University of Oslo, Norway
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
The `Cerebrum.utils` sub-package contains various standalone utils.

The utilities here should be general functions and classes.  If you think "this
could be used outside Cerebrum", then it probably belongs in here.

Util modules typically implements one or more:

- reusable code snippets
- standards and default values
- Wrappers for 3rd party packages

3rd party packages
-------------------
We typically don't want to expose a 3rd party module API too much in
Cerebrum, as it increases the cost and complexity if we ever need to remove
or swap out the package.

We can limit the exposure of third party APIs by defining our own wrapper
APIs.  This limits the exposure to a single module (the wrapper module).
E.g. :mod:`.phone` and mod:`phonenumbers`.

Other wrappers
--------------
Some built-in or third party APIs are a bit finicky to work with.  E.g.
working with `datetime` objects with timezones.  The :mod:`.date` API wraps
:mod:`datetime`, :mod:`pytz`, and :mod:`aniso8601` with an API that makes
it easier to create native, tz-aware datetime objects.


Standards and defaults
----------------------
Cerebrum enforces some defaults and standards when it comes to e.g. parsing
input values:

- :mod:`.textnorm` exposes unicode normalizers that uses *NFC* by default
- :mod:`.date` module exposes strict ISO8601 date and datetime parsers

"""
