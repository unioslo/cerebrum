#!/usr/bin/env  python

# The major version number of Gro
GRO_MAJOR_VERSION = 0

# The minor version of Gro
GRO_MINOR_VERSION = 1

from Cerebrum.Utils import Factory
import cereconf

import sys
from omniORB import CORBA, PortableServer, sslTP
import CosNaming
import LOHandler
from Constants import *

from Cerebrum.gro import Cerebrum_core__POA, Cerebrum_core


class GroImpl( Cerebrum_core__POA.Gro ):
    """
    Implements the methods in the Gro interface.
    These are provided to remote clients"""

    def __init__( self, com ):
        self.com = com
        self._db = Factory.get( 'Database' )()
        self.loHandler = com.get_corba_representation( LOHandler.LOHandler( self, self._db ) )

    def get_version( self ):
        return Cerebrum_core.Version( GRO_MAJOR_VERSION, GRO_MINOR_VERSION )
        
    def test( self ):
        mahString = "foomeee"
        print "server: %s"% (mahString)
        return mahString
    
    def get_lo_handler( self ):
        return self.loHandler

    
class Communication( object ):
    def __init__( self ):
        self.context = None
        self.orb = None
        self.rootPOA = None
        
    def resolve_and_register( self ):
        """
        Locates the naming service, and registers our naming
        context with it """
        d = cereconf.SSL_DIR
        sslTP.certificate_authority_file(d + "/CA.crt")
        sslTP.key_file(d + "/server.pem") 
        sslTP.key_file_password("server")
        self.orb = CORBA.ORB_init(sys.argv + ['-ORBendPoint', 'giop:ssl::'], CORBA.ORB_ID)
        self.rootPOA = self.orb.resolve_initial_references( "RootPOA" )
        ns = self.orb.resolve_initial_references( "NameService" )
        rootContext = ns._narrow(CosNaming.NamingContext)

        if rootContext is None:
            #Fatal error, handle this better
            print "Could not narrow root naming context"
            sys.exit(1)

        #register in the name service
        name = [CosNaming.NameComponent( CONTEXT_NAME, GRO_SERVICE_NAME )]
        try:
            self.context = rootContext.bind_new_context( name )
        except CosNaming.NamingContext.AlreadyBound, ex:
            existing = rootContext.resolve( name )
            self.context = existing._narrow( CosNaming.NamingContext )
            if self.context is None:
                #Fatal error, handle this better
                print "Could not bind or find existing context"
                sys.exit( 1 )

    def bind_object( self, toBind, name ):
        """
        Shortcut function to bind an object to a name in our
        naming context in the name server"""
        name = [CosNaming.NameComponent( name, "" )]
        try:
            self.context.bind( name, toBind._this() )
        except CosNaming.NamingContext.AlreadyBound:
            self.context.rebind( name, toBind._this() )

    def get_corba_representation( self, *objects ):
        """
        Shortcut function to activate an object for remote
        communication. Must be called on all objects that
        clients are to interact with"""

        # convert all objects to corba-objects
        r = [ self.rootPOA.id_to_reference( self.rootPOA.activate_object(i) ) for i in objects ]

        # return a tuple only if there is more than 1 object
        return len(r) == 1 and r[0] or tuple(r)
    
    def start(self):
        """
        Activates Gro. Note that the thread will block"""
        self.rootPOA._get_the_POAManager().activate()
        self.orb.run()

def main():
    com = Communication()
    com.resolve_and_register()
    server = GroImpl( com )
    com.bind_object( server, GRO_OBJECT_NAME )
    print "All OK. Starting to block"
    com.start()

if __name__ == '__main__':        
    main()
