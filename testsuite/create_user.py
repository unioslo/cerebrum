#!/usr/bin/env python2.2

import random

from Cerebrum import Database,Constants,Errors
from Cerebrum import Person
# from Cerebrum import PosixUser
from Cerebrum import Account
from Cerebrum.modules.no.uio import OU
from Cerebrum.modules.no import fodselsnr

Cerebrum = Database.connect()
ou = OU.OU(Cerebrum)
person = Person.Person(Cerebrum)
co = Constants.Constants(Cerebrum)
account = Account.Account(Cerebrum)
# account = PosixUser.PosixUser(Cerebrum)
person = Person.Person(Cerebrum)

def main():
    account.clear()
    uid = account.get_free_uid()

    external_id = "30535890168"
    creator_id  = 888888
    group_id    = 999999

    person.find_by_external_id(co.externalid_fodselsnr, external_id)

    # populate(owner_type, owner_id, np_type, creator_id, expire_date):
    account.populate(co.entity_person,
                     person.person_id,
                     None, 
                     creator_id, None)

    # populate_posix_user(user_uid, gid, gecos, home, shell):
    account.populate_posix_user(uid, group_id, None,
                                "/home/dir", co.posix_shell_bash)

    account.affect_domains(co.entity_accname_default)
    account.populate_name(co.entity_accname_default, "u"+str(uid))

    account.affect_auth_types(co.auth_type_md5)
    account.populate_authentication_type(co.auth_type_md5, "dette er et MD5 passord")

    account.write_db()
    Cerebrum.commit()

if __name__ == '__main__':
    main()


