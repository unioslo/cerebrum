"""Abstract superclasses for the model, ie. the business data.
   Implementation modules should subclass all of these classes
   providing network communication, updating the database or
   whatever might be neccessary.
"""


class Address:
    pass


class ContactInfo:
    pass


class Entity:
    
    def __init__(self):
        # Holds a list of all names for each valuedomain
        self.names = {}
        self.addresses = []
        self.contactinfo = []
        self.spreads = []
    
    def getByID (cls, id):
        """ Retrieves an instance with given id """
        # entity_info og entity_type_code
        pass
        
    getByID = classmethod(getByID)
    
    def delete(self):
        """ Deletes this entity from the database.
        """
        pass
        
    def getAddressInfo(self):
        pass
        
    def getContactInfo(self):
        pass
        
    def getSpreadInfo(self):
        pass
        
    def addQuarantine(self, quarantineType, description, startDate=None, 
                      disableUntil=None, endDate='default'):
        """ Adds the enitity to a defined <quarantineType> with <description>.
            
            Quarantine starts at <startDate>, defaults to None which is now.
            
            Quarantine ends at <endDate>, defaults to 'default' which uses the 
            duration field from the defined quarantine-type. Setting this parameter
            to None means indefinitely.
            
            Setting <disableUntil> indicates that the quarantine is lifted until
            given date. This is useful e.g. for giving users who have been
            quarantined for having too old passwords a limited time to change
            their password; in order to change their password they must use
            their old password, and this won't work when they're quarantined.
        """
        pass
        
    def listQuarantines(self):
        """ Returns a list of quarantine-objects, if the entity has any quarantines
            set.
        """
        pass


class Group(Entity):
    
    def create(cls, name, description):
        """ Creates a new group with given name and description.
        """
        pass

    create = classmetod(create)
    
    def findByName(cls, name):
        """ Retrieves an instance with given name.
        """
        pass
        
    findByName = classmethod(findByName)

    def getMembers(self):
        """ Retrieves members of the group, does _not_ recurse, ie.
            groups that's a member of the group will be listed.
        """
        pass
        
    def getAllAccounts(self):
        """ Retrieves members of the group, _with_ recursion.
        """
        pass
        
    def addMember(self, member, operation):
        """ Adds <member> to group with <operation>.
        """
        pass
        
    def removeMember(self, member):
        """ Removes <member> from group.
        """
        pass

    def changeMemberOperation(self, member, operation):
        """ Changes <member>'s <operation> in group.
        """
        self.removeMember(member)
        self.addMember(member, operation)

    def deleteGroup(self):
        """ Deletes the group.
        """
        pass


class Account(Entity):

    def create(cls, name):
        """ Creates an account with given name.
        """
        pass

    def findByName(cls, name):
        """ Retrieves an instace with given name.
        """
        pass

    findByName = classmethod(findByName)

class Quarantine:
    def __init__ (self, startDate, endDate, quarantineType, reason):
        self.startDate = startDate
        self.endDate = endDate
        self.type = quarantineType
        self.reason = reason
