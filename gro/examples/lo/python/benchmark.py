#!/usr/bin/env python
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
