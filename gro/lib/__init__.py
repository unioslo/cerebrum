from classes.Account import *
from classes.Disk import *
from classes.Entity import *
from classes.Group import *
from classes.Host import *
from classes.Locking import *
from classes.OU import *
from classes.Person import *
from classes.Types import *

from classes.Builder import *

from APHandler import APHandler
# Base classes
APHandler.register_gro_class(Account)
APHandler.register_gro_class(AccountAuthentication)
APHandler.register_gro_class(Address)
APHandler.register_gro_class(ContactInfo)
APHandler.register_gro_class(Disk)
APHandler.register_gro_class(Entity)
APHandler.register_gro_class(Group)
APHandler.register_gro_class(GroupMember)
APHandler.register_gro_class(Host)
APHandler.register_gro_class(NameType)
APHandler.register_gro_class(Note)
APHandler.register_gro_class(OU)
APHandler.register_gro_class(Person)
APHandler.register_gro_class(PersonName)
APHandler.register_gro_class(SourceSystem)
APHandler.register_gro_class(Spread)
# Type classes (or constants)
APHandler.register_gro_class(AddressType)
APHandler.register_gro_class(AuthenticationType)
APHandler.register_gro_class(ContactInfoType)
APHandler.register_gro_class(EntityType)
APHandler.register_gro_class(GenderType)
APHandler.register_gro_class(GroupMemberOperationType)
APHandler.register_gro_class(GroupVisibilityType)
APHandler.register_gro_class(OUPerspectiveType)
APHandler.register_gro_class(QuarantineType)
# Search classes
AccountSearch = Account.create_search_class()
DiskSearch = Disk.create_search_class()
GroupSearch = Group.create_search_class()
HostSearch = Host.create_search_class()
OUSearch = OU.create_search_class()
PersonSearch = Person.create_search_class()

APHandler.register_gro_class(AccountSearch)
APHandler.register_gro_class(DiskSearch)
APHandler.register_gro_class(GroupSearch)
APHandler.register_gro_class(HostSearch)
APHandler.register_gro_class(OUSearch)
APHandler.register_gro_class(PersonSearch)

APHandler.build_classes()
