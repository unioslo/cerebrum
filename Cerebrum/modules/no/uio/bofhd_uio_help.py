# -*- coding: iso-8859-1 -*-
group_help = {
    'email': "E-mail commands",
    'group': "Group commands",
    'misc': 'Miscellaneous commands',
    'person': 'Person related commands',
    'print': 'Printer quota manipulation',
    'quarantine': 'Quarantine related commands',
    'spread': 'Spread related commands',
    'user': 'Account building and manipulation',
    'perm': 'Control of Privileges in Cerebrum'
    }

# The texts in command_help are automatically line-wrapped, and should
# not contain \n
command_help = {
    'email': {
    'email_forward': 'Turn e-mail forwarding for a user on/off',
    'email_add_forward': 'Add a forward address',
    'email_remove_forward': 'Remove a forward address',
    'email_info': 'View e-mail information about a user or address',
    'email_migrate': 'Migrate users from old to new e-mail service',
    'email_move': 'Move a user\'s e-mail to another server',
    'email_tripnote': 'Turn vacation messages on/off',
    'email_add_tripnote': 'Add vacation message',
    'email_remove_tripnote': 'Remove vacation message',
    },
    'group': {
    'group_add': 'Let an account join a group',
    'group_create': 'Create a new Cerebrum group',
    'group_def': 'Set default filegroup for an account',
    'group_delete': 'Delete a group from Cerebrum',
    'group_gadd': 'Let another group join a group',
    'group_gremove': 'Remove member-groups from a given group',
    'group_info': 'View information about a spesific group',
    'group_list': 'List account members of a group',
    'group_list_all': 'List all existing groups',
    'group_list_expanded': 'List all members of a group, direct og indirect',
    'group_promote_posix': 'Make en existing group into a POSIX-group',
    'group_demote_posix': 'Make an existing POSIX-group into a Cerebrum group',
    'group_remove': 'Remove member accounts from a given group',
    'group_set_expire': 'Set expire date for a group',
    'group_set_visibility': 'Set visibility for a group',
    'group_user': 'List all groups an account is a member of',
    },
    'misc': {
    'misc_affiliations': 'List all the affiliations defined in the database',
    'misc_change_request': 'Change execution time for a pending request',
    'misc_checkpassw': 'Test the quality of a given password',
    'misc_clear_passwords': 'clear password(s) from the altered-passwords list in the current sessions',
    'misc_dadd': 'Register a disk in Cerebrum database',
    'misc_dls': 'List all registered disk for a given host',
    'misc_drem': 'Remove a disk entry from Cerebrum',
    'misc_hadd': 'Register a new host in the Cerebrum database',
    'misc_hrem': 'Remove a host entry from Cerebrum',
    'misc_list_passwords': 'View/print all the password altered during a session',
    'misc_list_requests': 'View pending jobs the current BOFH user has requestet/may confirm',
    'misc_user_passwd': 'Check whether an account has a given password',
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
    },
    'person': {
    'person_accounts': 'View account a person is owner of',
    'person_create': 'Register a new person in Cerebrum',
    'person_find': 'Search for a person in Cerebrum',
    'person_info': 'View information about a person',
    'person_list_user_priorities': 'view an ordered list of all the account owned by the person person and their priorities',
    'person_set_id': 'Set a new id for a person',
    'person_student_info': 'View student information for a give person',
    'person_set_user_priority': 'Change account priorities for a person',
    },
    'print': {
    'printer_qoff': 'Turn off the printer quota for an account',
    'printer_qpq': 'View the printer quota information for an account',
    'printer_upq': 'Manually update printer quota for an account',
    },
    'quarantine': {
    'quarantine_disable': 'Temporarily remove a quarantine',
    'quarantine_list': 'List definen quarantine types',
    'quarantine_remove': 'Remove a quarantine from a Cerebrum entity',
    'quarantine_set': 'Quarantine a given entity',
    'quarantine_show': 'View active quarantines for a given entity',
    },
    'spread': {
    'spread_add': 'Assing a new spread for an entity',
    'spread_list': 'List all defined spreads',
    'spread_remove': 'Remove a spread from an entity',
    },
    'user': {
    'user_affiliation_add': 'Add affiliation for an account',
    'user_affiliation_remove': 'Remove an affiliation for an account',
    'user_create': 'Create a POSIX user account',
    'user_delete': 'Delete an account',
    'user_demote_posix': 'Make a POSIX user account into a generic Cerebrum account',
    'user_gecos': 'Set gecos field for a user account',
    'user_history': "Show history of the account with uname. Limited to users subordinate to a privilege group the BOFH user is a member of",
    'user_info': 'View general information about an account',
    'user_move': 'Move a users home directory to another disk',
    'user_password': 'Set a new password for an account',
    'user_promote_posix': 'Make a Cerebrum account into a POSIX user account',
    'user_reserve': 'Reserve a user name in the database',
    'user_set_expire': 'Set expire date for an account',
    'user_set_np_type': 'Set/remove np-type for an account (i.e. program, system etc)',
    'user_set_owner': 'Assing ownership of an account',
    'user_shell': 'Set login-sehll for a POSIX user account',
    'user_student_create': 'Create a user for a student'
    },
    }

