"""Implements AbstractModels using the xmlrpc-based Bohf protocol.
   ``server`` parameters refer to instances of
   Cerebrum.client.ServerConnection.ServerConnection
"""

import AbstractModel as Abstract
# We'll override those that we need to override
from Abstract import *


import ServerConnection
from mx import DateTime
from warnings import warn
import types

def date_string(date):
    """Formats the date as a iso8601-string if it is a DateTime object,
       or else, just return unchanged."""
    if isinstance(date, DateTime.DateTimeType):
        return date.strftime("%Y-%m-%d")
    else:
        return date    

class Constants(Abstract.Constants):
    UNION = "union"
    INTERSECTION = "intersection"
    DIFFERENCE = "difference"

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

    def __init__(self, entity, type, start, end, who, why, disable_until):
        if isinstance(type, types.StringTypes):
            type = QuarantineType.get_by_name(type, entity.server)
        super(Quarantine, self).__init__(entity, type, 
                                         start, end, who, why, disable_until)
    
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
        self.type = info['type']
    
    def delete(self):
        pass
        
    def add_quarantine(self, type, why="", 
                       start=None, end=None):
        """Create and store a new quarantine on entity"""
        # we only need the type name
        if isinstance(type, QuarantineType):
            type = type.name
        
        # Make sure start-end are strings so we can concatinate them
        (start, end) = map(date_string, (start, end))
                         
        if start and end:
            from_to = "%s--%s" % (start, end)
        else:
            from_to = start    
        self.server.quarantine_set("id:%s" % self.id, 
                                   type, why, from_to)
        
    def get_quarantines(self):
        quarantines = self.server.quarantine_show("id:%s" % self.id)
        result = []
        for q in quarantines:
            quarantine = Quarantine(self, q.type, q.start,
                         q.end, q.who, q.why, q.disable_until)
            result.append(quarantine)
        return result    
 
    def _get_qtype(self, quarantine=None, type=None):
        """Retrieve the quarantine type string from either
           a quarantine type or a quarantine object 
           (but not both)"""
        if (not(type or quarantine) or 
               (type and quarantine)):
              raise ValueError, "type OR quarantine must be given"
        if quarantine:
            type = quarantine.type
            assert self == quarantine.entity
        if not isinstance(type, types.StringTypes):    
            # get string
            type = type.type
        return type

    def remove_quarantine(self, quarantine=None, type=None):
        """Removes a quarantine identified by either 
           quarantine = Quarantine-instance   --or
           type = QuarantineType or quarantine type string"""
        qtype = self._get_qtype(quarantine, type)
        self.server.quarantine_remove("id:%s" % self.id,
                                      qtype)
   
    def disable_quarantine(self, quarantine=None, type=None,
                                 until=None):
        """Removes a quarantine identified by either 
           'quarantine': Quarantine-instance   --or
           'type': QuarantineType or quarantine type string.
           Disables until date given by 'until'"""
        qtype = self._get_qtype(quarantine, type)
        self.server.quarantine_disable("id:%s" % self.id,
                                       qtype, until)

    
    def get_history(self, max_entries=None):
        # get the history log, and some helping information on entities and
        # chang he types
        if max_entries:
            entries = self.server.entity_history(self.id, max_entries)
        else:
            entries = self.server.entity_history(self.id)
        
        return _history_to_changes(self.server, entries)    


    def add_note(self, subject, description):
        self.server.note_add(self.id,  subject, description)
    
    def show_notes(self):
        notes_server = self.server.note_show(self.id)    
        notes = []
        for note_server in notes_server:
            note = Note(note_server.note_id,
                        self.id,
                        note_server.create_date,
                        note_server.creator,
                        note_server.subject,
                        note_server.description)
            notes.append(note)
        return notes       
    
    def remove_note(self, note):
        if isinstance(note, Note):
            note = note.id
        self.server.note_remove(self.id, note)    

class Group(Entity, Abstract.Group):
    
    def __init__(self, server):
        super(Group, self).__init__(server)
    
    def create(cls, server, name, description):
        info = server.group_create(name, description)
        id = info['group_id']
        return fetch_object_by_id(server, id)
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

