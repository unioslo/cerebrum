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

import md5
import os
import sys
import urllib
import ConfigParser

from omniORB import CORBA, importIDL, importIDLString


conf = ConfigParser.ConfigParser()
conf.read(('client.conf.template', 'client.conf'))

if conf.getboolean('spine', 'use_ssl'):
    from omniORB import sslTP
    sslTP.certificate_authority_file(conf.get('ssl', 'ca_file'))
    sslTP.key_file(conf.get('ssl', 'key_file'))
    sslTP.key_file_password(conf.get('ssl', 'password'))

cache_dir = conf.get('cache', 'cache_dir')
core_idl_file = os.path.join(conf.get('spine', 'idl'))
idl_file = os.path.join(cache_dir, conf.get('cache', 'idl_file'))
md5_file = os.path.join(cache_dir, conf.get('cache', 'md5_file'))

def connect(args=[]):
    """Returns the server object.
    
    Method for connecting and fetch the Spine object.
    """
    if conf.getboolean('spine', 'use_ssl'):
        orb = CORBA.ORB_init(args + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)
    else:
        orb = CORBA.ORB_init(args, CORBA.ORB_ID)
    ior = urllib.urlopen(conf.get('corba', 'url')).read()
    obj = orb.string_to_object(ior)
    spine = obj._narrow(SpineCore.Spine)
    if spine is None:
        raise Exception("Could not narrow the spine object")
    return spine

if conf.getboolean('cache', 'cache'):
    # Add cache path to sys.path if it doesnt exists
    if cache_dir not in sys.path:
        sys.path.append(cache_dir)

    try:
        import SpineCore
    except:
        os.system('omniidl -bpython -C %s %s' % (cache_dir, core_idl_file))
        import SpineCore

    try:
        spine = connect()
        f = open(md5_file)
        cached_md5 = f.read()
        f.close()
        if cached_md5 != spine.get_idl_md5():
            raise 'Get new IDL'
        import SpineIDL
        Errors = SpineIDL.Errors
    except:
        try:
            spine = connect()
            source = spine.get_idl()
            spine_md5 = spine.get_idl_md5()
            md5sum = md5.md5()
            md5sum.update(source)
            if md5sum.hexdigest() != spine_md5:
                raise RuntimeError('Spine reported erroneous MD5 sum for IDL definitions: %s != %s' % (spine_md5, md5sum.hexdigest()))
        except CORBA.TRANSIENT:
            raise RuntimeError('Unable to connect to Spine.')
        generated = os.path.join(cache_dir, idl_file)
        f = open(generated, 'w')
        f.write(source)
        f.close()
        os.system('omniidl -bpython -C %s %s' % (cache_dir, generated))
        f = open(md5_file, 'w')
        f.write(spine_md5)
        f.close()
        import SpineIDL
        Errors = SpineIDL.Errors
else:
    importIDL(core_idl_file)
    import SpineCore

    try:
        idl = connect().get_idl()
    except CORBA.TRANSIENT:
        raise RuntimeError('Unable to connect to Spine.')
    importIDLString(idl)
    import SpineIDL
    Errors = SpineIDL.Errors

# arch-tag: 380b39b2-0d61-411c-80ce-a3b230b04618
