#!/usr/bin/env python2.2

# Updates an accounts password. Iff no password set, make one.
# TODO: co.auth_type_md5_crypt shoulb be replaced by something.
#       Code for this in bofh_uio_cmds.

import cerebrum_path
import os
import sys
import cereconf

from Cerebrum import Entity
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.Utils import Factory

# Set up the basics.
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='mkpasswd')

acc = Account.Account(db)
ent = Entity.Entity(db)

for row in ent.list_all_with_type(co.entity_account):
    acc.clear()
    acc.find(row['entity_id'])
    name = acc.get_account_name()

    try:
        auth = acc.get_account_authentication(co.auth_type_md5_crypt)
        print "Found: %s:%s" % (name, auth) 
    except Errors.NotFoundError:
        pltxt = acc.make_passwd(acc.get_account_name())
        print "Not found: %s, new: %s" % (name,pltxt)
        acc.set_password(pltxt)
        acc.write_db()

db.commit()

# arch-tag: 13430f5e-be96-4c8f-8820-37f6a39538b9
