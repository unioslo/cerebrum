#!/usr/bin/env python

# Updates an accounts password. Iff no password set, make one.
# TODO: co.auth_type_md5_crypt shoulb be replaced by something.
#       Code for this in bofh_uio_cmds.

import cerebrum_path
import cereconf
import os
import sys
import pickle


from Cerebrum import Entity
from Cerebrum.modules import Email
from Cerebrum import Errors
from Cerebrum.Utils import Factory

# Set up the basics.
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='mkpasswd')

acc = Factory.get('Account')(db)
ent = Entity.Entity(db)
pass_cache = {}


def read_plain_pass():
    global pass_cache
    count = 0
    passwords = db.get_log_events(types=[co.account_password])
    for row in passwords:
      try:
        pass_cache[row['subject_entity']] = pickle.loads(row.change_params)['password']
      except:
        type, value, tb = sys.exc_info()
        print "Aiee! %s %s" % (str(type), str(value))
      count += 1
    if count < 1000:
      print "Something is not right.. only %d passwords found. Bailing out" % count
      sys.exit(1)
    


read_plain_pass()

for row in ent.list_all_with_type(co.entity_account):
    acc.clear()
    try:
        acc.find(row['entity_id'])
    except Errors.NotFoundError:
        print "Error: No account for entity_id:%d" % row['entity_id']
    name = acc.get_account_name()

    try:
        auth = acc.get_account_authentication(co.auth_type_md5_crypt)
        print "Hash password Found: %s:%s" % (name, auth)
        if acc.entity_id not in pass_cache:
          print "Plaintext pass NOT found, generating new"
          raise Errors.NotFoundError, "Must create new password"
        else:
          print "Plaintext password found"          
    except Errors.NotFoundError:
        pltxt = acc.make_passwd(acc.get_account_name())
        print "Not found: %s, new: %s" % (name,pltxt)
        acc.set_password(pltxt)
        acc.write_db()

db.commit()
