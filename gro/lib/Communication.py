#!/usr/bin/env  python
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

import sys

from omniORB import CORBA, sslTP

import cereconf

class Communication(object):
    def __init__(self):
        sslTP.certificate_authority_file(cereconf.SSL_CA_FILE)
        sslTP.key_file(cereconf.SSL_KEY_FILE)
        sslTP.key_file_password(cereconf.SSL_KEY_FILE_PASSWORD)

        self.orb = CORBA.ORB_init(sys.argv + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)

        self.rootPOA = self.orb.resolve_initial_references("RootPOA")

    def servant_to_reference(self, *objects):
        """
        Must be called on all objects that
        clients are to interact with"""

        # convert all objects to corba-objects
        r = [self.rootPOA.id_to_reference(self.rootPOA.activate_object(i)) for i in objects]

        # return a tuple only if there is more than 1 object
        return len(r) == 1 and r[0] or tuple(r)

    def reference_to_servant(self, *objects):
        r = [self.rootPOA.reference_to_servant(i) for i in objects]

        # return a tuple only if there is more than 1 object
        return len(r) == 1 and r[0] or tuple(r)
    
    def start(self):
        """
        Activates and starts Communication"""
        self.rootPOA._get_the_POAManager().activate()
        self.orb.run()

_com = None
def get_communication():
    global _com
    if _com is None:
        _com = Communication()

    return _com

# arch-tag: 8f1cc382-a927-4722-aa79-8c6f96d6f02b
