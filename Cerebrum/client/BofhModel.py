"""Implements AbstractModels using the xmlrpc-based Bohf protocol.
   ``server`` parameters refer to instances of
   Cerebrum.client.ServerConnection.ServerConnection
"""

import AbstractModel as Abstract
import ServerConnection
from mx import DateTime
from warnings import warn
import types

class Constants(Abstract.Constants):
    UNION = "union"
    INTERSECTION = "intersection"
    DIFFERENCE = "difference"


class Address(Abstract.Address):
    pass

class ContactInfo(Abstract.ContactInfo):
    pass
            
class ChangeType(Abstract.ChangeType):
    pass

class Change(Abstract.Change):
    pass

class QuarantineType(Abstract.QuarantineType):
    
    # cache for get_by_name
    _cache = {}

    def get_all(cls, server):
        quarantines = server.quarantine_list()
        cls._cache.clear()
        for q in quarantines:
            (name, desc) = (q['name'], q['desc'])
            quarantinetype = cls(name, desc)
            cls._cache[name] = quarantinetype
        return cls._cache.values()

    get_all = classmethod(get_all)     

    def get_by_name(cls, name, server):
        if not cls._cache:
            cls.get_all(server)
        return cls._cache[name]    
        
    get_by_name = classmethod(get_by_name)
    

class Quarantine(Abstract.Quarantine):

    def __init__(self, entity, quarantine_type, start, end, who, why, disable_until):
        if isinstance(quarantine_type, types.StringTypes):
            quarantine_type = QuarantineType.get_by_name(quarantine_type, entity.server)
        super(Quarantine, self).__init__(entity, quarantine_type, 
                                         start, end, who, why, disable_until)
    
    def remove(self):
        self.server.quarantine_remove(self.entity.type,
                                      "id:%s" % self.entity.id,
                                      self.type.name)
   
    def disable(self, until=None):
        if isinstance(until, DateTime.DateTimeType):
            until = until.strftime("%Y-%m-%d")
        self.server.quarantine_disable(self.entity.type,
                                       "id:%s" % self.entity.id,
                                       self.type.name,
                                       until)    

class Entity(Abstract.Entity):
    
    def __init__(self, server):
        self.server = server
        self.id = None # undetermined at this stage
        
    def __eq__(self, other):
        return isinstance(other, Entity) and self.id == other.id
        
    def __hash__(self):
        return hash(self.id) ^ hash(Entity)
    
    def fetch_by_id(cls, server, id):
        """ Retrieves an instance from ``server`` with given ``id``.
            ``server`` is a ServerConnection.
        """
        # instanciate what ever class we might be 
        entity = cls(server)
        info = server.entity_info(id)
        entity._load_entity_info(info)
        return entity
        
    fetch_by_id = classmethod(fetch_by_id)    
    
    def _load_entity_info(self, info):
        """Loads entity specific data to this object
           from a infohash as defined by bofh.
        """
        self.id = info['entity_id'] 
        # are these really useful for anything?
        self.names = info.get('names', [])
        self.type = info['type']
    
    def delete(self):
        pass
        
    def add_quarantine(self, quarantine_type, why="", 
                       start=None, end=None):
        """Create and store a new quarantine on entity"""
        # we only need the type name
        if isinstance(quarantine_type, QuarantineType):
            quarantine_type = quarantine_type.name
            
        fix_date = lambda date: (isinstance(date, DateTime.DateTimeType) and 
                                date.strftime("%Y-%m-%d") or date)
        (start, stop) = map(fix_date, (start, stop))
                         
        if start and stop:
            from_to = "%s--%s" % (start, stop)
        else:
            from_to = start    
        self.server.quarantine_set(self.type, "id:%s" % self.id, 
                                   quarantine_type, why, from_to)
        
    def get_quarantines(self):
        quarantines = self.server.quarantine_show(self.type,
                                                  "id:%s" % self.id)
        result = []
        for q in quarantines:
            quarantine = Quarantine(self, q.type, q.start,
                         q.end, q.who, q.why, q.disable_until)
            result.append(quarantine)
        return result    

    
    def get_history(self):
        # get the history log, and some helping information on entities and
        # chang he types
        (history, entities, change_types) = self.server.entity_history(self.id)

        # Use entity info-dicts to create all entities that are referred to
        # within history
        entity_map = {}
        for (id,info) in entities.items():
            entity = fetch_object_by_id(self.server, id, info=info)
            entity_map[int(id)] = entity

        # And vice versa for the change types    
        change_map = {}
        for (change_type_id, change_details) in change_types.items():
            (category, change_type, msg) = change_details
            change_type = ChangeType(change_type_id, category, change_type, msg)
            change_map[int(change_type_id)] = change_type

        # resolve all references to entities and change_types    
        changes = []
        for entry in history:
            change = Change(type = change_map.get(entry['type']),
                            date = entry['date'],
                            subject = entity_map.get(entry['subject']),
                            dest = entity_map.get(entry['dest']),
                            params = entry['params'],
                            # change_by might be a program name 
                            # instead of entity, just include that string
                            change_by = entity_map.get(entry['change_by']) or entry['change_by'])
            changes.append(change)
        return changes       


