"""Implements AbstractModels using the xmlrpc-based Bohf protocol.
   ``server`` parameters refer to instances of
   Cerebrum.client.ServerConnection.ServerConnection
"""

import AbstractModel as Abstract
import ServerConnection
from warnings import warn

class Address(Abstract.Address):
    pass


class ContactInfo(Abstract.ContactInfo):
    pass


class Entity(Abstract.Entity):
    
    def __init__(self, server):
        Abstract.Entity.__init__(self)
        self.server = server
    
    def load_entity_info(self, id):
        """Loads entity specific data from server using the given ``id``.
        """
        warn("entity_info not implemented yet")
        return
        info = self.server.entity_info(id)
        self.names = info['names']
        self.type = info['type']

    def get_by_id(cls, id, server):
        """ Retrieves an instance from ``server`` with given ``id``.
            ``server`` is a ServerConnection.
        """
        entity = Entity(server)
        entity.load_entity_info(id)
        return entity
        
    get_by_id = classmethod(get_by_id)    
    
    def delete(self):
        pass
        
    def get_address_info(self):
        pass
        
    def get_contact_info(self):
        pass
        
    def get_spread_info(self):
        pass
        
    def add_quarantine(self, quarantine_type, description, start_date=None, 
                      disable_until=None, end_date='default'):
        pass
        
    def list_quarantines(self):
        pass


class Group(Entity, Abstract.Group):
    
    def __init__(self, server):
        Entity.__init__(self, server)
    
    def create(cls, name, description, server):
        group = Group(server)
        group.name = name
        group.description = description

        # FIXME: Check for errors...
        info = server.group_create(name, description)
        group.load_entity_info(info['group_id'])
        group.expire = info['expire']
        group.gid = info.get('gid')
        group.spreads = info['spread'].split(",")
        return group
        
    create = classmethod(create)
    
    def find_by_name(cls, name, server):
        group = Group(server)
        # FIXME: Check for errors: not found, etc.
        info = server.group_info(name)
        #'gid', 'entity_id', 'spread', 'expire', 'desc'
        #spread=kommaseparert liste med code_str
        
        group.name = name
        group.load_entity_info(info['entity_id'])
        group.description = info['desc']
        group.expire = info['expire']
        group.gid = info.get('gid')
        # FIXME: Only spread names currently
        group.spreads = info['spread'].split(",")
        return group
        
    find_by_name = classmethod(find_by_name)

    def get_members(self):
        # FIXME: Check for errors...
        info = self.server.group_list(self.name)
        
        members = []
        for grpmember in info:
            member = {}
            member['id'] = grpmember['id']
            member['type'] = grpmember['type']
            member['name'] = grpmember['name']
            member['operation'] = grpmember['memberop']
            # FIXME: Need to create the new_object_by_id-function
            member['object'] = new_object_by_id(member['id'])
            members.append(member)
            
        return members
        
    def get_all_accounts(self):
        pass
        
    def add_member(self, member, operation="union"):
        """ Adds ``member`` to group with ``operation``.
            ``operation`` is one of 'union', 'difference' and
            'intersection', the default is 'union'.
        """
        # FIXME: Make this use the soon-to-be-universiall group_add
        self.server.group_gadd(member.name, self.name, operation)

    def remove_member(self, member):
        # FIXME: Make this use the soon-to-be-universiall group_remove
        self.server.group_gremove(member.name, self.name)

    def delete_group(self):
        self.server.group_delete(self.name)

