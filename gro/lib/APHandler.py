from Cerebrum.Utils import Factory
from Cerebrum.gro.Cerebrum_core import Errors
from Cerebrum.gro.db import db
from Cerebrum.gro import Cerebrum_core__POA, Node, Locking, Locker
from Cerebrum.gro import Entity, Types

from omniORB.any import to_any, from_any
import mx.DateTime


class APHandler(Cerebrum_core__POA.APHandler, Locker):
    """Access point handler.

    Each client has his own access point, wich will be used to identify the client
    so we can lock down nodes to the client and check if the client got access to
    make the changes he tries to do. The client has to provide the GRO a username
    and password before he gets the aphandler. This information will be stored in
    this object.
    """

    def __init__( self, com, username, password ):
        self.login( username, password ) # Raises exception if failed.
        self.com = com
        self.username = username
        self.password = password
        self.objects = [] # used to store objects the client access, for transactions

    def login( username, password ):
        """Login the user with the username and password.
        """
        account = Factory.get( 'Account' )( db )
        
        # Check username
        try:
            account.find_by_name( username )
        except Cerebrum.Errors.NotFoundError:
            raise Exception, "Unknown username or password" # GRO-exceptions!

        # Check quarantines
        pass

        # Check password
        if password != password: # CRYPTERING!! != account.password!
            raise Exception, "Unknown username or password" # GRO-exceptions!

        # Log successfull login..

    def get_username( self ):
        """Returns the username of the client.
        """
        return self.username

    def begin(self):
        """Starts a transaction, not sure how yet :)
        """
        pass

    def rollback(self):
        """Rollback changes done in the transaction.
        """
        for o in self.objects:
            o.rollback()
        self.objects = []

    def commit(self):
        """Commit changes to the database.

        Tries first to commit all nodes, then unlocks them.
        """
        for o in self.objects:
            o.commit()
        self.objects = []


class APObject(Cerebrum_core__POA.Object):
    """ Access point proxy node.

    The APOBject contains the APHandler and an object. It acts as a proxy for the object.
    This is to give us a sort of automatic session handling that will solve two problems:
    1 - The client does not have to deal with a session id
    2 - GRO can perform locking on objects requested by an client,
        using the APHandler to identify it.
    """

    def __init__( self, ap, obj ):
        self.ap = ap
        self.obj = obj

    def _convert( self, obj ):
        """Convert an object.
    
        If the object is a list, it will be converted to a tuple.
        If the object is a node, it will be converted to a corba-node.
        If the object is an int, a long, a float or a string it will not be converted.
        """
        if hasattr( obj, '__iter__' ) or type( obj ) in ( list, tuple ):
            return [self._convert( i ) for i in obj]

        elif type( obj ) in ( int, long, float, str ):
            return obj

        elif type( obj ) == mx.DateTime.DateTimeType:
            return obj.ticks()

        elif isinstance( obj, Builder ):
            ap_object = APObject( self.ap, obj )
            return self.ap.com.get_corba_representation( ap_object )

        elif obj is None:
            return 'wtf. None!'

        else:
            raise Errors.ServerError('Server failed to convert object')

    def get_primary_key( self ):
        """ Returns a tuple with the primary key changed into an anyobject. """
        key = self.obj.get_primary_key()[1]
        if type( key ) != tuple:
            key = [key]
        return to_any( self._convert( key ) )

    def get_class_name( self ):
        """ Returns the classname for the object. """
        return self.obj.__class__.__name__

    def get_read_attributes( self ):
        """ Returns a list over all readable attributes for the object. """
        return self.obj.read_slots

    def get_write_attributes( self ):
        """ Returns a list over all writeable attributes for the node. """
        return self.obj.write_slots

    def begin( self ):
        """Begins a transaction.
    
        A read lock will be requested on this node. Raises an 
        AlreadyLockedError if the node is already locked for writing.
        """
        self.lock_for_reading()

    def rollback(self):
        """Remove/drop changes done to the node.
    
        Rollbacks changes done to this node, and unlocks all locks on this node.
        """
        self.obj.rollback()

    def commit(self):
        """Save changes to the database.
    
        Commits the changes in this node to the database. Returns a list with
        al changed attributes. Raises a NotLockedError if the node isn't locked
        for writing.
        """
        if not self.updated:
            return []

        updated = self.obj.updated
        changed = self.obj.commit()
        assert updated.issubset(changed)
        return updated
