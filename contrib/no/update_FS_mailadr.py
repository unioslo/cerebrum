#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

import getopt
import re
import sys
from Cerebrum.Utils import Factory
from Cerebrum import Database

def usage(exitcode=0):
    print """Usage: [options]
    Updates all e-mail adresses in FS that come from Cerebrum
    -v | --verbose
    -d | --dryrun
    --db-user name: connect with given database username
    --db-service name: connect to given database
    """
    sys.exit(exitcode)

def main():
    db_user = db_service = None
    verbose = dryrun = 0
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dv",
                                   ["dryrun", "verbose", "db-user=",
                                    "db-service="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o, val in opts:
        if o in ('-v', '--verbose'):
            verbose += 1
        elif o in ('-d', '--dryrun'):
            dryrun = 1
        elif o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val

    db = Database.connect(user=db_user, service=db_service,
                          DB_driver='Oracle')
    fs = FS(db)
    db = Factory.get('Database')()
    fnr2primary = {}            # TODO: Fill with mapping fnr -> email adress
    re_cerebrum_addr = re.compile('[@.]uio\.no$', re.IGNORECASE)
    # TODO: should either be in cereconf, or deduced from the email system

    for r in fs.GetAllPersonsEmail():
        fnr = "%06d%05d" % (int(r['fodselsdato']), int(r['personnr']))
        current_email_addr = fnr2primary.get(fnr, None)
        if current_email_addr is None and r['emailadresse'] is not None:
            # Only update address if it is a cerebrum address
            if re_cerebrum_addr.search(r['emailadresse']) is None:
                continue
        if current_email_addr <> r['emailadresse']:
            if verbose:
                if r['emailadresse'] is not None:
                    print "%s: deleting %s" % (fnr, r['emailadresse'])
                print "%s: writing %s" % (fnr, current_email_addr)
            if not dryrun:
                fs.WriteMailAddr(r['fodselsdato'], r['personnr'],
                                 current_email_addr)
                fs.db.commit()

if __name__ == '__main__':
    main()
