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
from ceresync import syncws as sync
from ceresync import config

import os
import sys
import socket

log = config.logger

class OURegister(object):
    """ OrganizationalUnit, where people work or students follow studyprograms.
    Needs name,id and parent as minimum.
    """

    def __init__(self):
        self.__data = {}

    def add(self, obj):
        self.__data[obj.id] = obj

    def get_path(self, key, path=None):
        path = path or []

        if key in self.__data:
            value = self.__data[key]
            path.append(value)
            return self.get_path(value.parent_id, path)

        return reversed(path)

    def get_acronym_list(self, key):
        return [ou.acronym.encode("utf-8") for ou in self.get_path(key)]

    def get_acronym(self, key):
        ou = self.__data.get(key)
        if ou:
            return ou.acronym.encode("utf-8")
        return ""

def load_changelog_id(changelog_file):
    local_id = 0
    if os.path.isfile(changelog_file):
        local_id = long(open(changelog_file).read())
        log.info("Loaded changelog-id %ld", local_id)
    else:
        log.info("Default changelog-id %ld", local_id)
    return local_id

def save_changelog_id(server_id, changelog_file):
    log.info("Storing changelog-id %ld", server_id)
    open(changelog_file, 'w').write(str(server_id))

def set_incremental_options(options, incr, server_id, changelog_file):
    if not incr:
        return

    local_id = load_changelog_id(changelog_file)
    log.debug("Local id: %ld, server_id: %ld", local_id, server_id)
    if local_id > server_id:
        log.warning("local changelogid is larger than the server's!")
    elif incr and local_id == server_id:
        log.info("No changes to apply. Quiting.")
        sys.exit(0)

    options['incr_from'] = local_id

def set_encoding_options(options, config):
    options['encode_to'] = 'utf-8'

def main():
    options = config.make_bulk_options() + config.make_testing_options()
    config.parse_args(options)
    changelog_file = config.get("sync","changelog_file", 
                                default="/var/lib/cerebrum/lastchangelog.id")

    incr = config.getboolean('args','incremental', allow_none=True)
    add = config.getboolean('args','add')
    update = config.getboolean('args','update')
    delete = config.getboolean('args','delete')
    using_test_backend = config.getboolean('args', 'use_test_backend')

    if incr is None:
        log.error("Invalid arguments. You must provide either the --bulk or the --incremental option")
        sys.exit(1)

    log.info("Setting up CereWS connection")
    try:
        s = sync.Sync(locking=not using_test_backend)
        server_id = s.get_changelogid()
    except sync.AlreadyRunningWarning, e:
        log.error(str(e))
        sys.exit(1)
    except sync.AlreadyRunning, e:
        log.error(str(e))
        sys.exit(1)
    except socket.error, e:
        log.error("Unable to connect to web service: %s", e)
        sys.exit(1)

    sync_options = {}
    set_incremental_options(sync_options, incr, server_id, changelog_file)
    config.set_testing_options(sync_options)
    set_encoding_options(sync_options, config)

    systems = config.get('ldap', 'sync', default='').split()
    for system in systems:
        log.info("Syncing system %s", system)
        if using_test_backend:
            backend = get_testbackend(s, system)
        else:
            backend = get_ldapbackend(s, system)

        backend.begin(
            incr=incr,
            bulk_add=add,
            bulk_update=update,
            bulk_delete=delete)

        for entity in get_entities(s, system, sync_options):
            backend.add(entity)
        backend.close()

    if incr or (add and update and delete):
        save_changelog_id(server_id, changelog_file)

def get_conf(system, name, default=None):
    conf_section = 'ldap_%s' % system
    if default is not None:
        return config.get(conf_section, name, default=default)
    return config.get(conf_section, name)

def get_testbackend(s, system):
    import ceresync.backend.test as testbackend
    backend_class = get_conf(system, "backend")

    if (backend_class == "PosixUser"):
        return testbackend.Account()
    elif (backend_class == "PosixGroup"):
        return testbackend.Group()
    elif (backend_class in ("Person", "FeidePerson")):
        return testbackend.Person()
    elif (backend_class == "OU"):
        return testbackend.OU()
    else:
        raise NotImplementedError("Haven't faked %s, and didn't plan on it." % backend_class)

def get_ldapbackend(s, system):
    from ceresync.backend import ldapbackend

    backend_class = get_conf(system, "backend")
    base = get_conf(system, "base")
    filter = get_conf(system, "filter", default="(objectClass='*')")
    backend = getattr(ldapbackend, backend_class)

    if backend_class in ("Person", "FeidePerson", "OracleCalendar"):
        register = OURegister()
        for ou in s.get_ous():
            register.add(ou)

        return backend(base=base, filter=filter, ouregister=register)

    if backend_class in ("AccessCardHolder",):
        register = OURegister()
        for ou in s.get_ous():
            register.add(ou)

        affiliations = get_conf(system, "affiliations").strip().split(" ")
        return backend(base=base, filter=filter, affiliations=affiliations, ouregister=register)
        
    log.info("Initializing %s backend with base %s", backend_class, base)
    return backend(base=base, filter=filter)

def get_entities(s, system, sync_options):
    entity = get_conf(system, "entity")
    backend_class = get_conf(system, "backend")

    my_options = sync_options.copy()

    if backend_class in ("OracleCalendar",):
        my_options['include_affiliations'] = True

    if entity == 'account':
        my_options['accountspread'] = get_conf(system, "spread")
    return getattr(s, "get_%ss" % entity)(**my_options)

if __name__ == "__main__":
    main()
