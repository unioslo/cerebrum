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

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Account

class AutoPriorityAccountMixin(Account.Account):

    def set_account_type(self, ou_id, affiliation, priority=None):
        if priority is None:
            priority = self._calculate_account_priority(ou_id, affiliation)
        return self.__super.set_account_type(ou_id, affiliation, priority)

    def _calculate_account_priority(self, ou_id, affiliation,
                                    current_pri=None):
        # Determine the status this affiliation resolves to
        if self.owner_id is None:
            raise ValueError, "non-owned account can't have account_type"
        person = Factory.get('Person')(self._db)
        status = None
        for row in person.list_affiliations(person_id=self.owner_id,
                                            include_deleted=True):
            if row['ou_id'] == ou_id and row['affiliation'] == affiliation:
                status = self.const.PersonAffStatus(
                    row['status'])._get_status()
                break
        if status is None:
            raise ValueError, "Person don't have that affiliation"
        affiliation = str(self.const.PersonAffiliation(int(affiliation)))

        # Find the range that we resolve to
        pri_ranges = cereconf.ACCOUNT_PRIORITY_RANGES
        if not isinstance(pri_ranges, dict):
            return None
        if not affiliation in pri_ranges:
            affiliation = '*'
        if not status in pri_ranges[affiliation]:
            status = '*'
        pri_min, pri_max = pri_ranges[affiliation][status]

        if pri_min <= current_pri < pri_max:
            return current_pri
        # Find taken values in this range and sort them
        taken = []
        for row in self.get_account_types(all_persons_types=True,
                                          filter_expired=False):
            taken.append(int(row['priority']))
        taken = [x for x in taken if x >= pri_min and x < pri_max]
        taken.sort()
        if (not taken):
            taken.append(pri_min)
        new_pri = taken[-1] + 2
        if new_pri < pri_max:
            return new_pri

        # In the unlikely event that the previous taken value was at the
        # end of the range
        new_pri = pri_max - 1
        while new_pri >= pri_min:
            if new_pri not in taken:
                return new_pri
            new_pri -= 1
        raise ValueError, "No free priorities for that account_type!"

# arch-tag: 47a2c496-b8e5-4674-a3ef-6f5745b91e0c
