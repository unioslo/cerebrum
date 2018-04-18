# -*- coding: utf-8 -*-

# Copyright 2003 University of Oslo, Norway
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
from __future__ import unicode_literals

import xml.sax
from time import localtime, strftime, time

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _SpreadCode


class AutostudError(Exception):
    pass


class LookupHelper(object):
    def __init__(self, db, logger, ou_perspective):
        self._db = db
        self._logger = logger
        self.spread_name2const = {}
        self._group_cache = {}
        self._sko_cache = {}
        self._ou_perspective = ou_perspective

        self.const = Factory.get('Constants')(self._db)
        for c in dir(self.const):
            const = getattr(self.const, c)
            if isinstance(const, _SpreadCode):
                self.spread_name2const[str(const)] = const
        self._cached_affiliations = [None]
        self._lookup_errors = []

    def _add_error(self, msg):
        self._lookup_errors.append(msg)

    def get_lookup_errors(self):
        return self._lookup_errors

    def get_spread(self, name):
        try:
            return self.spread_name2const[name]
        except KeyError:
            self._add_error("bad spread: {}".format(name))
            return None

    def get_group(self, name):
        if self._group_cache.has_key(name):
            return self._group_cache[name]
        group = Factory.get('Group')(self._db)
        group.clear()
        try:
            group.find_by_name(name)
            self._group_cache[name] = int(group.entity_id)
        except (Errors.NotFoundError, ValueError):
            self._group_cache[name] = None
            self._add_error("ukjent gruppe: {}".format(name))
        return self._group_cache[name]

    def get_stedkode(self, name, institusjon):
        if self._sko_cache.has_key(name):
            return self._sko_cache[name]
        try:
            ou = Factory.get('OU')(self._db)
            fak = int(name[:2])
            inst = int(name[2:4])
            gr = int(name[4:])
            ou.clear()
            ou.find_stedkode(fak, inst, gr, institusjon)
            self._sko_cache[name] = int(ou.entity_id)
        except (Errors.NotFoundError, ValueError):
            self._sko_cache[name] = None
            self._add_error("ukjent sko: {}".format(name))
        return self._sko_cache[name]

    def get_all_child_sko(self, sko):
        ret = []
        ou = Factory.get('OU')(self._db)
        ou.find(sko)
        ret.append("{:02d}{:02d}{:02d}".format(
            ou.fakultet, ou.institutt, ou.avdeling))
        for row in ou.list_children(self._ou_perspective, recursive=True):
            ou.clear()
            ou.find(row['ou_id'])
            ret.append("{:02d}{:02d}{:02d}".format(
                ou.fakultet, ou.institutt, ou.avdeling))
        return ret

    def get_person_affiliations(self, fnr=None, person_id=None):
        # We only need to cache the last entry as input is sorted by fnr
        if self._cached_affiliations[0] is None or (
                not (self._cached_affiliations[0] in (fnr, person_id))):
            person = Factory.get('Person')(self._db)
            if fnr is not None:
                person.find_by_external_id(self.const.externalid_fodselsnr,
                                           fnr, source_system=self.const.system_fs)
            else:
                person.find(person_id)
            ret = []
            for row in person.get_affiliations():
                ret.append({
                    'ou_id': int(row['ou_id']),
                    'affiliation': int(row['affiliation']),
                    'status': int(row['status'])})
            if fnr is None:
                self._cached_affiliations = (fnr, ret)
            else:
                self._cached_affiliations = (person_id, ret)
        return self._cached_affiliations[1]
