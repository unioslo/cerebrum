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

    def __init__(self, com, username, password):
        self.login(username, password) # Raises exception if failed.
        self.com = com
        self.username = username
        self.nodes = [] # Nodes wich the ap has modified. Transactions!

    def login(username, password):
        """Login the user with the username and password.
        """
        account = Factory.get('Account')(db)
        
        # Check username
        try:
            account.find_by_name(username)
        except Cerebrum.Errors.NotFoundError:
            raise Exception, "Unknown username or password" # GRO-exceptions!

        # Check quarantines
        pass

        # Check password
        if password != password # CRYPTERING!! != account.password!
            raise Exception, "Unknown username or password" # GRO-exceptions!

        # Log successfull login..

    def get_username(self):
        """Returns the username of the client.
    
        Used by the node if a client wants a list over who got a lock on the node.
        Overrides the get_username()-method in the locker-class.
        """
        return self.username

    def getEntity(self, id):
        """Returns a corba node of the entity which got the specified id.
        """
        entity = Entity.Entity(id)
        apNode = APNode(self, entity)

        self.nodes.append(apNode)
        return self.com.get_corba_representation(apNode)

    def getTypeByName(self, className, name):
        """Returns a corba node which got the specified name.
        
        Both class and name of the wanted database-object is needed.
        Raises an exception if className was not found.
        """
        if className in Types.__all__:
            NodeClass = getattr(Types, className)
            node = NodeClass.getByName(name)
            apNode = APNode(self, node)
            
            self.nodes.append(apNode)
            return self.com.get_corba_representation(apNode)

        raise Errors.NoSuchTypeError('className %s was not found' % className)

    def getNode(self, className, key):
        """Returns a corba node which got the name specified by key.
    
        The diffrence between this method and getTypeBy() is that this method
        maps classnames to a string that can differ from the classname.
        """
        if className not in Node.classMap:
            raise Errors.NoSuchTypeError('className %s was not found' % className)
        l = []
        for i in from_any(key):
            if isinstance(i, APNode):
                l.append(i.node)
            else:
                l.append(i)
        apNode = APNode(self, Node.classMap[className](*l))

        self.nodes.append(apNode)
        return self.com.get_corba_representation(APNode(apNode)

    def begin(self):
        """Starts a transaction, not sure how yet :)
        """
        pass

    def rollback(self):
        """Rollback changes done in the transaction.
        """
        for node in self.nodes:
            node.rollback()
        self.nodes = []

    def commit(self):
        """Commit changes to the database.

        Tries first to commit all nodes, then unlocks them.
        """
        for node in self.nodes:
            node.commit()
        for node in self.nodes:
            node.unlock()
        self.nodes = []


class APNode(Cerebrum_core__POA.Node):
    """Access point proxy node.

    The APNode contains the APHandler and a node. It acts as a proxy for the node.
    This is to give us a sort of automatic session handling that will solve two problems:
    1 - The client does not have to deal with a session id
    2 - GRO can perform locking on nodes requested by an client,
        using the APHandler to identify it.
    """

    def __init__(self, ap, node):
        self.ap = ap
        self.node = node

    def _convert(self, obj):
        """Convert an object.
    
        If the object is a list, it will be converted to a tuple.
        If the object is a node, it will be converted to a corba-node.
        If the object is an int, a long, a float or a string it will not be converted.
        """
        if hasattr(obj, '__iter__') or type(obj) in (list, tuple):
            return [self._convert(i) for i in obj]

        elif type(obj) in (int, long, float, str):
            return obj

        elif type(obj) == mx.DateTime.DateTimeType:
            return obj.ticks()

        elif isinstance(obj, Node):
            apNode = APNode(self.ap, obj)
            return self.ap.com.get_corba_representation(apNode)

        elif obj is None:
            print 'warning! obj is None'
            return 'wtf. None!'

        else:
            print type(obj)
            raise Errors.ServerError('Server failed to convert object')

    def getParents(self):
        """Returns the parents of the node.
        """
        return self._convert(self.node.parents)

    def getChildren(self):
        """Returns the children of the node.
        """
        return self._convert(self.node.children)

    def getPrimaryKey(self):
        """Returns a tuple with the primary key changed into an anyobject.
        """
        key = self.node.getPrimaryKey()[1]
        if type(key) != tuple:
            key = [key]
        return to_any(self._convert(key))

    def _get(self, key):
        """Returns node values.

        Raises an exception if the node wasn't read-locked, or if the key isn't a
        valid attribute.
        """
        if key in self.node.readSlots:
            # check locking
            if key in self.node.writeSlots and not self.is_readlocked_by_me():
                raise Errors.NotLockedError('You dont got read lock for this node')
            value = getattr(self.node, key)
            b = self._convert(value)
            return b
        raise Errors.NoSuchAttributeError('%s was not found in node' % key)

    def get(self, key):
        """Wrapper for the _get-method.

        Will return the same as the _get-method, but the value of the attribute 
        is transformed into an any type. get can return any type of value, but
        if you know you want a string, you should use getString.
        """
        return to_any(self._get(key))

    # Methods wich dont return the value as an any-type
    getString = getLong = getNode = getNodeSeq = _get

    def getClassName(self):
        """Returns the classname for the node.
        """
        return self.node.__class__.__name__

    def getReadAttributes(self):
        """Returns a list over all readable attributes for the node.
        """
        return self.node.readSlots

    def getWriteAttributes(self):
        """Returns a list over all writeable attributes for the node.
        """
        return self.node.writeSlots

    def _set( self, key, value ):
        """Sets a node attribute.
        
        Set an attribute on a node if:
         - The node got that attribute AND
         - The attribute is writeable.
        Called by setString and setLong.
        """
        if key not in self.node.readSlots:
            raise NoSuchAttributeError( 'Not a valid attribute for the node.' )
        if key not in self.node.writeSlots:
            raise ReadOnlyAttributeError( '%s is not writeable.' % key )
        if not self.is_writelocked_by_me():
            raise NotLockedError( 'You don\'t got a writelock on this node.' )
        setattr( self.node, key, value )

    def setString(self, key, value):
        """Wrapper-method for _set() so corba can send it as a string.
        """
        self._set( key, value )

    def setLong(self, key, value):
        """Wrapper-method for _set() so corba can send it as a long.
        """
        self._set( key, value )

    def lock_for_reading( self ):
        """Prevent others from locking the node for writing.

        Lock the node so no other client can put a writelock on it.
        Raises an AlreadyLockedError if the node is already locked for
        writing by another client.
        """
        self.node.lock_for_reading( self.ap )

    def lock_for_writing( self ):
        """Obtain access to make changes to the node.

        Before a changeable attribute can be written, a write lock must be obtained.
        Raises an AlreadyLockedError if the node is already locked for writing
        by another client.
        """
        self.node.lock_for_writing( self.ap )

    def unlock( self ):
        """Remove all locks the current client got on this node.
        """
        # You should not be able to unlock a changed node, without rollbacking it.
        self.node.unlock( self.ap )

    def is_readlocked_by_me( self ):
        """Check if this node is locked for reading for me.
        """
        return self.node.is_readlocked_by_me( self.ap )

    def is_readlocked_by_other( self ):
        """Check if this node is locked for reading by someone else.
        """
        return self.node.is_readlocked_by_other( self.ap )

    def is_writelocked_by_me( self ):
        """Check if this node is locked for writing by me.
        """
        return self.node.is_writelocked_by_me( self.ap )

    def is_writelocked_by_other( self ):
        """Check if this node is locked for writing by someone else.
        """
        return self.node.is_writelocked_by_other( self.ap )

    def get_readlockers( self ):
        """Get a list over all clients with a readlock on this node.
        """
        return self.node.get_readlockers( self.ap )

    def get_writelocker( self ):
        """Get the username of the client with has a writelock on this node.
        """
        return self.node.get_writelocker( self.ap )

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
        if self.is_writelocked_by_me():
            self.node.rollback()
        self.unlock()

    def commit(self):
        """Save changes to the database.
    
        Commits the changes in this node to the database. Returns a list with
        al changed attributes. Raises a NotLockedError if the node isn't locked
        for writing.
        """
        if not self.updated:
            return []
        if not self.is_writelocked_by_me():
            raise Errors.NotLockedError('Trying to commit without a lock')

        updated = self.node.updated
        changed = self.node.commit()
        assert updated.issubset(changed)
        return updated

