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
import CosNaming

import cereconf

class Communication(object):
    def __init__(self):
        sslTP.certificate_authority_file(cereconf.SSL_CA_FILE)
        sslTP.key_file(cereconf.SSL_KEY_FILE)
        sslTP.key_file_password(cereconf.SSL_KEY_FILE_PASSWORD)

        self.orb = CORBA.ORB_init(sys.argv + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)

        self.rootPOA = self.orb.resolve_initial_references("RootPOA")
        ns = self.orb.resolve_initial_references("NameService")
        root_context = ns._narrow(CosNaming.NamingContext)

        if root_context is None:
            raise Exception("Could not narrow root naming context")

        #register in the name service
        name = [CosNaming.NameComponent(cereconf.GRO_CONTEXT_NAME, cereconf.GRO_SERVICE_NAME)]
        try:
            self.context = root_context.bind_new_context(name)
        except CosNaming.NamingContext.AlreadyBound, ex:
            existing = root_context.resolve(name)
            self.context = existing._narrow(CosNaming.NamingContext)
            if self.context is None:
                raise Exception("Could not bind or find existing context")

    def bind_object(self, to_bind, name):
        """
        Shortcut function to bind an object to a name in our
        naming context on the name server"""
        name = [CosNaming.NameComponent(name, "")]
        obj = to_bind._this()
        print self.orb.object_to_string(obj)
        try:
            self.context.bind(name, obj)
        except CosNaming.NamingContext.AlreadyBound:
            self.context.rebind(name, obj)

    def register_objects(self, *objects):
        """
        Must be called on all objects that
        clients are to interact with"""

        # convert all objects to corba-objects
        r = [self.rootPOA.id_to_reference(self.rootPOA.activate_object(i)) for i in objects]

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
