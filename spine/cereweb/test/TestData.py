from mx.DateTime import DateTime
from lib.data.EntityDTO import EntityDTO
from lib.data.AccountDTO import AccountDTO
from lib.data.GroupDTO import GroupDTO
from lib.data.DTO import DTO

bootstrap_account_id = 2
account_without_posix_groups = bootstrap_account_id
posix_account_id = 355252
posix_account_primary_group_id = 354983
noted_account_id = 355252
quarantined_account_id = 355252
nonposix_account_id = 354991
nonposix_account_owner_id = 354985
nonposix_account_creator_id = 2
affiliated_account_id = 123397
account_cetest1 = 354991
groupless_account_id = 356047
large_group_id = 149
posix_group_id = 354983
posix_group_name = "test_posix"
expired_group_id = 354981
nonposix_group_id = 354984
quarantined_group_id = 354992
notes_group_id = 354992
spread_group_id = 354992
test_testesen_id = 354985

def get_test_testesen():
    dto = EntityDTO()
    dto.id = test_testesen_id
    dto.name = 'Test Testesen'
    dto.type_name = 'person'
    dto.type_id = 19
    return dto

def get_nonposix_account_dto():
    dto = AccountDTO()
    dto.id = nonposix_account_id
    dto.name = 'cetest1'
    dto.type_name = 'account'
    dto.type_id = 17
    dto.expire_date = DateTime(3000, 1, 1)
    dto.create_date = DateTime(2009, 6, 11)

    return dto

def get_posix_account_dto():
    dto = AccountDTO()
    dto.id = posix_account_id
    dto.name = 'ctestpos'
    dto.type_name = 'account'
    dto.type_id = 17
    dto.is_posix = True
    dto.posix_uid = 1048796
    dto.create_date = DateTime(2009, 6, 24)
    dto.gecos = "Test Testesen"
    dto.shell = "bash"
    return dto

def get_affiliation_account_dto():
    dto = DTO()
    dto.priority = 312
    dto.type_name = "STUDENT"
    dto.type_id = 96

    dto.ou = EntityDTO()
    dto.ou.id = 60
    dto.ou.name = "Institutt for elektronikk og telekommunikasjon"
    dto.ou.type_name = "ou"
    dto.ou.type_id = 23
    return dto

def get_nonposix_account_owner_dto():
    dto = EntityDTO()
    dto.id = nonposix_account_owner_id
    dto.name = 'Test Testesen'
    dto.type_name = 'person'
    dto.type_id = 19
    return dto
    
def get_nonposix_account_creator_dto():
    dto = EntityDTO()
    dto.id = nonposix_account_creator_id
    dto.name = 'bootstrap_account'
    dto.type_name = 'account'
    dto.type_id = 17
    return dto

def get_posix_account_primary_group_dto():
    dto = EntityDTO()
    dto.id = posix_account_primary_group_id
    dto.name = 'test_posix'
    dto.type_name = "group"
    dto.type_id = 18
    return dto
    

def get_cetest1():
    dto = EntityDTO()
    dto.id = account_cetest1
    dto.name = 'cetest1'
    dto.type_name = 'account'
    dto.type_id = 17
    return dto

def get_fake_posix_group():
    dto = GroupDTO()
    dto.id = 354983
    dto.name = 'test_posix'
    dto.description = 'Group used in cereweb-tests'

    dto.create_date = DateTime(2009, 6, 11)
    dto.members = []

    dto.posix_gid = 1002
    dto.is_posix = True

    dto.is_expired = False
    dto.expire_date = None

    dto.visibility_name = "All"
    dto.visibility_value = "A"

    dto.expire_date = DateTime(3000, 1, 1)
    return dto
