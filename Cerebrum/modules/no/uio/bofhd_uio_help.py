group_help = {
    'group': "Gruppe-kommando",
    'misc': 'Diverse kommandoer',
    'person': 'Personrelaterte kommandoer',
    'print': 'Skriver relaterte kommandoer',
    'quarantine': 'Karantene (sperre) relaterte kommandoer',
    'spread': 'Spread relaterte kommandoer',
    'user': 'Brukerrelaterte kommandoer',
    'perm': 'Rettighetsrelaterte kommandoer'
    }

command_help = {
    'group': {
    'group_add': 'Melde accounts inn i en gruppe',
    'group_create': 'Byggge en ny gruppe',
    'group_def': 'Sett default gruppe',
    'group_delete': 'Sletter gruppen',
    'group_gadd': 'Melde grupper inn',
    'group_gremove': 'Melde grupper ut',
    'group_info': 'viser litt info om gruppen',
    'group_list': 'Liste alle direkte medlemmer i en gruppe',
    'group_list_all': 'Liste alle grupper',
    'group_list_expanded': 'Liste alle ekspanderte medlemmer i en gruppe',
    'group_posix_create': 'Gjøre en eksisterende gruppe til en PosixGroup',
    'group_posix_delete': 'Gjøre en PosixGroup til en Group',
    'group_remove': 'Melde accounts ut',
    'group_set_expire': 'Sette expire på en gruppe',
    'group_set_visibility': 'Sette visibility på en gruppe',
    'group_user': 'Liste alle gruppene til en bruker',
    },
    'misc': {
    'misc_aff_status_codes': 'Vis alle mulige affiliation status koder',
    'misc_affiliations': 'Vis alle mulige affiliations',
    'misc_all_requests': 'vis alle flytte_requests som ikke er confirmet ennå',
    'misc_checkpassw': 'sjekk om et passord er godt nok',
    'misc_lmy': 'I have no idea what this is supposed to do',
    'misc_lsko': 'I have no idea what this is supposed to do',
    'misc_mmove': 'vis alle flyttinger som jeg kan confirme/jeg har requestet',
    'misc_profile_download': 'hente ned profil fil fra serveren',
    'misc_profile_upload': 'laste opp ny profil fil til serveren',
    'misc_user_passwd': 'Sjekk om en brukers passord er en gitt streng',
    },
    'perm': {
    'perm_opset_list': 'lists defined opsets',
    'perm_opset_show': 'shows definition of the given opset',
    'perm_target_list': 'list auth_op_target data of the given type',
    'perm_add_target_attr': 'adds attr',
    'perm_del_target_attr': 'removes attr',
    'perm_list': 'lists op_set_name and op_target for entity_id',
    'perm_grant': 'adds entry to auth_role',
    'perm_revoke': 'removes entry from auth_role',
    },
    'person': {
    'person_accounts': 'vis brukernavn for person',
    'person_create': 'bygger en person',
    'person_find': 'søker etter personer',
    'person_info': 'viser informasjon om en person',
    'person_set_id': 'setter ekstern id for en person',
    'person_student_info': 'Viser informasjon om studenten',
    'person_user_priority': 'Sett prioritet for bruker',
    },
    'print': {
    'printer_qoff': 'Skru av kvote på en bruker',
    'printer_qpq': 'Vise informasjon om en brukers skrivekvote',
    'printer_upq': 'Oppdaterer brukerens skriverkvote',
    },
    'quarantine': {
    'quarantine_disable': 'Midlertidig utkobling av en karantene',
    'quarantine_list': 'List karantenetyper',
    'quarantine_remove': 'Fjern en karantene fra en entitet',
    'quarantine_set': 'Sett karantene på en entitet',
    'quarantine_show': 'Vis karantener for en entitet',
    },
    'spread': {
    'spread_add': 'Gi en entitet en ny spread',
    'spread_list': 'List mulige spread',
    'spread_remove': 'Fjern spread fra en entitet',
    },
    'user': {
    'user_affiliation_add': 'Legg til affiliation for bruker',
    'user_affiliation_remove': 'Fjern affiliation for bruker',
    'user_affiliations': 'Vis brukerens affiliations',
    'user_bcreate': 'Batch bygging av brukere fra fil',
    'user_clear_created': 'Glem byggede brukere (se list_created)',
    'user_create': 'Bygge bruker',
    'user_delete': 'slette en gitt bruker',
    'user_gecos': 'Sette gecos på en bruker',
    'user_history': 'Vis historikk for en bruker',
    'user_info': 'vis info om en bruker',
    'user_list_created': 'oversikt over byggede brukere',
    'user_move': 'Flytter en bruker',
    'user_password': 'Setter passord for en bruker',
    'user_posix_create': 'Gjøre en bruker om til en PosixUser',
    'user_posix_delete': 'Gjøre en PosixUser om til en Account',
    'user_set_expire': 'Sett ekspireringsdato for en bruker',
    'user_set_np_type': 'Sett/slett np_type for en bruker',
    'user_shell': 'Sette loginshell for en bruker',
    'user_splatt': 'Sperrer brukers konto',
    'user_student_create': 'Bygg student-bruker'
    },
    }

