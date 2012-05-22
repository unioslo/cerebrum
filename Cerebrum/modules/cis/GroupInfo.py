#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2010, 2011, 2012 University of Oslo, Norway
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

import random, hashlib
import string, pickle
from mx.DateTime import RelativeDateTime, now
import twisted.python.log

import cereconf, cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory

class SimpleLogger(object):
    """Simple logger that has the same API as the Cerebrum logger, but uses
    twisted's logger.
    """
    def __init__(self):
        pass

    def _log(self, *args):
        """The logger."""
        # join is supposed to be faster than string concatenation
        twisted.python.log.msg(' '.join(args))

    def error(self, msg):
        self._log('ERROR:', msg)

    def warning(self, msg):
        self._log('WARNING:', msg)

    def info(self, msg):
        self._log('INFO:', msg)

    def debug(self, msg):
        self._log('DEBUG:', msg)

## Globals
log = SimpleLogger()

class GroupInfo(object):


    def __init__(self):
        self.db = Factory.get('Database')()
        self.db.cl_init(change_program='group_service')
        self.co = Factory.get('Constants')(self.db)
        self.grp = Factory.get("Group")(self.db)

    def close(self):
        """Explicitly close this instance of the class. This is to make sure
        that all is closed down correctly, even if the garbage collector can't
        destroy the instance."""
        log.warning("GroupInfo. Closing itself.")
        if hasattr(self, 'db'):
            try:
                self.db.close()
            except Exception, e:
                log.warning("Problems with db.close: %s" % e)
        else:
            # TODO: this could be removed later, when it is considered stable
            log.warning("db doesn't exist")

    def search_members_flat(self, groupname):
        account = Factory.get("Account")(self.db)
        try:
            self.grp.clear()
            self.grp.find_by_name(groupname)
        except Errors.NotFoundError:
            raise Errors.CerebrumRPCException

        grp_id = self.grp.entity_id

        self.grp.clear()
        members = []
        for row in self.grp.search_members(group_id=grp_id):
            entry = {}
            entry['member_type'] = str(self.co.EntityType(row['member_type']))
            entry['member_id'] = str(row['member_id'])
            try:
                account.clear()
                account.find(row['member_id'])
                entry['uname'] = account.get_account_name()
            except  Errors.NotFoundError:
                entry['uname'] = 'Not found'
                log.warning("Member account %s not found." %entry['member_id'])
            members.append(entry)
        return members

