from omniORB import CORBA, sslTP
import CosNaming

import cereconf
from Constants import *
import Cerebrum_core

def connect(args=[]):
    """ 
    Method for connecting to a CORBA name service
    and fetch the Gro object. The method prefers
    SSL connections.
    """
    # Set up the SSL context
    d = cereconf.SSL_DIR
    sslTP.certificate_authority_file( d + "/CA.crt" )
    sslTP.key_file( d + "/client.pem" )
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
