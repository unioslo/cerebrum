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

    def isReadLockedByMe(self):
        return self.node.isReadLockedByMe(self.ap)

    def isWriteLockedByMe(self):
        return self.node.isWriteLockedByMe(self.ap)

    def lockForReading(self):
        self.node.lockForReading(self.ap)

    def unlock(self):
        self.node.unlock(self.ap)

    def begin(self):
        self.lockForReading()

    def rollback(self):
        if self.isWriteLockedByMe():
            self.node.rollback()
        self.unlock()

    def commit(self):
        if not self.updated:
            return []
        if not self.isWriteLockedByMe():
            raise Errors.NotLockedError('Trying to commit withough a lock')

        updated = self.node.updated
        changed = self.node.commit()
        assert updated.issubset(changed)
        return updated
