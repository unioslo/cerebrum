#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007, 2008 University of Oslo, Norway
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


"""Delete AD-traits for a given account.

Usage: remove_all_ad_traits.py -u uname [-d]
"""

import getopt
import sys
from Cerebrum import Errors
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
db.cl_init(change_program="remove_ad_traits")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)


def remove_ad_traits(uname):
    ac.clear()
    try:
        ac.find_by_name(uname)
    except Errors.NotFoundError:
        usage(2, "Unknown user %s" % uname)

    ac.delete_ad_attrs()
    print "Deleted all ad traits for user"
  

def usage(err=0, msg=None):
    if err:
        print >>sys.stderr, err
    if msg:
        print >>sys.stderr, msg
    print >>sys.stderr, __doc__
    sys.exit(bool(err))


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'u:d',
                                   ['dryrun'])
    except getopt.GetoptError:
        sys.exit(1)

    uname = None
    dryrun = False
    for opt, val in opts:
        if opt in ('-u',):
            uname = val
        if opt in ('-d', '--dryrun',):
            dryrun = True

    if not uname:
        usage(1)

    remove_ad_traits(uname)

    if dryrun:
        print "Rolling back all changes"
        db.rollback()
    else:
        print "Committing all changes"
        db.commit()
        
if __name__ == '__main__':
    main()

