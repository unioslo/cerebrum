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

import time

from Cerebrum.extlib import sets
from Cerebrum.gro.Cerebrum_core import Errors

from Caching import Caching
from Locking import Locking
from Builder import Builder
from CorbaBuilder import CorbaBuilder

import Database

__all__ = ['GroBuilder']

class GroBuilder(Builder, Caching, Locking, CorbaBuilder):
    def __init__(self, *args, **vargs):
        write_lock = vargs.get('write_lock', None)
        if 'write_lock' in vargs:
            del vargs['write_lock']
        nocache = vargs.get('nocache', False)
        if 'nocache' in vargs:
            del vargs['nocache']

        # check if this object is old
        if Builder.__init__(self, *args, **vargs):
            return

        Locking.__init__(self, write_lock=write_lock)
        Caching.__init__(self, nocache=nocache)

    def get_database(self):
        c = self.get_writelock_holder()
        if c is not None:
            return c.get_database() # The lockholder has get_database()
        else:
            return Database.get_database()

    def save(self):
        """ Save all changed attributes """
        # make sure there is a writelock
        assert self.get_writelock_holder() is not None

        super(GroBuilder, self).save()


# arch-tag: 246ee465-24a3-4541-a55a-7548356aebfb
