"""Abstract superclasses for the model, ie. the business data.
   Implementation modules should subclass all of these classes
   providing network communication, updating the database or
   whatever might be neccessary. """

class CerebrumError(Exception):
    """General Cerebrum error"""
    def __str__(self):
        args = Exception.__str__(self) # Get our arguments
        if args: 
            return self.__doc__ + ': ' + args
        else:
            return self.__doc__

class ServerError(CerebrumError):
    """Server error"""

class ServerRestartedError(ServerError):
    """Server restarted"""

class NotSupportedError(ServerError):
    """Method not supported"""

class NoQuarantineSupport(NotSupportedError):
    """Entity type does not support quarantines"""

class Address(object):

    def set_info(cls, entity_id, source_system, address_type, 
                address_text=None, p_o_box=None, city=None, 
                country=None):
        """Sets address-info for a given entity_id, and returns
           an address-object with this info."""
        pass
        
    set_info = classmethod(set_info)

    def get_info(cls, entity_id):
        """Retrieves a list of address-objects for given entity"""
        pass

    get_info = classmethod(get_info)

class ChangeType(object):
    """A type of change in the history log"""
    def __init__(self, change_type_id, category, change_type, msg):
        self.id = change_type_id
        self.category = category
        self.type = change_type
        self.message = msg
        
    def __eq__(self, other):
        return isinstance(other, ChangeType) and self.id == other.id
        
    def __hash__(self):
        return hash(self.id) ^ hash(ChangeType)

    def __str__(self):
        return "%s %s" % (self.category, self.type)    

class Change(object):
    """A change entry in the history log. A Change is of a given ChangeType."""
    def __init__(self, type, date, subject, dest, params, change_by):
        self.type = type # a ChangeType
        self.date = date # mx.DateTime
        self.subject = subject # Entity
        self.dest = dest # Entity or None
        self.params = params # dict or None
        self.change_by = change_by # Entity or string (program name)
        
    def __repr__(self):
        date = self.date.strftime("%Y-%m-%d")
        if self.dest:
            dest = " " + str(self.dest)
        else:
            dest = ""    
        return "<Change %s %s %s%s>" % (date, self.type, self.subject, dest)
    def __str__(self):    
        date = self.date.strftime("%Y-%m-%d")    
        return "%s <%s> %s" % (date, self.change_by, self.message())
    def message(self):
        words = self.__dict__.copy()
        try:
            words.update(self.params)
        except Exception, e:
            pass
        try:
            return self.type.message % words
        except KeyError:
            return "%s %s" % (self.type.message, self.subject)

class ContactInfo(object):

    def set_info(cls, entitiy_id, source_system, contact_type,
                contact_pref=None, contact_value=None, 
                description=None):
        """Sets contactinfo for a given entity_id, and returns
           a contactinfo-object with this info."""
        pass

    set_info = classmethod(set_info)

    def get_info(cls, entity_id):
        """Retrieves a list of contactinfo-objects for given entity."""
        pass
    get_info = classmethod(get_info)

class Note(object):
    """A small message or comment to be attached to an Entity"""
    """A small message or comment to be attached to an Entity"""
    def __init__(self, id, entity, create_date, creator, 
                 subject, description):
        self.id = id         
        self.entity = entity
        self.create_date = create_date
        self.creator = creator
        self.subject = subject
        self.description = description
    def __repr__(self):
        return "<Note #%s %s %s>" % (self.id, 
                                     self.create_date.strftime("%Y-%m-%d"), 
                                     self.creator)       
    def __str__(self):
        return "%s <%s> %s" % (self.create_date.strftime("%Y-%m-%d"),
                              self.creator, self.subject)

class QuarantineType(object):
    """A type of quarantine that can be set on entities"""
    def __init__(self, name, description):
        self.name = name
        self.description = description
    
    def __str__(self):
        return self.description
    
    def __repr__(self):
        return "<QuarantineType %s>" % self.name
    
    def __eq__(self, other):
        return isinstance(other, QuarantineType) and \
               other.name == self.name    
    
    def get_all(cls):    
        """Returns all known Quarantine types"""
        pass
    get_all = classmethod(get_all)    

    def get_by_name(cls, name):
        """Returns the quarantine type of the given name"""
        pass
    get_by_name = classmethod(get_by_name)    
        
        
class Quarantine(object):
    def __init__(self, entity, type, start, end, who, why, disable_until):
        self.entity = entity
        self.type = type
        self.start = start
        self.end = end
        self.who = who
        self.why = why
        self.disable_until = disable_until
    
    def __repr__(self):
        return "<Quarantine %s on %s from %s>" % (self.type.name, 
                                                  self.entity,
                                                  self.start)

