#!/usr/bin/env python

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Constants
from sets import Set
from Cerebrum.spine.SpineLib import Builder
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet

db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner']
if db_user is None:
    db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user']
    if db_user is not None:
        print "'table_owner' not set in CEREBRUM_DATABASE_CONNECT_DATA."
        print "Will use regular 'user' (%s) instead." % db_user

def create_op_set(set_name, set_desc, op_codestrs):
    db = Factory.get('Database')(user=db_user)
    auth_op_set = BofhdAuthOpSet(db)
    auth_op_set.populate(set_name)
    auth_op_set.write_db()
    for codestr in op_codestrs:
        code = _AuthRoleOpCode(codestr)
        auth_op_set.add_operation(int(code))
    db.commit()


name = 'own_account'
desc = 'operations all users should be allowed to do with their own account'
auth_op_codestrs = [
    'Account.get_name',
    'Account.get_accounts',
    'Account.get_addresses',
    'Account.get_groups',
    'Account.get_address',
    'Account.get_homedir',
    'Account.get_id',
    'Account.get_entity_name',
    'Account.get_expire_date',
    'Account.get_owner',
    'Account.is_posix',
    'Account.set_password',
    'Account.get_external_ids',
    'Account.is_quarantined',
    'Account.get_external_id',
    'Account.is_expired',
    'Account.get_spreads',
    'Account.get_create_date',
    'Account.get_description',
    'Account.get_direct_groups',
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
    'Person.is_quarantined',]

create_op_set(name, desc, auth_op_codestrs)

name = 'public'
desc = 'Commands har ikke targets og er derfor forskjellige fra Person og Account'
auth_op_codestrs = ['Commands.find_email_address',
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

create_op_set(name, desc, auth_op_codestrs)
