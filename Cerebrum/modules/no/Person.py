# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

import re
import cereconf
from Cerebrum import Person

class PersonFnrMixin(Person.Person):
    """Methods to get Norwegian fodselsnummer information."""

    def __init__(self, db):
        self.__super.__init__(db)
        self._fnr_sources = dict(zip(
            [int(getattr(self.const,s)) for s in cereconf.SYSTEM_LOOKUP_ORDER],
            range(-len(cereconf.SYSTEM_LOOKUP_ORDER), 0)))

    # Rough check for valid fodselsnummer
    check_fnr = re.compile(r'[0-7]\d[0156]\d{8}\Z').match

    def preferred_fnr(self, person_id, nums=None):
        """Return person_id's preferred fodselsnr, from nums if given, or None.

        <nums> is either None or a sequence with <person_id>'s fodselsnrs.
        Prefer permanent nums over B-nums over fake nums.
        Reject severely malformed nums.
        With several equally good nums, choose by cereconf.SYSTEM_LOOKUP_ORDER
        (unless self._fnr_sources is overridden)."""
        selected = None
        select = "SELECT external_id, source_system" \
                 " FROM [:table schema=cerebrum name=person_external_id]" \
                 " WHERE person_id = %d AND id_type = %d"
        if nums is None:
            selected = self.query(select %
                                  (person_id, self.const.externalid_fodselsnr))
            nums = [s[0] for s in selected]
        # Prefer permanent nums over B-nums over fake nums. Skip very bad nums.
        best_nums = {}
        best_score = 0
        for fnr in filter(self.check_fnr, nums):
            if fnr[2] > '4' or fnr[6] == '9':
                score = 1               # Fake number from FS or LT
            elif fnr[0] > '3':
                score = 2               # B-number (6 months lifetime)
            else:
                score = 3               # Permanent number
            if score > best_score:
                best_score = score
                best_nums = {fnr: True}
            elif score == best_score:
                best_nums[fnr] = True
        if len(best_nums) < 2:
            return (best_nums.keys() or (None,))[0]
        # Several equally good numbers.  Choose by preferred source system.
        nums = []
        if selected is None:
            selected = self.query(select %
                                  (person_id, self.const.externalid_fodselsnr))
        for fnr, source in selected:
            if fnr in best_nums:
                nums.append((self._fnr_sources.get(int(source), 1), fnr))
        if nums:
            nums.sort()
            return nums[0][1]
        # The supplied numbers are not in the database.
        return None

    def getdict_fodselsnr(self, users_only=False):
        """Return a dict {person_id: fodselsnr}.

        Some values may be objects that must be converted to strings.
        If users_only, only return persons with accounts with affiliations."""
        result = {}                     # {person_id: fodselsnr}
        multi = {}                      # {person_id: {fodselsnr: 0}}
        f = "[:table schema=cerebrum name=entity_external_id] eei"
        if users_only:
            f += " JOIN [:table schema=cerebrum name=account_type] at" \
                 " ON at.person_id=eei.entity_id"
        for person_id, fnr in self.query("""
            SELECT DISTINCT eei.entity_id, eei.external_id FROM %s
            WHERE eei.id_type = %d""" % (f, self.const.externalid_fodselsnr)):
            person_id = int(person_id)
            if result.setdefault(person_id, fnr) is not fnr:
                multi.setdefault(person_id, {result[person_id]: 0})[fnr] = 0
        if multi:
            # Handle persons with several different fodselsnrs:
            # Defer the choice of which number to use until it is used,
            # since many of the entries in the dict may be left unused.
            class fnr_selector(object):
                __slots__ = ('args', 'val')
                def __init__(self, *args):
                    self.args = args
                def __str__(self):
                    if self.args:
                        self.val = self.preferred_fnr(*self.args) or ''
                        self.args = False
                    return self.val
                def __nonzero__(self):
                    return bool(self.__str__())
            fnr_selector.preferred_fnr = self.preferred_fnr
            for person_id, nums in multi.iteritems():
                result[person_id] = fnr_selector(person_id, nums.keys())
        return result

# arch-tag: 64f8187c-3b85-401b-b11d-8c5ab1c41049
