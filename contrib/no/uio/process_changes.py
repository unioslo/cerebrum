#!/usr/bin/env python2.2

# This script should be ran regularly from cron.  It process the
# changelog, and performs a number of tasks:
#
# - when a user has been creted: create users homedir

import cerebrum_path

import cereconf
from Cerebrum.modules import CLHandler
from Cerebrum.Utils import Factory
from Cerebrum import Disk
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup

rsh = "/local/bin/ssh"
db = Factory.get('Database')()
const = Factory.get('CLConstants')(db)
ei = CLHandler.CLHandler(db)
posix_user = PosixUser.PosixUser(db)
posix_group = PosixGroup.PosixGroup(db)

def test_setup():
    """Debug methods while testing: inserts ChangeLog entries"""
    db.cl_init(change_by=None, change_program='foobarprog')
    db.log_change(54, const.a_create, None)
    db.log_change(57, const.a_create, None)
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
    posix_user.clear()
    posix_user.find(entity_id)
    posix_group.clear()
    posix_group.find(posix_user.gid)

    uname = posix_user.get_name(const.account_namespace)['entity_name']
    home = posix_user.home
    user_uid = str(posix_user.posix_uid)
    default_group = str(posix_group.posix_gid)

    # TODO: find out which machine to connect to.
    # send more info like full-name (used for eudora ini files), but
    # find a safe way to quote it that is parseable by /bin/sh (STDIN)?
    host = Disk.Host(db)
    disk = Disk.Disk(db)
    disk.clear()
    disk.find(posix_user.disk_id)
    host.clear()
    host.find(disk.host_id)
    
    homedir = "%s/%s" % (disk.path, posix_user.account_name)
    cmd = ['/local/etc/reguser/mkhomedir', uname, homedir,
           user_uid, default_group, cereconf.POSIX_HOME_TEMPLATE_DIR,
           cereconf.POSIX_USERMOD_SCRIPTDIR, posix_user.get_gecos()]
    cmd = (rsh, '-n', host.name) + ("'"+quote_list(cmd)+"'",)

    print "DO: %s" % str(cmd)
    

for evt in ei.get_events('uio_ch', [const.a_create]):
    if evt.change_type_id == int(const.a_create):
        print "Creating entity_id=%s" % (evt.subject_entity)
        make_user(evt.subject_entity)
# test_setup()
db.commit()

