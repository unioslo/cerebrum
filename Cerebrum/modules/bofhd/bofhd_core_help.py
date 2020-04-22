#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2018 University of Oslo, Norway
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
#
"""This is the core help text for bofhd, which is mostly used by jbofh.

Please do not copy this file, but instead make imports from it. This is to
avoid that all help text is duplicated all over.

All help text in this file should be general enough to suit most Cerebrum
instances. If some instances needs a different explanation for a given command
or argument, the certain text variable should be overridden in a file in the
directory of the given instance.

"""

from __future__ import unicode_literals

group_help = {
    'disk': "Disk related commands",
    'entity': "Entity commands",
    'group': "Group commands",
    'host': "Host related commands",
    'misc': 'Miscellaneous commands',
    'ou': 'Organizational unit related commands',
    'perm': 'Control of Privileges in Cerebrum',
    'person': 'Person related commands',
    'pquota': 'Pquota related commands',
    'quarantine': 'Quarantine related commands',
    'spread': 'Spread related commands',
    'trait': 'Trait related commands',
    'user': 'Account building and manipulation',
}

# The texts in command_help are automatically line-wrapped, and should
# not contain \n
command_help = {
    'disk': {
        "disk_list":
            "List the disks registered with a host.  A quota value in "
            "parenthesis means it uses to the host's default disk quota.",
        "disk_quota":
            "Enable quotas on a disk, and set the default value",
    },
    'entity': {
        'entity_accounts':
            "List information about accounts associated with given entities",
        'entity_history':
            "List the changes made to an entity.",
    },
    'group': {
        'group_multi_add': 'Let an account, person or group join a group',
        'group_add': 'Let an account join a group',
        'group_add_admin': 'Set an account or group to be admin of a group',
        'group_add_moderator':
            'Set an account or group to be moderator of a group',
        'group_create': 'Create a new Cerebrum group',
        'group_rename': 'Rename a group. Don\'t use unless you\'re aware '
            'of the consequences! Stateless integrations would after a '
            'rename first delete the group and its data, before a new one '
            'is created!',
        'group_def': 'Set default filegroup for an account',
        'group_delete': 'Delete a group from Cerebrum',
        'group_demote_posix':
            'Make an existing POSIX group into a Cerebrum group',
        'group_exchange_visibility':
            'Set address book visibility for an Exchange group',
        'group_exchange_info':
            'View information about an Exchange group',
        'group_exchange_create':
            'Create an Exchange group from an existing or a new group',
        'group_exchange_remove':
            'Remove Exchange group attributes from a group',
        'group_gadd': 'Let src_group(s) join dest_group(s)',
        'group_gremove': 'Remove src_group(s) from given dest_group(s)',
        'group_info': 'View information about a group',
        'group_list': 'List direct members of a group',
        'group_list_expanded':
            'List all members of a group, direct and indirect',
        'group_memberships': 'List all groups an entity is a member of',
        'group_memberships_expanded':
            'List all groups an entity is a member of, direct and indirect',
        'group_padd': 'Let a person join a group',
        'group_premove': 'Remove a person from a group',
        'group_personal': 'Create a new personal filegroup for an account',
        'group_promote_posix': 'Make an existing group into a POSIX group',
        'group_roomlist_create':
            'Make a roomlist from scratch. Remove with spread remove/group '
            'delete',
        'group_multi_remove': 'Remove member(s) from a given group',
        'group_remove': 'Remove member accounts from a given group',
        'group_remove_admin': 'Remove an admin from a group',
        'group_remove_moderator': 'Remove a moderator from a group',
        'group_request': 'Send in request for a new Cerebrum group',
        'group_search': 'Search for a group using various criteria',
        'group_set_description': 'Set description for a group',
        'group_set_displayname':
            'Set displayname with nb as varian for an Exchange-group/room '
            'list',
        'group_set_expire': 'Set expire date for a group',
        'group_set_type': 'Set category/type for a group',
        'group_set_visibility': 'Set visibility for a group',
    },
    'host': {
        'host_info': 'Show information about a host',
        'host_disk_quota': 'Set the default disk quota for a host',
    },
    'misc': {
        'misc_affiliations':
            'List all known affiliations',
        'misc_cancel_request':
            'Cancel a pending request',
        'misc_change_request':
            'Change execution time for a pending request',
        'misc_check_password':
            'Test the quality of a given password',
        'misc_clear_passwords':
            'Forget the passwords which have been set this session',
        'misc_dadd':
            'Register a new disk',
        'misc_dls':
            "Use 'disk list' instead",
        'misc_drem':
            'Remove a disk',
        'misc_hadd':
            'Register a new host',
        'misc_hrem':
            'Remove a host',
        'misc_list_bofhd_request_types':
            'List the various types of operations that can be done via '
            'bofhd-requests',
        'misc_list_passwords':
            'View/print all the password altered this session',
        'misc_reload':
            'Re-read server config file (use with care)',
        'misc_list_requests':
            'View pending jobs',
        'misc_samba_mount':
            'Maps disk to logon-server (for use with Samba)',
        'misc_verify_password':
            'Check whether an account has a given password',
        'misc_password_issues':
            'Find out why a password cannot be changed',
    },
    'ou': {
        'ou_search': 'Search for OUs by name or a partial stedkode',
        'ou_info': 'View information about an OU',
        'ou_tree': 'Show parents/children of an OU',
    },
    'perm': {
        'perm_opset_list': 'List defined opsets',
        'perm_opset_show': 'View definition of the given opset',
        'perm_target_list': 'List auth_op_target data of the given type',
        'perm_add_target': 'Define a new auth_op_target',
        'perm_add_target_attr': 'Add attributes to an auth target',
        'perm_del_target': 'Remove an auth_op_target',
        'perm_del_target_attr': 'Removes attributes for a given target',
        'perm_list': 'List an entitys permissions',
        'perm_grant': 'Add an entry to auth_role',
        'perm_revoke': 'Remove an entry from auth_role',
        'perm_who_owns': 'Show owner of a target',
        'perm_who_has_perm':
            'Show who has the given op_set permission somewhere',
    },
    'person': {
        'person_accounts':
            'View the accounts a person owns',
        'person_affiliation_add':
            'Add an affiliation to a person',
        'person_affiliation_remove':
            'Remove an affiliation from a person',
        'person_clear_address':
            "Remove a person's address coming from a given source system",
        'person_clear_name':
            'Remove the names coming from a source system from a person',
        'person_clear_id':
            'Remove specific external id type from a source system from a '
            'person',
        'person_create':
            'Register a new person in Cerebrum',
        'person_find':
            'Search for a person in Cerebrum',
        'person_info':
            'View information about a person',
        'person_list_user_priorities':
            'View a list ordered by priority of all the accounts owned by a '
            'person',
        'person_set_bdate':
            'Set a new birth date for a person',
        'person_set_id':
            'Set a new id for a person',
        'person_get_id':
            'Get an external id for a person',
        'person_set_name':
            'Change the full name of a manually registered person',
        'person_student_info':
            'View student information for a person',
        'person_set_user_priority':
            'Change account priorities for a person',
    },
    'quarantine': {
        'quarantine_disable': 'Temporarily remove a quarantine',
        'quarantine_list': 'List defined quarantine types',
        'quarantine_remove': 'Remove a quarantine from a Cerebrum entity',
        'quarantine_set': 'Quarantine a given entity',
        'quarantine_show': 'View active quarantines for a given entity',
    },
    'spread': {
        'spread_add': 'Assign a new spread for an entity',
        'spread_list': 'List all defined spreads',
        'spread_remove': 'Remove a spread from an entity',
    },
    'trait': {
        'trait_info':
            'Display all traits associated with an entity',
        'trait_list':
            'List all entities which have specified trait',
        'trait_remove':
            'Remove a trait from an entity',
        'trait_set':
            "Add or update an entity's trait",
        'trait_types':
            'List all defined trait types (not all are editable)',
    },
    'user': {
        'user_affiliation_add': 'Add affiliation for an account',
        'user_affiliation_remove': 'Remove an affiliation for an account',
        'user_create_personal':
            'Create a POSIX user account owned by a person',
        'user_create_unpersonal': 'Create a user account owned by a group',
        'user_create_sysadm': 'Create a sysadm account, e.g. "foo-drift"',
        'user_delete': 'Delete an account',
        'user_demote_posix':
        'Make a POSIX user account into a generic Cerebrum account',
        'user_find': 'Search for users',
        'user_gecos': 'Set gecos field for a user account',
        'user_history':
            'Show history of the account with uname. Limited to users '
            'subordinate to a privilege group the BOFH user is a member of',
        'user_info': 'View general information about an account',
        'user_migrate_exchange': 'Migrate echange user',
        'user_migrate_exchange_finished':
            'Mark that migration of user is finished',
        'user_move':
            'Move a users home directory to another disk. '
            '(<<help basics>> for details)',
        'user_password': 'Set a new password for an account',
        'user_promote_posix':
            'Make a Cerebrum account into a POSIX user account',
        'user_reserve_personal':
            'Reserve a user name in the database for a person',
        'user_restore': 'Restore a deactivated user',
        'user_set_disk_quota': 'Temporary override users disk quota',
        'user_set_disk_status': 'Set homedir status for user',
        'user_set_expire': 'Set expire date for an account',
        'user_set_np_type':
            'Set/remove np-type for an account (i.e. program, system etc.)',
        'user_set_owner': 'Assign ownership for an account',
        'user_shell': 'Set login-shell for a POSIX user account',
        'user_send_welcome_sms':
            'Manually send out the Welcome SMS to a user',
    },
}
arg_help = {
    'account_name':
        ['uname', 'Enter account name',
         'Enter the name of the account for this operation'],
    'account_name_id_uid':
        ['uname', 'Enter account name',
         """Enter the name of the account for this operation. """
         """Also accepts Entity id as id:xxx or UID as uid:xxx"""],
    'account_name_id':
        ['uname', 'Enter account name',
         """Enter the name of the account for this operation."""
         """Also accepts Entity id as id:xxx"""],
    'account_name_member':
        ['uname', 'Enter members account name',
         'Enter the name of an account that already is a member'],
    'account_name_src':
        ['uname', 'Enter source account name',
         'You should enter the name of the source account for this operation'],
    'account_password':
        ['password', 'Enter password'],
    'address_type':
        ['address_type', 'Enter address type',
         'The name of the address type, e.g. POST/PRIVPOST/STREET'],
    'admin_name':
        ['admin_name', 'Enter name of the admin (group assumed)',
         'Enter the type and name of the admin, like type:name. The possible '
         'types are account and group, if no type is entered, it is assumed '
         'to be a group.'],
    'affiliation':
        ['affiliation', 'Enter affiliation',
         """A persons affiliation defines the current role of that person within
         a defined organizational unit. 'misc affiliations' lists all possible
         affiliations"""],
    'affiliation_optional':
        ['aff_opt', 'Affiliation? (optional)',
         'Enter affiliation to narrow search. Leave empty to search all '
         'affiliations.'],
    'affiliation_status':
        ['aff_status', 'Enter affiliation status',
         """Affiliation status describes a persons current status within a
         defined organizational unit (e.a. whether the person is an active
         student or an employee on leave). 'misc affiliations' lists
         affiliation status codes"""],
    'source_system':
        ['source_system', 'Enter source system',
         'The name of the source system, i.e. FS/SAP/Override etc.'],
    'command_line':
        ['command', 'Enter command line'],
    'date':
        ['date', 'Enter date (YYYY-MM-DD)',
         'The legal date format is 2003-12-31'],
    'datetime':
        ['datetime', 'Enter datetime YYYY-MM-DD(THH:MM)',
         'The legal datetime format is 2003-12-31T16:00,\n'
         'or simply 2003-12-31 (time then defaults to 00:00)'],
    'date_birth':
        ['date', 'Enter date of birth(YYYY-MM-DD)',
         'The legal date format is 2003-12-31'],
    'disk':
        ['/path/to/disk', 'Enter disk',
         "Enter the path to the disk without trailing slash or username.  "
         "Example:\n"
         "  /usit/sauron/u1\n\n"
         "If the disk isn't registered in Cerebrum and never should be, "
         "enter the whole path verbatim, prepended by a colon.  Example:\n"
         "  :/usr/local/oracle"],
    'disk_quota_set':
        ['size', 'Enter quota size',
         """Enter quota size in MiB, or 'none' to disable quota, or 'default' to
         use the host's default quota value."""],
    'disk_quota_size':
        ['size', 'Enter quota size',
         'Enter quota size in MiB, or -1 for unlimited quota'],
    'disk_quota_expire_date':
        ['end_date', 'Enter end-date for override', 'Format is 2003-12-31'],
    'display_name_language':
        ['language', 'Enter language short name',
         "Allowed values: en, nn, nb (nb used in exports)"],
    'email_domain':
        ['domain', 'Enter email domain'],
    'entity_id':
        ['id', 'Enter entity ID',
         "Numeric ID of the entity you wish to process."],
    'external_id_type':
        ['external_id_type', 'Enter external id type',
         'The external id type, i.e. NO_BIRTHNO/NO_STUDNO etc'],
    'group_disp_name':
        ['disp_name', 'Enter display name (optional, may differ from name)'],
    'group_exchange_attr':
        ['exchange_attr', 'Enter attribute to modify',
         """Valid attributes:
            - depart_restriction (Open, Closed, ApprovalRequired)
            - join_restriction (Open, Closed, ApprovalRequired)
            - moderation_enabled (T/F)
            - moderated_by ('uname1, uname2,...')
            - managed_by (e-mailaddress)
            - addrbook_visibility (H/V)"""],
    'group_name':
        ['gname', 'Enter groupname'],
    'group_name_id':
        ['gname', 'Enter groupname',
         """Accepts group name or entity id of group as id:gid"""],
    'group_name_dest':
        ['dest_gname', 'Enter the destination group'],
    'group_name_new':
        ['gname', 'Enter the new group name'],
    'group_name_src':
        ['src_gname', 'Enter the source group'],
    'group_name_admin':
        ['gname', 'Enter the name(s) of the admin group(s)'],
    'group_operation':
        ['op', 'Enter group operation',
         """Three values are legal: union, intersection and difference.
         Normally only union is used."""],
    'group_type':
        ['type', 'Enter type', "Group type (e.g. manual-group)"],
    'group_visibility':
        ['vis', 'Enter visibility', "Example: A (= all)"],
    'id':
        ['id', 'Enter id',
         "Enter a group's internal id"],
    'id:entity_ext':
        ['entity_id', 'Enter entity_id, example: group:foo',
         'Enter an entity_id either as number or as group:name / '
         'account:name'],
    'id:gid:name':
        ['group', 'Enter an existing entity',
         """Enter the entity as type:name, for example 'name:foo'. If only a
         name is entered, the type 'name' is assumed.  Other types are 'gid'
         (only Posix groups), and 'id' (Cerebrum's internal id)."""],
    'id:target:account':
        ['account', 'Enter an existing entity',
         u"""Enter the entity as type:name, for example 'account:bob'.  If only a
         name is entered, the type 'account' is assumed.  Other types include
         'group', 'fnr' (fødselsnummer), 'id' (Cerebrum's internal id) and
         'host'. The type name may be abbreviated. (Some of the types may not
         make sense for this command)."""],
    'id:target:group':
        ['group', 'Enter an existing entity',
         u"""Enter the entity as type:name, for example 'group:foo'.  If only a
         name is entered, the type 'group' is assumed.  Other types include
         'account', 'fnr' (fødselsnummer), 'id' (Cerebrum's internal id) and
         'host'.  The type name may be abbreviated.  (Some of the types may not
         make sense for this command)."""],
    'id:target:person':
        ['person', 'Enter an existing entity',
         u"""Enter the entity as type:name, for example: 'account:bob'. If only a
         name is entered, it will be assumed to be either an account or a fnr.
         If an account is given, the person owning the account will be used.
         Other types:
         - account
         - fnr (fødselsnummer)
         - id (Cerebrum's internal id)
         - external_id (e.g. student numbers and SAP ids)
         - host

         The type name may be abbreviated.

         Some of the types may not make sense for this command."""],
    'id:target:entity':
        ['entity', 'Enter an existing entity',
         """Enter the entity as type:name, for example: 'account:bob'

         If only a name is entered, it will be assumed to be either an account
         or a fnr.

         Valid types are
          - 'account' (name of user => Account or PosixUser)
          - 'person' (name of user => Person)
          - 'fnr' (external ID, Norwegian SSN => Person)
          - 'group' (name of group => Group or PosixGroup)
          - 'host' (name of host => Host)
          - 'id' (entity ID => any)
          - 'external_id' (i.e. employee or studentnr)
          - 'stedkode' (stedkode => OU)
         """],
    'id:op_target':
        ['op_target_id', 'Enter op_target_id'],
    'id:request_id':
        ['request_id', 'Enter request_id',
         "'misc list_requests' returns legal values"],
    'include_lms':
        ['lms-group y/n', 'Include lms-groups',
         'Include all the groups, including lms(fronter)-groups'],
    'limit_number_of_results':
        ['number', 'Number of results for query',
         "Gives upper limit for how many entries to include, counting " +
         "backwards from the most recent.\n" +
         "Default (when left empty) is 0, which means no limit"],
    'member_type':
        ['member_type', 'Enter type of member',
         'account, person or group'],
    'member_name_src':
        ['member_name_src', 'Enter name of source member'],
    'mobile_phone':
        ['mobile', 'Enter the mobile number',
         "Enter the 8 digit mobile phone number of the receiver"],
    'moderator_name':
        ['mod_name', 'Enter name of the moderator (group assumed)',
         'Enter the type and name of the moderator, like type:name. The '
         'possible types are account and group, if no type is entered, it is '
         'assumed to be a group.'],
    'move_type':
        ['move_type', 'Enter move type',
         """Enter desired move type. Example: 'immediate'
         Legal move types   : Arguments
         - immediate        : <account-name> <destination-disk>
         - batch            : <account-name> <destination-disk>
         - nofile           : <account-name> <destination-disk>
         - hard_nofile      : <account-name> <destination-disk>
         - student          : <account-name>
         - student_immediate: <account-name>
         - give             : <account-name> <group-name> <reason>
         - request          : <account-name> <disk-id> <reason>
         - confirm          : <account-name>
         - cancel           : <account-name>"""],
    'number_size_mib':
        ['size', 'Enter size (in MiB)',
         'Enter the size of storage, in mebibytes (1024*1024 bytes)'],
    'number_percent':
        ['percent', 'Enter percent',
         'Enter the percentage (without trailing percent sign)'],
    'on_or_off':
        ['on/off', 'Enter action',
         "Legal actions:\n - on\n - off"],
    'ou':
        ['ou', 'Enter OU',
         'Enter the 6-digit code of the organizational unit the person is '
         'affiliated to. Example: 150300'],
    'ou_stedkode_or_id':
        ['ou', 'Enter OU stedkode/id',
         'Enter a 6-digit stedkode of an organizational unit, or id:? to '
         'look up by entity ID.'],
    'ou_perspective':
        ['perspective', 'Enter a perspective (usually SAP or FS)',
         'Enter a perspective used for getting the organizational structure.'],
    'ou_search_pattern':
        ['pattern', 'Enter search pattern',
         'Enter a string (% works as a wildcard) or a partial stedkode to' +
         'search for.'],
    'ou_search_language':
        ['language', 'Enter a language code (nb/en)',
         'Enter a language code (nb/en) to be used for searching and ' +
         'displaying OU names and acronyms.'],
    'person_id':
        ['person_id', 'Enter person id',
         u"""Enter person id as idtype:id. If idtype is fnr or account, the
         idtype does not have to be specified. The currently defined id-types
         are:
         - account_name : username
         - fnr          : norwegian fødselsnummer
         - id           : entity-id
         - entity_id    : entity-id"""],
    'person_id_other':
        ['person_id', 'Enter person id',
         u"""Enter person id as idtype:id. If idtype is fnr or account, the
         idtype does not have to be specified. The currently defined id-types
         are:
         - account_name : username
         - fnr          : norwegian fødselsnummer
         - id           : entity-id
         - entity_id    : entity-id"""],
    'person_id:current':
        ['[id_type:]current_id', 'Enter current person id',
         'Enter current person id.  Example: fnr:01020312345'],
    'person_id:new':
        ['[id_type:]new_id', 'Enter new person id',
         'Enter new person id.  Example: fnr:01020312345'],
    'person_name':
        ['name', 'Enter person name'],
    'person_name_full':
        ['fullname', 'Enter persons fullname'],
    'person_name_first':
        ['firstname', 'Enter all persons given names'],
    'person_name_last':
        ['lastname', 'Enter persons family name'],
    'person_name_type':
        ['nametype', 'Enter person name type'],
    # this is also in help.py, but without the search type "stedkode"
    'person_search_type':
        ['search_type', 'Enter person search type',
         """Possible values:
         - 'name'
         - 'date' of birth, on format YYYY-MM-DD
         - 'stedkode'
         - 'ou' (entity id)
         - 'studnr'
         - 'sapnr'
         - 'passnr'"""],
    'posix_shell':
        ['shell', 'Enter shell',
         'Enter the required shell without path.  Example: bash'],
    'print_select_range':
        ['range', 'Select range',
         """Select persons by entering a space-separated list of numbers. Ranges
         can be written as "3-15" """],
    'print_select_template':
        ['template', 'Select template',
         """Choose template by entering its template.  The format of the
         template name is: <language>:<template-name>.  If language ends with
         -letter the letter will be sent through snail-mail from a central
         printer."""],
    'quarantine_type':
        ['qtype', 'Enter quarantine type',
         "'quarantine list' lists defined quarantines"],
    'quarantine_start_date':
        ['start_date', 'Enter start date (YYYY-MM-DD)',
         "The legal date format is 2003-12-31"],
    'spread':
        ['spread', 'Enter spread',
         "'spread list' lists possible values"],
    'spread_filter':
        ['spread_filter',
         'Enter spread to filter by (leave empty for no filtering)',
         """Results should only include groups having the given spread. If no
         value is given, no filtering will occur. The bofh-command
         'spread list' lists possible values"""],
    'string_attribute':
        ['attr', 'Enter attribute',
         "Experts only.  See the documentation for details"],
    'string_bofh_request_target':
        ['target', 'Enter target',
         'Enter a target id corresponding to the previously specified type'],
    'string_bofh_request_search_by':
        ['search_by', 'Enter type to search by',
         """Enter the operation that you want to search for.  Legal values:
         'requestee' username : the user that requested the operation
         'operation' type : the type of operation (move_user, move_user_now,
                            move_student, move_request, delete_user etc.)
         'disk' path: a disk used as target
         'account' username: the user affected by the operation"""],
    'string_description':
        ['description', 'Enter description'],
    'string_dl_desc':
        ['dl_desc', 'Enter description, not mandatory if an existing group '
         'is used'],
    'string_spread':
        ['spread', 'Enter spread. Example: AD_group NIS_fg@uio'],
    'string_email_host':
        ['hostname', 'Enter e-mail server.  Example: cyrus02'],
    'string_filename':
        ['filename', 'Enter filename'],
    'string_group_filter':
        ['filter', 'Enter filter',
         """Enter a comma-separated list of filters.  There are four filter types:
         'name'   - Name of group
         'desc'   - Description text of group
         'expire' - Include expired groups (default "no")
         'spread' - List only groups with specified spread

         A filter is entered on the format 'type:value'.  If you leave out the
         type, 'name' is assumed.  The values for 'name' and 'desc' can contain
         wildcards (* and ?).

         Example:
         pc*,spread:AD_group  - list all AD groups whose names start with """
         "'pc'"],
    'string_host':
        ['hostname', 'Enter hostname', 'Accepts hostname. Example: ulrik'],
    'string_new_priority':
        ['new_priority', 'Enter value new priority value',
         'Enter a positive integer (1..999), lower integers give higher '
         'priority'],
    'string_np_type':
        ['np_type', 'Enter non-personal account type',
         """Type of non-personal account."""],
    'string_op_set':
        ['op_set_name', 'Enter name of operation set',
         "Experts only. See the documentation for details"],
    'string_old_priority':
        ['old_priority', 'Enter old priority value',
         "Select the old priority value"],
    'string_perm_target':
        ['id|type', 'Enter target id or type',
         'Legal types: host, disk, group'],
    'string_perm_target_type':
        ['type', 'Enter target type',
         'Legal types: host, disk, group'],
    'string_perm_target_type_access':
        ['type', 'Enter target type',
         'Legal types: host, disk, group, dns, ou, maildom, global_host, '
         'global_group, global_person, global_ou, global_dns, global_maildom'],
    'string_disk_status':
        ['disk_status', 'Enter disk status',
         'Legal values: archived create_failed not_created on_disk'],
    'string_from_to':
        ['from_to', 'Enter end date (YYYY-MM-DD) or ' +
         'begin and end date (YYYY-MM-DD--YYYY-MM-DD)'],
    'string_sms':
        ['string_sms',
         'Enter SMS-message'],
    'string_why':
        ['why', 'Why?',
         'You should type a text indicating why you perform the operation'],
    'string_mdb':
        ['mdb', 'Enter mdb. Example: MailboxDatabase01'],
    'trait':
        ['trait', 'Name of trait'],
    'trait_val':
        ['value', 'Trait value',
         """Enter the trait value as key=value.  'key' is one of

         - target_id    value is an entity, entered as type:name
         - date         value is on format YYYY-MM-DD
         - numval       value is an integer
         - strval       value is a string

         The key name may be abbreviated.  If value is left empty, the value
         associated with key will be cleared.  Updating an existing trait will
         blank all unnamed keys."""],
    'user_create_person_id':
        ['owner', 'Enter account owner',
         u"""Identify account owner (person or group) by entering:
         Birthdate (YYYY-MM-DD)
         Norwegian fødselsnummer (11 digits)
         Export-ID (exp:exportid)
         External ID (idtype:idvalue)
         Entity ID (entity_id:value)
         Group name (group:name)"""],
    'user_create_select_person':
        ['<not displayed>', '<not displayed>',
         """Select a person from the list by entering the corresponding number.
         If the person is not registered, you must create an instance with
         "person create" """],
    'user_existing':
        ['uname', 'Enter an existing user name'],
    'user_search_type':
        ['search_type', 'Enter user search type',
         """Possible values:
         - 'stedkode'
         - 'host'
         - 'disk'"""],
    'user_set_owner_group_person':
        ['', '',
         "Person: accepts user name or Entity id of person as id:xxx. "
         "Group: accepts group name or Entity id of group as id:xxx."],

    'yes_no_force':
        ['force', 'Force the operation?'],
    'yes_no_all_op':
        ['all', 'All operations?',
         "Select all log event where the entity is involved (yes), or only " +
         "the ones where the entity itself is changed (no)"],
    'yes_no_from_existing':
        ['from_existing', 'Create Exchange group from existing group, '
         'optional, def no, (y/n)?'],
    'yes_no_expire_group':
        ['expire_group', 'Set an expire data in 90 days for group (y/n)?'],
    'yes_no_include_expired':
        ['include_expired', 'Include expired? (y/n)'],
    'yes_no_with_request':
        ['yes_no_with_request', 'Issue bofhd request? (y/n)'],
    'yes_no_extrainfo':
        ['yes_no_extrainfo', 'Show extra information? (y/n)'],
    'yes_no_visible':
        ['visible', 'Should it be visible? (y/n)'],
    'show_policy':
        ['policy', 'Show policies? (policy)',
         'If argument is "policy", all hostpolicies related to the given '
         'host will be listed'],
}


