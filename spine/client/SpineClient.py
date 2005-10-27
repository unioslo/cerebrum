#!/usr/bin/env python
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

import os
import sys
import urllib

from omniORB import CORBA, sslTP, importIDL, importIDLString
import config

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

path = os.path.dirname(os.path.realpath(__file__))

class SpineClient:
    spine_core = os.path.join(path, 'SpineCore.idl')
    def __init__(self, ior_url, use_ssl=False, ca_file=None, key_file=None, ssl_password=None, idl_path=path, automatic=True):
        if not os.path.exists(self.spine_core):
            raise IOError, '%s not found' % spine_core

        if idl_path not in sys.path:
            sys.path.append(idl_path)

        self.ior_url = ior_url
        self.use_ssl = use_ssl
        self.ca_file = ca_file
        self.key_file = key_file
        self.ssl_password = ssl_password
        self.idl_path = idl_path

        self.md5_file = os.path.join(self.idl_path, 'SpineIDL.md5')
        self.idl_file = os.path.join(self.idl_path, 'SpineIDL.idl')

        if not self.check_md5() and automatic:
            self.bootstrap()

        import SpineIDL, SpineCore

    def init_ssl(self):
        sslTP.certificate_authority_file(self.ssl_ca_file)
        sslTP.key_file(self.ssl_key_file)
        sslTP.key_file_password(self.ssl_password)

        return CORBA.ORB_init(['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)

    def init(self):
        return CORBA.ORB_init()

    def connect(self):
        """Returns the server object.
        
        Method for connecting and fetch the Spine object.
        The method prefers SSL connections.
        """
        try:
            import SpineCore
        except ImportError:
            importIDL(self.spine_core)
            import SpineCore


        if self.use_ssl:
            orb = self.init_ssl()
        else:
            orb = self.init()

        ior = urllib.urlopen(self.ior_url).read()
        obj = orb.string_to_object(ior)
        spine = obj._narrow(SpineCore.Spine)
        if spine is None:
            raise Exception("Could not narrow the spine object")

        return spine

    def check_md5(self):
        try:
            spine = self.connect() 
            return spine.get_idl_md5() == open(self.md5_file).read()
        except IOError:
            return False

    def bootstrap(self):
        spine = self.connect()
        print>>sys.stderr, '- connected to:', spine
        print>>sys.stderr, '- downloading source'
        source = spine.get_idl()
        print>>sys.stderr, '- (%s bytes)' % len(source)
        fd = open(self.idl_file, 'w')
        fd.write(source)
        fd.close()
        print>>sys.stderr, '- Compiling to', self.idl_path

        os.system('omniidl -bpython -C %s %s %s' % (self.idl_path, self.spine_core, self.idl_file))

        import SpineIDL, SpineCore
        print>>sys.stderr, '- All done:', SpineIDL, SpineCore
        fd = open(self.md5_file, 'w')
        fd.write(spine.get_idl_md5())
        fd.close()

class Search:
    def __init__(self, tr):
        self.tr = tr
        self.searches = {}

    def __getattr__(self, name):
        def wrapped(alias, **args):
            s = getattr(self.tr, name)()
            self.searches[s] = alias
            for key, value in args.items():
                getattr(s, 'set_%s' % key)(value)
            return s

        return wrapped

    def dump(self, searcher):
        names = [self.searches[i] for i in searcher.get_search_objects()]
        for structs in zip(*[i.dump() for i in searcher.get_dumpers()]):
            yield dict(zip(names, structs))

# arch-tag: 2f4948da-4732-11da-8c59-869c4ebe94a5
