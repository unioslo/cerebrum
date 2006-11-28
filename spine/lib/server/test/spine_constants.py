#!/usr/bin/env python

own_account = [
        'Account.get_accounts',
        'Account.get_address',
        'Account.get_addresses',
        'Account.get_create_date',
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
        'Account.get_owner',
        'Account.get_spreads',
        'Account.is_expired',
        'Account.is_posix',
        'Account.is_quarantined',
        'Account.set_password']

own_person = [
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
        'Person.is_quarantined']

public_commands = [
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
        'Commands.strptime']

operation_sets = {
    'own_account': {
      'desc': 'operations all users should be allowed to do with their own account',
      'codestrs': own_account + own_person },
    'public': {
      'desc': 'operations all users should be allowed to do',
      'codestrs': public_commands }
    }
