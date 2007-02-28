#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2007 Norwegian University of Science and Technology, Norway
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

import errors
import sync
import config
import traceback
import sys

def main():
    incr = False
    id = -1
    s = sync.Sync(incr,id)

    # FIXME move to config-file
    f = open("/cerebrum/dumps/cerebrum-til-kjernen.sdv","w")

    # Syncronize persons
    print "Fetching persons"
    try:
        persons = s.get_persons()
        # FIXME
        # Search needs username, email, ou and affiliation as well.
        for person in persons:
            birthdate = person.birth_date[:10]
            export_id = person.export_id.split('exp-')[1]
            full_name = person.full_name
            surname = person.last_name
            pnr = person.nin
            f.write(birthdate + ";" + export_id + ";" + full_name + ";" + surname + ";" + pnr + ";\n")
        f.flush()
        f.close()
    except IOError,e:
        print "Exception %s occured, aborting" % e
        sys.exit()

    print "Done"


if __name__ == "__main__":
    main()

