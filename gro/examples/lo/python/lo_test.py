#!/usr/bin/env python
import sys

sys.path.append( '../../../' )
sys.path.append( '../../../Generated' )

from omniORB import CORBA, sslTP
from Constants import *
import Cerebrum_core, CosNaming

import Iterator

def connect(args):
    """ 
    Method for connecting to a CORBA name service
    and fetch the Gro object. The method prefers
    SSL connections.
    """
    # Set up the SSL context
    sslTP.certificate_authority_file( "../../../ssl/CA.crt" )
    sslTP.key_file( "../../../ssl/client.pem" ) 
    sslTP.key_file_password( "client" )    

    # Initialize the ORB
    orb = CORBA.ORB_init( args, CORBA.ORB_ID )
    # Get the name service and narrow the root context
    obj = orb.resolve_initial_references("NameService")
    rootContext = obj._narrow(CosNaming.NamingContext)
    
    if rootContext is None:
        print "Error while trying to narrow root naming context"
        sys.exit(1)
        
    # Fetch gro using the name service
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

def print_items( iterator ):
    """ 
    Method for printing items in an iterator containing
    sequences of KeyValue-objects.
    """
    for item in Iterator.BufferedIterator(iterator):
        print '-'
        for i in item:
            print i.key, '-', i.value

if __name__ == '__main__':
    # Get the Gro object
    gro = connect( sys.argv )

    # Get and print the Gro version
    version = gro.get_version()
    print "Connected to Gro version %s.%s"%(version.major, version.minor)

    # Get the LO handler
    obj = gro.get_lo_handler()
    loHandler = obj._narrow( Cerebrum_core.LOHandler )

    # To fetch all objects of class PosixUser and PosixGroup:
    for i in 'PosixUser','PosixGroup':
        latest, entities = loHandler.get_all( i, [] )

        print i
        print_items( entities )

        print 'latest changeid:', latest
        
    # To fetch all objects of class Posix{User,Group} changed since id 1:
    for i in 'PosixUser', 'PosixGroup':
        latest, entities, deleted = loHandler.get_update( i, [], 1 )

        print i
        print_items( entities )
        print_items( deleted )

        print 'latest changeid:', latest

# arch-tag: 45d624d6-9466-4c8f-877c-80436ae80c65
