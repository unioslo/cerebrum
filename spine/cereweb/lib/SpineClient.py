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

"""
This module handles the connection with the server.

Public functions:
connect     - connects to the server, and returns the spine object.
"""

import sys
import os
import urllib
import ConfigParser

from omniORB import CORBA, sslTP

import Cerebrum_core
import SpineIDL

#Configuration of the connection to the server.
path = os.path.dirname(__file__) or '.'
conf = ConfigParser.ConfigParser()
conf.read(path + '/' + 'cereweb.conf.template')
conf.read(path + '/' + 'cereweb.conf')


sslTP.certificate_authority_file(conf.get('ssl', 'ca_file'))
sslTP.key_file(conf.get('ssl', 'key_file'))
sslTP.key_file_password(conf.get('ssl', 'password'))

ior_url = conf.get('corba', 'url')

orb = CORBA.ORB_init(['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)

def connect(args=[]):
    """Returns the server object.
    
    Method for connecting and fetch the Spine object.
    The method prefers SSL connections.
    """
    ior = urllib.urlopen(ior_url).read()
    obj = orb.string_to_object(ior)
    spine = obj._narrow(Cerebrum_core.Spine)
    if spine is None:
        raise Exception("Could not narrow the spine object")

    return spine

# arch-tag: 2e2f1f7a-4582-4ef7-a4e8-0b538df047c1
