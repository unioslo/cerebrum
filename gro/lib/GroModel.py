import classes.Registry
registry = classes.Registry.get_registry()

from classes.Builder import Attribute, Builder, CorbaBuilder, Method
registry.register_class(Attribute)
registry.register_class(Builder)
registry.register_class(CorbaBuilder)
registry.register_class(Method)

from classes.Searchable import Searchable
registry.register_class(Searchable)

from classes.CerebrumClass import CerebrumAttr, CerebrumClass, CerebrumEntityAttr, CerebrumTypeAttr
registry.register_class(CerebrumAttr)
registry.register_class(CerebrumClass)
registry.register_class(CerebrumEntityAttr)
registry.register_class(CerebrumTypeAttr)

from classes.Types import *
registry.register_class(AddressType)
registry.register_class(AuthenticationType)
registry.register_class(AuthOperationType)
registry.register_class(ContactInfoType)
registry.register_class(EntityType)
registry.register_class(GenderType)
registry.register_class(GroupMemberOperationType)
registry.register_class(GroupVisibilityType)
registry.register_class(NameType)
registry.register_class(OUPerspectiveType)
registry.register_class(QuarantineType)
registry.register_class(SourceSystem)
registry.register_class(Spread)

from classes.Auth import *
registry.register_class(AuthOperationSet)
registry.register_class(AuthOperation)
registry.register_class(AuthOperationAttr)
registry.register_class(AuthRole)
registry.register_class(EntityAuth)

from classes.Entity import Entity, Note, Address, ContactInfo
registry.register_class(Entity)
registry.register_class(Note)
registry.register_class(Address)
registry.register_class(ContactInfo)

from classes.Account import Account, AccountAuthentication
registry.register_class(Account)
registry.register_class(AccountAuthentication)

from classes.ChangeLog import ChangeType, ChangeEvent
registry.register_class(ChangeType)
registry.register_class(ChangeEvent)

from classes.Host import Host
registry.register_class(Host)

from classes.Disk import Disk
registry.register_class(Disk)

from classes.Group import Group, GroupMember
registry.register_class(Group)
registry.register_class(GroupMember)

from classes.OU import OU, OUStructure
registry.register_class(OU)
registry.register_class(OUStructure)

from classes.Person import Person, PersonName
registry.register_class(Person)
registry.register_class(PersonName)

from classes.Date import Date
registry.register_class(Date)
