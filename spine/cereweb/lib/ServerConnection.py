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

When loaded it will, if neceserly, compile the corba-stubs from both
the static server-idl and the generated idl which we must connect to
the server to get.

Public functions:
connect     - connects to the server, and returns the spine object.
"""

import sys
import os
import urllib
import ConfigParser

from omniORB import CORBA, sslTP, importIDL, importIDLString

#Configuration of the connection to the server.
path = os.path.dirname(__file__)
conf = ConfigParser.ConfigParser()
conf.read(path + '/' + 'cereweb.conf.template')
conf.read(path + '/' + 'cereweb.conf')

sslTP.certificate_authority_file(conf.get('ssl', 'ca_file'))
sslTP.key_file(conf.get('ssl', 'key_file'))
sslTP.key_file_password(conf.get('ssl', 'password'))

idl_path = conf.get('idl', 'path')
idl_server = os.path.join(idl_path, conf.get('idl', 'server'))
idl_errors = os.path.join(idl_path, conf.get('idl', 'errors'))

def connect(args=[]):
    """Returns the server object.
    
    Method for connecting and fetch the Spine object.
    The method prefers SSL connections.
    """
    orb = CORBA.ORB_init(args + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)
    ior = urllib.urlopen(conf.get('corba', 'url')).read()
    obj = orb.string_to_object(ior)
    spine = obj._narrow(Cerebrum_core.Spine)
    if spine is None:
        raise Exception("Could not narrow the spine object")

    return spine

if conf.getboolean('spine', 'cache'):
    # add tmp path to sys.path if it doesnt exists
    cache_dir = conf.get('spine', 'cache_dir')
    if cache_dir not in sys.path:
        sys.path.append(cache_dir)

    try:
        import Cerebrum_core
    except:
        os.system('omniidl -bpython -C %s %s %s' % (cache_dir, idl_server, idl_errors))
        import Cerebrum_core

    try:
        import generated
    except:
        source = connect().get_idl()
        generated = os.path.join(cache_dir, 'generated.idl')
        fd = open(generated, 'w')
        fd.write(source)
        fd.close()
        os.system('omniidl -bpython -C %s -I%s %s' % (cache_dir, idl_path, generated))
        import generated
else:
    importIDL(idl_server)
    importIDL(idl_errors)
    import Cerebrum_core

    idl = connect().get_idl()
    importIDLString(idl, ['-I' + idl_path])
    import generated

# arch-tag: 866d57dc-d0ae-4751-b89e-8e2800aa8511
