import Cerebrum.Entity

from Cerebrum.extlib import sets
from Cerebrum.gro.Utils import Lazy, LazyMethod, Clever

from Entity import Entity

from db import db

__all__ = ['Group']

class Group(Entity):
    slots = ['name', 'description', 'expireDate', 'members', 'posixGid']

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
        e = Cerebrum.Group.Group(db)
        e.find(self.id)

        self._name = e.group_name
        self._description = e.description
        self._expireDate = e.expire_date

    def loadChildren(self):
        Entity.loadChildren(self)

        self._children.update(self.members)
    
    def loadMembers(self):
        self._members = sets.Set()
        e = Cerebrum.Group.Group(db)
        e.entity_id = self.id

        self._members.update([Entity(int(i)) for i in e.get_members()])

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
