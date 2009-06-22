from mx.DateTime import DateTime
from lib.data.MemberDTO import MemberDTO
from lib.data.GroupDTO import GroupDTO

account_cetest1 = 354991
large_group_id = 149
posix_group_id = 354983
posix_group_name = "test_posix"
expired_group_id = 354981
nonposix_group_id = 354984
quarantined_group_id = 354992
notes_group_id = 354992
spread_group_id = 354992

def get_test_testesen():
    dto = MemberDTO()
    dto.id = 354985
    dto.name = 'Test Testesen'
    dto.type_name = 'person'
    dto.has_owner = False
    return dto

def get_cetest1():
    dto = MemberDTO()
    dto.id = 354991
    dto.name = 'cetest1'
    dto.type_name = 'account'
    dto.has_owner = True
    dto.owner = get_test_testesen()
    return dto

def get_fake_posix_group():
    dto = GroupDTO()
    dto.id = 354983
    dto.name = 'test_posix'
    dto.description = 'Group used in cereweb-tests'

    dto.create_date = DateTime(2009, 6, 11)
    dto.members = [get_cetest1()]

    dto.posix_gid = 1002
    dto.is_posix = True

    dto.is_expired = False
    dto.expire_date = None

    dto.visibility_name = "All"
    dto.visibility_value = "A"

    dto.expire_date = DateTime(3000, 1, 1)
    return dto
