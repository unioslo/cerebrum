# -*- coding: utf-8 -*-
# Copyright 2004-2019 University of Oslo, Norway
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
PosixLDIF customization for UiT.
"""
from __future__ import unicode_literals

import logging

from Cerebrum.Utils import Factory
from Cerebrum.modules import LDIFutils
from Cerebrum.modules.PosixLDIF import PosixLDIF
from Cerebrum.modules.posix.UserExporter import make_clock_time


logger = logging.getLogger(__name__)
clock_time = make_clock_time(logger)


class PosixLDIF_UiTMixin(PosixLDIF):  # noqa: N801
    """PosixLDIF mixin class providing functionality specific to UiT."""

    def write_user_objects_head(self, f):
        # UiT: Add a system object
        entry = {'objectClass': ['top', 'uioUntypedObject']}
        ou_dn = "cn=system,dc=uit,dc=no"
        f.write(LDIFutils.entry_string(ou_dn, entry))

        super(PosixLDIF_UiTMixin, self).write_user_objects_head(f)

    def init_user(self, *args, **kwargs):
        # Prepare to include eduPersonAffiliation, taken from OrgLDIF.
        self.org_ldif = Factory.get('OrgLDIF')(self.db)
        self.org_ldif.init_edu_person_aff_lookup()

        super(PosixLDIF_UiTMixin, self).init_user(*args, **kwargs)

        self.account_aff = account_aff = {}
        for arow in self.posuser.list_accounts_by_type():
            val = (arow['affiliation'], int(arow['ou_id']))
            account_id = int(arow['account_id'])
            if account_id in account_aff:
                account_aff[account_id].append(val)
            else:
                account_aff[account_id] = [val]

    def user_object(self, row):
        account_id = row['account_id']

        if account_id in self.quarantines:
            logger.info('Skipping quarantined account_id=%r (%r)',
                        account_id, self.quarantines[account_id])
            dn, entry = None, None
        else:
            dn, entry = super(PosixLDIF_UiTMixin, self).user_object(row)

        if entry:
            # Add displayName, norEduPersonLegalName and
            # objectClass: norEduPerson
            if 'displayName' in entry:
                entry['displayName'].extend(entry['cn'])
            else:
                entry['displayName'] = entry['cn']

            if 'norEduPersonLegalName' in entry:
                entry['norEduPersonLegalName'].extend(entry['cn'])
            else:
                entry['norEduPersonLegalName'] = entry['cn']

            entry['objectClass'].extend(('norEduPerson', 'uitAccount',))
        return dn, entry

    def update_user_entry(self, account_id, entry, owner_id):
        # eduPersonAffiliation (taken from OrgLDIF)
        added = self.org_ldif.affiliations.get(owner_id)
        if added:
            added = LDIFutils.attr_unique(self.org_ldif.select_list(
                self.org_ldif.eduPersonAff_selector, owner_id, added))
            if added:
                entry['eduPersonAffiliation'] = added
        entry['objectClass'].append('eduPerson')

        return super(PosixLDIF_UiTMixin, self).update_user_entry(
            account_id, entry, owner_id)
