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
Account.register_attribute(DatabaseAttr('posix_uid', table, int))
Account.register_attribute(DatabaseAttr('gid', table, Group))
Account.register_attribute(DatabaseAttr('pg_member_op', table, GroupMemberOperationType))
Account.register_attribute(DatabaseAttr('gecos', table, str), get=get_gecos)
Account.register_attribute(DatabaseAttr('shell', table, PosixShell))
Account.db_attr_aliases[table] = {'id':'account_id'}

Account.build_methods()
Account.search_class.build_methods()
