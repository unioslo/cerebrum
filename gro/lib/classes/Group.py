import Cerebrum.Entity

from Cerebrum.extlib import sets

from Clever import Clever, LazyMethod, Lazy
from Node import Node
from Entity import Entity

from db import db

__all__ = ['Group', 'GroupMember']

class Group(Entity):
    slots = ['name', 'description', 'visibility', 'expireDate', 'members', 'posixGid']
    readSlots = Entity.readSlots + slots
    writeSlots = Entity.writeSlots + ['name', 'description', 'visibility', 'expireDate', 'posixGid']

    def __init__(self, id, parents=Lazy, children=Lazy, *args, **vargs):
        Entity.__init__(self, id, parents, children)
        Clever.__init__(self, Group, *args, **vargs)

    def _getByCerebrumGroup(cls, e):
        id = int(e.entity_id)
        name = e.group_name
        description = e.description
        expireDate = e.expire_date
        return Group(id, name=name, description=description, expireDate=expireDate)

    def getByName(cls, name):
        e = Cerebrum.Group.Group(db)
        e.find_by_name(name)

        return cls._getByCerebrumGroup(e)

    def getByPosixGid(cls, posixGid):
        e = Cerebrum.modules.PosixGroup.PosixGroup(db)
        e.find_by_gid(posixGid)
        
        g = cls._getByCerebrumGroup(e)
        g._posixGid = int(e.posix_gid)

        return g

    _getByCerebrumGroup = classmethod(_getByCerebrumGroup)
    getByName = classmethod(getByName)
    getByPosixGid = classmethod(getByPosixGid)

    def load(self):
        import Types

        e = Cerebrum.Group.Group(db)
        e.find(self.id)

        self._name = e.group_name
        self._description = e.description
        self._visibility = Types.GroupVisibilityType(int(e.visibility))
        self._expireDate = e.expire_date

    def loadChildren(self):
        Entity.loadChildren(self)

        self._children.update(self.members)
    
    def loadMembers(self):
        import Types, Entity

        self._members = sets.Set()
        e = Cerebrum.Group.Group(db)
        e.entity_id = self.id

        for row in db.query('''SELECT operation, member_id, member_type
                               FROM group_member
                               WHERE group_id = %s''' % self.id):
            operation = Types.GroupMemberOperationType(int(row['operation']))
            member = Entity.Entity(int(row['member_id']),
                                   entityType=Types.EntityType(int(row['member_type'])))
            self._members.add(GroupMember(group=self, operation=operation, member=member))

    def loadPosixGid(self):
        try: # sukk.. Cerebrum er så teit..
            e = Cerebrum.modules.PosixGroup.PosixGroup(db)
            e.find(self.id)

            self._posixGid = int(e.posix_gid)

        except Cerebrum.Errors.NotFoundError:
            self._posixGid = None

    getMembers= LazyMethod('_members', 'loadMembers')
    getPosixGid = LazyMethod('_posixGid', 'loadPosixGid')

Clever.prepare(Group, 'load')

class GroupMember(Node):
    slots = ['group', 'operation', 'member']
    readSlots = Node.readSlots + slots
    writeSlots = Node.writeSlots + ['operation']

    def __init__(self, parents=Lazy, children=Lazy, *args, **vargs):
        Node.__init__(self, parents, children)
        Clever.__init__(self, GroupMember, *args, **vargs)

    def getKey(group, operation, member, *args, **vargs):
        return group, operation, member
    getKey = staticmethod(getKey)

    def __repr__(self):
        return '%s(group=%s, operation=%s, member=%s)' % (self.__class__.__name__, self.group, self.operation, self.member)
    
    def load(self):
        raise Exception('FU')

Clever.prepare(GroupMember, 'load')
