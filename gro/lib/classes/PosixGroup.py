from DatabaseClass import DatabaseAttr

from Group import Group

import Registry
registry = Registry.get_registry()

Group.register_attribute(DatabaseAttr('posix_gid', 'posix_group', int, optional=True))
Group.db_attr_aliases['posix_group'] = {'id':'group_id'}
Group.build_methods()
Group.build_search_class()
