#!/usr/bin/env python2.2

import sys

from Cerebrum import Constants
from Cerebrum import Person
from Cerebrum.Utils import Factory
from server.bofhd_cmds import BofhdExtension

def create_user(db, external_id):
    print "Creating posix user for person with external id", external_id

    const = Constants.Constants(db)

    ef = BofhdExtension(db)

    # Are these still used? [pere 2003-02-06]
    home = "/home/dir"
    posix_gid = 999999
    shell = const.posix_shell_bash

    person_info = ef._get_person(external_id)

    print "PersonID:", person_info.entity_id

    ef.account_create(None, 'accname', 'fnr', external_id)


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


