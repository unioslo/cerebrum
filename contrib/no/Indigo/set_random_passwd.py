#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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
import cereconf
from Cerebrum.Utils import Factory

def main():
    
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)

    db.cl_init(change_program='initial_passwd')

    # Register accounts with an active password
    active = {}
    for row in ac.list_account_authentication():
        if not row['auth_data'] == None:
            active[int(row['account_id'])] = True

    for aff in (co.affiliation_ansatt, co.affiliation_elev):
        for row in ac.list_accounts_by_type(affiliation=aff):
            id = int(row['account_id'])
            # If the user has passwords listed, we don't create new
            # ones.
            if active.has_key(id):
                continue
            ac.clear()
            ac.find(id)
            pw = ac.make_passwd(ac.account_name)
            ac.set_password(pw)
            ac.write_db()

    db.commit()
    
if __name__ == '__main__':
    main()
