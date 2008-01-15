#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2007 University of Oslo, Norway
#
# This filebackend is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.



from ceresync import config 
import SpineClient
import os


def setup_home(path, uid, gid):
    if not os.path.isdir(path):
        os.mkdir(path, 0700)
        os.chown(path, uid, gid)

class sync(object):
    def __init__(self):
        self.connection = SpineClient.SpineClient(config=config.conf).connect()
        self.session = self.connection.login(config.conf.get('spine', 'login'),
                                   config.conf.get('spine', 'password'))
        self.tr = self.session.new_transaction()
        self.cmd = self.tr.get_commands()

    def __del__(self):
        try: self.session.logout()
        except: pass

s = sync()
tr = s.tr
cmd = s.cmd    

try:
    hostname = config.conf.get('homedir', 'hostname')
except:
    hostname = os.uname()[1]

try:
    setup_script = config.conf.get('homedir', 'setup_script')
except:
    setup_script="/local/skel/bdb-setup"




status_create_failed = tr.get_home_status("create_failed")
status_on_disk = tr.get_home_status("on_disk")
status_not_created = tr.get_home_status("not_created")

me = cmd.get_host_by_name(hostname)

hds = tr.get_home_directory_searcher()
ds = tr.get_disk_searcher()
ds.set_host(me)
hds.add_join("disk", ds, "")
hds.set_status(status_not_created)


def get_path(hd):
    disk = hd.get_disk()
    home = hd.get_home()
    if disk:
        path = disk.get_path()
        if home:
            return path + "/" + home
        else:
            return path + "/" + hd.get_account().get_name()
    else:
        return home
    




def make_homedir(hd):
    #path = hd.get_path() XXX
    path = get_path(hd)
    account = hd.get_account()
    username = account.get_name()
    uid = account.get_posix_uid()
    gid = account.get_primary_group().get_posix_gid()
    
    setup_home(path, uid, gid)
    r = os.system("%s %d %d %s %s" % (setup_script,
                                      uid, gid, path, username))
    if r<0:
        raise Exception("Create failed")

for hd in hds.search():
    try:
        make_homedir(hd)
        hd.set_status(status_on_disk)
    except:
        # XXX log
        hd.set_status(status_create_failed)

tr.commit()
s.session.logout()
