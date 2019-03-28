#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2016 University of Oslo, Norway
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

"""Default configuration for db_clean.py"""

forever = -1

# Default max age
default_age = 3600*24*185  # 6 months

# In any case, ignore all entries newer than this
minimum_age = 3600*24*6 + 3600*22

# Entries are expired after 'default_age', unless overridden here.
# Toggled changes as defined in 'togglers' may still be removed regardless
# of the age defined here.
# Any entry defined here must also be referenced in the 'togglers'
# structure. In the toggler entry, set 'togglable' to False if you
# want to keep toggled changes.
max_ages = {
    'account_create': forever,
    'account_delete': forever,
    'account_destroy': forever,
    'account_password': forever,
    'account_move': forever,
    'account_home_updated': forever,
    'account_home_added': forever,
    'account_home_removed': forever,
    'account_password_token': 3600*24*31,

    'group_create': forever,
    'group_add': forever,

    'ou_create': forever,
    'person_create': forever,
    'spread_add': forever,
    'guest_create': forever,

    'posix_demote': forever,
    'posix_promote': forever,
    'posix_group_demote': forever,
    'posix_group_promote': forever,

    'account_type_add': 3600*24*31,
    'account_type_mod': 3600*24*31,
    'account_type_del': 3600*24*31,

    'ephorte_role_add': forever,
    'ephorte_role_rem': forever,
    'ephorte_role_upd': forever,
    'ephorte_perm_add': forever,
    'ephorte_perm_rem': forever,

    'subnet_create': forever,
    'subnet_delete': forever,
    'subnet_mod': forever,

    'hostpolicy_policy_add': forever,
    'hostpolicy_policy_remove': forever,
    'hostpolicy_relationship_add': forever,
    'hostpolicy_relationship_remove': forever,
    'hostpolicy_role_create': forever,
    'hostpolicy_role_delete': forever,
    'hostpolicy_role_mod': forever,
    'hostpolicy_atom_create': forever,
    'hostpolicy_atom_delete': forever,
    'hostpolicy_atom_mod': forever,

    'homedir_add': forever,
    'homedir_update': forever,
    'homedir_remove': forever,

    'entity_note_add': forever,
    'entity_note_del': forever,

    'consent_approve': forever,
    'consent_decline': forever,
    'consent_remove': forever,
}

# The togglers data structure is a list of entries that has the format:
#
#   {'columns': iterable,
#    'change_params': iterable,  # optional
#    'triggers': iterable,
#    'togglable': bool}  # optinal, default True
#
# The combination of the columns and change_params works like a
# database primary key for events of the type listed in triggers.  We
# only want to keep the last event of this type.
#

