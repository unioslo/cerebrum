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

import sys

sys.path.append( '../../../' )
sys.path.append( '../../../Generated' )

from omniORB import CORBA, sslTP
from Constants import *
import Cerebrum_core, CosNaming
import Cerebrum_core.Errors

import Iterator

def connect(args):
    sslTP.certificate_authority_file( "../../../ssl/CA.crt" )
    sslTP.key_file( "../../../ssl/client.pem" ) 
    sslTP.key_file_password( "client" )    
    orb = CORBA.ORB_init( args, CORBA.ORB_ID )
    obj = orb.resolve_initial_references("NameService")
    rootContext = obj._narrow(CosNaming.NamingContext)
    
    if rootContext is None:
        print "Error while trying to narrow root naming context"
        sys.exit(1)
        
    name = [CosNaming.NameComponent( CONTEXT_NAME,
                                     GRO_SERVICE_NAME),
            CosNaming.NameComponent( GRO_OBJECT_NAME, "")]
    try:
        obj = rootContext.resolve( name )
    except CosNaming.NamingContext.NotFound:
        print "Could not find context(s)"
        sys.exit(1)
            
    gro = obj._narrow(Cerebrum_core.Gro)
    if gro is None:
        print "Could not narrow the gro object"
        sys.exit(1)
    return gro

if __name__ == '__main__':
    gro = connect( sys.argv )
    version = gro.get_version()
    print "Connected to Gro version %s.%s"%(version.major, version.minor)
    obj = gro.get_lo_handler()
    loHandler = obj._narrow( Cerebrum_core.LOHandler )

    import time
    a = time.time()

    bulk = loHandler.synchronized_benchmark(10000, 1000)
    bulk.set_amount(1000)
    while 1:
        try:
            n = len(bulk.next())
            print 'items:', n
        except Cerebrum_core.Errors.IteratorEmptyError:
            break
    print time.time() - a

# arch-tag: 053bd304-03a1-46a8-95a8-3f2cfcbe1385