class Account(Entity, Abstract.Account):
    
    def _load_entity_info(self, info):
        super(Account, self)._load_entity_info(info)
        self.name = info['name']
        self.create_date = info['create_date']
        self.expire_date = info['expire_date']
        self.spread = info['spread']
        self.owner_id = info['owner_id']
        self.creator_id = info['creator_id']

    def create(cls, server, name, owner, affiliation):
        """Creates an account, returns created account-object or None"""
        
        # FIXME: only supported owner-type right now is person
        try:
            if owner.type != 'person':
                return None
        except:
            return None
            
        info = server.user_reserve("idtype-not_in_use", owner.id, affiliation, name)
        if info.get('account_id'):
            return fetch_object_by_id(server, info['account_id'])
        else:
            return None
        
    create = classmethod(create)

    def fetch_by_name(cls, name):
        pass
    fetch_by_name = classmethod(fetch_by_name)
    
    def search(cls, server, name=None, create_date=None, creator_id=None, 
               expire_date=None, owner_id=None, np_type=None):
        pass
    search = classmethod(search)

    def set_owner(self, entity_id):
        pass

    def set_expire_date(self, expire_date):
        pass

    def get_owner_object(self):
        return fetch_object_by_id(self.server, self.owner_id)

    def get_creator_object(self):
        return fetch_object_by_id(self.server, self.creator_id)
    
    def get_auth_data(self, method=None):
        pass

    def get_account_types(self):
        pass

    def delete(self):
        pass    

class Person(Entity, Abstract.Person):

    # FIXME - This routine should return why create wasn't 
    #         successfull, not just None 
    def create(cls, server, name, birthno, birthdate, ou, affiliation, aff_status):
        """Creates a person, and returns the object, if successfull, 
           returns None otherwise"""
        info = server.person_create(birthno, birthdate, name, ou, affiliation, aff_status)
        if info.get('person_id'):
            person = fetch_object_by_id(server, info['person_id'])
        else:
            return None
            
    create = classmethod(create)

    def search(cls, server, name=None, account=None, birthno=None, birthdate=None):
        """Retrieves a list of persons, or empty list if none"""
        info = None
        if name:
            info = server.person_find("name", name)
        elif account:
            info = server.person_find("person_id", account)
        elif birthdate:
            info = server.person_find("date", birthdate)
        else:
            return None
            
        if info:
            persons = []
            for entry in info:
                person = fetch_object_by_id(server, entry['id'])
                persons.append(person)

            return persons
            
    search = classmethod(search)

    def _load_entity_info(self, info):
        super(Person, self)._load_entity_info(info)
        self.name = info['name']
        self.birthdate = info['birthdate']
        self._affiliations = info['affiliations']
        self.names = info['names']
        self.description = info['description']
        self.gender = info['gender']    
        self.deceased = info['deceased']

    def delete(self):
        pass
    
    def affiliations(self):
        # resolve 'ou' if needed 
        for affiliation in self._affiliations:
            if isinstance(affiliation['ou'], OU):
                # already resolved 
                continue
            ou = fetch_object_by_id(self.server, affiliation['ou'])
            affiliation['ou'] = ou
        return self._affiliations      
    affiliations = property(affiliations)    

    def get_accounts(self):
        """Retrieves a list of accounts this person owns, or empty list if none"""
        info = self.server.person_accounts("entity_id:%s" % self.id)

        accounts = []
        for acc in info:
            accountinfo = fetch_object_by_id(self.server, acc['account_id'])
            accounts.append(accountinfo)
        
        return accounts

                                                    
class OU(Entity, Abstract.OU):

    def create(cls):
        pass
    create = classmethod(create)

    def search(cls, server, name=None, account=None, birthno=None, birthdate=None):
        pass
    search = classmethod(search)

    def _load_entity_info(self, info):
        super(OU, self)._load_entity_info(info)
        self.name = info['name']
        self.acronym = info['acronym']
        self.short_name = info['short_name']
        self.display_name = info['display_name']
        self.sort_name = info['sort_name']

    def delete(self):
        pass

def operator_history(server, first_change=None):
    """Returns Change objects made by the current operator. If a
       Change object is supplied to first_change - only changes
       performed AFTER that change will be included."""
    if first_change:
        start_id = first_change._id +1
        entries = server.operator_history(start_id)
    else:
        entries = server.operator_history()    

    return _history_to_changes(server, entries)

def _history_to_changes(server, entries):        
    """Unwrap change objects from the database to Change objects"""
    (history, entities, change_types) = entries

    # Use entity info-dicts to create all entities that are referred to
    # within history
    entity_map = {}
    for (id,info) in entities.items():
        entity = fetch_object_by_id(server, id, info=info)
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
        change._id = entry.id
        changes.append(change)
    return changes       
    


def fetch_object_by_id(server, id, info=None):
    # Mapping between entity types and classes defined here
    # TODO: Move out from fetch_object_by_id - to be able to 
    # extend the mapping
    classes = {
        'group': Group,
        'person': Person,
        'account': Account,
        'ou': OU,
        # 'host': Host,
        # 'disk': Disk
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