togglers = [
    # Spreads
    {'columns': ('subject_entity', ),
     'change_params': ('spread', ),
     'triggers': ('spread_add',
                  'spread_del')},

    # Group members
    {'columns': ('subject_entity', 'dest_entity'),
     'triggers': ('group_add',
                  'group_rem')},

    # Group creation/modification
    {'columns': ('subject_entity', ),
     'triggers': ('group_create',
                  'group_mod',
                  'group_destroy')},

    # Group POSIX demotion
    {'columns': ('subject_entity', ),
     'triggers': ('posix_group_demote', )},

    # Group POSIX promotion
    {'columns': ('subject_entity', ),
     'triggers': ('posix_group_promote', )},

    # Account create
    {'columns': ('subject_entity', ),
     'triggers': ('account_create', )},

    # Account modification
    {'columns': ('subject_entity', ),
     'triggers': ('account_mod', )},

    # Account POSIX demotion
    {'columns': ('subject_entity', ),
     'triggers': ('posix_demote', )},

    # Account POSIX promotion
    {'columns': ('subject_entity', ),
     'triggers': ('posix_promote', )},

    # Account delete
    {'columns': ('subject_entity', ),
     'triggers': ('account_delete', )},

    # Account destroy
    {'columns': ('subject_entity', ),
     'triggers': ('account_destroy', )},

    # Account passwords
    {'columns': ('subject_entity', ),
     'triggers': ('account_password', )},

    # AccountType
    # TBD:  Hvordan håndtere account_type_mod der vi bare logger old/new_pri
    {'columns': ('subject_entity', ),
     # may remove a bit too much, but we log too little to filter better...
     # 'change_params': ('ou_id', 'affiliation', ),
     'triggers': ('account_type_add',
                  'account_type_mod',
                  'account_type_del')},

    # Disk
    {'columns': ('subject_entity', ),
     'triggers': ('disk_add',
                  'disk_mod',
                  'disk_del')},

    # Host
    {'columns': ('subject_entity', ),
     'triggers': ('host_add',
                  'host_mod',
                  'host_del')},

    # OU
    {'columns': ('subject_entity', ),
     'triggers': ('ou_create',
                  'ou_mod')},

    # OU perspective
    {'columns': ('subject_entity', ),
     'change_params': ('perspective', ),
     'triggers': ('ou_unset_parent',
                  'ou_set_parent')},

    # Person creation
    {'columns': ('subject_entity', ),
     'triggers': ('person_create',
                  'person_update')},

    # Person names
    {'columns': ('subject_entity', ),
     'change_params': ('name_variant', 'src', ),
     'triggers': ('person_name_del',
                  'person_name_add',
                  'person_name_mod')},

    # Person external id
    {'columns': ('subject_entity', ),
     'change_params': ('id_type', 'src'),
     'triggers': ('entity_ext_id_del',
                  'entity_ext_id_mod',
                  'entity_ext_id_add')},

    # Person affiliation
    # TBD: The CL data could preferably contain more data
    {'columns': ('subject_entity', ),
     'triggers': ('person_aff_add',
                  'person_aff_mod',
                  'person_aff_del')},

    # Person affiliation source
    {'columns': ('subject_entity', ),
     'triggers': ('person_aff_src_add',
                  'person_aff_src_mod',
                  'person_aff_src_del')},

    # Quarantines
    {'columns': ('subject_entity', ),
     'change_params': ('q_type', ),
     'triggers': ('quarantine_add',
                  'quarantine_mod',
                  'quarantine_del')},
    {'columns': ('subject_entity', ),
     'triggers': ('quarantine_refresh',)},

    # Entity creation/deletion
    {'columns': ('subject_entity', ),
     'triggers': ('entity_add',
                  'entity_del')},

    # Entity names
    {'columns': ('subject_entity', ),
     'change_params': ('domain', ),
     'triggers': ('entity_name_add',
                  'entity_name_mod',
                  'entity_name_del')},

    # Entity contact info
    # TBD: The CL data could preferably contain more data
    {'columns': ('subject_entity', ),
     'triggers': ('entity_cinfo_add',
                  'entity_cinfo_del')},

    # Entity address info
    # TBD: The CL data could preferably contain more data
    {'columns': ('subject_entity', ),
     'triggers': ('entity_addr_add',
                  'entity_addr_del')},

    # Traits
    {'columns': ('subject_entity', ),
     'change_params': ('code', ),
     'triggers': ('trait_add',
                  'trait_del')},
    {'columns': ('subject_entity', ),
     'change_params': ('code', ),
     'togglable': False,
     'triggers': ('trait_mod', )},

    # Account homedir  (obsolete)
     {'columns': ('subject_entity', ),
      'togglable': False,
      'triggers': ('account_move', )},
    # Account homedir
     {'columns': ('subject_entity', ),
      'change_params': ('spread', ),
      'togglable': False,
      'triggers': ('account_home_updated',
                   'account_home_added',
                   'account_home_removed')},
    # Set/update homedir
     {'columns': ('subject_entity', ),
      'change_params': ('homedir_id', ),
      'togglable': False,
      'triggers': ('homedir_add',
                   'homedir_update',
                   'homedir_remove')},

    # DNS records/information
    {'columns': ('subject_entity', ),
     'triggers': ('a_record_add',
                  'a_record_del',
                  'a_record_update')},
    {'columns': ('subject_entity', ),
     'triggers': ('host_info_add',
                  'host_info_del',
                  'host_info_update')},
    {'columns': ('subject_entity', ),
     'triggers': ('ip_number_add',
                  'ip_number_del',
                  'ip_number_update', )},
    {'columns': ('subject_entity', ),
     'triggers': ('mac_adr_set', )},
    {'columns': ('subject_entity', ),
     'triggers': ('srv_record_add',
                  'srv_record_del')},
    {'columns': ('subject_entity', ),
     'triggers': ('cname_add',
                  'cname_del',
                  'cname_update')},
    {'columns': ('subject_entity', ),
     'triggers': ('dns_owner_add',
                  'dns_owner_update',
                  'dns_owner_del')},
    {'columns': ('subject_entity', ),
     'triggers': ('general_dns_record_add',
                  'general_dns_record_update')},
    {'columns': ('subject_entity', ),
     'triggers': ('aaaa_record_add',
                  'aaaa_record_del',
                  'aaaa_record_update')},
    {'columns': ('subject_entity', ),
     'triggers': ('ipv6_number_add',
                  'ipv6_number_del',
                  'ipv6_number_update', )},

    # Subnet changes
    {'columns': ('subject_entity', ),
     'togglable': False,
     'triggers': ('subnet_create',
                  'subnet_delete',
                  'subnet_mod',)},

    # Disk quota
    {'columns': ('subject_entity', ),
     'change_params': ('homedir_id', ),
     'triggers': ('disk_quota_set',
                  'disk_quota_clear')},

    # ePhorte
    {'columns': ('subject_entity', ),
     'togglable': False,
     'triggers': ('ephorte_role_add',
                  'ephorte_role_upd',
                  'ephorte_role_rem')},
    {'columns': ('subject_entity', ),
     'togglable': False,
     'triggers': ('ephorte_perm_add',
                  'ephorte_perm_rem')},

    # Host policy
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_policy_add', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_relationship_add', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_role_mod', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_atom_mod', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_role_create', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_atom_delete', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_relationship_remove', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_role_delete', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_policy_remove', )},
    {'columns': ('subject_entity', ),
     'triggers': ('hostpolicy_atom_create', )},

    # Password tokens should be around long enough to trace password theft
    {'columns': ('subject_entity', ),
     'togglable': False,
     'triggers': ('account_password_token', )},

    # Guests
    {'columns': ('subject_entity', ),
     'triggers': ('guest_create', )},

    # Entity notes
    {'columns': ('subject_entity', ),
     'triggers': ('entity_note_add',
                  'entity_note_del', )},

    # Consents
    {'columns': ('subject_entity', ),
     'togglable': False,
     'triggers': ('consent_approve',
                  'consent_decline',
                  'consent_remove', )},
]