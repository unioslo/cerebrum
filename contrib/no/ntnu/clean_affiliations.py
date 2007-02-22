#! /usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright 2007 University of Oslo, Norway
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

# Clean out manually registered affiliation if an equivalent affiliation
# has been registered by an authoritative system.


import cerebrum_path
from Cerebrum import Utils
from Cerebrum import Person

Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='clean_affiliations')

p = Factory.get('Person')(db)

auto = sets.Set()
manual = sets.Set()

for person,ou,aff,source,status,dd,cd in p.list_affiliations():
    if source == co.system_manual:
        manual.add((person, ou, aff))
    else:
        auto.add((person, ou, aff))

count=0
for person,ou,aff in manual.intersection(auto):
    # Use delete_date?
    p.clear()
    p.find(person)
    p.delete_affiliation(ou, aff, co.system_manual)
    p.write_db()
    count++

printf "removed %d manual affiliations" % count

db.commit()