class Group(Entity, Abstract.Group):
    
    def __init__(self, server):
        super(Group, self).__init__(server)
    
    def create(cls, server, name, description):
        group = Group(server)
        group.name = name
        group.description = description

        # FIXME: Check for errors...
        info = server.group_create(name, description)
        group._load_entity_info(info)
        group.expire = info['expire']
        group.gid = info.get('gid')
        group.spreads = info['spread'].split(",")
        return group
        
    create = classmethod(create)
    
    def fetch_by_name(cls, server, name):
        group = cls(server)
        # FIXME: Check for errors: not found, etc.
        info = server.group_info(name)
        group._load_entity_info(info)
        # FIXME: Only spread names currently
        # TODO: Don't fetch spreads here
        #spread=kommaseparert liste med code_str
        group.spreads = info['spread'].split(",")
        return group
        
    fetch_by_name = classmethod(fetch_by_name)
    
    def _load_entity_info(self, info):
        super(Group, self)._load_entity_info(info)
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
        info = self.server.group_list("id:%s" % self.id)
        
        members = []
        for grpmember in info:
            member = {}
            member['id'] = grpmember['id']
            member['type'] = grpmember['type']
            member['name'] = grpmember['name']
            member['operation'] = grpmember['op']
            member['object'] = fetch_object_by_id(self.server, member['id'])
            # Should be just tuples of (object, operation)
            members.append(member)
            
        return members
        
    def get_all_accounts(self):
        members = self.server.group_list_expanded("id:%s" % self.id)
        return [fetch_object_by_id(self.server, member['member_id']) 
                for member in members]
        
    def add_member(self, member, operation=Constants.UNION):
        """ Adds ``member`` to group with ``operation``.
            ``operation`` is one of Constants.UNION, 
            INTESECTION or DIFFERENCE, default is UNION."""
        self.server.group_add_entity(member.id, self.id, operation)

    def remove_member(self, member_id=None, member_entity=None, 
                      operation=Constants.UNION):
        """Removes member given by id (member_id) or Entity instance (member_entity).
           If operation is not given, UNION-members are removed"""              
        if member_id and member_entity:
            raise TypeError, "member_id or member_entity must be given, not both"    
        if member_entity:
            member_id = member_entity.id
        if not member_id:
            raise TypeError, "member_id or member_entity must be given"
        self.server.group_remove_entity(member_id, self.id, operation)

    def delete_group(self):
        self.server.group_delete(self.name)

def fetch_object_by_id(server, id, info=None):
    # Mapping between entity types and classes defined here
    # TODO: Move out from fetch_object_by_id - to be able to 
    # extend the mapping
    classes = {
        'group': Group,
#        'account': Account,
        # 'ou': OU,
        # 'person': Person,
        # 'host': Host,
#        'disk': Disk
    }

    # We need this info dictionary up front to check info['type']
    if info is None:
        info = server.entity_info(id)
    # Note that parameter id is not used at all if info is given. entity.id is
    # set by Entity._load_entity_info  using info['entity_id'] later on
    # We don't care what kind of class GeneralEntity really is    
    GeneralEntity = classes.get(info['type'], Entity)
    entity = GeneralEntity(server)
    entity._load_entity_info(info)
    return entity

