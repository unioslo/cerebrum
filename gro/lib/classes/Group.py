import Cerebrum.Entity
import Cerebrum.Group

from Cerebrum.extlib import sets

from Builder import Builder, Attribute, Method
from Entity import Entity

from db import db

__all__ = ['Group', 'GroupMember']

class Group(Entity):
    slots = Entity.slots + [Attribute('name', 'string', writable=True),
                            Attribute('description', 'string', writable=True),
                            Attribute('visibility', 'GroupVisibilityType', writable=True),
                            Attribute('expire_date', 'Date', writable=True)]
    methodSlots = Entity.methodSlots + [Method('get_members', 'MemberList')]

    def _getByCerebrumGroup(cls, e):
        entity_id = int(e.entity_id)
        name = e.group_name
        description = e.description
        visibility = Types.GroupVisibilityType(int(e.visibility))
        expire_date = e.expire_date
        return Group(entity_id, name=name, visibility=visibility, description=description, expire_date=expire_date)

    _getByCerebrumGroup = classmethod(_getByCerebrumGroup)
    
    def load(self):
        import Types

        e = Cerebrum.Group.Group(db)
        e.find(self._entity_id)

        self._name = e.group_name
        self._description = e.description
        self._visibility = Types.GroupVisibilityType(int(e.visibility))
        self._expire_date = e.expire_date

    def get_members(self): # jada.. denne skal også fikses...
        import Types, Entity

        members = []
        e = Cerebrum.Group.Group(db)
        e.entity_id = self._entity_id

        for row in db.query('''SELECT operation, member_id, member_type
                               FROM group_member
                               WHERE group_id = %s''' % self._entity_id):
            operation = Types.GroupMemberOperationType(int(row['operation']))
            member_id = int(row['member_id'])
            members.append(GroupMember(group_id=self._entity_id, operation=operation, member_id=member_id))
        return members

class GroupMember(Builder):
    slots = [Attribute('group_id', 'long'),
             Attribute('operation', 'GroupMemberOperationType'),
             Attribute('member_id', 'long')]

    def __repr__(self):
        return '%s(group=%s, operation=%s, member=%s)' % (self.__class__.__name__, self._group_id, self._operation, self._member_id)
