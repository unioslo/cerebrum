from Cerebrum.gro.Cerebrum_core import Errors
from Cerebrum.gro import Cerebrum_core__POA, Utils, Node, Locking, Locker

from omniORB.any import to_any, from_any
import mx.DateTime


""" Access point handler.

Each client has his own access point, wich will be used to identify the client
so we can lock down nodes to the client and check if the client got access to
make the changes he tries to do. The client has to provide the GRO a username
and password before he gets the aphandler. This information will be stored in
this object."""
class APHandler(Cerebrum_core__POA.APHandler, Locker):

    def __init__(self, com, username, password):
        self.com = com
        self.username = username
        self.password = password


    """ Returns the username of the client.
    
    Used by the node if a client wants a list over who got a lock on the node.
    Overloads the getUsername()-method in the locker-class."""
    def getUsername(self):
        return self.username


    """ Returns a corba node of the entity wich got that specific id. """
    def getEntity(self, id):
        import classes.Entity
        entity = classes.Entity.Entity(id)
        apNode = APNode(self, entity)

        return self.com.get_corba_representation(apNode)


    """ Returns a corba node wich got that specific name.
    
    You need to specify wich class and wich name the database-object you want.
    Raises an exception if the classname was not found."""
    def getTypeByName(self, className, name):
        import classes.Types
        if className in classes.Types.__all__:
            NodeClass = getattr(classes.Types, className)
            node = NodeClass.getByName(name)
            apNode = APNode(self, node)

            return self.com.get_corba_representation(apNode)

        raise Errors.NoSuchTypeError('className %s was not found' % className)

    def getNode(self, className, key):
        if className not in Node.classMap:
            raise Errors.NoSuchTypeError('className %s was not found' % className)
        l = []
        for i in from_any(key):
            if isinstance(i, APNode):
                l.append(i.node)
            else:
                l.append(i)
        node = Node.classMap[className](*l)
        return self.com.get_corba_representation(APNode(self, node))


""" Access point proxy node.

The node contain the APHandler and a node. It act as a proxy for the node.
This is to give us a sort of an automatic session handling, so the client
do not have to deal with a session id, and that we can lock down nodes for
the specific client, using the APHandler as a identifier for the client."""
class APNode(Cerebrum_core__POA.Node):

    def __init__(self, ap, node):
        self.ap = ap
        self.node = node


    """ Convert a object.
    
    If the object is a list, it will be convertet to a tuple.
    If the object is a node, it will be convertet to a corba-node.
    If the ojbect is a int, long, float or string it will not be converted."""
    def _convert(self, obj):
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


    """ Returns the parents of the node. """
    def getParents(self):
        return self._convert(self.node.parents)


    """ Returns the childrens of the node. """
    def getChildren(self):
        return self._convert(self.node.children)

    def getPrimaryKey(self):
        key = self.node.getPrimaryKey()[1]
        if type(key) != tuple:
            key = [key]
        return to_any(self._convert(key))


    """ Returns node values.

    Raises exception if the node wasnt readlocked, or if they key isnt a
    valid attribute."""
    def _get(self, key):
        if key in self.node.readSlots:
            # check locking
            if key in self.node.writeSlots and not self.isReadLockedByMe():
                raise Errors.NotLockedError('You dont got read lock for this node')
            value = getattr(self.node, key)
            b = self._convert(value)
            return b
        raise Errors.NoSuchAttributeError('%s was not found in node' % key)


    """ Wrapper for the _get-method.
    
    Will return the same as the _get-method, but the value of the attribute 
    is transformed into an any type. get can return any type of value, but
    if you know you want a string, you should use getString."""
    def get(self, key):
        return to_any(self._get(key))


    """ Methods wich dont return the value as an any-type. """
    getString = getLong = getNode = getNodeSeq = _get


    """ Returns the classname for the node. """
    def getClassName(self):
        return self.node.__class__.__name__

    def getReadAttributes(self):
        return self.node.readSlots

    def getWriteAttributes(self):
        return self.node.writeSlots

    def setString(self, key, value):
        setattr(self.node, key, value)

    def setLong(self, key, value):
        setattr(self.node, key, value)

    """ Prevent other from locking the node for writing.

    Lock the node so no other client can put a writelock on it.
    Raises an AlreadyLockedError if its already writelocked by someone else"""
    def lockForReading( self ):
        self.node.lockForReading( self.ap )


    """ Obtain access to make changes to the node.

    Before you can change a changeable attribute you must lock it for writing.
    Raises an AlreadyLockedError if its already locked by someone else."""
    def lockForWriting( self ):
        self.node.lockForWriting( self.ap )


    """ Remove all your locks on the node.

    Raises an NotLockedError if you dont got any locks on the node."""
    def unlock( self ):
        self.node.unlock( self.ap )


    """ Check if the node is locked for reading for me. """
    def isReadLockedByMe( self ):
        return self.node.isReadLockedByMe( self.ap )


    """ Check if the node is locked for reading by others. """
    def isReadLockedByOther( self ):
        return self.node.isReadLockedByOther( self.ap )


    """ Check if the node is locked for writing by me. """
    def isWriteLockedByMe( self ):
        return self.node.isWriteLockedByMe( self.ap )

    
    """ Check if someone else got a writelock on the node. """
    def isWriteLockedByOther( self ):
        return self.node.isWriteLockedByother( self.ap )


    """ Get a list over all wich has a readlock on the node. """
    def getReadLockers( self ):
        return self.node.getReadLockers( self.ap )


    """ Get the username of the client wich has a writelock on this node. """
    def getWriteLocker( self ):
        return self.node.getWriteLocker( self.ap )


    """ Begins a transaction.
    
    It will lock the node for reading for you.
    Raises an AlreadyLockedError if the node is already locked."""
    def begin( self ):
        self.lockForReading()


    """ Remove/drop changes done to the node.
    
    Rollbacks changes done to the node, and unlocks all locks on the node.
    Raises an NotLockedError if the node isnt locked for writing."""
    def rollback(self):
        if self.isWriteLockedByMe():
            self.node.rollback()
        self.unlock()


    """ Save changes to the database.
    
    Commits the changes in the node to the database. Returns a list over
    changed atrributes. Raises an NotLockedError if the node isnt locked
    for writing. """
    def commit(self):
        if not self.updated:
            return []
        if not self.isWriteLockedByMe():
            raise Errors.NotLockedError('Trying to commit without a lock')

        updated = self.node.updated
        changed = self.node.commit()
        assert updated.issubset(changed)
        return updated

