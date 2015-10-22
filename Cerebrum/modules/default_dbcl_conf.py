#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2012 University of Oslo, Norway""
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

from Cerebrum.Utils import Factory
db = Factory.get('Database')()
co = Factory.get('Constants')(db)

"""
Configuration data
===================

change_log cleaning:
--------------------
This is the default db_clean for the change_log table configuration, for
instance specific adapted configuration check the file :
<cerebrum_config>/etc/<instance>/dbcl_conf.py that would be sourcing all
the constants from the CLCleanDefConf and overwrite them if needed with
instance specific constants.

Main configurations:
* plaintext passord skal sensureres etter 1 døgn, men selve change
  entryen skal overleve

* Alle entries har en maks levetid på 6 måneder, med unntak av:
  - account create: skal ikke slettes
  - account delete: skal ikke slettes
  - add spread
  - gruppe innmeldinger uten påfølgende utmelding
  - siste passord endring
  - ephorte role_add: skal ikke slettes (foreløbig)
  - ephorte role_rem: skal ikke slettes (foreløbig)
  - ephorte role_upd: skal ikke slettes (foreløbig)
  - ephorte perm_add: skal ikke slettes (foreløbig)
  - ephorte perm_rem: skal ikke slettes (foreløbig)
  - subnet_create: skal ikke slettes (foreløbig)
  - subnet_delete: skal ikke slettes (foreløbig)
  - subnet_mod: skal ikke slettes (foreløbig)

* Skal slettede entities ha kortere levetid?

* Når noe endrer tilstand, tar vi bare vare på den siste endringen
  F.eks:
  - passord satt (vi tar imidlertid vare på alle endringer siste 14
    dager for å fange flere bytter etterhverandre)
  - når en person meldes inn, og senere ut av en gruppe
  - når en person endrer navn for et gitt ss m/en gitt type
  - - - - - - - - - - -  adresse av en gitt tye
  - - - - - - - - - - -  contact info av en gitt type
  - person_affiliation for gitt ou+aff kombinasjon
  - person_affiliation_source for gitt ou+aff kombinasjon
  - account_type

* noe må fylle igjen gamle hull i change_handler_data, uvisst om det
  er dette scriptet.  Usikkert om behovet er tilstede.
"""


