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
from ceresync import syncws as sync
import os, sys
log = config.logger

statuses= ['archived','create_failed','not_created','on_disk','pending_restore']

def setup_home(path, uid, gid, dryrun):
    if not os.path.isdir(path):
        parent= os.path.dirname(path)
        if not os.path.isdir(parent):
            log.debug("Creating parent dir: %s",parent)
            if not dryrun:
                os.mkdir(parent, 0755)
        log.debug("Creating dir: %s", path)
        if not dryrun:        
            os.mkdir(path, 0700)
            os.chown(path, uid, gid)
        return True
    else:
        return False

def make_homedir(sync, homedir, setup_script, dryrun=False, no_report=False):
    path= homedir.homedir
    username= homedir.account_name
    uid= homedir.posix_uid
    gid= homedir.posix_gid
    result_status= 'on_disk'
    log.debug("Creating homedir for %s: %s", username, path)
    if dryrun:
        return

    try:
        if setup_home(path, uid, gid, dryrun):
            log.info("Running setup script: %s", setup_script)
            if not dryrun:
                r = os.system("echo %s %d %d %s %s" % (setup_script,
                                              uid, gid, path, username))
                if r != 0:
                    raise Exception("\"%s\" failed" % setup_script)

            log.info("Created homedir %s for %s" % (path, username))
        else:
            log.debug("Homedir %s for %s is ok" % (path, username))
    except Exception, e:
        log.warn("Failed creating homedir for %s: %s" % (username, e))
        result_status= 'create_failed'

    if not no_report and not dryrun:
        sync.set_homedir_status(homedir.homedir_id, result_status)

def show_homedirs(s, hostname):
    for status in statuses:
        print "Status: %s" % (status,)
        for homedir in s.get_homedirs(status, hostname):
            print "  %-9s %s" % (homedir.account_name, homedir.homedir)

def lint_homedirs(s, hostname):
    status='on_disk'
    print "Status %s in cerebrum, but does not exist on disk:" % (status,)
    for homedir in s.get_homedirs(status, hostname):
        if not os.path.isdir(homedir.homedir):
            print homedir.homedir

    status='not_created'
    print "Status %s in cerebrum, but does exist on disk:" % (status,)
    for homedir in s.get_homedirs(status, hostname):
        if os.path.isdir(homedir.homedir):
            print homedir.homedir

def main():
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
    show_db         = config.getboolean('args', 'show_db')
    lint            = config.getboolean('args', 'lint')
    hostname        = config.get('homedir', 'hostname', default=os.uname()[1])
    hostname        = config.get('args', 'hostname', default=hostname) # Allow command-line override
    setup_script    = config.get('homedir', 'setup_script', default="/local/skel/bdb-setup")
    
    home_status='not_created'
    if retry_failed:
        home_status='create_failed'

    s= sync.Sync()
    if lint:
        lint_homedirs(s, hostname)
    elif show_db:
        show_homedirs(s, hostname)
    else:
        for homedir in s.get_homedirs(home_status, hostname):
            make_homedir(s, homedir, setup_script, dryrun, no_report)

if __name__ == "__main__":
    main()
