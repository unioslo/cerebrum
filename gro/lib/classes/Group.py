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
    methodSlots = Entity.methodSlots + [Method('get_group_members', 'GroupMemberSeq')]

    cerebrum_class = Cerebrum.Group.Group

    def _getByCerebrumGroup(cls, e):
        entity_id = int(e.entity_id)
        name = e.group_name
        description = e.description
        visibility = Types.GroupVisibilityType(int(e.visibility))
        expire_date = e.expire_date
        return Group(entity_id, name=name, visibility=visibility, description=description, expire_date=expire_date)

    _getByCerebrumGroup = classmethod(_getByCerebrumGroup)
    
    def _load_group(self):
        import Types

        e = Cerebrum.Group.Group(db)
        e.find(self._entity_id)

        self._name = e.group_name
        self._description = e.description
        self._visibility = Types.GroupVisibilityType(int(e.visibility))
        self._expire_date = e.expire_date

    load_name = load_description = load_visibility = load_expire_date = _load_group

    def get_group_members(self):
        import Types, Entity

        members = []
        e = Cerebrum.Group.Group(db)
        e.entity_id = self._entity_id

        union, intersection, difference = e.list_members()

        unionType = Types.GroupMemberOperationType.getByName('union')
        intersectionType = Types.GroupMemberOperationType.getByName('intersection')
        differenceType = Types.GroupMemberOperationType.getByName('difference')

        for rows, operation in ((union, unionType),
                                (intersection, intersectionType),
                                (difference, differenceType)):
            for member_type, member_id in rows:
                members.append(GroupMember(group_id=self._entity_id,
                                           operation=operation,
                                           member_id=int(member_id),
                                           member_type=int(member_type)))
        return members

class GroupMember(Builder):
    primary = [Attribute('group_id', 'long'),
               Attribute('operation', 'GroupMemberOperationType'),
               Attribute('member_id', 'long')]
    slots = primary + [Attribute('member_type', 'long')]
