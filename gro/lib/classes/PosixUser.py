from DatabaseClass import DatabaseAttr
from Account import Account
from Group import Group
from Types import CodeType, GroupMemberOperationType

import Registry
registry = Registry.get_registry()

__all__ = ['PosixUser', 'PosixShell']

import Cerebrum.modules.PosixUser

table = 'posix_shell_code'
class PosixShell(CodeType):
    primary = [
        DatabaseAttr('id', table, int),
    ]
    slots = [
        DatabaseAttr('name', table, str),
        DatabaseAttr('shell', table, str)
    ]

    db_attr_aliases = {
        table:{
            'id':'code',
            'name':'code_str'
        }
    }
registry.register_class(PosixShell)

def get_gecos(self):
    p = Cerebrum.modules.PosixUser.PosixUser(self.get_database())
    p.find(self.get_id())

    return p.get_gecos()

table = 'posix_user'
Account.register_attribute(DatabaseAttr('posix_uid', table, int, optional=True))
Account.register_attribute(DatabaseAttr('primary_group', table, Group, optional=True))
Account.register_attribute(DatabaseAttr('pg_member_op', table, GroupMemberOperationType, optional=True))
Account.register_attribute(DatabaseAttr('gecos', table, str, optional=True), get=get_gecos)
Account.register_attribute(DatabaseAttr('shell', table, PosixShell, optional=True))
Account.db_attr_aliases[table] = {'id':'account_id', 'primary_group':'gid'}

Account.build_methods()
Account.search_class.build_methods()

# arch-tag: 85b076c6-69e1-4108-9ac8-f3fe60a44920
