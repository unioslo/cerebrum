#!/usr/bin/env python

from sets import Set

# This is the auth_operation_sets and auth_operations used at NTNU.
public = [ # {{{
        'CerewebMotd.get_creator',
        'EntityExternalId.get_id_type',
        'EntityExternalId.get_external_id',
        'Commands.find_email_address',
        'Commands.get_account_by_name', 
        'Commands.get_date',
        'Commands.get_date_none', 
        'Commands.get_date_now',
        'Commands.get_datetime', 
        'Commands.get_email_domains_by_category', 
        'Commands.get_extentions',
        'Commands.get_group_by_name',
        'Commands.get_last_changelog_id', 
        'Commands.has_extention',
        'Commands.strptime',
        'Account.get_id',
        'Account.get_name',
        'Account.get_type',
        'Account.get_description',
] # }}}
mySelf = [ # {{{
        'Account.get_accounts',
        'Account.get_address',
        'Account.get_addresses',
        'Account.get_create_date',
        'Account.get_creator',
        'Account.get_description',
        'Account.get_direct_groups',
        'Account.get_entity_name',
        'Account.get_expire_date',
        'Account.get_external_id',
        'Account.get_external_ids',
        'Account.get_groups',
        'Account.get_homedir',
        'Account.get_id',
        'Account.get_name',
        'Account.get_type',
        'Account.get_owner',
        'Account.get_owner_type',
        'Account.get_spreads',
        'Account.is_expired',
        'Account.is_posix',
        'Account.is_quarantined',
        'Account.set_password',
        'Person.get_accounts',
        'Person.get_active_quarantines',
        'Person.get_address',
        'Person.get_addresses',
        'Person.get_affiliations',
        'Person.get_all_contact_info',
        'Person.get_all_quarantines',
        'Person.get_birth_date',
        'Person.get_cached_full_name',
        'Person.get_contact_info',
        'Person.get_deceased_date',
        'Person.get_description',
        'Person.get_direct_groups',
        'Person.get_email_domain',
        'Person.get_entity_name',
        'Person.get_export_id',
        'Person.get_external_id',
        'Person.get_external_ids',
        'Person.get_gender',
        'Person.get_groups',
        'Person.get_id',
        'Person.get_names',
        'Person.get_primary_account',
        'Person.get_quarantine',
        'Person.get_quarantines',
        'Person.get_spreads',
        'Person.get_type',
        'Person.is_quarantined',
] # }}}
orakel = [ # {{{
        'Commands.create_cereweb_option', # fyll inn ordentlig data her.
] # }}}

operation_sets = {
    'public': {
      'desc': 'operations all users should be allowed to do',
      'codestrs': public},
    'mySelf': {
      'desc': 'operations all users should be allowed to do with their own account',
      'codestrs': mySelf},
    'orakel': {
      'desc': 'operations that the orakel-group should be allowed to do on users in a given affiliation',
      'codestrs': orakel},
}

# vim: foldmethod=marker nowrap