class Entity(object):
    
    def __init__(self, server):
        self.addresses = []
        self.contactinfo = []
        self.spreads = []
    
    def __repr__(self):
        try:
            desc = " " + self.name
        except AttributeError:
            desc = ""    
        if hasattr(self, "id"):
            desc = " id=%s%s" % (self.id, desc)
        return "<%s%s>" % (self.type, desc)
    
    def __str__(self):
        try:
            return self.name
        except AttributeError:
            if hasattr(self, "id"):
                return str(self.id)
            else:
                return repr(self)
    
    def fetch_by_id(cls, id):
        """Retrieves an instance with given id """
        # entity_info og entity_type_code
        pass
        
    fetch_by_id = classmethod(fetch_by_id)
    
    def delete(self):
        """Deletes this entity from the database.
        """
        pass
    
    def add_quarantine(self, type, why="", 
                       start=None, end=None):
        """Create and store a new quarantine on entity.
        Note: Only one quarantine of each quarantine type can be set on any
        given entity.
        
        type must be given, see QuarantineType.get_all()

        why is a string explaining the quarantine in verbose, if needed

        start - if given - is a date (mx.DateTime or iso8601-string) of
              when to start the quarantine. If not given, start==today

        end - likewise - but when to end. If not given, the quarantine has no given
                         end date.
        """
        
    def get_quarantines(self):
        """Returns a list of quarantine-objects, if the entity has any quarantines
            set.
        """
        pass

    def remove_quarantine(self, quarantine=None, type=None):    
        """Removes an existing quarantine from entity. 
        Parameters should be *either* a matching Quarantine object quarantine
        or a type - that could be QuarantineType or string."""
        pass
    
    def disable_quarantine(self, quarantine=None, type=None,
                           until=None):
        """Disables an existing quarantine on entity.
        
        Parameters should be *either* a matching Quarantine object quarantine
        or a type - that could be QuarantineType or string.
        until, if given, is the day to disable until - either a 
        
        mx.DateTime object or a ISO8601-formatted date, ex: "2003-12-24"
        """
        pass                       
    
    def get_history(self):
        """Returns a list of Change objects for recent changes"""
        pass    
    def add_note(self, subject, description):
        """Attatches a note to the entity."""
        pass

    def show_notes(self):
        """Get all notes attached to entities. 
        Returns a list of Note objects"""
        pass

    def remove_note(self, note):
        """Removes a given Note object from this entity"""
        pass
                            


class Group(Entity):
    
    def __str__(self):
        return self.name
    
    def create(cls, server, name, description):
        """ Creates a new group with given name and description.
        """
        pass
    create = classmethod(create)
    
    def fetch_by_name(cls, server, name):
        """ Retrieves an instance with given name.
        """
        pass
    fetch_by_name = classmethod(fetch_by_name)

    def search(cls, spread=None, name=None, desc=None):
        """Retrieve groups that matches the given criteria. 
           ``name`` and ``desc`` (if given) should be strings. 
           Wildcards * and ? might be used.
           Returns tuples of (id, name, description).
           """
        pass    

    def get_members(self):
        """ Retrieves members of the group, does _not_ recurse, ie.
            groups that's a member of the group will be listed.
        """
        pass
        
    def get_all_accounts(self):
        """ Retrieves members of the group, _with_ recursion.
        """
        pass
        
    def add_member(self, member, operation):
        """ Adds ``member`` to group with ``operation``.
        """
        pass
        
    def remove_member(self, member):
        """ Removes ``member`` from group.
        """
        pass

    def change_member_operation(self, member, operation):
        """Changes ``member``'s ``operation`` in group."""
        self.remove_member(member)
        self.add_member(member, operation)

    def delete_group(self):
        """Deletes the group."""
        pass


class Account(Entity):
    
    def __str__(self):
        return self.name

#    def create(cls, name):
#        """Creates an account with given name."""
#        pass
#    create = classmethod(create)

    def fetch_by_name(cls, name):
        """Retrieves an instance with given name."""
        pass
    fetch_by_name = classmethod(fetch_by_name)

    def search(cls, name=None, create_date=None, creator_id=None, home=None, 
               disk_id=None, expire_date=None, owner_id=None, np_type=None, auth_method=None):
        """Retrieves accounts that matches the given criteria.
           ``name``, ``home`` (if given) should be strings. Wildcards (* and ?) might be used.
           ``create_date`` and ``expire_date`` are special strings:
             >YYYY-MM-DD, =YYYY-MM-DD, <YYYY-MM-DD
           ``disk_id`` and ``owner_id`` are integers.
           ``np_type``, integer or string, wildcards allowed [if string]
           ``auth_method``, integer or string, wildcards allowed [if string]."""
        pass

    def set_home(self, home):
        """Changes ``home`` for account."""
        pass

    def set_disk_id(self, disk_id):
        """Sets ``disk_id`` for account."""
        pass

    def set_owner(self, entity_id):
        """Sets owner of account."""
        pass
    
    def set_expire_date(self, expire_date):
        """Sets expire_date of account."""
        pass

    def get_auth_data(self, method=None):
        """Retrieves auth_data for given auth. method, if method is 
           None, all methods are returned.
           Result is a touple of touples ((method,auth_data),)."""
        pass

    def get_account_types(self):
        """Retrieves a touple of dicts with account_types for account."""
        pass
    
    def delete(self):
        """Delete the account."""
        pass   


class Person(Entity):

    def __str__(self):
        return self.name

    def create(cls):
        pass
    create = classmethod(create)

    def search(cls, name=None, account=None, birthno=None, birthdate=None):
        pass

    def delete(self):
        pass

class OU(Entity):

    def __str__(self):
        return self.name

    def create(cls):
        pass
    create = classmethod(create)

    def search(cls, name=None):
        pass

    def delete(self):
        pass

class Constants(object):
    JOIN = 1
    INTERSECTION = 2
    DIFFERENCE = 3
