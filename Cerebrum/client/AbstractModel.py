"""Abstract superclasses for the model, ie. the business data.
   Implementation modules should subclass all of these classes
   providing network communication, updating the database or
   whatever might be neccessary. """


class Address:

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

class ChangeType:
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

class Change:
    """A change entry in the history log"""
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
            dest = " " + self.dest
        else:
            dest = ""    
        return "<Change %s %s %s%s>" % (date, self.type, self.subject, self.dest)
    def __str__(self):    
        words = self.__dict__.copy()
        try:
            words.update(self.params)
        except Exception, e:
            pass
        try:
            msg = self.type.message % words
        except KeyError:
            msg = "%s %s" % (self.type.message, self.subject)
        date = self.date.strftime("%Y-%m-%d")    
        return "%s %s" % (date, msg)

class ContactInfo:

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
        

class Entity:
    
    def __init__(self, server):
        # Holds a list of all names for each valuedomain
        self.names = {}
        self.addresses = []
        self.contactinfo = []
        self.spreads = []
    
    def __repr__(self):
        names = ["%s=%s" % (key, value) for (key,value) in self.names]
        desc = " ".join(names)
        if desc:
            desc = " " + desc
        if hasattr(self, "id"):
            desc = " id=%s%s" % (self.id, desc)
        return "<%s%s>" % (self.type, desc)
    
    def __str__(self):
        try:
            return self.names[0][1]    
        except:
            if hasattr(self, "id"):
                return self.id    
            else:
                return repr(self)    
            
    
    def fetch_by_id(cls, id):
        """Retrieves an instance with given id """
        # entity_info og entity_type_code
        pass
        
    fetch_by_id = classmethod(fetch_by_id)
    
    def delete(self):
        """ Deletes this entity from the database.
        """
        pass
        
    def get_address_info(self):
        pass
        
    def get_contact_info(self):
        pass
        
    def get_spread_info(self):
        pass
        
    def add_quarantine(self, quarantine_type, description, start_date=None, 
                       disable_until=None, end_date='default'):
        """Adds the enitity to a defined ``quarantine_type`` with ``description``.
           
           Quarantine starts at ``start_date``, defaults to None which is now.
           
           Quarantine ends at ``end_date``, defaults to 'default' which uses the 
           duration field from the defined quarantine-type. Setting this parameter
           to None means indefinitely.
           
           Setting ``disable_until`` indicates that the quarantine is lifted until
           given date. This is useful e.g. for giving users who have been
           quarantined for having too old passwords a limited time to change
           their password; in order to change their password they must use
           their old password, and this won't work when they're quarantined.
        """
        pass
        
    def get_quarantines(self):
        """ Returns a list of quarantine-objects, if the entity has any quarantines
            set.
        """
        pass
    
    def get_history(self):
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

    def create(cls, name):
        """Creates an account with given name."""
        pass
    create = classmethod(create)

    def fetch_by_name(cls, name):
        """Retrieves an instance with given name."""
        pass
    fetch_by_name = classmethod(fetch_by_name)


class Quarantine:
    def __init__ (self, start_date, end_date, quarantine_type, reason):
        self.start_date = start_date
        self.end_date = end_date
        self.type = quarantine_type
        self.reason = reason

class Constants:
    JOIN = 1
    INTERSECTION = 2
    DIFFERENCE = 3
