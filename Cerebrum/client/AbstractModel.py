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
    
    def __init__(self):
        # Holds a list of all names for each valuedomain
        self.names = {}
        self.addresses = []
        self.contactinfo = []
        self.spreads = []
    
    def get_by_id(cls, id):
        """Retrieves an instance with given id """
        # entity_info og entity_type_code
        pass
        
    get_by_id = classmethod(get_by_id)
    
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
        
    def list_quarantines(self):
        """ Returns a list of quarantine-objects, if the entity has any quarantines
            set.
        """
        pass


class Group(Entity):
    
    def create(cls, name, description):
        """ Creates a new group with given name and description.
        """
        pass
    create = classmethod(create)
    
    def find_by_name(cls, name):
        """ Retrieves an instance with given name.
        """
        pass
    find_by_name = classmethod(find_by_name)

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

    def create(cls, name):
        """Creates an account with given name."""
        pass
    create = classmethod(create)

    def find_by_name(cls, name):
        """Retrieves an instance with given name."""
        pass
    find_by_name = classmethod(find_by_name)


class Quarantine:
    def __init__ (self, start_date, end_date, quarantine_type, reason):
        self.start_date = start_date
        self.end_date = end_date
        self.type = quarantine_type
        self.reason = reason
