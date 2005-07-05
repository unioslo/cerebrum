#!/usr/bin/env python
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
import sys
import urllib

from omniORB import CORBA, sslTP, importIDL, importIDLString

def fixOmniORB():
    """Workaround for bugs in omniorb

    Makes it possible to use obj1 == obj2 instead of having to do
    obj1._is_equivalent(obj2).
    Also makes it possible to use corba objects as keys in
    dictionaries etc.
    """
    import omniORB.CORBA
    import _omnipy
    def __eq__(self, other):
        if self is other:
            return True
        return _omnipy.isEquivalent(self, other)

    def __hash__(self):
        # sys.maxint is the maximum value returned by _hash
        return self._hash(sys.maxint)

    omniORB.CORBA.Object.__hash__ = __hash__
    omniORB.CORBA.Object.__eq__ = __eq__

#FIXME: make optional?
fixOmniORB()

import Cereweb
from Cereweb import config

try:
    import SpineCore
    import SpineIDL
except:
    print>>sys.stderr, 'need to run bootstrap'

idl_core = config.conf.get('idl', 'spine_core')

if not os.path.exists(idl_core):
    print 'ERROR: %s not found, please set correct idl path' % idl_core
    sys.exit(1)

ior_url = config.conf.get('corba', 'url')

def init_ssl(args):
    sslTP.certificate_authority_file(config.conf.get('ssl', 'ca_file'))
    sslTP.key_file(config.conf.get('ssl', 'key_file'))
    sslTP.key_file_password(config.conf.get('ssl', 'password'))

    return CORBA.ORB_init(args + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)

def init(args):
    return CORBA.ORB_init(args)

def connect(args=[]):
    """Returns the server object.
    
    Method for connecting and fetch the Spine object.
    The method prefers SSL connections.
    """
    importIDL(idl_core)
    import SpineCore

    if config.conf.getboolean('corba', 'use_ssl'):
        orb = init_ssl(args)
    else:
        orb = init(args)

    ior = urllib.urlopen(ior_url).read()
    try:
        obj = orb.string_to_object(ior)
    except:
        print 'ERROR: %s not found, please set correct corba url' % ior_url
        sys.exit(2)
    spine = obj._narrow(SpineCore.Spine)
    if spine is None:
        raise Exception("Could not narrow the spine object")

    return spine

def bootstrap():
    spine = connect()
    print '- connected to:', spine
    import Cereweb
    target = os.path.dirname(os.path.dirname(os.path.realpath(Cereweb.__file__)))
    print '- downloading source'
    source = spine.get_idl()
    print '- (%s bytes)' % len(source)
    generated = os.path.join(target, 'SpineIDL.idl')
    fd = open(generated, 'w')
    fd.write(source)
    fd.close()
    print '- Compiling to', target

    os.system('omniidl -bpython -C %s -Wbpackage=Cereweb %s %s' %
                                            (target, idl_core, generated))

    import Cereweb.SpineIDL, Cereweb.SpineCore
    print '- All done:', Cereweb.SpineIDL, Cereweb.SpineCore

# arch-tag: 3da72f49-4a08-47ab-b189-5147403d3181
