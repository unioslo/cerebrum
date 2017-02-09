# -*- coding: utf-8 -*-
#
# Copyright 2013-2016 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

from Cerebrum.modules.bofhd.bofhd_core_help import *

def get_help_strings():
    return (group_help, command_help, arg_help)

def _group_help_modifications():
    """Updates the global group_help dictionary."""
    removekeys = ['disk', 'entity', 'host', 'pquota']
    #remove_keys(group_help, removekeys)
    # Add elements
    group_help['print'] = 'Printer quota manipulation'

def _command_help_modifications():
    """Updates the global command_help dictionary."""

    # Changes due to discovered typos, poor English or the core help being close enough:
    # email/email_spam_action and email/email_spam_level: user's while not meaning users' and not using "the" looks weird, using "target's" like in the original
    # group/group_list_expanded: not "og"
    # misc/misc_affiliations: defined affiliations
    # person_accounts: 'View the accounts a person owns' instead of 'View account a person is owner of'
    # misc_dls: disks instead of disk
    # misc_list_passwords: passwords instead of password
    # person/person_accounts: accounts instead of account

    # Can this be right?
    # misc/misc_check_passw instead of misc/misc_check_password ?

    removekeys = ['disk', 'entity', 'host']
    #remove_keys(command_help, removekeys)

    # Remove all but some subkeys for some keys
    keep = {'access':['access_grant', 'access_group', 'access_host', 'access_revoke'],
            'email':['email_add_address', 'email_add_domain_affiliation', 'email_add_forward', 'email_add_tripnote','email_create_domain', 'email_create_forward_target', 'email_create_multi', 'email_delete_multi', 'email_domain_configuration', 'email_domain_info', 'email_forward', 'email_info', 'email_list_tripnotes', 'email_migrate', 'email_move', 'email_quota', 'email_remove_address', 'email_remove_domain_affiliation', 'email_remove_forward', 'email_remove_tripnote', 'email_spam_action', 'email_spam_level', 'email_tripnote', 'email_update']
            }
    #remove_not_kept_subkeys(command_help, keep)

    # Remove subkeys
    remove = {'group':['group_memberships', 'group_multi_add', 'group_multi_remove', 'group_padd', 'group_search', 'group_set_description'],
             'misc':['misc_cancel_request', 'misc_list_requests', 'misc_verify_password', 'misc_check_password', 'misc_samba_mount'],
             'person': ['person_clear_address', 'person_clear_id', 'person_clear_name', 'person_set_bdate', 'person_set_name'],
             'perm': ['perm_who_has_perm'],
             'user': ['user_find', 'user_restore', 'user_send_welcome_sms', 'user_set_disk_quota', 'user_set_disk_status']}
    #remove_keys_subkeys(command_help, remove)

    # Add Keys
    command_help['print'] = {}

    # Add subkeys
    command_help['email']['email_exchange_migrate'] = 'Migrate email account from IMAP to Exchange'
    command_help['group']['group_list_all'] = 'List all existing groups'
    command_help['print']['printer_qoff'] = 'Turn off the printer quota for an account'
    command_help['print']['printer_qpq'] = 'View the printer quota information for an account'
    command_help['print']['printer_upq'] = 'Manually update printer quota for an account'
    command_help['misc']['misc_checkpassw'] = 'Test the quality of a given password'
    command_help['misc']['misc_user_passwd'] = 'Check whether an account has a given password'

    # Modify subkeys
    command_help['group']['group_gadd'] = 'Let another group join a group'
    command_help['group']['group_gremove'] = 'Remove member-groups from a given group'
    command_help['group']['group_list'] = 'List account members of a group'
    command_help['misc'].update({'misc_affiliations': 'List all defined affiliations',
                            'misc_change_request': 'Change execution time for a pending request',
                            'misc_clear_passwords': 'Clear password(s) from the altered-passwords list in the current sessions',
                            'misc_dadd': 'Register a disk in Cerebrum database',
                            'misc_dls': 'List all registered disks for a given host',
                            'misc_drem': 'Remove a disk entry from Cerebrum',
                            'misc_hadd': 'Register a new host in the Cerebrum database',
                            'misc_hrem': 'Remove a host entry from Cerebrum',
                            'misc_list_passwords': 'View/print all the passwords altered during a session'})
    command_help['user']['user_student_create'] = 'Create a user for a student'


