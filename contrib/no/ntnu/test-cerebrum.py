#! /usr/bin/env python
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

#
# Test availability of cerebrum database.
#

import cerebrum_path
from Cerebrum import Utils

Factory = Utils.Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
db.cl_init(change_program='test')

acc = Factory.get('Account')(db)
acc.find_by_name("bootstrap_account")
print "OK found %s" % acc.get_name(co.account_namespace)
