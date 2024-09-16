# -*- coding: utf-8 -*-
#
# Copyright 2013-2024 University of Oslo, Norway
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
"""
This is the core help text for bofhd.

The help texts are mainly used in interactive cli clients, like bofh.  Please
do not copy this file, but instead make imports from it.  This is to avoid
that all help text is duplicated all over.

.. important::
   Help texts are often closely related to specific argument parsers or lookup
   functinos, and should *probably* be placed closer to those.

   The only help texts here should be defaults for e.g. parameters in the
   `cmd_param` module, or for command groups, functions, and arguments used in
   the `bofhd_core` module.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

group_help = {
    'entity': "Entity commands",
    'group': "Group commands",
    'misc': 'Miscellaneous commands',
    'person': 'Person related commands',
    'pquota': 'Pquota related commands',
    'spread': 'Spread related commands',
    'user': 'Account building and manipulation',
}

# The texts in command_help are automatically line-wrapped, and should
# not contain \n
command_help = {
    'entity': {
        'entity_accounts': (
            "List information about accounts associated with given entities"
        ),
        'entity_history': (
            "List the changes made to an entity."
        ),
    },
    'group': {
        'group_multi_add': 'Let an account, person or group join a group',
        'group_add': 'Let an account join a group',
        'group_create': 'Create a new Cerebrum group',
        'group_rename': (
            "Rename a group. Don't use unless you're aware "
            "of the consequences! Stateless integrations would after a "
            "rename first delete the group and its data, before a new one "
            "is created!"
        ),
        'group_def': 'Set default filegroup for an account',
        'group_delete': 'Delete a group from Cerebrum',
        'group_demote_posix': (
            'Make an existing POSIX group into a Cerebrum group'
        ),
        'group_exchange_visibility': (
            'Set address book visibility for an Exchange group'
        ),
        'group_exchange_info': (
            'View information about an Exchange group'
        ),
        'group_exchange_create': (
            'Create an Exchange group from an existing or a new group'
        ),
        'group_exchange_remove': (
            'Remove Exchange group attributes from a group'
        ),
        'group_gadd': 'Let src_group(s) join dest_group(s)',
        'group_gremove': 'Remove src_group(s) from given dest_group(s)',
        'group_info': 'View information about a group',
        'group_list': 'List direct members of a group',
        'group_list_expanded': (
            'List all members of a group, direct and indirect'
        ),
        'group_list_admins': (
            'List all administrators of a group by type (account or group)'
        ),
        'group_list_mods': (
            'List all moderators of a group by type (account or group)'
        ),
        'group_accounts': (
            'Lists all accounts owned by a group'
        ),
        'group_memberships': 'List all groups an entity is a member of',
        'group_memberships_expanded': (
            'List all groups an entity is a member of, direct and indirect'
        ),
        'group_padd': 'Let a person join a group',
        'group_premove': 'Remove a person from a group',
        'group_personal': 'Create a new personal filegroup for an account',
        'group_promote_posix': 'Make an existing group into a POSIX group',
        'group_roles': (
            'List all groups an entity has a role for. Either directly or '
            'indirectly through a membership in an admin/moderator group'
        ),
        'group_roomlist_create': (
            'Make a roomlist from scratch. Remove with spread remove/group '
            'delete'
        ),
        'group_multi_remove': 'Remove member(s) from a given group',
        'group_remove': 'Remove member accounts from a given group',
        'group_request': 'Send in request for a new Cerebrum group',
        'group_search': 'Search for a group using various criteria',
        'group_set_description': 'Set description for a group',
        'group_set_displayname': (
            'Set displayname with nb as varian for an Exchange-group/room '
            'list'
        ),
        'group_clear_expire': 'Remove expire date for a group',
        'group_set_expire': 'Set expire date for a group',
        'group_set_type': 'Set category/type for a group',
        'group_set_visibility': 'Set visibility for a group',
    },
    'misc': {
        'misc_affiliations': 'List all known affiliations',
        'misc_check_password': 'Test the quality of a given password',
        'misc_clear_passwords': (
            'Forget the passwords which have been set this session'
        ),
        'misc_list_passwords': (
            'View/print all the password altered this session'
        ),
        'misc_reload': 'Re-read server config file (use with care)',
        'misc_verify_password': (
            'Check whether an account has a given password'
        ),
        'misc_password_issues': 'Find out why a password cannot be changed',
    },
    'person': {
        'person_accounts': 'View the accounts a person owns',
        'person_affiliation_add': 'Add an affiliation to a person',
        'person_affiliation_remove': 'Remove an affiliation from a person',
        'person_clear_address': (
            "Remove a person's address coming from a given source system"
        ),
        'person_clear_name': (
            'Remove the names coming from a source system from a person'
        ),
        'person_clear_id': (
            'Remove specific external id type from a source system from a '
            'person'
        ),
        'person_create': 'Register a new person in Cerebrum',
        'person_find': 'Search for a person in Cerebrum',
        'person_info': 'View information about a person',
        'person_list_user_priorities': (
            'View a list ordered by priority of all the accounts owned by a '
            'person'
        ),
        'person_set_bdate': 'Set a new birth date for a person',
        'person_set_id': 'Set a new id for a person',
        'person_get_id': 'Get an external id for a person',
        'person_set_name': (
            'Change the full name of a manually registered person'
        ),
        'person_student_info': 'View student information for a person',
        'person_set_user_priority': 'Change account priorities for a person',
        'person_dfosap_import': 'Trigger manual import of person from DFO-SAP',
    },
    'spread': {
        'spread_add': 'Assign a new spread for an entity',
        'spread_list': 'List all defined spreads',
        'spread_remove': 'Remove a spread from an entity',
    },
    'user': {
        'user_affiliation_add': 'Add affiliation for an account',
        'user_affiliation_remove': 'Remove an affiliation for an account',
        'user_create_personal': (
            'Create a POSIX user account owned by a person'
        ),
        'user_create_unpersonal': 'Create a user account owned by a group',
        'user_create_sysadm': 'Create a sysadm account, e.g. "foo-drift"',
        'user_delete': 'Delete an account',
        'user_demote_posix': (
            'Make a POSIX user account into a generic Cerebrum account'
        ),
        'user_find': 'Search for users',
        'user_gecos': 'Set gecos field for a user account',
        'user_history': (
            'Show history of the account with uname. Limited to users '
            'subordinate to a privilege group the BOFH user is a member of'
        ),
        'user_info': 'View general information about an account',
        'user_migrate_exchange': 'Migrate echange user',
        'user_migrate_exchange_finished': (
            'Mark that migration of user is finished'
        ),
        'user_password': 'Set a new password for an account',
        'user_promote_posix': (
            'Make a Cerebrum account into a POSIX user account'
        ),
        'user_reserve_personal': (
            'Reserve a user name in the database for a person'
        ),
        'user_restore': 'Restore a deactivated user',
        'user_restore_unpersonal': 'Restore a deactivated unpersonal user',
        'user_set_disk_status': 'Set homedir status for user',
        'user_set_expire': 'Set expire date for an account',
        'user_set_np_type': (
            'Set/remove np-type for an account (i.e. program, system etc.)'
        ),
        'user_set_owner': 'Assign ownership for an account',
        'user_shell': 'Set login-shell for a POSIX user account',
        'user_send_welcome_sms': (
            'Manually send out the Welcome SMS to a user'
        ),
    },
}
arg_help = {
    'account_name': [
        'uname',
        'Enter account name',
        'Enter the name of the account for this operation',
    ],
    'account_name_id_uid': [
        'uname',
        'Enter account name',
        textwrap.dedent(
            """
            Enter the name of the account for this operation.
            Also accepts Entity id as id:xxx or UID as uid:xxx
            """
        ).strip(),
    ],
    'account_name_id': [
        'uname',
        'Enter account name',
        textwrap.dedent(
            """
            Enter the name of the account for this operation.
            Also accepts Entity id as id:xxx
            """).strip(),
    ],
    'account_name_member': [
        'uname',
        'Enter members account name',
        'Enter the name of an account that already is a member',
    ],
    'account_name_src': [
        'uname',
        'Enter source account name',
        'You should enter the name of the source account for this operation',
    ],
    'account_password': [
        'password',
        'Enter password',
    ],
    'address_type': [
        'address_type',
        'Enter address type',
        'The name of the address type, e.g. POST/PRIVPOST/STREET',
    ],
    'affiliation': [
        'affiliation',
        'Enter affiliation',
        textwrap.dedent(
            """
            A persons affiliation defines the current role of that person
            within a defined organizational unit.

            'misc affiliations' lists all possible affiliations
            """
        ).strip(),
    ],
    'affiliation_optional': [
        'aff_opt',
        'Affiliation? (optional)',
        textwrap.dedent(
            """
            Enter affiliation to narrow search. Leave empty to search all
            affiliations.
            """
        ).strip(),
    ],
    'affiliation_status': [
        'aff_status',
        'Enter affiliation status',
        textwrap.dedent(
            """
            Affiliation status describes a persons current status within a
            defined organizational unit (e.a. whether the person is an active
            student or an employee on leave). 'misc affiliations' lists
            affiliation status codes
            """
        ).strip(),
    ],
    'source_system': [
        'source_system',
        'Enter source system',
        'The name of the source system, i.e. FS/SAP/Override etc.',
    ],
    'command_line': [
        'command',
        'Enter command line',
    ],
    'date': [
        'date',
        'Enter date (YYYY-MM-DD)',
        'The legal date format is 2003-12-31',
    ],
    'datetime': [
        'datetime',
        'Enter datetime YYYY-MM-DD(THH:MM)',
        textwrap.dedent(
            """
            The legal datetime format is 2003-12-31T16:00,
            or simply 2003-12-31 (time then defaults to 00:00)
            """
        ).strip(),
    ],
    'date_birth': [
        'date',
        'Enter date of birth(YYYY-MM-DD)',
        'The legal date format is 2003-12-31',
    ],
    'disk': [
        '/path/to/disk',
        'Enter disk',
        textwrap.dedent(
            """
             Enter the path to the disk without trailing slash or username.
             Example:
               /usit/sauron/u1

             If the disk isn't registered in Cerebrum and never should be,
             enter the whole path verbatim, prepended by a colon.  Example:
               :/usr/local/oracle
            """
        ).lstrip(),
    ],
    'display_name_language': [
        'language',
        'Enter language short name',
        "Allowed values: en, nn, nb (nb used in exports)",
    ],
    'email_domain': [
        'domain',
        'Enter email domain',
    ],
    'entity_id': [
        'id',
        'Enter entity ID',
        "Numeric ID of the entity you wish to process.",
    ],
    'entity_type': [
        # This is the default help text for cmd_param.EntityType, which is
        # usually paired with a cmd_param.Id, and uses
        # BofhdCommandBase._get_entity() for lookup.
        "entity_type",
        "Entity Type",
        textwrap.dedent(
            """
            Specify an entity type.  Typical values:

             - account
             - group
             - person
             - stedkode

            Some commands may accept more types, while others only accepts a
            subset of the examples given here.
            """
        ).strip(),
    ],
    'external_id_type': [
        'external_id_type',
        'Enter external id type',
        'The external id type, i.e. NO_BIRTHNO/NO_STUDNO etc',
    ],
    'external_id_value': [
        'external_id_value',
        'Enter external id value',
        'The external id value, i.e 123456/abcd-abcd-abcd etc',
    ],
    'group_disp_name': [
        'disp_name',
        'Enter display name (optional, may differ from name)',
    ],
    'group_exchange_attr': [
        'exchange_attr',
        'Enter attribute to modify',
        textwrap.dedent(
            """
            Valid attributes:
              - depart_restriction (Open, Closed, ApprovalRequired)
              - join_restriction (Open, Closed, ApprovalRequired)
              - moderation_enabled (T/F)
              - moderated_by ('uname1, uname2,...')
              - managed_by (e-mailaddress)
              - addrbook_visibility (H/V)
            """
        ).strip(),
    ],
    'group_name': [
        'gname',
        'Enter groupname',
    ],
    'group_name_id': [
        'gname',
        'Enter groupname',
        "Accepts group name or entity id of group as id:gid",
    ],
    'group_name_dest': [
        'dest_gname',
        'Enter the destination group',
    ],
    'group_name_new': [
        'gname',
        'Enter the new group name',
    ],
    'group_name_src': [
        'src_gname',
        'Enter the source group',
    ],
    'group_name_admin': [
        'admin_gname',
        'Enter the name(s) of the admin group(s)',
    ],
    'group_operation': [
        'op',
        'Enter group operation',
        textwrap.dedent(
            """
            Three values are legal: union, intersection and difference.
            Normally only union is used.
            """
        ).strip(),
    ],
    'group_type': [
        'type',
        'Enter type',
        "Group type (e.g. manual-group)",
    ],
    'group_visibility': [
        'vis',
        'Enter visibility',
        "Example: A (= all)",
    ],
    'id': [
        # This is the default help text for cmd_param.Id, which is usually
        # paired with a cmd_param.EntityType, and uses
        # BofhdCommandBase._get_entity() for lookup.
        'id',
        'Enter identifier',
        textwrap.dedent(
            """
            Enter a Cerebrum entity identifier.

            The identifier format depends on the entity type.

            For groups and accounts:

              - <entity-id>
              - id:<entity-id>
              - <entity-name>
              - name:<entity-name>

            For org units:

              - <stedkode>

            For persons:

              - <username>
              - id:<entity-id>

              Person lookup may also support a selection of
              <id-type>:<id-value> mappings.

            Note that some entity types may not be supported by the command.
            """
        ).strip()
    ],
    'id:gid:name': [
        'group',
        'Enter an existing entity',
        textwrap.dedent(
            """
            Enter the entity as type:name, for example 'name:foo'.  If only a
            name is entered, the type 'name' is assumed.  Other types are 'gid'
            (only Posix groups), and 'id' (Cerebrum's internal id).
            """
        ).strip(),
    ],
    'id:target:account': [
        'account',
        'Enter an existing entity',
        textwrap.dedent(
            """
            Enter the entity as type:name, for example 'account:bob'.  If only
            a name is entered, the type 'account' is assumed.  Other types
            include 'group', 'fnr' (fødselsnummer), 'id' (Cerebrum's internal
            id) and 'host'.  The type name may be abbreviated.  Some of the
            types may not make sense for this command.
            """
        ).strip(),
    ],
    'id:target:group': [
        'group',
        'Enter an existing entity',
        textwrap.dedent(
            """
            Enter the entity as type:name, for example 'group:foo'.  If only a
            name is entered, the type 'group' is assumed.  Other types include
            'account', 'fnr' (fødselsnummer), 'id' (Cerebrum's internal id) and
            'host'.  The type name may be abbreviated.  Some of the types may
            not make sense for this command.
            """
        ).strip(),
    ],
    'id:target:person': [
        'person',
        'Enter an existing entity',
        textwrap.dedent(
            """
            Enter the entity as type:name, for example: 'account:bob'.  If only
            a name is entered, it will be assumed to be either an account or a
            fnr.  If an account is given, the person owning the account will be
            used.  Other types:
              - account
              - fnr (fødselsnummer)
              - id (Cerebrum's internal id)
              - external_id (e.g. student numbers and SAP ids)
              - host

            The type name may be abbreviated.
            Some of the types may not make sense for this command.
            """
        ).strip(),
    ],
    'id:target:entity': [
        'entity',
        'Enter an existing entity',
        textwrap.dedent(
            """
            Enter the entity as type:name, for example: 'account:bob'

            If only a name is entered, it will be assumed to be either an
            account or a fnr.

            Valid types are
              - 'account' (name of user => Account or PosixUser)
              - 'person' (name of user => Person)
              - 'fnr' (external ID, Norwegian SSN => Person)
              - 'group' (name of group => Group or PosixGroup)
              - 'host' (name of host => Host)
              - 'id' (entity ID => any)
              - 'external_id' (i.e. employee or studentnr)
              - 'stedkode' (stedkode => OU)
            """
        ).strip(),
    ],
    'include_lms': [
        'lms-group y/n',
        'Include lms-groups',
        'Include all the groups, including lms(fronter)-groups',
    ],
    'limit_number_of_results': [
        'number',
        'Number of results for query',
        textwrap.dedent(
            """
            Gives upper limit for how many entries to include, counting
            backwards from the most recent.
            Default (when left empty) is 0, which means no limit.
            """
        ).strip(),
    ],
    'member_type': [
        'member_type',
        'Enter type of member',
        'account, person or group',
    ],
    'member_name_src': [
        'member_name_src',
        'Enter name of source member',
    ],
    'mobile_phone': [
        'mobile',
        'Enter the mobile number',
        "Enter the 8 digit mobile phone number of the receiver",
    ],
    'moderator_name': [
        'mod_name',
        'Enter name of the moderator (group assumed)',
        textwrap.dedent(
            """
            Enter the type and name of the moderator, like type:name. The
            possible types are account and group, if no type is entered, it is
            assumed to be a group.
            """
        ).strip(),
    ],
    'number_size_mib': [
        'size',
        'Enter size (in MiB)',
        'Enter the size of storage, in mebibytes (1024*1024 bytes)',
    ],
    'number_percent': [
        'percent',
        'Enter percent',
        'Enter the percentage (without trailing percent sign)',
    ],
    'on_or_off': [
        'on/off',
        'Enter action',
        "Legal actions:\n - on\n - off",
    ],
    'ou': [
        'ou',
        'Enter OU',
        textwrap.dedent(
            """
            Enter the 6-digit code of the organizational unit the person is
            affiliated to.  Example: "150300"
            """
        ).strip(),
    ],
    'person_id': [
        'person_id',
        'Enter person id',
        textwrap.dedent(
            """
            Enter person id as idtype:id. If idtype is fnr or account, the
            idtype does not have to be specified. The currently defined
            id-types are:
              - account_name : username
              - fnr          : norwegian fødselsnummer
              - id           : entity-id
              - entity_id    : entity-id
            """
        ).strip(),
    ],
    'person_id_other': [
        'person_id',
        'Enter person id',
        textwrap.dedent(
            """
            Enter person id as idtype:id. If id-type is fnr or account, the
            id-type does not have to be specified. The currently defined
            id-types are:
              - account_name : username
              - fnr          : norwegian fødselsnummer
              - id           : entity-id
              - entity_id    : entity-id
            """
        ).strip(),
    ],
    'person_id:current': [
        '[id_type:]current_id',
        'Enter current person id',
        'Enter current person id.  Example: fnr:01020312345',
    ],
    'person_id:new': [
        '[id_type:]new_id',
        'Enter new person id',
        'Enter new person id.  Example: fnr:01020312345',
    ],
    'person_name': [
        'name',
        'Enter person name',
    ],
    'person_name_full': [
        'fullname',
        'Enter persons fullname',
    ],
    'person_name_first': [
        'firstname',
        'Enter all persons given names',
    ],
    'person_name_last': [
        'lastname',
        'Enter persons family name',
    ],
    'person_name_type': [
        'nametype',
        'Enter person name type',
    ],
    # this is also in help.py, but without the search type "stedkode"
    'person_search_type': [
        'search_type',
        'Enter person search type',
        textwrap.dedent(
            """
            Possible values:
              - 'name'
              - 'date' of birth, on format YYYY-MM-DD
              - 'stedkode'
              - 'ou' (entity id)
              - 'studnr'
              - 'sapnr'
              - 'dfo_pid'
              - 'passnr'
            """
        ).strip(),
    ],
    'posix_shell': [
        'shell',
        'Enter shell',
        'Enter the required shell without path.  Example: bash',
    ],
    'print_select_range': [
        'range',
        'Select range',
        textwrap.dedent(
            """
            Select persons by entering a space-separated list of numbers.
            Ranges can be written as "3-15"
            """
        ).strip(),
    ],
    'print_select_template': [
        'template',
        'Select template',
        textwrap.dedent(
            """
            Choose template by entering its template.  The format of the
            template name is: <language>:<template-name>.  If language ends
            with -letter the letter will be sent through snail-mail from a
            central printer.
            """
        ).strip(),
    ],
    'quarantine_type': [
        'qtype',
        'Enter quarantine type',
        "'quarantine list' lists defined quarantines",
    ],
    'quarantine_start_date': [
        'start_date',
        'Enter start date (YYYY-MM-DD)',
        "The legal date format is 2003-12-31",
    ],
    'spread': [
        'spread',
        'Enter spread',
        "'spread list' lists possible values",
    ],
    'spread_filter': [
        'spread_filter',
        'Enter spread to filter by (leave empty for no filtering)',
        textwrap.dedent(
            """
            Results should only include groups having the given spread.  If no
            value is given, no filtering will occur.  The bofh-command 'spread
            list' lists possible values.
            """
        ).strip(),
    ],
    'string_description': [
        'description',
        'Enter description',
    ],
    'string_dl_desc': [
        'dl_desc',
        'Enter description, not mandatory if an existing group is used',
    ],
    'string_spread': [
        'spread',
        'Enter spread. Example: AD_group NIS_fg@uio',
        "'spread list' lists possible values",
    ],
    'string_email_host': [
        'hostname',
        'Enter e-mail server.  Example: cyrus02',
    ],
    'string_filename': [
        'filename',
        'Enter filename',
    ],
    'string_group_filter': [
        'filter',
        'Enter filter',
        textwrap.dedent(
            """
            Enter a comma-separated list of filters.  There are four filter
            types:

              'name'   - Name of group
              'desc'   - Description text of group
              'expire' - Include expired groups (default "no")
              'spread' - List only groups with specified spread

            A filter is entered on the format 'type:value'.  If you leave out
            the type, 'name' is assumed.  The values for 'name' and 'desc' can
            contain wildcards (* and ?).

            Example:
              pc*,spread:AD_group  - list all AD groups whose names start with
              "'pc'"
            """
        ).lstrip(),
    ],
    'string_host': [
        'hostname',
        'Enter hostname',
        'Accepts hostname. Example: ulrik',
    ],
    'string_new_priority': [
        'new_priority',
        'Enter value new priority value',
        textwrap.dedent(
            """
            Enter a positive integer (1..999), lower integers give higher
            priority
            """
        ).strip(),
    ],
    'string_np_type': [
        'np_type',
        'Enter non-personal account type',
        "Type of non-personal account.",
    ],
    'string_old_priority': [
        'old_priority',
        'Enter old priority value',
        "Select the old priority value",
    ],
    'string_perm_target_type_access': [
        'type',
        'Enter target type',
        textwrap.dedent(
            """
            Legal types: host, disk, group, ou, maildom, global_host,
            global_group, global_person, global_ou, global_maildom
            """
        ).strip(),
    ],
    'string_disk_status': [
        'disk_status',
        'Enter disk status',
        'Legal values: archived create_failed not_created on_disk',
    ],
    'string_from_to': [
        'from_to',
        "Enter end date or date range",
        textwrap.dedent(
            """
            Enter end date (YYYY-MM-DD) or begin and end date
            (YYYY-MM-DD--YYYY-MM-DD)
            """
        ).strip(),
    ],
    'string_sms': [
        'string_sms',
        'Enter SMS-message',
    ],
    'string_why': [
        'why',
        'Why?',
        'You should type a text indicating why you perform the operation',
    ],
    'string_mdb': [
        'mdb',
        'Enter mdb. Example: MailboxDatabase01',
    ],
    'user_create_person_id': [
        'owner',
        'Enter account owner',
        textwrap.dedent(
            """
            Identify account owner (person or group) by entering:

              Birthdate (YYYY-MM-DD)
              Norwegian fødselsnummer (11 digits)
              Export-ID (exp:exportid)
              External ID (idtype:idvalue)
              Entity ID (entity_id:value)
              Group name (group:name)
            """
        ).lstrip(),
    ],
    'user_create_select_person': [
        '<not displayed>',
        '<not displayed>',
        textwrap.dedent(
            """
            Select a person from the list by entering the corresponding number.
            If the person is not registered, you must create an instance with
            "person create"
            """
        ).strip(),
    ],
    'user_existing': [
        'uname',
        'Enter an existing user name',
    ],
    'user_search_type': [
        'search_type',
        'Enter user search type',
        textwrap.dedent(
            """
            Possible values:
              - 'stedkode'
              - 'host'
              - 'disk'
            """
        ).lstrip(),
    ],
    'user_set_owner_group_person': [
        '',
        '',
        textwrap.dedent(
            """
            Person: accepts user name or Entity id of person as id:xxx.
            Group: accepts group name or Entity id of group as id:xxx.
            """
        ).strip(),
    ],
    'yes_no_force': [
        'force',
        'Force the operation?',
    ],
    'yes_no_all_op': [
        'all',
        'All operations?',
        textwrap.dedent(
            """
            Select all log event where the entity is involved (yes), or only
            the ones where the entity itself is changed (no)
            """
        ).strip(),
    ],
    'yes_no_from_existing': [
        'from_existing',
        'Create Exchange group from existing group (y/[n])',
        textwrap.dedent(
            """
            Create Exchange group from existing group.  Optional, default: no
            """
        ).strip(),
    ],
    'yes_no_expire_group': [
        'expire_group',
        'Set an expire data in 90 days for group (y/n)?',
    ],
    'yes_no_include_expired': [
        'include_expired',
        'Include expired? (y/n)',
    ],
    'yes_no_with_request': [
        'yes_no_with_request',
        'Issue bofhd request?  (y/n)',
    ],
    'yes_no_extrainfo': [
        'yes_no_extrainfo',
        'Show extra information? (y/n)',
    ],
    'yes_no_visible': [
        'visible',
        'Should it be visible? (y/n)',
    ],
}


def get_help_strings():
    """Return the dictionaries containing the help strings."""
    return group_help, command_help, arg_help