def _arg_help_modifications():
    """Updates the global arg_help dictionary."""

    removekeys = ['address_type', 'affiliation_optional', 'command_line', 'disk_quota_expire_date', 'disk_quota_set', 'disk_quota_size', 'email_failure_message',
                  'email_forward_address', 'entity_id', 'external_id_type', 'id:target:group', 'id:target:person',
                  'id:request_id', 'id:target:account',
                  'limit_number_of_results', 'mailing_admins', 'mailing_list', 'mailing_list_alias',
                  'mailing_list_description', 'mailing_list_exist', 'mailing_list_profile', 'member_name_src', 'member_type', 'mobile_phone', 'rt_queue', 'show_policy', 'spread_filter',
                  'string_bofh_request_search_by', 'string_bofh_request_target', 'string_disk_status', 'string_email_delivery_host', 'string_email_filter', 'string_email_move_type',
                  'string_email_on_off', 'string_email_target_name', 'string_exec_host', 'yes_no_all_op', 'yes_no_extrainfo', 'yes_no_include_expired', 'yes_no_with_request',
                  'user_search_type']
    #remove_keys(arg_help, removekeys)

    # Modify subkeys
    arg_help['disk'][0] = 'disk'
    arg_help['disk'][2] = 'Enter the path to the disc without trailing slash or username.\n Example: /usit/sauron/u1\n For non-cerebrum disks, prepend the path with a :'
    arg_help['email_category'][2] = "Legal categories include:\n - noexport     don't include domain in data exports\n - cnaddr       primary address is firstname.lastname\n - uidaddr      primary address is username\n - all_uids     all usernames are valid e-mail addresses\n - uio_globals  direct Postmaster etc. to USIT"
    arg_help['group_name_dest'][0] = 'gname'
    arg_help['group_name_src'][0] = 'gname'
    arg_help['move_type'][2] = 'Legal move types:\n - immediate\n - batch\n - nofile\n - hard_nofile\n - student\n - student_immediate\n - give\n - request\n - confirm\n - cancel'
    arg_help['person_search_type'][2] = "Possible values:\n  - 'name'\n  - 'date' of birth, on format YYYY-MM-DD\n  - 'person_id'\n  - 'stedkode'"
    arg_help['source_system'][2] = 'The name of the source system, i.e. system_fs/system_lt etc.'
    arg_help['spam_action'][2] = "Choose one of\n          'dropspam'    Messages classified as spam won't be delivered at all\n          'spamfolder'  Deliver spam to a separate IMAP folder\n          'noaction'    Deliver spam just like legitimate email"
    arg_help['spam_level'][2] = "Choose one of\n          'aggressive_spam' Filter everything that resembles spam\n          'most_spam'       Filter most emails that looks like spam\n          'standard_spam'   Only filter email that obviously is spam\n          'no_filter'       No email will be filtered as spam"
    arg_help['string_email_host'][1] = 'Enter e-mail server.  Example: mail-sg2'
    arg_help['string_group_filter'][2] = 'Enter a comma-separated list of filters.  There are four filter types:\n  \'name\'   - Name of group\n  \'desc\'   - Description text of group\n  \'expire\' - Include expired groups (default "no")\n  \'spread\' - List only groups with specified spread\n\nA filter is entered on the format \'type:value\'.  If you leave out the\ntype, \'name\' is assumed.  The values for \'name\' and \'desc\' can contain\nwildcards (* and ?).\n\nExample:\n  pc*,spread:AD_group  - list all AD groups whose names start with \'pc\''
    arg_help['trait_val'][2] = "Enter the trait value as key=value.  'key' is one of\n\n * target_id -- value is an entity, entered as type:name\n * date -- value is on format YYYY-MM-DD\n * numval -- value is an integer\n * strval -- value is a string\n\nThe key name may be abbreviated.  If value is left empty, the value\nassociated with key will be cleared.  Updating an existing trait will\nblank all unnamed keys."
    arg_help['user_create_person_id'][2] = 'Identify account owner (person or group) by entering:\n  Birthdate (YYYY-MM-DD)\n  Norwegian f\xf8dselsnummer (11 digits)\n  Export-ID (exp:exportid)\n  External ID (idtype:idvalue)\n  Entity ID (entity_id:value)\n  Group name (group:name)'
    arg_help['person_id'][2] = 'Enter person id as idtype:id.\nIf idtype=fnr, the idtype does not have to be specified.\nThe currently defined id-types are:\n  - fnr : norwegian f\xf8dselsnummer.'


def _init():
    _group_help_modifications()
    _command_help_modifications()
    _arg_help_modifications()

if __name__ != "__main__":
    _init()
