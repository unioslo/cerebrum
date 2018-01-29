#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 University of Oslo, Norway
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

import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum import Errors

db=Factory.get("Database")()
co=Factory.get("Constants")(db)
person=Factory.get("Person")(db)

class statdict(dict):
    def inc(self, key):
        self[key] = self.get(key, 0) + 1

naffs = 0
naffs_by_type = statdict()
naffs_by_subtype = statdict()
naffs_by_ou = statdict()
naffs_by_ou_type = statdict()
naffs_by_ou_subtype = statdict()

npaffs = 0
npaffs_by_type = {}
npaffs_by_subtype = {}
npaffs_by_ou = {}
npaffs_by_ou_type = {}
npaffs_by_ou_subtype = {}

allaffs = set()
allstatus = set()
allous = set()

def fetch_statistics():
    # There is no API to do select count(...)
    # Therefore this method (a single full select)
    # should put the least strain on the db
    paffs = set()
    paffs_by_type = {}
    paffs_by_subtype = {}
    paffs_by_ou = {}
    paffs_by_ou_type = {}
    paffs_by_ou_subtype = {}
    global naffs
    global npaffs
    #
    affs=person.list_affiliations()
    for a in affs:
        naffs += 1
        naffs_by_type.inc(a["affiliation"])
        naffs_by_subtype.inc(a["status"])
        naffs_by_ou.inc(a["ou_id"])
        naffs_by_ou_type.inc((a["ou_id"], a["affiliation"]))
        naffs_by_ou_subtype.inc((a["ou_id"], a["status"]))
        paffs.add(a["person_id"])
        paffs_by_type.setdefault(a["affiliation"], set()).add(a["person_id"])
        paffs_by_subtype.setdefault(a["status"], set()).add(a["person_id"])
        paffs_by_ou.setdefault(a["ou_id"], set()).add(a["person_id"])
        paffs_by_ou_type.setdefault((a["ou_id"], a["affiliation"]), set()).add(a["person_id"])
        paffs_by_ou_subtype.setdefault((a["ou_id"], a["status"]), set()).add(a["person_id"])
        allaffs.add(a["affiliation"])
        allstatus.add(a["status"])
        allous.add(a["ou_id"])

    npaffs = len(paffs)
    for k, v in paffs_by_type.items(): npaffs_by_type[k] = len(v)
    for k, v in paffs_by_subtype.items(): npaffs_by_subtype[k] = len(v)
    for k, v in paffs_by_ou.items(): npaffs_by_ou[k] = len(v)
    for k, v in paffs_by_ou_type.items(): npaffs_by_ou_type[k] = len(v)
    for k, v in paffs_by_ou_subtype.items(): npaffs_by_ou_subtype[k] = len(v)

def print_affiliation_summary():
    status_by_aff = {}
    for s in allstatus:
        s = co.PersonAffStatus(s)
        status_by_aff.setdefault(s.affiliation, set()).add(s)   

    print "%-29s %9s %9s" % ("", "#persons", "#affs")
    print "%-29s %9d %9d" % ("total", npaffs, naffs)
    for a in allaffs:
        a = co.PersonAffiliation(a)
        print "%-29s %9d %9d" % (str(a), npaffs_by_type[a], naffs_by_type[a])
        for s in status_by_aff.get(a, []):
            print "%-29s %9d %9d" % (str(s), npaffs_by_subtype[s], naffs_by_subtype[s])

fetch_statistics()
print_affiliation_summary()


