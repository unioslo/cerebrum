#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2012 University of Oslo, Norway
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

"""Generate LDIF for the services tree.

This has LDAP users and passwords for some services which use LDAP.

Quick hack.  TODO:
- Use a spread instead of cereconf to pick the users.
- Obey quarantines - after deciding which ones.
- We want password expiry messages to these users.
"""

import sys

import cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.LDIFutils import LDIFWriter
from Cerebrum.QuarantineHandler import QuarantineHandler

def main():
    logger = Factory.get_logger("cronjob")
    db = Factory.get('Database')()
    const = Factory.get("Constants")(db)
    account = Factory.get('Account')(db)
    auth_prefix, auth_method = "{crypt}", int(const.auth_type_md5_crypt)

    ldif = LDIFWriter('SERVICES', None)
    dn = ldif.getconf('dn')
    ldif.write_container()
    for username in ldif.getconf('users'):
        account.clear()
        try:
            account.find_by_name(username)
        except Errors.NotFoundError:
            logger.error("User '%s' not found" % username)
            sys.exit(1)
        passwd = None
        qh = QuarantineHandler.check_entity_quarantines(db, account.entity_id)
        if not (qh.should_skip() or qh.is_locked()):
            try:
                passwd = account.get_account_authentication(auth_method)
            except Errors.NotFoundError:
                logger.warn("Password not found for user %s", username)
        ldif.write_entry("cn=%s,%s" % (username, dn), {
            'description': "Note: The password is maintained in Cerebrum.",
            'objectClass': ('applicationProcess', 'simpleSecurityObject'),
            'userPassword': auth_prefix + (passwd or "*locked")})
    ldif.close()

if __name__ == '__main__':
    main()
