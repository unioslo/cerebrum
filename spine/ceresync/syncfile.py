#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005, 2006 University of Oslo, Norway
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

from ceresync import syncws as sync
from ceresync import config
import re
from sys import exit

log = config.logger

name_regex=re.compile("^[A-Za-z0-9_-]+$")
def check_account(account):
    if not name_regex.match(account.name):
        return "Bad accountname"
    if not account.posix_uid >= 1000:
        return "Bad uid (%s)" % account.posix_uid
    if not account.posix_gid >= 1000:
        return "Bad gid (%s)" % account.posix_gid
    if account.passwd == "":
        account.passwd = "x"
    return None

def check_group(group):
    if not name_regex.match(group.name):
        return "Bad groupname"
    if not group.posix_gid >= 1000:
        return "Bad gid (%s)" % group.posix_gid
    for n in group.members:
        if not name_regex.match(n):
            group.members.remove(n)
    return None


def main():
    sync_options = {}
    config.parse_args(config.make_testing_options())
    config.set_testing_options(sync_options)

    try:
        s = sync.Sync()
    except sync.AlreadyRunningWarning, e:
        log.warning(str(e))
        exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        exit(1)

    if config.getboolean('args', 'use_test_backend'):
        import ceresync.backend.test as filebackend
    else:
        import ceresync.backend.file as filebackend

    accounts = filebackend.Account()
    groups = filebackend.Group()
    primary_group = {}

    log.debug("Syncronizing accounts")
    accounts.begin(unicode=True)
    try:
        for account in s.get_accounts(**sync_options):
            log.debug("Processing account '%s'", account.name)
            primary_group[account.name]=account.primary_group
            fail = check_account(account)
            if not fail: 
                accounts.add(account)
            else:
                log.warning("Skipping account '%s', reason: %s",
                            account.name,fail) 
    except IOError,e:
        log.error("Exception %s occured, aborting",e)
    else:
        accounts.close()

    log.debug("Syncronizing groups")
    groups.begin(unicode=True)
    try:
        for group in s.get_groups(**sync_options):
            fail = check_group(group)
            group.members = [m for m in group.members
                             if (primary_group.get(m) is not None and
                                 primary_group.get(m) != group.name)]
            if not fail:
                groups.add(group)
            else:
                log.warning("Skipping group '%s', reason: %s",group.name, fail)
    except IOError,e:
        log.error("Exception %s occured, aborting",e)
    else:
        groups.close()

if __name__ == "__main__":
    main()
