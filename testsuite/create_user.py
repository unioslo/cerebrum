#!/usr/bin/env python2.2

import random
import sys

from Cerebrum import Database,Constants,Errors
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import cereconf
from Cerebrum.modules.no.uio import OU
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules import PosixUser

Cerebrum = Database.connect()
ou = OU.OU(Cerebrum)
const = Constants.Constants(Cerebrum)
account = Account.Account(Cerebrum)
# account = PosixUser.PosixUser(Cerebrum)

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
    shell = const.posix_shell_bash

    creator_id = 888888    # TODO: Set this

    try:
        account = Account.Account(db)  # TODO: Flytt denne
        account.clear()
        posix_user = PosixUser.PosixUser(db)  # TODO: Flytt denne
        posix_user.clear()
        if(posix_uid is None):
            posix_uid = posix_user.get_free_uid()

        print "PID:", person_id, "UID:", posix_uid, "Shell:", shell

        if(uname is None):                  # Find a suitable username
            person = Person.Person(db)
            person.find(person_id)
            name = None
            for ss in cereconf.PERSON_NAME_SS_ORDER:
                try:
                    name = person.get_name(getattr(const, ss), const.name_full)
                    break
                except Errors.NotFoundError:
                    pass
            if name is None:
                raise "No name for person!"  #TODO: errror-class
            name = name.split()
            uname = posix_user.suggest_unames(const.account_namespace,
                                              name[0], name[1])
            uname = uname[0]

        # Home should be specified without trailing uname.  (Might want to override this?)
        if home != "/":           
            home = home + "/" + uname

        account.populate(uname, const.entity_person,
                         person_id,
                         np_type, 
                         creator_id, expire_date)
        account.write_db()
        Account.Account.find(posix_user, account.account_id)
        posix_user.populate(account.account_id, posix_uid, posix_gid, gecos,
                            home, shell)
        passwd = posix_user.make_passwd(uname)
        # posix_user.affect_auth_types(const.auth_type_md5)
        posix_user.set_password(passwd)
        posix_user.write_db()
        
        db.commit()
        return {'password' : passwd, 'uname' : uname}
    except Database.DatabaseError:
        db.rollback()
        # TODO: Log something here
        raise "Something went wrong, " \
              "see log for details: %s" % (sys.exc_info()[1])

def user_create_old(db, person_id, home):
    account.clear()
    posix_uid = account.get_free_uid()
    creator_id  = 888888
    group_id    = 999999

    print "PID:", person_id, "UID:", posix_uid, "Shell:", shell

    # populate(owner_type, owner_id, np_type, creator_id, expire_date):
    account.populate(const.entity_person,
                     person_id,
                     None, 
                     creator_id, None)

    uname = "u"+str(posix_uid)
    home = map_home(home, uname)

    # populate_posix_user(user_uid, gid, gecos, home, shell):
    account.populate_posix_user(posix_uid, group_id, None, home,
                                const.posix_shell_bash)

    account.affect_domains(const.entity_accname_default)
    account.populate_name(const.entity_accname_default, uname)

    account.affect_auth_types(const.auth_type_md5)
    account.populate_authentication_type(const.auth_type_md5, "dette er et MD5 passord")
 
    account.write_db()
    db.commit()

def main():
    if len(sys.argv) == 2:
        external_id = sys.argv[1]
    else:
        external_id = "30535890168"

    print "Creating posix user for person with external id", external_id

    person = Person.Person(Cerebrum)
    person.find_by_external_id(const.externalid_fodselsnr, external_id)

    if 1:
        user_create_new(Cerebrum, person.person_id, "/home/dir")
    else:
        user_create_old(Cerebrum, person.person_id, "/home/dir")

    #Cerebrum.commit()

if __name__ == '__main__':
    main()


