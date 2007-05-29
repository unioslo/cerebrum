#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright 2007 University of Oslo, Norway
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

import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.Errors import NotFoundError
import os.path
import sys

db = Factory.get("Database")()
co = Factory.get("Constants")(db)
host = Factory.get("Host")(db)
disk = Factory.get("Disk")(db)
account = Factory.get("Account")(db)
db.cl_init(change_program="import_homedirs")

ok=0
not_ok=0

# XXX getopt
spread = 'user@stud'
passwdfile = '/etc/passwd'
verbose = 1
status = 'on_disk'
#

spread=co.Spread(spread)
status=co.AccountHomeStatus(status)

def get_disk_home(opath):
    """Suggest a (disk_id, home) for this path"""
    disk.clear()
    end = []
    path = opath
    while True:
        (path, dir) = os.path.split(path)
        end.insert(0, dir)
        if path == "/":
            return (None, opath)
        try:
            disk.find_by_path(path)
            return (disk.entity_id, os.path.join(*end))
        except NotFoundError:
            pass


for l in open(passwdfile).readlines():
    (uname, passwd, uid, gid, gecos, homedir, shell) = l.split(":")
    disk_id=None
    home=None
    try:
        account.clear()
        account.find_by_name(uname)
        (disk_id, home) = get_disk_home(homedir)
        if home == [uname]:
            home=None
        # XXX: check existing homedir.
        homedir_id = account.set_homedir(disk_id=disk_id, home=home,
                                         status=status)
        account.set_home(spread, homedir_id)
        ok+=1
    except NotFoundError:
        not_ok+=1
        if verbose:
            print >>sys.stderr, "Could find user %s" % uname
    except Exception, e:
        not_ok+=1
        if verbose:
            print >>sys.stderr, "Could not set home %s (%s, %s) for %s: %s" % (
                homedir, disk_id, home, uname, e)


print >>sys.stderr, "Set homedir for %d users, failed for %d users" % (
    ok, not_ok)
