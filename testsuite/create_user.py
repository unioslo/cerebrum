#!/usr/bin/env python2.2

import sys

from Cerebrum import Database,Constants
from Cerebrum import Person
from server.bofhd import ExportedFuncs
from server.bofhd import CallableFuncs

Cerebrum = Database.connect()
const = Constants.Constants(Cerebrum)

def user_create_bofhd(db, person_id, home):
    ef = ExportedFuncs(db, "config.dat")
    posix_gid = 999999
    shell = const.posix_shell_bash

    print "PersonID:", person_id, "Shell:",shell

    ef.cfu.user_create(None, person_id, None, None, None, None, posix_gid,
                       None, home, shell)
def main():
    if len(sys.argv) == 2:
        external_id = sys.argv[1]
    else:
        external_id = "30535890168"

    print "Creating posix user for person with external id", external_id

    person = Person.Person(Cerebrum)
    person.find_by_external_id(const.externalid_fodselsnr, external_id)

    user_create_bofhd(Cerebrum, person.person_id, "/home/dir")
    # commit is done in user_create()
    #Cerebrum.commit()

if __name__ == '__main__':
    main()


