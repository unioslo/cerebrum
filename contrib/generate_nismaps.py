#!/usr/bin/env python2.2

from Cerebrum import Database,Constants,Errors
from Cerebrum import Person
from Cerebrum import Account
import pprint
import time

Cerebrum = Database.connect()
person = Person.Person(Cerebrum)
co = Constants.Constants(Cerebrum)
account = Account.Account(Cerebrum)
person = Person.Person(Cerebrum)

def generate_passwd():
    pp = pprint.PrettyPrinter(indent=4)
    count = 0
    for id in account.get_all_posix_users():
        id = id[0]
        account.find_posixuser(id)
        # account.find(id)

        # TODO: The value_domain should be fetched from somewhere
        # The array indexes should be replaced with hash-keys
        uname = account.get_name(co.entity_accname_default)[0][2]
        # TODO: Something should set which auth_type to use for this map
        try:
            passwd = account.get_account_authentication(co.auth_type_md5)
        except Errors.NotFoundError:
            passwd = '*'
        
        default_group = "posix_group.find(%s)" % account.gid
        gecos = account.gecos
        if gecos == None:
            gecos = account.get_gecos()
        shell = Constants._PosixShellCode(int(account.shell)).description
        print "%s:%s:%s:%s:%s:%s:%s" %(
            uname,
            passwd,
            account.user_id,
            default_group,
            gecos,
            account.home,
            shell)
	# convert to 7-bit

def main():
    generate_passwd()

if __name__ == '__main__':
    main()

