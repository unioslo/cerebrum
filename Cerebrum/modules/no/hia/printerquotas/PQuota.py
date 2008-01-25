#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

"""
This file is a HiA-specific extension of Cerebrum. The purpose of this
script is to keep track of printer quota updates for students at HiA.
The actual accounting is done in eDir.

- finn fram alle som har betalt semavg (STATUS_BET_OK='J')
- sjekk blant disse om sem_quota_up er oppdatert for inneværende semester
  (1. januar, 1. juli)
- finn fram alle account.accountBalance fra eDir for de sem_quota_up ikke
  er oppdatert for inneværende semester
- sett sem_quota_up til now()
- sett account.accountBalance = old + NW_PR_QUOTA
"""
import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hia import EdirLDAP
from Cerebrum.DatabaseAccessor import DatabaseAccessor

import string
import time

class PQuota(DatabaseAccessor):
    def __init__(self, db):
        super(PQuota, self).__init__(db)
        t = time.localtime()[0:3]
        self.year = t[0]
        self.month = t[1]
        
    def find(self, person_id):
        return self.query_1(
            """SELECT term_quota_updated, year_quota_updated,
                      total_quota
               FROM [:table schema=cerebrum name=pquota_status]
               WHERE person_id=:person_id""", {'person_id':person_id})

    def list_updated(self):
        return self.query(
            """SELECT person_id
               FROM [:table schema=cerebrum name=pquota_status]
               WHERE term_quota_updated='%s' AND
                     year_quota_updated=%s""" % (self._get_term(), self.year))

    def insert_new_quota(self, person_id):
        binds = {
            'person_id': person_id,
            'total_quota': int(0)}
        return self.execute(
            """INSERT INTO [:table schema=cerebrum name=pquota_status]
            (%s) VALUES (%s)""" % (", ".join(binds.keys()),
                                   ", ".join([":%s" % k for k in binds.keys()])),
            binds)

    def update_free_quota(self, person_id):
        binds = {'person_id': person_id}
        set = "term_quota_updated='%s'," % self._get_term()
        set += "year_quota_updated=%s" % self.year
        return self.execute(
            """UPDATE [:table schema=cerebrum name=pquota_status]
               SET %s
               WHERE person_id=:person_id""" % set, binds)
                                                
    def update_total(self, person_id, total):
        set = 'total_quota=%s' % total
        binds = {'person_id': person_id} 
        return self.execute(
            """UPDATE [:table schema=cerebrum name=pquota_status]
               SET %s
               WHERE person_id=:person_id""" % set, binds)

    def delete_quota(self, person_id):
        return self.execute(
            """DELETE FROM [:table schema=cerebrum name=pquota_status]
            WHERE person_id=:person_id""", {'person_id':person_id})
    
    def _get_term(self):
        term = 'H'
        if self.month <= 6:
            term = 'V'
        return term



# arch-tag: b093c760-6309-11da-8279-5543ac51fde0
