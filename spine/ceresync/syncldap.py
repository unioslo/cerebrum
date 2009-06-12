#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
#
# This file is part of Cerebrum.
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

from ceresync import errors
from ceresync import sync
from ceresync.backend import ldapbackend
from ceresync import config
import traceback
from sys import exit
import os

log = config.logger


def main():
    config.parse_args(config.make_bulk_options())

    spine_cache = config.get('spine','last_change') or \
                  "/var/lib/cerebrum/sync.last_change"

    incr   = config.getboolean('args', 'incremental', allow_none=True)
    add    = config.getboolean('args', 'add')
    update = config.getboolean('args', 'update')
    delete = config.getboolean('args', 'delete')

    if incr is None:
        log.error("Invalid arguments. You must provide either the --bulk or the --incremental option")
        exit(1)

    local_id= 0
    if os.path.isfile(spine_cache):
        local_id= long( file(spine_cache).read() )
    try:
        log.info("Connecting to spine-server")
        s = sync.Sync(incr,local_id)
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        exit(1)
    
    server_id= s.cmd.get_last_changelog_id()
    encoding= s.session.get_encoding()
    log.info("Local id: %ld, server id: %ld", local_id, server_id)
    
    if local_id > server_id:
        log.warning("Local changelogid is larger than the server's!")

    if incr and local_id == server_id:
        log.info("Nothing to be done.")
        s.close()
        return

    systems =[ 
        ["ou=nav,ou=system,dc=ntnu,dc=no",
         "user@nav",ldapbackend.PosixUser],
        ["ou=kalender,ou=system,dc=ntnu,dc=no",
         "user@kalender", ldapbackend.OracleCalendar]
    ]
         
    for base, spread, backend in systems:
        log.info("Syncronizing %s, %s" % (base, spread))
        system = backend(base=base)
        system.begin(encoding, incr, add, update, delete)

        try:
            s.view.set_account_spread(s.tr.get_spread(spread))
            for account in s.get_accounts():
                system.add(account)
        except IOError,e:
            log.error("Exception %s occured, aborting" % e)
        else:
            system.close()

    # Defaults to fetch configuration from sync.conf
    user = ldapbackend.PosixUser(base=config.get("ldap","user_base"))
    groups = ldapbackend.PosixGroup(base=config.get("ldap","group_base"))
    persons = ldapbackend.Person(base=config.get("ldap","people_base"))

    # Syncronize users 
    spread = config.get("sync", "account_spread")
    log.info("Syncronizing users, spread %s" % spread)
    s.view.set_account_spread(s.tr.get_spread(spread))
    user.begin(encoding, incr, add, update, delete)
    try:
        accounts = s.get_accounts()
        log.debug("Antall brukere i get_accounts: %d" % len(accounts))
        for account in accounts:
            if account.posix_uid == -1: continue # Possible at all?
            if account.full_name == "": continue # Do not add system users to ou=users
            user.add(account)
    except IOError,e:
        log.error("Exception %s occured, aborting" % e)
    else:
        user.close()

    # Syncronize persons
    log.info("Syncronizing persons")
    persons.begin(encoding, incr, add, update, delete)
    try:
        for person in [p for p in s.get_persons() if p.primary_account != -1]:
            persons.add(person)
    except IOError,e:
        log.error("Exception %s occured, aborting" % e)
    else:
        persons.close()

    # Syncronize groups
    log.info("Syncronizing groups")
    groups.begin(encoding, incr, add, update, delete)
    try:
        for group in s.get_groups():
            if group.posix_gid == None: continue
            groups.add(group)
    except IOError,e:
        log.error("Exception %s occured, aborting" % e)
    else:
        groups.close()

    log.info("Final closing")
    s.close()
    log.info("Done")

    if incr or ( not incr and add and update and delete ):
        log.debug("Storing changelog-id %ld", server_id)
        file(spine_cache, 'w').write( str(server_id) )

if __name__ == "__main__":
    main()

# arch-tag: 7c77c215-87d0-47da-8ccd-a967768a3321
