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

from Cerebrum.gro import Cerebrum_core
from omniORB import CORBA, sslTP
import CosNaming
import cereconf

_orb = None
def get_orb(args=[]):
    global _orb
    if _orb is None:
        # Set up the SSL context
        sslTP.certificate_authority_file(cereconf.SSL_CA_FILE)
        sslTP.key_file(cereconf.SSL_KEY_FILE)
        sslTP.key_file_password(cereconf.SSL_KEY_FILE_PASSWORD)

        # Initialize the ORB
        _orb = CORBA.ORB_init(args, CORBA.ORB_ID)
    return _orb


def connect(args=[]):
    """ 
    Method for connecting to a CORBA name service
    and fetch the Gro object. The method prefers
    SSL connections.
    """
    orb = get_orb(args)
    # Get the name service and narrow the root context
    obj = orb.resolve_initial_references("NameService")
    rootContext = obj._narrow(CosNaming.NamingContext)

    if rootContext is None:
        raise Exception("Could not narrow the root naming context")

    # Fetch gro using the name service
    name = [CosNaming.NameComponent(cereconf.GRO_CONTEXT_NAME, cereconf.GRO_SERVICE_NAME),
            CosNaming.NameComponent(cereconf.GRO_OBJECT_NAME, "")]

    obj = rootContext.resolve(name)

    gro = obj._narrow(Cerebrum_core.Gro)
    if gro is None:
        raise Exception("Could not narrow the gro object")
    return gro

def string_to_object(string):
    """Returns an object form of the string"""
    return get_orb().string_to_object(string)

def get_server(req):
    """Returns the server object"""
    server = req.session['server']
    return string_to_object(server)

# arch-tag: 866d57dc-d0ae-4751-b89e-8e2800aa8511