arg_help = {
    'account_name_member': ['uname', 'Enter members accountname'],
    'account_name_src': ['uname', 'Enter source accountname',
                         'You should enter the name of the source account for this operation'],
    'account_password': ['password', 'Enter password'],
    'affiliation': ['affiliation', 'Enter affiliaton',
                    "'misc affiliations' lists all possible affiliations"],
    'affiliation_status': ['aff_status', 'Enter affiliation status',
                           "'misc aff_status_codes' lists affiliation status codes"],
    'date': ['date', 'Enter date'],
    'disk': ['disk', 'Enter disk'],
    'group_name': ['gname', 'Enter groupname'],
    'group_name_dest': ['gname', 'Enter the destination group'],
    'group_name_new': ['gname', 'Enter the new group name'],
    'group_name_src': ['gname', 'Enter the source group'],
    'group_operation': ['op', 'Enter group operation'],
    'group_visibility': ['vis', 'Enter visibility'],
    'id': ['id', 'Enter id'],
    'id:op_target': ['op_target_id', 'Enter op_target_id'],
    'move_type': ['move_type', 'Enter move type',
                  """Legal move types:
 - immediate
 - batch
 - nofile
 - student
 - student_immediate
 - request
 - confirm
 - cancel"""],
    'ou': ['ou', 'Enter OU', 'The OU is identified by its 6-digits stedcode'],
    'person_id': ['person_id', 'Enter person id',
    """Enter person id as idtype:id.
If idtype=fnr, the idtype does not have to be specified.
The currently defined id-types are:
  - fnr : norwegian fødselsnummer."""],
    'person_id:current': ['[id_type:]current_id', 'Enter current person id'],
    'person_id:new': ['[id_type:]new_id', 'Enter newperson id'],
    'person_name': ['name', 'Enter person name'],
    'person_name_full': ['fullname', 'Enter persons fullname'],
    'person_name_type': ['nametype', 'Enter person name type'],
    'posix_shell': ['shell', 'Enter shell'],
    'print_select_range': ['range', 'Select persons by entering a space-separated list of numbers.  Ranges can be written like "3-15"'],
    'print_select_template': ['template',
                              'Choose template by entering its template.  The format of the template\n'+
                              'name is: <language>:<template-name>.  If language ends with "-letter",\n'+
                              'the letter will be sendt through snail-mail from a central printer.'],
    'quarantine_type': ['qtype', 'Enter quarantine type', """'quarantine list' lists possible values"""],
    'spread': ['spread', 'Enter spread', """'spread list' lists possible values"""],
    'string_attribute': ['attr', 'Enter attribute'],
    'string_description': ['description', 'Enter description'],
    'string_filename': ['filename', 'Enter filename'],
    'string_group_filter': ['filter', 'Enter filter'],
    'string_np_type': ['np_type', 'Enter np_type', """Valid values include:
'p' - Programvarekonto."""],
    'string_op_set': ['op_set_name', 'Enter name of operation set'],
    'string_perm_target': ['id|type', 'Enter target id or type', 'Legal types: host, disk, group'],
    'string_from_to': ['from_to', 'Enter from and optionally to-date (YYYY-MM-DD-YYYY-MM-DD)'],
    'string_why': ['why', 'Why?'],
    'user_create_id': ['owner', 'Enter account owner', """Identify account owner (person or group) by entering:
  Birthdate (YYYY-MM-DD)
  Norwegian fødselsnummer (11 digits)
  Export-ID (exp:exportid)
  External ID (idtype:idvalue)
  Group name (group:name)"""],
    'user_existing': ['uname', 'Enter an existing user name'],
    'yes_no_force': ['force', 'Force the operation?']
    }
