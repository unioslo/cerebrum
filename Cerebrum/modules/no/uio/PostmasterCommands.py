#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011, 2012 University of Oslo, Norway
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
"""Cerebrum functionality for Postmaster's webservice.

"""

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory

class Commands:
    """The available commands for the postmaster webservice. The public commands
    are in the Postmaster server, which calls this class for the Cerebrum
    functionality.

    This class is instantiated for each incoming call, and closed and destroyed
    after each call. Note that we should explicitly shut down db connections,
    since the server could run many connections in parallell.

    Note that this class should be independent of what server and communication
    form we are using.

    """

    def __init__(self):
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)

    def close(self):
        """Explicitly close the current instance of this class. This is to make
        sure that all is closed down correctly, even if the garbace collector
        can't destroy the instance. For now, this means the database link.
        """
        if hasattr(self, 'db'):
            try:
                self.db.close()
            except Exception, e:
                log.warning("Problems with db.close: %s" % e)

    def _get_aff_status(self, input):
        """Return a list of CerebrumCodes for given affiliation or affilation
        status strings, e.g. 'STUDENT', 'STUDENT/aktiv' and
        'ANSATT/vitenskapelig'. Returned in two lists, affs and statuses.
        """
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

    def _get_ous(self, skos):
        """Return ou_ids for given skos. If the sko is not complete, its sub
        OUs are returned as well.
        """
        ou = Factory.get('OU')(self.db)
        ou_ids = []
        for sko in skos:
            ou_ids += [ous['ou_id'] for ous in 
                             ou.get_stedkoder(fakultet=sko[:2] or None,
                                              institutt=sko[2:4] or None,
                                              avdeling=sko[4:6] or None)]
        return ou_ids

    def get_addresses_by_affiliation(self, status, source, skos=None):
        """Find persons that has the given affiliations/statuses from the given
        source systems and at the given stedkoder (SKOs), if any. Return a list
        of all the persons' primary e-mail addresses.

        Note that some persons might not have any user affiliations, thus having
        no *primary* affiliation, even if they have user accounts with e-mail
        addresses.

        """
        affs = stats = ou_ids = None
        if status:
            affs, stats = self._get_aff_status(status)
        if source:
            source = [self.co.AuthoritativeSystem(s) for s in source]
        if skos:
            ou_ids = self._get_ous(skos)
            if not ou_ids:
                raise Errors.CerebrumRPCException('OUs not found')

        pe = Factory.get('Person')(self.db)

        pe2email = dict(pe.list_primary_email_address(self.co.entity_person))
        rows = []
        if affs:
            rows += pe.list_affiliations(affiliation=affs, ou_id=ou_ids)
        if stats:
            rows += pe.list_affiliations(status=stats, ou_id=ou_ids)

        ret = set(pe2email[row['person_id']] for row in rows
                  if pe2email.has_key(row['person_id']))
        print 'DEBUG: Returning %d e-mail addresses' % len(ret)
        return ret

