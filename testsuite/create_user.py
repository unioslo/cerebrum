#!/usr/bin/env python2.2

import random
import sys

from Cerebrum import Database,Constants,Errors
from Cerebrum import Person
# from Cerebrum import PosixUser
from Cerebrum import Account
from Cerebrum import cereconf
from Cerebrum.modules.no.uio import OU
from Cerebrum.modules.no import fodselsnr

Cerebrum = Database.connect()
ou = OU.OU(Cerebrum)
person = Person.Person(Cerebrum)
co = Constants.Constants(Cerebrum)
account = Account.Account(Cerebrum)
# account = PosixUser.PosixUser(Cerebrum)
person = Person.Person(Cerebrum)

def map_home(home, uname):
    # Home should be specified without trailing uname.  (Might
    # want to override this?)
    if home != "/":           
        home = home + "/" + uname
    return home

def user_create_new(db, person_id, home):
    np_type = None
    expire_date = None
    uname = None
    posix_uid = None
    posix_gid = 999999
    gecos = None
    shell = co.posix_shell_bash

    creator_id = 888888    # TODO: Set this

    try:
        account = Account.Account(db)  # TODO: Flytt denne
        account.clear()
        if(posix_uid is None):
            posix_uid = account.get_free_uid()

        print "PID:", person_id, "UID:", posix_uid, "Shell:", shell

        if(uname is None):                  # Find a suitable username
            person = Person.Person(db)
            person.find(person_id)
            name = None
            for ss in cereconf.PERSON_NAME_SS_ORDER:
                try:
                    name = person.get_name(getattr(co, ss), co.name_full)
                    break
                except Errors.NotFoundError:
                    pass
            if name is None:
                raise "No name for person!"  #TODO: errror-class
            name = name.split()
            uname = account.suggest_unames(co.entity_accname_default,
                                           name[0], name[1])
            uname = uname[0]

        home = map_home(home, uname)

        account.populate(co.entity_person,
                         person_id,
                         np_type, 
                         creator_id, expire_date)

        # populate_posix_user(user_uid, gid, gecos, home, shell):
        account.populate_posix_user(posix_uid, posix_gid, gecos, home, shell)
            
        account.affect_domains(co.entity_accname_default)
        account.populate_name(co.entity_accname_default, uname)
            
        passwd = account.make_passwd(uname)
        account.affect_auth_types(co.auth_type_md5)
        # account.populate_authentication_type(co.auth_type_md5, passwd)
        account.set_password(passwd)
            
        account.write_db()
        db.commit()
        return {'password' : passwd, 'uname' : uname}
    except Database.DatabaseError:
        db.rollback()
        # TODO: Log something here
        raise "Something went wrong, " \
              "see log for details: %s" % (sys.exc_info()[1])

def user_create_old(db, person_id, home):
    account.clear()
    uid = account.get_free_uid()
    creator_id  = 888888
    group_id    = 999999

    # populate(owner_type, owner_id, np_type, creator_id, expire_date):
    account.populate(co.entity_person,
                     person_id,
                     None, 
                     creator_id, None)

    uname = "u"+str(uid)
    home = map_home(home, uname)

    # populate_posix_user(user_uid, gid, gecos, home, shell):
    account.populate_posix_user(uid, group_id, None, home,
                                co.posix_shell_bash)

    account.affect_domains(co.entity_accname_default)
    account.populate_name(co.entity_accname_default, uname)

    account.affect_auth_types(co.auth_type_md5)
    account.populate_authentication_type(co.auth_type_md5, "dette er et MD5 passord")
 
    account.write_db()
    db.commit()

def main():
    if len(sys.argv) == 2:
        external_id = sys.argv[1]
    else:
        external_id = "30535890168"

    person.find_by_external_id(co.externalid_fodselsnr, external_id)

    if 1:
        user_create_new(Cerebrum, person.person_id, "/home/dir")
    else:
        user_create_old(Cerebrum, person.person_id, "/home/dir")

    #Cerebrum.commit()

if __name__ == '__main__':
    main()


