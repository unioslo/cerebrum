#!/usr/bin/env python2.2

from Cerebrum import Database,Constants,Errors
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum.modules import PosixUser
import pprint
import time

Cerebrum = Database.connect()
person = Person.Person(Cerebrum)
co = Constants.Constants(Cerebrum)
account = Account.Account(Cerebrum)
posix_user = PosixUser.PosixUser(Cerebrum)
person = Person.Person(Cerebrum)

def generate_passwd():
    pp = pprint.PrettyPrinter(indent=4)
    count = 0
    for id in posix_user.get_all_posix_users():
        id = id[0]
        posix_user.find(id)
        # account.find(id)

        # TODO: The value_domain should be fetched from somewhere
        # The array indexes should be replaced with hash-keys
        uname = posix_user.get_name(co.account_namespace)[0][2]
        # TODO: Something should set which auth_type to use for this map
        try:
            passwd = posix_user.get_account_authentication(co.auth_type_md5)
        except Errors.NotFoundError:
            passwd = '*'
        
        default_group = "posix_group.find(%s)" % posix_user.gid
        gecos = posix_user.gecos
        if gecos is None:
            gecos = posix_user.get_gecos()
        shell = Constants._PosixShellCode(int(posix_user.shell)).description
        print "%s:%s:%s:%s:%s:%s:%s" %(
            uname,
            passwd,
            posix_user.posix_uid,
            default_group,
            gecos,
            posix_user.home,
            shell)
	# convert to 7-bit

def main():
    generate_passwd()

if __name__ == '__main__':
    main()

