#!/usr/bin/env python2.2

# This script should be ran regularly from cron.  It process the
# changelog, and performs a number of tasks:
#
# - when a user has been creted: create users homedir

import cerebrum_path

from Cerebrum.modules import CLHandler
from Cerebrum.Utils import Factory

rsh = "/local/bin/ssh"
db = Factory.get('Database')()
db.cl_init()
const = Factory.get('CLConstants')(db)
ei = CLHandler.CLHandler(db)

def test_setup():
    db.cl_init(change_by=None, change_program='foobarprog')
    db.log_change(1, const.a_create, None)
    db.log_change(2, const.a_create, None)
    db.commit()

def quote_list(lst):  # TODO: check that input is in [a-zA-Z0-9-_ '"]
    ret = ""
    for n in range(len(lst)):
        t = str(lst[n])
        t.replace('"', '\"')
        t.replace('\\', '\\\\')
        if t.find(" ") >= 0:
            t = '"'+t+'"'
        lst[n] = t
    return " ".join(lst)

def make_user(entity_id):
    uname = "uname"
    (home, user_uid, default_group, fullname) = ("home", "uid", "df", "fullt navn")
    machine = "foobar"
    cmd = ['echo', '/local/etc/reguser/adduser', uname, home,
           user_uid, default_group, fullname]
    cmd = (rsh, '-n', machine) + ("'"+quote_list(cmd)+"'",)

    print "DO: %s" % str(cmd)
    

for evt in ei.get_events('uio_ch', [const.a_create]):
    if evt.change_type_id == int(const.a_create):
        print "Creating entity_id=%s" % (evt.subject_entity)
        make_user(evt.subject_entity)
db.commit()

