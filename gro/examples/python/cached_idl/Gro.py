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

import sys
import os
import urllib

from omniORB import CORBA, sslTP, importIDL, importIDLString

import config

sslTP.certificate_authority_file(config.conf.get('ssl', 'ca_file'))
sslTP.key_file(config.conf.get('ssl', 'key_file'))
sslTP.key_file_password(config.conf.get('ssl', 'password'))

idl_path = config.conf.get('idl', 'path')
idl_gro = os.path.join(idl_path, config.conf.get('idl', 'gro'))
idl_errors = os.path.join(idl_path, config.conf.get('idl', 'errors'))

def connect(args=[]):
    """ 
    Method for connecting and fetch the Gro object.
    The method prefers SSL connections.
    """
    orb = CORBA.ORB_init(args + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)
    ior = urllib.urlopen(config.conf.get('corba', 'url')).read()
    obj = orb.string_to_object(ior)
    gro = obj._narrow(Cerebrum_core.Gro)
    if gro is None:
        raise Exception("Could not narrow the gro object")

    return gro

if config.conf.getboolean('gro', 'cache'):
    # add tmp path to sys.path if it doesnt exists
    cache_dir = config.conf.get('gro', 'cache_dir')
    if cache_dir not in sys.path:
        sys.path.append(cache_dir)

    try:
        import Cerebrum_core
    except:
        os.system('omniidl -bpython -C %s %s %s' % (cache_dir, idl_gro, idl_errors))
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
    importIDL(idl_gro)
    importIDL(idl_errors)
    import Cerebrum_core

    idl = connect().get_idl()
    importIDLString(idl, ['-I' + idl_path])
    import generated

# arch-tag: 0ce9d2b5-5c92-4625-9bee-074b555772b2