def get_help_strings():
    """Return the dictionaries containing the help strings."""
    return group_help, command_help, arg_help


def remove_keys(dictionary, keylist):
    """Remove a list of keys from a dictionary"""
    for key in keylist:
        del dictionary[key]


def remove_keys_subkeys(dictionary, remove_dictionary, verbose=False):
    """Remove the list of subkeys given a dictionary and a dictionary of keys
    and subkeys that are to be removed."""
    # Remove every subkey in the remove_dictionary
    removelist = []
    for key, subkeys in remove_dictionary.items():
        if key in dictionary:
            for subkey in subkeys:
                if subkey in dictionary[key]:
                    if verbose:
                        print("removed " + key + "->" + subkey)
                    removelist.append((key, subkey))
    # The actual removal
    for key, subkey in removelist:
        del dictionary[key][subkey]


def remove_not_kept_subkeys(dictionary, keep_dictionary, verbose=False):
    """Remove the list of subkeys given a dictionary and a dictionary of keys
    and subkeys that are to be kept."""
    # Remove every subkey not in the keep dictionary for a given key.
    removelist = []
    for key, subkeys in dictionary.items():
        for subkey in subkeys:
            if ((key in keep_dictionary) and
                    (subkey not in keep_dictionary[key])):
                if verbose:
                    print("removed " + key + "->" + subkey)
                removelist.append((key, subkey))
    # Do the actual removal
    for key, subkey in removelist:
        del dictionary[key][subkey]
