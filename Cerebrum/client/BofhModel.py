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
    
    def fetch_by_id(cls, server, id):
        """ Retrieves an instance from ``server`` with given ``id``.
            ``server`` is a ServerConnection.
        """
        entity = cls(server)
        entity.load_entity_info(id)
        return entity
        
    fetch_by_id = classmethod(fetch_by_id)    
    
    def load_entity_info(self, id):
        """Loads entity specific data to this object
           from server using the given ``id``.
           Returns a dictionary of possibly other useful items.
           (for subclasses)
        """
        self.id = id
        warn("entity_info not implemented yet")
        info = self.server.entity_info(id)
        self.names = info['names']
        self.type = info['type']
        return info
    
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
        
    def get_quarantines(self):
        pass


class Group(Entity, Abstract.Group):
    
    def __init__(self, server):
        Entity.__init__(self, server)
    
    def create(cls, server, name, description):
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
    
    def fetch_by_name(cls, server, name):
        group = Group(server)
        # FIXME: Check for errors: not found, etc.
        info = server.group_info(name)
        group.load_entity_info(info['entity_id'])
        # FIXME: Only spread names currently
        # TODO: Don't fetch spreads here
        #spread=kommaseparert liste med code_str
        group.spreads = info['spread'].split(",")
        return group
        
    fetch_by_name = classmethod(fetch_by_name)
    
    def load_entity_info(self, id):
        info = Entity.load_entity_info(self, id)    
        self.name = info['name']
        self.description = info['description']
        self.visibility = info['visibility']
        self.creatorid = info['creator_id']
        self.create = info['create_date']
        self.expire = info['expire_date']
        self.gid = info.get('gid')
        # TODO - get spreads (or make a method to get spreads)
        self.spreads = []

    def search(cls, server, spread=None, name=None, desc=None):
        filter = {}
        if spread is not None:
            filter['spread'] = spread
        if name is not None:    
            filter['name'] = name
        if desc is not None:    
            filter['desc'] = desc
        rows = server.group_search(filter)
        # convert to list of tuples
        groups = []
        for row in rows:
            groups.append((row['id'],
                           row['name'],
                           row['desc']))
        return groups    
    search = classmethod(search)    

    def get_members(self):
        # FIXME: Check for errors...
        info = self.server.group_list(self.name)
        
        members = []
        for grpmember in info:
            member = {}
            member['id'] = grpmember['id']
            member['type'] = grpmember['type']
            member['name'] = grpmember['name']
            member['operation'] = grpmember['op']
            # FIXME
            warn("Need to create the new_object_by_id-function")
            #member['object'] = new_object_by_id(member['id'])
            # Should be just tuples of (object, operation)
            members.append(member)
            
        return members
        
    def get_all_accounts(self):
        pass
        
    def add_member(self, member, operation=Constants.UNION):
        """ Adds ``member`` to group with ``operation``.
            ``operation`` is one of Constants.UNION, 
            INTESECTION or DIFFERENCE, default is UNION."""
        self.server.group_add_entity(member.id, self.id, operation)

    def remove_member(self, member):
        # FIXME: Make this use the soon-to-be-universiall group_remove
        self.server.group_gremove(member.name, self.name)

    def delete_group(self):
        self.server.group_delete(self.name)

def fetch_object_by_id(server, id):
    classes = {
        'group': Group,
        'account': Account,
        # 'ou': OU,
        # 'person': Person,
        #'host': Host,
        'disk': Disk
    }
    info = server.entity_info(id)
    entity_class = classes.get(info['type'], Entity)
    return entity_class.fetch_by_id(server, id)

class Constants(Abstract.Constants):
    UNION = "union"
    INTERSECTION = "intersection"
    DIFFERENCE = "difference"

