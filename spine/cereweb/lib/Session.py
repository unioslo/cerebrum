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

import os
import cPickle
import SpineClient

class Session(dict):
    def __init__(self, id):
        self.id = id
        self.filename = '/tmp/cereweb_%s' % id
        if os.path.exists(self.filename):
            fd = open(self.filename)
            self.update(cPickle.load(fd))
            fd.close()

    def save(self):
        tmpname = self.filename + ".tmp." + str(os.getpid())
        fd = open(tmpname, 'w')
        cPickle.dump(self.items(), fd)
        fd.close()
        os.rename(tmpname, self.filename)

    def get_spine_session(self):
        return SpineClient.orb.string_to_object(self['spine_session'])

    def set_spine_session(self, obj):
        self['spine_session'] = SpineClient.orb.object_to_string(obj)

# arch-tag: dbefe1f3-848c-4192-b0f1-75f5435b5887