class CLCleanDefConf:
    #def __init__(self, AGE_FOREVER, default_age, max_ages, minimum_age,
    #				keep_togglers, never_forget_homedir):
      AGE_FOREVER = -1
      default_age = 3600*24*185      # 6 months
      minimum_age = 3600*24*6 + 3600*22

      # Sometimes we need to know where the users homedirectory was three
      # years ago so that we can restore files the user owned then.
      never_forget_homedir = True

      # All entries will be expired after default_age, unless max_ages
      # overrides it.  Data in max_ages may be removed by keep_togglers.
      # This allows us to allways keep a group_add, unless there was a
      # subsequent group_remove.
      # Adding an entry for a new entity in max_ages requires 
      # having it referenced in the keep_togglers data structure.

      max_ages = {
        int(co.account_create): AGE_FOREVER,
        int(co.account_delete): AGE_FOREVER,
        int(co.account_destroy): AGE_FOREVER,
        int(co.group_create): AGE_FOREVER,
        int(co.ou_create): AGE_FOREVER,
        int(co.person_create): AGE_FOREVER,
        int(co.group_add): AGE_FOREVER,
        int(co.spread_add): AGE_FOREVER,
        int(co.account_password): AGE_FOREVER,
        int(co.posix_demote): AGE_FOREVER,
        int(co.posix_group_demote): AGE_FOREVER,
        int(co.posix_promote): AGE_FOREVER,
        int(co.posix_group_promote): AGE_FOREVER,
        # TODO: Once account_type changes are better logged, we don't need
        # this special case
        int(co.account_type_add): 3600*24*31,
        int(co.account_type_mod): 3600*24*31,
        int(co.account_type_del): 3600*24*31,
        }

      if hasattr(co, 'ephorte_role_add'):
        for c in (co.ephorte_role_add, co.ephorte_role_rem, co.ephorte_role_upd,
                  co.ephorte_perm_add, co.ephorte_perm_rem):
            max_ages[int(c)] = AGE_FOREVER
            
      if hasattr(co, 'subnet_create'):
          max_ages[int(co.subnet_create)] = AGE_FOREVER
          max_ages[int(co.subnet_delete)] = AGE_FOREVER
          max_ages[int(co.subnet_mod)] = AGE_FOREVER

      if hasattr(co, 'hostpolicy_policy_add'):
        for c in (co.hostpolicy_policy_add, co.hostpolicy_relationship_add,
                  co.hostpolicy_role_mod, co.hostpolicy_atom_mod,
                  co.hostpolicy_role_create, co.hostpolicy_atom_delete,
                  co.hostpolicy_relationship_remove, co.hostpolicy_role_delete,
                  co.hostpolicy_policy_remove, co.hostpolicy_atom_create):
            max_ages[int(c)] = AGE_FOREVER

      if never_forget_homedir:
        for c in (co.account_move, co.account_home_updated,
                  co.account_home_added, co.account_home_removed,
                  co.homedir_add, co.homedir_update,
                  co.homedir_remove):
              max_ages[int(c)] = AGE_FOREVER

      try:
        max_ages[int(co.guest_create)] = AGE_FOREVER
        max_ages[int(co.entity_note_add)] = AGE_FOREVER
        max_ages[int(co.entity_note_del)] = AGE_FOREVER
      except:
        pass

      # The keep_togglers datastructure is a list of entries that has the
   	  # format:
      #
      #   ({'columns': []
      #     'change_params': []
      #     'triggers': []}
      #
      # The combination of the columns and change_params works like a
      # database primary-key for events of the type listed in triggers.  We
      # only want to keep the last event of this type.

      keep_togglers = [
        # Spreads
        {'columns': ('subject_entity', ),
         'change_params': ('spread', ),
         'triggers': (co.spread_add, co.spread_del)},
        # Group members
        {'columns': ('subject_entity', 'dest_entity'),
         'triggers': (co.group_add, co.group_rem)},
        # Group creation/modification
        {'columns': ('subject_entity', ),
         'triggers': (co.group_create, co.group_mod, co.group_destroy)},
        # Group updates
        {'columns': ('subject_entity', ),
         'triggers': (co.posix_group_demote, )},
        # Group updates
        {'columns': ('subject_entity', ),
         'triggers': (co.posix_group_promote, )},
        # Account create
        {'columns': ('subject_entity', ),
         'triggers': (co.account_create, )},
        # Account updates
        {'columns': ('subject_entity', ),
         'triggers': (co.account_mod, )},
        # Account updates
        {'columns': ('subject_entity', ),
         'triggers': (co.posix_demote, )},
        # Account updates
        {'columns': ('subject_entity', ),
         'triggers': (co.posix_promote, )},
        # Account delete
        {'columns': ('subject_entity', ),
         'triggers': (co. account_delete,)},
        # Account destroy
        {'columns': ('subject_entity', ),
         'triggers': (co. account_destroy,)},
        # Account passwords
        {'columns': ('subject_entity', ),
         'triggers': (co.account_password, )},
        # AccountType
        # TBD:  Hvordan håndtere account_type_mod der vi bare logger old_pri og new_pri
        {'columns': ('subject_entity', ),
         # may remove a bit too much, but we log too little to filter better...
         # 'change_params': ('ou_id', 'affiliation', ),
         'triggers': (co.account_type_add, co.account_type_mod,
                      co.account_type_del)},
        # Disk
        {'columns': ('subject_entity', ),
         'triggers': (co.disk_add, co.disk_mod, co.disk_del)},
        # Host
        {'columns': ('subject_entity', ),
         'triggers': (co.host_add, co.host_mod, co.host_del)},
        # OU
        {'columns': ('subject_entity', ),
         'triggers': (co.ou_create, co.ou_mod)},
        # OU perspective
        {'columns': ('subject_entity', ),
         'change_params': ('perspective', ),
         'triggers': (co.ou_unset_parent, co.ou_set_parent)},
        # Person creation
        {'columns': ('subject_entity', ),
         'triggers': (co.person_create, co.person_update)},
        # Person names
        {'columns': ('subject_entity', ),
         'change_params': ('name_variant', 'src', ),
         'triggers': (co.person_name_del, co.person_name_add, co.person_name_mod)},
        # Person external id
        {'columns': ('subject_entity', ),
         'change_params': ('id_type', 'src'),
         'triggers': (co.entity_ext_id_del, co.entity_ext_id_mod,
                      co.entity_ext_id_add)},
        # Person affiliation
        # TBD: The CL data could preferably contain more data
        {'columns': ('subject_entity', ),
         'triggers': (co.person_aff_add, co.person_aff_mod, co.person_aff_del)},
        # Person affiliation source
        {'columns': ('subject_entity', ),
         'triggers': (co.person_aff_src_add, co.person_aff_src_mod,
                      co.person_aff_src_del)},
        # Quarantines
        {'columns': ('subject_entity', ),
         'change_params': ('q_type', ),
         'triggers': (co.quarantine_add, co.quarantine_mod, co.quarantine_del)},
        {'columns': ('subject_entity', ),
         'triggers': (co.quarantine_refresh,)},
        # Entity creation/deletion
        {'columns': ('subject_entity', ),
         'triggers': (co.entity_add, co.entity_del)},
        # Entity names
        {'columns': ('subject_entity', ),
         'change_params': ('domain', ),
         'triggers': (co.entity_name_add, co.entity_name_mod, co.entity_name_del)},
        # Entity contact info
        # TBD: The CL data could preferably contain more data
        {'columns': ('subject_entity', ),
         'triggers': (co.entity_cinfo_add, co.entity_cinfo_del)},
        # Entity address info
        # TBD: The CL data could preferably contain more data
        {'columns': ('subject_entity', ),
         'triggers': (co.entity_addr_add, co.entity_addr_del)},
        # Traits
        {'columns': ('subject_entity', ),
         'change_params': ('code', ),
         'triggers': (co.trait_add, co.trait_del)},
        {'columns': ('subject_entity', ),
         'change_params': ('code', ),
         'toggleable': False,
         'triggers': (co.trait_mod, )},
        ]

      if never_forget_homedir:
        toggleable = 0
      else:
        toggleable = 1

      keep_togglers.extend([
        # Account homedir  (obsolete)
        {'columns': ('subject_entity', ),
         'toggleable': toggleable,
         'triggers': (co.account_move, )},
        # Account homedir
        {'columns': ('subject_entity', ),
         'toggleable': toggleable,
         'change_params': ('spread', ),
         'triggers': (co.account_home_updated, co.account_home_added,
                      co.account_home_removed)},
        # Set/update homedir
        {'columns': ('subject_entity', ),
         'toggleable': toggleable,
         'change_params': ('homedir_id', ),
         'triggers': (co.homedir_add, co.homedir_update, co.homedir_remove)}
        ])

      if hasattr(co, 'a_record_add'):
        # dnsinfo changes
        keep_togglers.extend([
            {'columns': ('subject_entity', ),
             'triggers': (co.a_record_add, co.a_record_del, co.a_record_update)},
            {'columns': ('subject_entity', ),
             'triggers': (co.host_info_add, co.host_info_del, co.host_info_update)},
            {'columns': ('subject_entity', ),
             'triggers': (co.ip_number_add, co.ip_number_del, co.ip_number_update, )},
            {'columns': ('subject_entity', ),
             'triggers': (co.mac_adr_set, )},
            {'columns': ('subject_entity', ),
             'triggers': (co.srv_record_add, co.srv_record_del)},
            {'columns': ('subject_entity', ),
             'triggers': (co.cname_add, co.cname_del, co.cname_update)},
            {'columns': ('subject_entity', ),
             'triggers': (co.dns_owner_add, co.dns_owner_update, co.dns_owner_del)},
            {'columns': ('subject_entity', ),
             'triggers': (co.general_dns_record_add, co.general_dns_record_update)}])

      if hasattr(co, 'subnet_create'):
      # subnet changes
         keep_togglers.extend([
            {'columns': ('subject_entity', ),
             'toggleable': False,
             'triggers': (co.subnet_create, co.subnet_delete, co.subnet_mod,)},
            ])

      if hasattr(co, 'disk_quota_set'):
      # Disk quota
        keep_togglers.extend([
         {'columns': ('subject_entity', ),
          'change_params': ('homedir_id', ),
          'triggers': (co.disk_quota_set, co.disk_quota_clear)}])

      # Ephorte changes
      if hasattr(co, 'ephorte_role_add'):
         keep_togglers.extend([
            {'columns': ('subject_entity', ),
             'toggleable': False,
             'triggers': (co.ephorte_role_add, co.ephorte_role_upd,
                          co.ephorte_role_rem)}])
      if hasattr(co, 'ephorte_perm_add'):
         keep_togglers.extend([
            {'columns': ('subject_entity', ),
             'toggleable': False,
             'triggers': (co.ephorte_perm_add, co.ephorte_perm_rem)}])

      # Host Policy
      if hasattr(co, 'hostpolicy_policy_add'):
        keep_togglers.extend([
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_policy_add, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_relationship_add, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_role_mod, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_atom_mod, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_role_create, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_atom_delete, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_relationship_remove, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_role_delete, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_policy_remove, )},
        {'columns': ('subject_entity', ),
         'triggers': (co.hostpolicy_atom_create, )},
        ])

      # Password tokens
      if hasattr(co, 'account_password_token'):
        # Phones for tokens are only necessary to store as long as it takes to
        # find out of a password theft
        max_ages[int(co.account_password_token)] = 3600*24*31
        keep_togglers.extend([
            {'columns': ('subject_entity', ),
             'toggleable': False,
             'triggers': (co.account_password_token, )}
            ])

      if hasattr(co, 'aaaa_record_add'):
        # IPV6 changes
        keep_togglers.extend([
            {'columns': ('subject_entity', ),
             'triggers': (co.aaaa_record_add, co.aaaa_record_del, co.aaaa_record_update)},
            {'columns': ('subject_entity', ),
             'triggers': (co.ipv6_number_add, co.ipv6_number_del, co.ipv6_number_update, )}])

      try:
       if max_ages[int(co.guest_create)]:
        keep_togglers.extend([
        {'columns': ('subject_entity', ),
         'triggers': (co.guest_create, )},])
       if max_ages[int(co.entity_note_add)] and max_ages[int(co.entity_note_del)]:
        keep_togglers.extend([
        {'columns': ('subject_entity', ),
         'triggers': (co.entity_note_add, co.entity_note_del, )},])
      except:
       pass
