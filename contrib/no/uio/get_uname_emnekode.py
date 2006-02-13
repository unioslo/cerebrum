#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
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


"""
Usage: get_kurs_evu_kurs <emnekode>

Gir en iversikt over brukernavnene til de som er registrert på kurset og en
oversikt over hvem som ikke har brukernavn.

Skulle noen ønske å sortere på etternavn, kan utskriften sendes til sort:

get_uname_emnekode.py INF1000 | sort -k 3 -t ' '

... sortere på brukernavn:

get_uname_emnekode.py INF1000 | sort -k 2 -t '>'
"""

import cerebrum_path
import cereconf

from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.no.uio.access_FS import FS

import sys
import time





def fetch_primary_uname(row, person, account, constants):

    birth_date = str(row.fodselsdato).zfill(6)
    no_ssn = birth_date + str(row.personnr)

    # Jupp, we try extra hard to get a username
    for source in [ constants.system_fs, None ]:
        try:
            person.clear()
            person.find_by_external_id(constants.externalid_fodselsnr,
                                       no_ssn,
                                       source_system = source)
            account_id = person.get_primary_account()
            if not account_id:
                return "No account"
            # fi

            account.clear()
            account.find(account_id)
            return account.get_account_name()
        except (Errors.NotFoundError, Errors.TooManyRowsError):
            pass
        # yrt
    # od

    return "No uname found"
# end fetch_primary_uname



def main():
    db_fs = Database.connect(user = "ureg2000", service = "FSPROD.uio.no",
                             DB_driver = "Oracle")
    fs = FS(db_fs)
    db_cerebrum = Factory.get("Database")()
    person = Factory.get("Person")(db_cerebrum)
    account = Factory.get("Account")(db_cerebrum)
    constants = Factory.get("Constants")(db_cerebrum)
    
    emnekode = sys.argv[1]
    for row in fs.student.get_emne_eksamensmeldinger(emnekode):
        uname = fetch_primary_uname(row, person, account, constants)
        
        print "%06d %05d %-20s%-30s --> %-10s" % (row.fodselsdato,
                                                  row.personnr,
                                                  row.etternavn,
                                                  row.fornavn,
                                                  uname)
    # od
# end main





if __name__ == '__main__':
    main()
# fi

# arch-tag: 7f383cd9-42a8-42be-a939-74efed067dde
