import crypt

from Builder import Method
from DatabaseClass import DatabaseClass, DatabaseAttr

from Account import Account
from Disk import Disk
from Types import Spread, HomeStatus

import Registry
registry = Registry.get_registry()

table = 'account_home'
class AccountHome(DatabaseClass):
    primary = [
        DatabaseAttr('account', table, Account),
        DatabaseAttr('spread', table, Spread)
    ]
    slots = [
        DatabaseAttr('home', table, str, write=True),
        DatabaseAttr('disk', table, Disk, write=True),
        DatabaseAttr('status', table, HomeStatus, write=True)
    ]

    db_attr_aliases = {
        table:{
            'account':'account_id',
            'disk':'disk_id'
        }
    }

registry.register_class(AccountHome)

# arch-tag: 0fd2376b-df17-418a-a7c9-2b6bd87406f9
