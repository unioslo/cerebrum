#!/usr/bin/env python
# -*- encoding,  utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option): any later version.
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
Change the values of various changelog constants to the new naming scheme.

This is done to preserve the int values of the already inserted constants so
that we don't end up with the same types of changes being referred to by
different constants in the database before and after the migration time.
"""
from __future__ import print_function

import argparse
import six

from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.Errors import TooManyRowsError, NotFoundError

# Key = (old category, old type)
# Value = (new category, new type)
MAPPING = {
    ('ac_type', 'add'): ('account_type', 'add'),
    ('ac_type', 'del'): ('account_type', 'remove'),
    ('ac_type', 'mod'): ('account_type', 'modify'),
    ('ad_attr', 'del'): ('ad_attr', 'remove'),
    ('apikey', 'apikey_add'): ('apikey', 'add'),
    ('apikey', 'apikey_del'): ('apikey', 'remove'),
    ('apikey', 'apikey_mod'): ('apikey', 'modify'),
    ('disk', 'del'): ('disk', 'remove'),
    ('disk', 'mod'): ('disk', 'modify'),
    ('dlgroup', 'add'): ('dlgroup_member', 'add'),
    ('dlgroup', 'addaddr'): ('dlgroup_addr', 'add'),
    ('dlgroup', 'modhidden'): ('dlgroup_hidden', 'modify'),
    ('dlgroup', 'modmanby'): ('dlgroup_manager', 'set'),
    ('dlgroup', 'modroom'): ('dlgroup_room', 'modify'),
    ('dlgroup', 'primary'): ('dlgroup_primary', 'set'),
    ('dlgroup', 'rem'): ('dlgroup_member', 'remove'),
    ('dlgroup', 'remaddr'): ('dlgroup_addr', 'remove'),
    ('dlgroup', 'remove'): ('dlgroup', 'delete'),
    ('dlgroup', 'roomcreate'): ('dlgroup_room', 'create'),
    ('e_account', 'create'): ('account', 'create'),
    ('e_account', 'delete'): ('account', 'deactivate'),
    ('e_account', 'destroy'): ('account', 'delete'),
    ('e_account', 'home_added'): ('account_home', 'add'),
    ('e_account', 'home_removed'): ('account_home', 'remove'),
    ('e_account', 'home_update'): ('account_home', 'modify'),
    ('e_account', 'mod'): ('account', 'modify'),
    ('e_account', 'move'): ('account', 'move'),
    ('e_account', 'password'): ('account_password', 'set'),
    ('e_account', 'passwordtoken'): ('account_passwordtoken', 'set'),
    ('e_account', 'pending_create'): ('virthome_account_create', 'request'),
    ('e_account', 'pending_email'): ('virthome_account_email', 'request'),
    ('e_group', 'pending_invitation'): ('virthome_group_member', 'request'),
    ('e_group', 'pending_owner_change'): (
        'virthome_group_owner_change', 'request'),
    ('e_group', 'pending_moderator_add'): (
        'virthome_group_moderator_add', 'request'),
    ('e_account', 'password_recover'): (
        'virthome_account_pwd_recover', 'request'),
    ('e_account', 'reset_expire_date'): (
        'virthome_account_reset_exp_date', 'request'),
    ('e_group', 'add'): ('group_member', 'add'),
    ('e_group', 'create'): ('group', 'create'),
    ('e_group', 'destroy'): ('group', 'delete'),
    ('e_group', 'mod'): ('group', 'modify'),
    ('e_group', 'rem'): ('group_member', 'remove'),

    ('email_address', 'add_address'): ('email_address', 'add'),
    ('email_address', 'rem_address'): ('email_address', 'remove'),
    ('email_domain', 'add_domain'): ('email_domain', 'add'),
    ('email_domain', 'rem_domain'): ('email_domain', 'remove'),
    ('email_domain', 'mod_domain'): ('email_domain', 'modify'),
    ('email_domain', 'addcat_domain'): ('email_domain_category', 'add'),
    ('email_domain', 'remcat_domain'): ('email_domain_category', 'remove'),
    ('email_entity_dom', 'add_entdom'): ('email_entity_domain', 'add'),
    ('email_entity_dom', 'rem_entdom'): ('email_entity_domain', 'remove'),
    ('email_entity_dom', 'mod_entdom'): ('email_entity_domain', 'modify'),
    ('email_forward', 'add_forward'): ('email_forward', 'add'),
    ('email_forward', 'disable_forward'): ('email_forward', 'disable'),
    ('email_forward', 'enable_forward'): ('email_forward', 'enable'),
    ('email_forward', 'local_delivery'): ('email_forward_local_delivery',
                                          'set'),
    ('email_forward', 'rem_forward'): ('email_forward', 'remove'),
    ('email_primary_address', 'add_primary'): ('email_primary_address', 'add'),
    ('email_primary_address', 'mod_primary'): ('email_primary_address',
                                               'modify'),
    ('email_primary_address', 'rem_primary'): ('email_primary_address',
                                               'remove'),
    ('email_quota', 'add_quota'): ('email_quota', 'add'),
    ('email_quota', 'rem_quota'): ('email_quota', 'remove'),
    ('email_quota', 'mod_quota'): ('email_quota', 'modify'),

    ('email_scan', 'add_scan'): ('email_scan', 'add'),
    ('email_scan', 'mod_scan'): ('email_scan', 'modify'),
    ('email_server', 'add_server'): ('email_server', 'add'),
    ('email_server', 'mod_server'): ('email_server', 'modify'),
    ('email_server', 'rem_server'): ('email_server', 'remove'),
    ('email_sfilter', 'add_sfilter'): ('email_sfilter', 'add'),
    ('email_sfilter', 'mod_sfilter'): ('email_sfilter', 'modify'),
    ('email_target', 'add_target'): ('email_target', 'add'),
    ('email_target', 'rem_target'): ('email_target', 'remove'),
    ('email_target', 'mod_target'): ('email_target', 'modify'),
    ('email_tfilter', 'add_filter'): ('email_tfilter', 'add'),
    ('email_tfilter', 'rem_filter'): ('email_tfilter', 'remove'),
    ('email_vacation', 'add_vacation'): ('email_vacation', 'add'),
    ('email_vacation', 'disable_vaca'): ('email_vacation', 'disable'),
    ('email_vacation', 'enable_vaca'): ('email_vacation', 'enable'),
    ('email_vacation', 'rem_vacation'): ('email_vacation', 'remove'),
    ('entity', 'add'): ('entity', 'create'),
    ('entity', 'del'): ('entity', 'delete'),
    ('entity', 'ext_id_add'): ('entity_external_id', 'add'),
    ('entity', 'ext_id_del'): ('entity_external_id', 'remove'),
    ('entity', 'ext_id_mod'): ('entity_external_id', 'modify'),
    ('entity_addr', 'del'): ('entity_addr', 'remove'),
    ('entity_cinfo', 'del'): ('entity_cinfo', 'remove'),
    ('entity_expire', 'del'): ('entity_expire', 'remove'),
    ('entity_expire', 'mod'): ('entity_expire', 'modify'),
    ('entity_name', 'del'): ('entity_name', 'remove'),
    ('entity_name', 'mod'): ('entity_name', 'modify'),
    ('entity_note', 'del'): ('entity_note', 'remove'),

    ('entity_nu_name', 'mod'): ('entity_nu_name', 'modify'),
    ('entity_nu_name', 'del'): ('entity_nu_name', 'remove'),

    ('ephorte', 'perm_add'): ('ephorte_perm', 'add'),
    ('ephorte', 'perm_rem'): ('ephorte_perm', 'remove'),
    ('ephorte', 'role_add'): ('ephorte_role', 'add'),
    ('ephorte', 'role_rem'): ('ephorte_role', 'remove'),
    ('ephorte', 'role_upd'): ('ephorte_role', 'modify'),

    ('exchange', 'acc_addr_add'): ('exchange_acc_addr', 'add'),
    ('exchange', 'acc_addr_rem'): ('exchange_acc_addr', 'remove'),
    ('exchange', 'acc_mbox_create'): ('exchange_acc_mbox', 'create'),
    ('exchange', 'acc_mbox_delete'): ('exchange_acc_mbox', 'delete'),
    ('exchange', 'acc_primaddr'): ('exchange_acc_primaddr', 'set'),
    ('exchange', 'group_add'): ('exchange_group_member', 'add'),
    ('exchange', 'group_rem'): ('exchange_group_member', 'remove'),
    ('exchange', 'local_delivery'): ('exchange_local_delivery', 'set'),
    ('exchange', 'per_e_reserv'): ('exchange_per_e_reserv', 'set'),
    ('exchange', 'set_ea_policy'): ('exchange_ea_policy', 'set'),
    ('exchange', 'shared_mbox_create'): ('exchange_shared_mbox', 'create'),
    ('exchange', 'shared_mbox_delete'): ('exchange_shared_mbox', 'delete'),
    ('feide_service', 'del'): ('feide_service', 'remove'),
    ('feide_service', 'mod'): ('feide_service', 'modify'),
    ('feide_service_authn_level', 'del'): ('feide_service_authn_level',
                                           'remove'),
    ('feide_service_authn_level', 'mod'): ('feide_service_authn_level',
                                           'modify'),
    ('homedir', 'del'): ('homedir', 'remove'),
    ('homedir', 'update'): ('homedir', 'modify'),
    ('host', 'a_rec_add'): ('host_a_rec', 'add'),
    ('host', 'a_rec_del'): ('host_a_rec', 'remove'),
    ('host', 'a_rec_upd'): ('host_a_rec', 'modify'),
    ('host', 'aaaa_rec_add'): ('host_aaaa_rec', 'add'),
    ('host', 'aaaa_rec_del'): ('host_aaaa_rec', 'remove'),
    ('host', 'aaaa_rec_upd'): ('host_aaaa_rec', 'modify'),
    ('host', 'cname_add'): ('host_cname', 'add'),
    ('host', 'cname_del'): ('host_cname', 'remove'),
    ('host', 'cname_upd'): ('host_cname', 'modify'),
    ('host', 'del'): ('host', 'remove'),
    ('host', 'dns_owner_add'): ('host_dns_owner', 'add'),
    ('host', 'dns_owner_del'): ('host_dns_owner', 'remove'),
    ('host', 'dns_owner_upd'): ('host_dns_owner', 'modify'),
    ('host', 'gen_dns_rec_add'): ('host_gen_dns_rec', 'add'),
    ('host', 'gen_dns_rec_del'): ('host_gen_dns_rec', 'remove'),
    ('host', 'gen_dns_rec_upd'): ('host_gen_dns_rec', 'modify'),
    ('host', 'host_info_add'): ('host_info', 'add'),
    ('host', 'host_info_del'): ('host_info', 'remove'),
    ('host', 'host_info_upd'): ('host_info', 'modify'),
    ('host', 'ip_number_add'): ('host_ip_number', 'add'),
    ('host', 'ip_number_del'): ('host_ip_number', 'remove'),
    ('host', 'ip_number_upd'): ('host_ip_number', 'modify'),
    ('host', 'ipv6_number_add'): ('host_ipv6_number', 'add'),
    ('host', 'ipv6_number_del'): ('host_ipv6_number', 'remove'),
    ('host', 'ipv6_number_upd'): ('host_ipv6_number', 'modify'),
    ('host', 'mac_adr_set'): ('host_mac_adr', 'set'),
    ('host', 'mod'): ('host', 'modify'),
    ('host', 'rev_ovr_add'): ('host_rev_ovr', 'add'),
    ('host', 'rev_ovr_del'): ('host_rev_ovr', 'remove'),
    ('host', 'rev_ovr_upd'): ('host_rev_ovr', 'modify'),
    ('host', 'srv_rec_add'): ('host_srv_rec', 'add'),
    ('host', 'srv_rec_del'): ('host_srv_rec', 'remove'),

    ('hostpolicy', 'atom_create'): ('hostpolicy_atom', 'create'),
    ('hostpolicy', 'atom_delete'): ('hostpolicy_atom', 'delete'),
    ('hostpolicy', 'atom_mod'): ('hostpolicy_atom', 'modify'),
    ('hostpolicy', 'policy_add'): ('hostpolicy', 'add'),
    ('hostpolicy', 'policy_remove'): ('hostpolicy', 'remove'),
    ('hostpolicy', 'relationship_add'): ('hostpolicy_relationship', 'add'),
    ('hostpolicy', 'relationship_remove'): ('hostpolicy_relationship',
                                            'remove'),
    ('hostpolicy', 'role_create'): ('hostpolicy_role', 'create'),
    ('hostpolicy', 'role_delete'): ('hostpolicy_role', 'delete'),
    ('hostpolicy', 'role_mod'): ('hostpolicy_role', 'modify'),

    ('ou', 'del'): ('ou', 'delete'),
    ('ou', 'mod'): ('ou', 'modify'),
    ('ou', 'set_parent'): ('ou_parent', 'set'),
    ('ou', 'unset_parent'): ('ou_parent', 'clear'),
    ('person', 'aff_add'): ('person_aff', 'add'),
    ('person', 'aff_del'): ('person_aff', 'remove'),
    ('person', 'aff_mod'): ('person_aff', 'modify'),
    ('person', 'aff_src_add'): ('person_aff_src', 'add'),
    ('person', 'aff_src_del'): ('person_aff_src', 'remove'),
    ('person', 'aff_src_mod'): ('person_aff_src', 'modify'),
    ('person', 'name_add'): ('person_name', 'add'),
    ('person', 'name_del'): ('person_name', 'remove'),
    ('person', 'name_mod'): ('person_name', 'modify'),
    ('person', 'update'): ('person', 'modify'),
    ('posix', 'demote'): ('posix_user', 'delete'),
    ('posix', 'group-demote'): ('posix_group', 'delete'),
    ('posix', 'group-promote'): ('posix_group', 'create'),
    ('posix', 'promote'): ('posix_user', 'create'),
    ('quarantine', 'del'): ('quarantine', 'remove'),
    ('quarantine', 'mod'): ('quarantine', 'modify'),
    ('subnet', 'subnet6_create'): ('subnet6', 'create'),
    ('subnet', 'subnet6_mod'): ('subnet6', 'modify'),
    ('subnet', 'subnet6_delete'): ('subnet6', 'delete'),
    ('subnet', 'subnet_create'): ('subnet', 'create'),
    ('subnet', 'subnet_mod'): ('subnet', 'modify'),
    ('subnet', 'subnet_delete'): ('subnet', 'delete'),
    ('trait', 'add'): ('entity_trait', 'add'),
    ('trait', 'del'): ('entity_trait', 'remove'),
    ('trait', 'mod'): ('entity_trait', 'modify'),
}


def main():
    """Switch category and type for lots of CLConstants"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser = add_commit_args(parser)
    args = parser.parse_args()

    database = Factory.get('Database')()
    not_found_keys = []
    for old_key, new_key in MAPPING.items():
        binds = {'old0': old_key[0],
                 'old1': old_key[1],
                 'new0': new_key[0],
                 'new1': new_key[1]}
        # Make sure it exists and we only update one value
        try:
            database.query_1(
                """
                SELECT * FROM [:table schema=cerebrum name=change_type]
                WHERE category=:old0 AND type=:old1
                """, binds)
        except NotFoundError:
            not_found_keys.append(old_key)
            continue
        except TooManyRowsError:
            raise SystemExit(
                "Multiple hits for key {} in db. Please investigate".format(
                    old_key))
        # Make sure the new key is not in use
        if database.query(
                """
                SELECT * FROM [:table schema=cerebrum name=change_type]
                WHERE category=:new0 AND type=:new1
                """, binds):
            raise SystemExit(
                "New key {} already exists in db. Please investigate".format(
                    new_key))
        # All checks passed. Let's go!
        database.execute(
            """
            UPDATE [:table schema=cerebrum name=change_type]
            SET category=:new0, type=:new1
            WHERE category=:old0 AND type=:old1
            """, binds)
        print("{old} to {new} updated successfully".format(old=old_key,
                                                           new=new_key))
    if not_found_keys:
        print("The following keys were not found in the database: ")
        not_found_keys = sorted(not_found_keys)
        [print(i) for i in not_found_keys]
        if not six.moves.input(
                "To ignore these constants, type YES: ") == 'YES':
            raise SystemExit('Did not receive YES. Exiting')
    else:
        print("All checks passed for all constants")

    if args.commit:
        print("Committing to database.")
        database.commit()
    else:
        print("Rolling back changes.")
        database.rollback()


if __name__ == '__main__':
    main()
