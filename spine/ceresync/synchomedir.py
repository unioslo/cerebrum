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
import os, sys
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

def make_disk_searcher(sync, hostname):
    tr = sync.tr
    cmd = sync.cmd 

    ds = tr.get_disk_searcher()
    ds.set_host(cmd.get_host_by_name(hostname))

    hds = tr.get_home_directory_searcher()
    hds.add_join("disk", ds, "")

    return hds

def get_status_constants(tr):
    # Create a little struct for holding status value constants
    class status_values(object): pass
    status_constants = status_values()

    status_constants.CREATE_FAILED = tr.get_home_status("create_failed")
    status_constants.ON_DISK = tr.get_home_status("on_disk")
    status_constants.NOT_CREATED = tr.get_home_status("not_created")
    return status_constants

def status_to_string(status, status_constants):
    if status == status_constants.CREATE_FAILED:
        return "CREATE_FAILED"
    elif status == status_constants.ON_DISK:
        return "ON_DISK"
    elif status == status_constants.NOT_CREATED:
        return "NOT_CREATED"
    return status

def make_homedir(hd, setup_script, status_constants, dryrun):
    #path = hd.get_path() XXX
    path = get_path(hd)
    account = hd.get_account()
    username = account.get_name()
    log.info("Creating homedir for %s: %s", username, path)

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
        log.warn("Failed creating homedir for %s: %s" % (username, e))
        hd.set_status(status_constants.CREATE_FAILED)
    else:
        hd.set_status(status_constants.ON_DISK)

def make_homedirs(tr, hds, status_constants, retry_failed, no_report):
    status_constants = get_status_constants(tr)
    if retry_failed:
        hds.set_status(status_constants.CREATE_FAILED)
    else:
        hds.set_status(status_constants.NOT_CREATED)

    for hd in hds.search():
        make_homedir(hd, setup_script, status_constants, dryrun)

    if no_report:
        tr.rollback()
    else:
        tr.commit()

def show_homedirs(tr, hds):
    status_constants = get_status_constants(tr)
    for hd in hds.search():
        print "%-9s %s:\t%s" % (hd.get_account().get_name(), 
                              status_to_string(hd.get_status(), status_constants),
                              get_path(hd))

def lint_homedirs(tr, hds):
    status_constants = get_status_constants(tr)
    hds.set_status(status_constants.ON_DISK)
    for hd in hds.search():
        path = get_path(hd)
        if not os.path.exists(path):
            print >>sys.stderr, "%s has status ON_DISK in Cerebrum, but does not exist" % path

def main():
    # Parse command-line arguments. -v, --verbose and -c, --config are handled by default.
    config.parse_args([
        config.make_option("-H", "--hostname", action="store", type="string", metavar="HOSTNAME",
                            help="pretend to be file server HOSTNAME"),
        config.make_option("-n", "--no-report", action="store_true", default=False,
                            help="don't report back to cerebrum"),
        config.make_option("-d", "--dryrun", action="store_true", default=False,
                            help="don't create directories, and don't report back to cerebrum (implies --no-report)"),
        config.make_option("-r", "--retry-failed", action="store_true", default=False,
                            help="retry homedirs with creation failed status"),
        config.make_option("-s", "--show-db", action="store_true", default=False,
                            help="only show database contents"),
        config.make_option("-l", "--lint", action="store_true", default=False,
                            help="only warn about inconsistencies between Cerebrum and the filesystem"),
    ])
    dryrun          = config.getboolean('args', 'dryrun')
    no_report       = config.getboolean('args', 'no_report')
    retry_failed    = config.getboolean('args', 'retry_failed')
    hostname        = config.get('homedir', 'hostname', default=os.uname()[1])
    hostname        = config.get('args', 'hostname', default=hostname) # Allow command-line override
    setup_script    = config.get('homedir', 'setup_script', default="/local/skel/bdb-setup")
    show_db         = config.getboolean('args', 'show_db')
    lint            = config.getboolean('args', 'lint')

    # --dryrun implies --no-report
    if dryrun:
        no_report = True

    log.debug("hostname is: %s" , hostname)
    log.debug("setupscript is: %s" , setup_script)

    s = sync.Sync()
    tr = s.tr

    hds = make_disk_searcher(s, hostname)

    if lint:
        lint_homedirs(tr, hds)
    elif show_db:
        show_homedirs(tr, hds)
    else:
        make_homedirs(tr, hds, retry_failed, no_report)

if __name__ == "__main__":
    main()
