#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2003-2015 University of Oslo, Norway
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
""" The CLDatabase combines the Database driver and the ChangeLog Event-API.

This class enables synchronization between the database transasction
commit/rollback with the ChangeLog commit/rollback.

When using the ChangeLog, you'll want to replace the `cereconf.CLASS_DATABASE'
with this class, or use this class as a mixin for the
`cereconf.CLASS_DATABASE'.

"""
from Cerebrum.Utils import Factory
db = Factory.get('DBDriver')
cl = Factory.get('ChangeLog')


class CLDatabase(db, cl):

    def __init__(self, *args, **kwd):
        self.cl_init()
        super(CLDatabase, self).__init__(*args, **kwd)

    def rollback(self):
        self.clear_log()
        super(db, self).rollback()

    def commit(self):
        try:
            self.write_log()
            super(db, self).commit()
        except:
            self.unpublish_log()
            raise
        else:
            self.publish_log()
