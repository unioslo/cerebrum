#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2003-2015 University of Oslo, Norway
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

import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum import Constants
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Constants import _ChangeTypeCode


# NOTE: _ChangeTypeCode has been moved from this module to Cerebrum.Constants.
#       Some modules might still import the _ChangeTypeCode from this module!

from Cerebrum.Constants import CLConstants

# NOTE: CLConstants has been moved from this module to Cerebrum.Constants.
#       Some modules might still import the CLConstants from this module!


def main():
    from Cerebrum.Utils import Factory
    from Cerebrum import Errors

    Cerebrum = Factory.get('Database')()
    co = CLConstants(Cerebrum)

    skip = dir(Cerebrum)
    skip.append('map_const')
    for x in filter(lambda x: x[0] != '_' and x not in skip, dir(co)):
        if type(getattr(co, x)) == type or callable(getattr(co, x)):
            continue
        if not isinstance(getattr(co, x), co.ChangeType):
            continue
        try:
            print "FOUND: co.%s:" % x
            print "  strval: %r" % str(getattr(co, x))
            print "  intval: %d" % int(getattr(co, x))
        except Errors.NotFoundError:
            print "NOT FOUND: co.%s" % x
        except Exception, e:
            print "ERROR: co.%s - %r" % (x, e)
            print "co.%s: %s = %d" % (x, getattr(co, x), getattr(co, x))


if __name__ == '__main__':
    main()
