# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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
import os
import urllib

from omniORB import CORBA, sslTP, importIDL, importIDLString

import config

sslTP.certificate_authority_file(config.conf.get('ssl', 'ca_file'))
sslTP.key_file(config.conf.get('ssl', 'key_file'))
sslTP.key_file_password(config.conf.get('ssl', 'password'))

idl_path = config.conf.get('idl', 'path')
idl_core = os.path.join(idl_path, config.conf.get('idl', 'core'))

def connect(args=[]):
    """Returns the server object.
    
    Method for connecting and fetch the Spine object.
    The method prefers SSL connections.
    """
    orb = CORBA.ORB_init(args + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)
    ior = urllib.urlopen(config.conf.get('corba', 'url')).read()
    obj = orb.string_to_object(ior)
    spine = obj._narrow(SpineCore.Spine)
    if spine is None:
        raise Exception("Could not narrow the spine object")

    return spine

if config.conf.getboolean('spine', 'cache'):
    # add tmp path to sys.path if it doesnt exists
    cache_dir = config.conf.get('spine', 'cache_dir')
    if cache_dir not in sys.path:
        sys.path.append(cache_dir)

    try:
        import SpineCore
    except:
        os.system('omniidl -bpython -C %s %s' % (cache_dir, idl_core))
        import SpineCore

    try:
        import SpineIDL
    except:
        source = connect().get_idl()
        generated = os.path.join(cache_dir, 'SpineIDL.idl')
        fd = open(generated, 'w')
        fd.write(source)
        fd.close()
        os.system('omniidl -bpython -C %s %s' % (cache_dir, generated))
        import SpineIDL
else:
    importIDL(idl_core)
    import SpineCore

    idl = connect().get_idl()
    importIDLString(idl)
    import SpineIDL

# arch-tag: 380b39b2-0d61-411c-80ce-a3b230b04618
