#!/usr/bin/env python2.2

import sys

from Cerebrum import Database,Constants
from Cerebrum import Person
from server.bofhd import ExportedFuncs
from server.bofhd import CallableFuncs

def create_user(db, external_id):
    print "Creating posix user for person with external id", external_id

    const = Constants.Constants(db)

    ef = ExportedFuncs(db, "config.dat")

    home = "/home/dir"
    posix_gid = 999999
    shell = const.posix_shell_bash

    person_info = ef.cfu.get_person(None, external_id)

    print "PersonID:", person_info['pid'], "Name:", person_info['name']

    ef.cfu.user_create(None, person_info['pid'], None, None, None, None,
                       posix_gid, None, home, shell)


def main():
    if len(sys.argv) == 2:
        external_id = sys.argv[1]
    else:
        external_id = "30535890168"

    Cerebrum = Database.connect()

    create_user(Cerebrum, external_id)

    # commit is done in user_create()
    #Cerebrum.commit()

if __name__ == '__main__':
    main()


