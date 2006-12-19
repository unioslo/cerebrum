#!/usr/bin/env python

from sets import Set

# This is the auth_operation_sets and auth_operations used at NTNU.

operation_sets = {
    'own_account': {
      'desc': 'operations all users should be allowed to do with their own account',
      'codestrs': ("Account.set_password", )},
    'public': {
      'desc': 'operations all users should be allowed to do',
      'codestrs': ("Commands.get_account_by_name",)},
    'orakel': {
      'desc': 'operations that the orakel-group should be allowed to do on users in a given affiliation',
      'codestrs': ("Account.a.set_expire_date",)},
}

# There are some types and codes that we need access to.

types = {
    'bootstrap_group': 19,
    'bootstrap_user': 20,
    'difference': 187,
    'intersection': 188,
    'union': 189,
    'account': 147,
    'disk': 148,
    'group': 149, 
    'visibility': 331,
    'host': 150, 
    'ou': 151, 
    'account_names': 363,
    'group_names': 363,
    'person': 152,
    'ANSATT': 301,
    'testbruker': 146,
} 

# Create a set of accounts for testing

accounts = {
    'user': {
        'id': 100,
        'type': types['account'],
        'owner': types['bootstrap_group'],
        'owner_type': types['group'],
        'np_type': types['testbruker'],
        'create_date': '2006-01-01',
        'creator': types['bootstrap_user'],
        'expire_date': '2008-01-01',
        'description': 'Test User',
        'name': 'testuser',
        'gecos': None,
        'posix_uid': None,
        'primary_group': None,
        'pg_member_op': None,
        'shell': None,
        'superuser': False,
    },
    'target': {
        'id': 105,
        'type': types['account'],
        'owner': types['bootstrap_group'],
        'owner_type': types['group'],
        'np_type': types['testbruker'],
        'create_date': '2006-01-01',
        'creator': types['bootstrap_user'],
        'expire_date': '2008-01-01',
        'description': 'Test User',
        'name': 'target',
        'gecos': None,
        'posix_uid': None,
        'primary_group': None,
        'pg_member_op': None,
        'shell': None,
        'superuser': False,
    },
    'orakel': {
        'id': 200,
        'type': types['account'],
        'owner': types['bootstrap_group'],
        'owner_type': types['group'],
        'np_type': types['testbruker'],
        'create_date': '2006-01-01',
        'creator': types['bootstrap_user'],
        'expire_date': '2008-01-01',
        'description': 'Test User',
        'name': 'orakelus',
        'gecos': None,
        'posix_uid': None,
        'primary_group': None,
        'pg_member_op': None,
        'shell': None,
        'superuser': False,
    },
    'bootstrap': {
        'id': types['bootstrap_user'],
        'type': types['account'],
        'owner': types['bootstrap_group'],
        'owner_type': types['group'],
        'np_type': types['testbruker'],
        'create_date': '2006-01-01',
        'creator': types['bootstrap_user'],
        'expire_date': '2008-01-01',
        'description': 'Superuser',
        'name': 'bootstrap_account',
        'gecos': None,
        'posix_uid': None,
        'primary_group': None,
        'pg_member_op': None,
        'shell': None,
        'superuser': True,
    },
}

# Create a set of people for testing

people = {
    'lise': {
        'export_id': None,
        'birth_date': '1960-01-21',
        'gender': 'F',
        'deceased_date': None,
        'desc': 'Testperson',
        'first': 'Lise',
        'last': 'Kjemi',
        'id': 1000,
    },
    'per': {
        'export_id': None,
        'birth_date': '1960-01-20',
        'gender': 'M',
        'deceased_date': None,
        'desc': 'Testperson',
        'first': 'Per',
        'last': 'Person',
        'id': 1001,
    },
    'test': {
        'export_id': None,
        'birth_date': '1960-01-19',
        'gender': 'M',
        'deceased_date': None,
        'desc': 'Testperson',
        'first': 'Test',
        'last': 'Testesen',
        'id': 1002,
    },
}

# Create a set of groups for testing

groups = {
    'testgroup': {
        'name': 'testgroup',
        'desc': 'Testgruppe',
        'expire': '2006-12-24',
    },
}

ous = {
    'testou': {
        'ou_id': 4000,
        'name': 'testou',
        'acronym': 'TO',
        'short_name': 'TO',
        'display_name': 'Test OU',
        'sort_name': 'TO',
        'type': types['ou'],
    },
}

# vim: foldmethod=marker nowrap
