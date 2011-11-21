#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 
# Copyright 2011 University of Oslo, Norway
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
"""Cerebrum functionality for Postmaster's webservice."""

import cereconf, cerebrum_path
from Cerebrum import Errors
from Cerebrum.Utils import Factory

class Commands:
    """The available commands for the postmaster webservice."""

    def __init__(self):
        self.db = Factory.get('Database')()
        #self.db.cl_init(change_program='postmaster_webservice')
        self.co = Factory.get('Constants')(self.db)

    def _get_aff_status(self, input):
        """Return a list of CerebrumCodes for given affiliation or affilation
        status strings, e.g. 'STUDENT', 'STUDENT/aktiv' and
        'ANSATT/vitenskapelig'. Returned in two lists, affs and statuses."""
        affs  = list()
        stats = list()
        for string in input:
            try:
                aff, status = string.split('/', 1)
            except ValueError:
                affs.append(self.co.PersonAffiliation(string))
            else:
                stats.append(self.co.PersonAffStatus(self.co.PersonAffiliation(aff), status))
        return (affs, stats)

    def get_addresses_by_affiliation(self, status, source, ous=None):
        affs = stats = None
        if status:
            affs, stats = self._get_aff_status(status)
        if source:
            source = [self.co.AuthoritativeSystem(s) for s in source]
        if None: 
            ous     = 'xxx'

        pe = Factory.get('Person')(self.db)

        pe2email = dict(pe.list_primary_email_address(self.co.entity_person))
        rows = []
        if affs:
            rows += pe.list_affiliations(affiliation=affs)
        if status:
            rows += pe.list_affiliations(status=stats)

        ret = set(pe2email[row['person_id']] for row in rows
                  if pe2email.has_key(row['person_id']))
        print 'DEBUG: Returning %d e-mail addresses' % len(ret)
        return ret

