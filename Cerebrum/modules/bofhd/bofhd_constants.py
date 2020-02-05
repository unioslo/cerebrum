# coding: utf-8
#
# Copyright 2018 University of Oslo, Norway
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
""" Constant types and common constants for the Bofhd module. """

from Cerebrum import Constants


class _AuthRoleOpCode(Constants._CerebrumCode):
    """Mappings stored in the auth_role_op_code table"""
    _lookup_table = '[:table schema=cerebrum name=auth_op_code]'


class Constants(Constants.Constants):

    AuthRoleOp = _AuthRoleOpCode

    auth_grant_disk = _AuthRoleOpCode(
        'grant_disk', 'Grant access to operate on disk')
    auth_grant_dns = _AuthRoleOpCode(
        'grant_dns', 'Grant access to operate on DNS targets')
    auth_grant_group = _AuthRoleOpCode(
        'grant_group', 'Grant access to operate on group')
    auth_grant_host = _AuthRoleOpCode(
        'grant_host', 'Grant access to operate on host')
    auth_grant_maildomain = _AuthRoleOpCode(
        'grant_maildom', 'Grant access to operate on mail domain')
    auth_grant_ou = _AuthRoleOpCode(
        'grant_ou', 'Grant access to operate on OU')
    auth_add_disk = _AuthRoleOpCode(
        'add_disks', 'Add userdisks to hosts')
    auth_add_group_admin = _AuthRoleOpCode(
        'add_group_admin', 'Add new admin to group')
    auth_create_host = _AuthRoleOpCode(
        'create_host', 'Add hosts for userdisks')
    auth_create_group = _AuthRoleOpCode(
        'create_group', 'Create groups')
    auth_search_group = _AuthRoleOpCode(
        'search_group', 'Search for groups')
    auth_delete_group = _AuthRoleOpCode(
        'delete_group', 'Delete groups')
    auth_expire_group = _AuthRoleOpCode(
        'expire_group', 'Expire groups')
    auth_disk_def_quota_set = _AuthRoleOpCode(
        'disk_def_quota', 'Set default disk quota')
    auth_disk_quota_set = _AuthRoleOpCode(
        'disk_quota_set', 'Set disk quota')
    auth_disk_quota_forever = _AuthRoleOpCode(
        'disk_quota_forev', 'Set unlimited disk quota duration')
    auth_disk_quota_unlimited = _AuthRoleOpCode(
        'disk_quota_unlim', 'Set unlimited disk quota')
    auth_disk_quota_show = _AuthRoleOpCode(
        'disk_quota_show', 'View disk quota information')
    auth_view_studentinfo = _AuthRoleOpCode(
        'view_studinfo', 'View student information')
    auth_view_contactinfo = _AuthRoleOpCode(
        'view_contactinfo', 'View contact information')
    auth_add_contactinfo = _AuthRoleOpCode(
        'add_contactinfo', "Add contact information")
    auth_remove_contactinfo = _AuthRoleOpCode(
        'rem_contactinfo', "Remove contact information")
    auth_alter_printerquota = _AuthRoleOpCode(
        'alter_printerquo', 'Alter printer quota')
    auth_modify_spread = _AuthRoleOpCode(
        'modify_spread', 'Modify spread')
    auth_create_person = _AuthRoleOpCode(
        'create_person', "Create person")
    auth_create_user = _AuthRoleOpCode(
        'create_user', 'Create user')
    auth_create_user_unpersonal = _AuthRoleOpCode(
        'create_unpersonal', 'Create unpersonal user')
    auth_remove_user = _AuthRoleOpCode(
        'remove_user', 'Remove user')
    auth_search_user = _AuthRoleOpCode(
        'search_user', 'Search for accounts')
    auth_view_history = _AuthRoleOpCode(
        'view_history', 'View history')
    auth_set_password = _AuthRoleOpCode(
        'set_password', 'Set password')
    auth_set_password_important = _AuthRoleOpCode(
        'set_password_imp', 'Set password for important accounts')
    auth_send_sms_welcome = _AuthRoleOpCode(
        'send_welcome_sms', 'Send welcome SMS to account')
    auth_set_gecos = _AuthRoleOpCode(
        'set_gecos', "Set account's gecos field")
    auth_set_trait = _AuthRoleOpCode(
        'set_trait', "Set trait")
    auth_remove_trait = _AuthRoleOpCode(
        'remove_trait', "Remove trait")
    auth_view_trait = _AuthRoleOpCode(
        'view_trait', "View trait")
    auth_list_trait = _AuthRoleOpCode(
        'list_trait', "List traits")
    auth_move_from_disk = _AuthRoleOpCode(
        'move_from_disk', 'Move account from disk')
    auth_move_to_disk = _AuthRoleOpCode(
        'move_to_disk', 'Move account to disk')
    auth_alter_group_membership = _AuthRoleOpCode(
        'alter_group_memb', 'Alter group memberships')
    auth_email_forward_off = _AuthRoleOpCode(
        'email_forw_off', "Disable user's forwards")
    auth_email_vacation_off = _AuthRoleOpCode(
        'email_vac_off', "Disable user's vacation message")
    auth_email_quota_set = _AuthRoleOpCode(
        'email_quota_set', "Set quota on user's mailbox")
    auth_email_create = _AuthRoleOpCode(
        'email_create', "Create e-mail addresses")
    auth_email_delete = _AuthRoleOpCode(
        'email_delete', "Delete e-mail addresses")
    auth_email_info_detail = _AuthRoleOpCode(
        'email_info_det', "View detailed information about e-mail account")
    auth_email_forward_info = _AuthRoleOpCode(
        'email_fwd_info',
        "View & search information about e-mail forwards")
    auth_email_reassign = _AuthRoleOpCode(
        'email_reassign', "Reassign e-mail addresses")
    auth_quarantine_set = _AuthRoleOpCode(
        'qua_add', "Set quarantine on entity")
    auth_quarantine_disable = _AuthRoleOpCode(
        'qua_disable', "Temporarily disable quarantine on entity")
    auth_quarantine_remove = _AuthRoleOpCode(
        'qua_remove', "Remove quarantine on entity")
    auth_guest_request = _AuthRoleOpCode(
        'guest_request', "Request guests")
    auth_add_affiliation = _AuthRoleOpCode(
        'add_affiliation', "Add affiliation")
    auth_remove_affiliation = _AuthRoleOpCode(
        'rem_affiliation', "Remove affiliation")
    auth_view_external_id = _AuthRoleOpCode(
        'view_external_ids', "View external IDs")
    # These are values used as auth_op_target.target_type.  This table
    # doesn't use a code table to map into integers, so we can't use
    # the CerebrumCode framework.  TODO: redefine the database table
    # In the meantime, we define the valid code values as constant
    # strings here.
    auth_target_type_disk = "disk"
    auth_target_type_dns = "dns"
    auth_target_type_group = "group"
    auth_target_type_host = "host"
    auth_target_type_maildomain = "maildom"
    auth_target_type_ou = "ou"
    auth_target_type_person = "person"
    auth_target_type_account = "account"
    auth_target_type_spread = "spread"
    # These are wildcards, allowing access to _all_ objects of that type
    auth_target_type_global_dns = "global_dns"
    auth_target_type_global_group = "global_group"
    auth_target_type_global_host = "global_host"
    auth_target_type_global_maildomain = "global_maildom"
    auth_target_type_global_ou = "global_ou"
    auth_target_type_global_person = "global_person"
    auth_target_type_global_account = "global_account"
    auth_target_type_global_spread = "global_spread"

