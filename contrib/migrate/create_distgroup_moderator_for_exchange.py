#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2014 University of Oslo, Norway
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
"""Simple script that creates the first distributiongroup in Cerebrum.
If you want some other group name, you will add getopt-stuff to this script!
Or else!!1
"""
import sys

from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailDomain
from Cerebrum.modules.Email import EmailAddress
from Cerebrum.modules.Email import EmailPrimaryAddressTarget

db = Factory.get('Database')()
db.cl_init(change_program='create_dg_moderator')
ac = Factory.get('Account')(db)
co = Factory.get('Constants')(db)
dg = Factory.get('DistributionGroup')(db)
gr = Factory.get('Group')(db)
et = Factory.get('EmailTarget')(db)
epat = EmailPrimaryAddressTarget(db)
ed = EmailDomain(db)
ea = EmailAddress(db)


group_name = 'groupadmin'

if len(sys.argv) > 1:
    group_domain = sys.argv[1]
else:
    group_domain = 'groups.uio.no'

ac.clear()
ac.find_by_name('bootstrap_account')

gr.clear()
gr.populate(
    creator_id=ac.entity_id,
    visibility=co.group_visibility_all,
    name='groupadmin',
    description='Default group moderator',
    group_type=co.group_type_unknown,
)
gr.write_db()

et.clear()
et.populate(co.email_target_dl_group, gr.entity_id, co.entity_group)
et.write_db()

ed.clear()
ed.find_by_domain(group_domain)
lp = 'dl-admin'

ea.clear()
ea.populate(lp, ed.entity_id, et.entity_id, expire=None)
ea.write_db()

epat.clear()
epat.populate(ea.entity_id, parent=et)
epat.write_db()

dg.clear()
dg.populate(roomlist='F', hidden='T', parent=gr)
dg.write_db()

db.commit()
