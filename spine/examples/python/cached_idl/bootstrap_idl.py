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
change this: sys.path.append('/home/erikgors/install/lib/python2.4/site-packages/')

import os
import urllib

from omniORB import CORBA, sslTP, importIDL, importIDLString

import config

sslTP.certificate_authority_file(config.conf.get('ssl', 'ca_file'))
sslTP.key_file(config.conf.get('ssl', 'key_file'))
sslTP.key_file_password(config.conf.get('ssl', 'password'))

idl_path = config.conf.get('idl', 'path')
idl_server = os.path.join(idl_path, config.conf.get('idl', 'server'))
idl_errors = os.path.join(idl_path, config.conf.get('idl', 'errors'))

ior_url = config.conf.get('corba', 'url')


def connect(args=[]):
    """Returns the server object.
    
    Method for connecting and fetch the Spine object.
    The method prefers SSL connections.
    """
    importIDL(idl_server)
    importIDL(idl_errors)
    import Cerebrum_core

    orb = CORBA.ORB_init(args + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)
    print '- fetching ior from:', ior_url
    ior = urllib.urlopen(ior_url).read()
    obj = orb.string_to_object(ior)
    spine = obj._narrow(Cerebrum_core.Spine)
    if spine is None:
        raise Exception("Could not narrow the spine object")

    return spine

def bootstrap():
    spine = connect()
    print '- connected to:', spine
    import Cereweb
    target = os.path.dirname(os.path.dirname(os.path.realpath(Cereweb.__file__)))
    print '- downloading source'
    source = spine.get_idl().replace('module generated', 'module SpineIDL')
    print '- (%s bytes)' % len(source)
    generated = os.path.join(target, 'SpineIDL.idl')
    fd = open(generated, 'w')
    fd.write(source)
    fd.close()
    print '- Compiling to', target
    print ''

    for i in (idl_errors, idl_server, generated):
        command = 'omniidl -bpython -C %s -Wbpackage=Cereweb -I %s %s' % (target, idl_path, i)
        os.system(command)

    import Cereweb.SpineIDL
    print '- All done:', Cereweb.SpineIDL

if __name__ == '__main__':
    bootstrap()

# arch-tag: 3da72f49-4a08-47ab-b189-5147403d3181