arg_help = {
    'account_name': ['uname', 'Enter account name',
                     'Enter the name of the account for this operation'],
    'account_name_member': ['uname', 'Enter members accountname',
                            "Enter the name of an account that already is a member"],
    'account_name_src': ['uname', 'Enter source accountname',
                         'You should enter the name of the source account for this operation'],
    'account_password': ['password', 'Enter password'],
    'affiliation': ['affiliation', 'Enter affiliaton',
"""A persons affiliation defines the current rolle of that person
within a defined organizational unit.  'misc affiliations' lists all
possible affiliations"""],
    'affiliation_status': ['aff_status', 'Enter affiliation status',
"""Affiliation status describes a persons current status within a
defined organizational unit (e.a. whether the person is an active
student or an employee on leave).  'misc aff_status_codes' lists
affiliation status codes"""],
    'date': ['date', 'Enter date (YYYY-MM-DD)',
             "The legal date format is 2003-12-31"],
    'date_birth': ['date', 'Enter date of birth(YYYY-MM-DD)',
             "The legal date format is 2003-12-31"],
    'disk': ['disk', 'Enter disk',
 """Enter the path to the disc without trailing slash or username.
 Example: /usit/sauron/u1
 For non-cerebrum disks, prepend the path with a :"""],
    'email_address': ['address', 'Enter e-mail address'],
    'email_forward_action': ['action', 'Enter action',
"""Legal forward actions:
 - on
 - off
 - local"""],
    'group_name': ['gname', 'Enter groupname'],
    'group_name_dest': ['gname', 'Enter the destination group'],
    'group_name_new': ['gname', 'Enter the new group name'],
    'group_name_src': ['gname', 'Enter the source group'],
    'group_operation': ['op', 'Enter group operation',
"""Three values are legal: union, intersection and difference.
Normally only union is used."""],
    'group_visibility': ['vis', 'Enter visibility', "Example: A (= all)"],
    'id': ['id', 'Enter id',
"""Enter a groups internal id"""],
    'id:entity_ext': ['entity_id', 'Enter entity_id, example: group:foo',
    'Enter an entity_id either as number or as group:name / account:name'],
    'id:op_target': ['op_target_id', 'Enter op_target_id'],
    'move_type': ['move_type', 'Enter move type',
                  """Legal move types:
 - immediate
 - batch
 - nofile
 - hard_nofile
 - student
 - student_immediate
 - give
 - request
 - confirm
 - cancel"""],
    'ou': ['ou', 'Enter OU',
    'Enter the 6-digit code of the organizational unit the person is affiliated to'],
    'person_id': ['person_id', 'Enter person id',
    """Enter person id as idtype:id.
If idtype=fnr, the idtype does not have to be specified.
The currently defined id-types are:
  - fnr : norwegian fødselsnummer."""],
    'person_id_other':['person_id','Enter person id',
    """Enter person id as idtype:id.
If idtype=fnr, the idtype does not have to be specified.
You may also use entity_id:id."""],
    'person_id:current': ['[id_type:]current_id',
                          'Enter current person id',
                          'Enter current person id.  Example: fnr:01020312345'],
    'person_id:new': ['[id_type:]new_id', 'Enter new person id',
                      'Enter new person id.  Example: fnr:01020312345'],
    'person_name': ['name', 'Enter person name'],
    'person_name_full': ['fullname', 'Enter persons fullname'],
    'person_name_type': ['nametype', 'Enter person name type'],
    'posix_shell': ['shell', 'Enter shell',
                    'Enter the required shell without path.  Example: bash'],
    'print_select_range': ['range', 'Select range',
"""Select persons by entering a space-separated list of numbers.
Ranges can be written as "3-15" """],
    'print_select_template': ['template', 'Select template',
"""Choose template by entering its template.  The format of the
template name is: <language>:<template-name>.  If language ends with
-letter the letter will be sendt through snail-mail from a central
printer."""],
    'quarantine_type': ['qtype', 'Enter quarantine type',
                        "'quarantine list' lists defined quarantines"],
    'spread': ['spread', 'Enter spread',
               "'spread list' lists possible values"],
    'string_attribute': ['attr', 'Enter attribute',
                         "Experts only.  See the documentation for details"],
    'string_description': ['description', 'Enter description'],
    'string_email_host': ['hostname',
                          'Enter e-mail server.  Example: mail-sg2'],
    'string_filename': ['filename', 'Enter filename'],
    'string_group_filter': ['filter', 'Enter filter'],
    'string_host': ['hostname', 'Enter hostname.  Example: ulrik'],
    'string_new_priority': ['new_priority', 'Enter value new priority value',
                            'Enter a positive integer (1..999), lower integers give higher priority'],
    'string_np_type': ['np_type', 'Enter np_type',
                       """Valid values include:
'P' - Programvarekonto
'T' - Testkonto."""],
    'string_op_set': ['op_set_name', 'Enter name of operation set',
                      "Experts only.  See the documentation for details"],
    'string_old_priority': ['old_priority', 'Enter old priority value',
                            "Select the old priority value"],
    'string_perm_target': ['id|type', 'Enter target id or type',
                           'Legal types: host, disk, group'],
    'string_perm_target_type': ['type', 'Enter target type',
                           'Legal types: host, disk, group'],
    'string_from_to': ['from_to', 'Enter from and optionally to-date (YYYY-MM-DD-YYYY-MM-DD)'],
    'string_why': ['why', 'Why?',
                   'You should type a text indicating why you perform the operation'],
    'user_create_person_id': ['owner', 'Enter account owner',
"""Identify account owner (person or group) by entering:
  Birthdate (YYYY-MM-DD)
  Norwegian fødselsnummer (11 digits)
  Export-ID (exp:exportid)
  External ID (idtype:idvalue)
  Group name (group:name)"""],
'user_create_select_person': ['<not displayed>', '<not displayed>',
"""Select a person from the list by entering the corresponding
number.  If the person is not registered, you must create an instance with "person
create" """],
'user_existing': ['uname', 'Enter an existing user name'],
    'yes_no_force': ['force', 'Force the operation?']
    }
