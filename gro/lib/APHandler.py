from Cerebrum.gro.Cerebrum_core import Errors
from Cerebrum.gro import Cerebrum_core__POA, Utils, Node, Locking, Locker

from omniORB.any import to_any, from_any

class APHandler(Cerebrum_core__POA.APHandler, Locker):
    def __init__(self, com, username, password):
        self.com = com
        self.username = username
        self.password = password

    def getUsername(self):
        return self.username

    def getEntity(self, id):
        import classes.Entity
        entity = classes.Entity.Entity(id)
        apNode = APNode(self, entity)

        return self.com.get_corba_representation(apNode)

    def getTypeByName(self, className, name):
        import classes.Types
        if className in classes.Types.__all__:
            NodeClass = getattr(classes.Types, className)
            node = NodeClass.getByName(name)
            apNode = APNode(self, node)

            return self.com.get_corba_representation(apNode)

        raise Errors.NoSuchTypeError('className %s was not found' % className)

class APNode(Cerebrum_core__POA.Node):
    def __init__(self, ap, node):
        self.ap = ap
        self.node = node

    def _convert(self, obj):
        if hasattr(obj, '__iter__'):
            return [self._convert(i) for i in obj]

        elif type(obj) in (int, long, float, str):
            return obj

        elif isinstance(obj, Node):
            apNode = APNode(self.ap, obj)
            return self.ap.com.get_corba_representation(apNode)

        elif obj is None:
            print 'warning! obj is None'
            return 0

        else:
            print type(obj)
            unknown_type

    def getParents(self):
        return self._convert(self.node.parents)

    def getChildren(self):
        return self._convert(self.node.children)

    def _get(self, key):
        if key in self.node.readSlots:
            # check locking
            if key in self.node.writeSlots and not self.isReadLockedByMe():
                raise Errors.NotLockedError('No read lock for this node')
            value = getattr(self.node, key)
            b = self._convert(value)
            return b
        raise Errors.NoSuchAttributeError('%s was not found in node' % key)

    def get(self, key):
        return to_any(self._get(key))

    getString = getLong = getNode = getNodeSeq = _get

    def getClassName(self):
        return self.node.__class__.__name__


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

