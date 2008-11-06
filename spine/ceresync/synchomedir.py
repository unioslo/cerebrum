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


from ceresync import sync
from ceresync import config 
import SpineClient
import os
log = config.logger

def setup_home(path, uid, gid):
    if not os.path.isdir(path):
        parent= os.path.dirname(path)
        if not os.path.isdir(parent):
            os.mkdir(parent, 0755)
        os.mkdir(path, 0700)
        os.chown(path, uid, gid)
        return True
    else:
        return False

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

def make_homedir(hd, setup_script, status_constants):
    #path = hd.get_path() XXX
    path = get_path(hd)
    account = hd.get_account()
    username = account.get_name()
    
    try:
        uid = account.get_posix_uid()
        gid = account.get_primary_group().get_posix_gid()
        if not dryrun:
            if setup_home(path, uid, gid):
                r = os.system("%s %d %d %s %s" % (setup_script,
                                              uid, gid, path, username))
                if r != 0:
                    raise Exception("\"%s\" failed" % setup_script)

                log.info("Created homedir %s for %s" % (path, username))
            else:
                log.debug("Homedir %s for %s is ok" % (path, username))
    except Exception, e:
        log.warn("Failed creating homedir for %s: %s" % (
            username, e))
        hd.set_status(status_constants.CREATE_FAILED)
    else:
        hd.set_status(status_constants.ON_DISK)

def main():
    # Parse command-line arguments. -v, --verbose and -c, --config are handled by default.
    config.parse_args([
        config.make_option("-H", "--hostname", action="store", type="string", 
                            help="pretend to be file server HOSTNAME"),
        config.make_option("-d", "--dryrun", action="store_true", default=False,
                            help="don't create directories, and don't report back to cerebrum"),
        config.make_option("-r", "--retry-failed", action="store_true", default=False,
                            help="retry homedirs with creation failed status"),
    ])
    dryrun          = config.get('args', 'dryrun')
    retry_failed    = config.get('args', 'retry_failed')
    hostname        = config.get('homedir', 'hostname', default=os.uname()[1])
    hostname        = config.get('args', 'hostname', default=hostname) # Allow command-line override
    setup_script    = config.get('homedir', 'setup_script', default="/local/skel/bdb-setup")

    log.debug("hostname is: %s" , hostname)
    log.debug("setupscript is: %s" , setup_script)

    s = sync.Sync()
    tr = s.tr
    cmd = s.cmd    

    # Create a little struct for holding status value constants
    class status_values(object): pass
    status_constants = status_values()

    status_constants.CREATE_FAILED = tr.get_home_status("create_failed")
    status_constants.ON_DISK = tr.get_home_status("on_disk")
    status_constants.NOT_CREATED = tr.get_home_status("not_created")

    ds = tr.get_disk_searcher()
    ds.set_host(cmd.get_host_by_name(hostname))

    hds = tr.get_home_directory_searcher()
    hds.add_join("disk", ds, "")
    if retry_failed:
        hds.set_status(status.CREATE_FAILED)
    else:
        hds.set_status(status.NOT_CREATED)

    for hd in hds.search():
        make_homedir(hd, setup_script, status_constants)

    if dryrun:
       tr.rollback()
    else:
       tr.commit()

if __name__ == "__main__":
    main()
