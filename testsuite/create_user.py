#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003 University of Oslo, Norway
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

import sys

from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Errors
import cereconf
from Cerebrum.Utils import Factory
from server.bofhd_cmds import BofhdExtension

def create_user(db, external_id):
    print "Creating posix user for person with external id", external_id

    const = Factory.get('Constants')(db)

    ef = BofhdExtension(db)

    # Are these still used? [pere 2003-02-06]
    home = "/home/dir"
    posix_gid = 999999
    shell = const.posix_shell_bash

    try:
        person_info = ef._get_person(external_id)
    except Errors.TooManyRowsError:
        return  # Person not uniquely identified

    print "PersonID:", person_info.entity_id
    account = Account.Account(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    ef.account_create(account.entity_id, 'accname', 'fnr', external_id)


def main():
    if len(sys.argv) == 2:
        external_id = sys.argv[1]
    else:
        external_id = "41023468172"

    Cerebrum = Factory.get('Database')()

    create_user(Cerebrum, external_id)

    # commit is done in user_create()
    #Cerebrum.commit()

if __name__ == '__main__':
    main()

# arch-tag: d8e77de2-e381-4607-b8bc-f4b78588e88d
