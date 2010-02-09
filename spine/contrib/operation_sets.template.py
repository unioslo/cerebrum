#!/usr/bin/env python


op_roles = [
    # Admin groups
    ('group', 'cereweb_nt_drift', 'admin_global',  ('global_ou', )),
    ('group', 'cereweb_nt_drift', 'admin_global',  ('global_person', )),
    ('group', 'cereweb_nt_drift', 'admin_ou', ('ou', 'NT')),
    ('group', 'cereweb_nt_drift', 'admin_ou', ('ou', 'NT')),
    ('group', 'cereweb_nt_drift', 'admin_ou', ('ou', 'NT')),
    ('group', 'cereweb_nt_drift', 'admin_ou', ('global_ou', None, 'STUDENT')),
    ('group', 'cereweb_nt_drift', 'admin_resources', ('host', 'gren.nt.ntnu.no')),
    ('group', 'cereweb_nt_drift', 'admin_resources', ('host', 'mail.nt.ntnu.no')),
    ('group', 'cereweb_nt_drift', 'admin_resources', ('host', 'ratbert.itea.ntnu.no')),
    ('group', 'cereweb_nt_drift', 'admin_resources', ('maildomain', 'nt.ntnu.no')),
    ('group', 'cereweb_nt_drift', 'admin_resources', ('spread', 'user@chembio')),
    ('group', 'cereweb_nt_drift', 'admin_resources', ('group', 'kall')),
    ('group', 'cereweb_nt_drift', 'admin_resources', ('group', 'kall_s')),

    ('group', 'cereweb_orakel', 'admin_global',  ('global_ou', )),
    ('group', 'cereweb_orakel', 'admin_global',  ('global_person', )),
    ('group', 'cereweb_orakel', 'admin_ou', ('global_person', )),
    ('group', 'cereweb_orakel', 'admin_ou', ('global_account', )),
    ('group', 'cereweb_orakel', 'admin_ou', ('global_ou', )),
    ('group', 'cereweb_orakel', 'admin_resources', ('global_host', )),
    ('group', 'cereweb_orakel', 'admin_resources', ('global_maildom', )),
    ('group', 'cereweb_orakel', 'admin_resources', ('global_spread', )),
    ('group', 'cereweb_orakel', 'admin_resources', ('group', None, 'A')),

    ('group', 'cereweb_basic', 'login', ('cereweb', )),
    ('group', 'cereweb_basic', 'read', ('global_person', )),
    ('group', 'cereweb_basic', 'read', ('global_account', )),
    ('group', 'cereweb_basic', 'read', ('global_ou', )),
    ('group', 'cereweb_basic', 'read', ('global_group', )),

    ('group', 'cereweb_abuse', 'abuse', ('global_person', )),
    
    # Ceresync
    ('account', 'ceresync_at', 'sync_all', ('spread', 'user@ldap')),
    ('account', 'ceresync_at', 'sync_all', ('spread', 'user@kerberos')),
    ('account', 'ceresync_at', 'sync_all', ('spread', 'user@ansoppr')),
    ('account', 'ceresync_at', 'sync_all', ('spread', 'user@oppringt')),
    ('account', 'ceresync_at', 'sync_all', ('spread', 'user@ntnu_ad')),
    ('account', 'ceresync_at', 'sync_all', ('spread', 'user@stud')),
    ('account', 'ceresync_at', 'sync_all', ('spread', 'user@ntnu_ad')),
    ('account', 'ceresync_at', 'sync_all', ('spread', 'user@ansatt')),
    ('account', 'ceresync_at', 'sync_all', ('global_person', )),

    ('account', 'ceresync_at', 'sync_all', ('global_person', )),
    ('account', 'ceresync_at', 'sync_all', ('global_account', )),
    ('account', 'ceresync_at', 'sync_all', ('global_ou', )),
    ('account', 'ceresync_at', 'sync_all', ('global_group', )),

    ('account', 'ceresync_ad', 'sync_all', ('spread', 'user@ntnu_ad')),
    ('account', 'ceresync_ad', 'sync_all', ('global_group',)),

    ('account', 'ceresync_stud', 'sync_all', ('spread', 'user@stud')),
    ('account', 'ceresync_stud', 'sync_all', ('global_group',)),

    ('account', 'ceresync_ansatt', 'sync_all', ('spread', 'user@ansatt')),
    ('account', 'ceresync_ansatt', 'sync_all', ('global_group',)),

    ('account', 'ceresync_radius', 'sync_all', ('spread', 'user@oppringt')),
    ('account', 'ceresync_radius', 'sync_all', ('spread', 'user@ansoppr')),
    ]    




op_sets = {
    'sync_all': [
        ('syncread_group', None),
        ('syncread_account', None),
        ('syncread_person', None),
        ('syncread_ou', None),
        ('syncread_alias', None),
        ('syncread_homedir', None),
        ('homedir_set_status', 'not_created'),
        ],
    'admin_global': [
        ('person_create', None),
        ('affiliation_edit', 'STUDENT'),
        ],
    # persons and accounts
    'admin_ou': [
        ('account_create', None),
        ('account_edit', None),
        ('person_edit', None),
        ('set_password', None),
        ('contact_edit', None),
        ('address_edit', None),
        ('external_id_edit', None),
        ('quarantine_edit', 'remote'),
        ('quarantine_edit', 'sluttet'),
        ('quarantine_edit', 'svakt_passord'),
        ('note_edit', None),
        ('affiliation_edit', 'ANSATT'),
        ('affiliation_edit', 'TILKNYTTET'),
        ],
    'super_ou': [
        ('person_delete', None),
        ('account_delete', None),
        ('group_create', None),
        ('group_edit', None),
        ('group_delete', None),
        ],
    'admin_resources': [
        ('group_edit_membership', None), #!!!!
        ('email_target_create', None),
        ('email_address_create', None),
        ('email_address_delete', None),
        ('homedir_edit', None),
        ('spread_edit', None),
        ],
    'super_resources': [
        ('disk_create', None),
        ('disk_delete', None),
        ('disk_edit', None),
        ('host_edit', None),
        ],
    'abuse': [
        ('quarantine_edit', "sperret"),
        ],
    'login': [
        ('login_access', None),
        ],
    'read': [
        ('group_read', None),
        ('person_read', None),
        ('account_read', None),
        ('note_read', None),
        ('external_id_read', None),
        ],
    }
