"""Abstract superclasses for the model, ie. the business data.
   Implementation modules should subclass all of these classes
   providing network communication, updating the database or
   whatever might be neccessary.
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
    
    def loadEntityInfo(self, id):
        """Loads entity specific data from server using the given <id>.
        """
        warn("entity_info not implemented yet")
        return
        info = self.server.entity_info(id)
        self.names = info['names']
        self.type = info['type']

    def getByID(cls, id, server):
        """ Retrieves an instance from <server> with given <id>.
            <server> is a ServerConnection.
        """
        entity = Entity(server)
        entity.loadEntityInfo(id)
        return entity
        
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


class Group(Entity, Abstract.Group):
    
    def __init__(self, server):
        Entity.__init__(self, server)
    
    def findByName(cls, name, server):
        """ Retrieves an instance with given name.
        """
        group = Group(server)
        # FIXME: Check for errors: not found, etc.
        info = server.group_info(name)
        #'gid', 'entity_id', 'spread', 'expire', 'desc'
        #spread=kommaseparert liste med code_str
        
        group.name = name
        group.loadEntityInfo(info['entity_id'])
        group.description = info['desc']
        group.expire = info['expire']
        group.gid = info.get('gid')
        # FIXME: Only spread names currently
        group.spreads = info['spread'].split(",")
        return group
        
    findByName = classmethod(findByName)

    def getMembers(self):
        """ Retrieves members of the group, does _not_ recurse, ie.
            groups that's a member of the group will be listed.
        """
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
        
    def getAllAccounts(self):
        """ Retrieves members of the group, _with_ recursion.
        """
        pass
        
    def addMember(self, member, operation="union"):
        """ Adds <member> to group with <operation>.
            <operation> is one of 'union', 'difference' and
            'intersection', the default is 'union'.
        """
        # FIXME: Make this use the soon-to-be-universiall group_add
        self.server.group_gadd(member.name, self.name, operation)

    def removeMember(self, member):
        """ Removes <member> from group.
        """
        # FIXME: Make this use the soon-to-be-universiall group_remove
        self.server.group_gremove(member.name, self.name)

    def deleteGroup(self):
        """ Deletes the group.
        """
        self.server.group_delete(self.name)

