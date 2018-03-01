# -*- encoding: utf-8 -*-
#
# Copyright 2010-2018 University of Oslo, Norway
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
"""This module contains help strings for voip bofhd extension. """


group_help = {
    "voip": "voip-module related commands.",
}


command_help = {
    "voip": {
        "voip_service_new":
            "Create a new voip service.",
        "voip_service_info":
            "Display information about a voip service.",
        "voip_service_type_list":
            "Show available voip_service types.",
        "voip_service_delete":
            "Remove a voip service from Cerebrum.",
        "voip_service_update":
            "Update data of a voip service.",
        "voip_service_find":
            "Find all voip_services matching criteria.",
        "voip_client_new":
            "Create a new voip client.",
        "voip_client_info":
            "Display information about a voip client.",
        "voip_client_list_info_code":
            "Show all available voip_client info codes.",
        "voip_client_list_type_code":
            "Show all available voip_client type codes.",
        "voip_client_delete":
            "Delete (completely) a voip_client from Cerebrum.",
        "voip_client_sip_enabled":
            "Change sipEnabled attribute of a voip_client.",
        "voip_client_secrets_reset":
            "Reset sip*Secret for a voip_client.",
        "voip_client_new_secret":
            "Set a new sipSecret for a voip_client.",
        "voip_client_set_info_code":
            "Set a new info code for a voip_client.",
        "voip_address_list_contact_codes":
            "List all available contact info codes.",
        "voip_address_add_number":
            "Register an additional voip number for an owner.",
        "voip_address_delete_number":
            "Remove a voip number from all associated owners.",
        "voip_address_info":
            "Display information about a voip address.",
        "voip_address_delete":
            "Delete a voip_address from Cerebrum.",
        "voip_address_find":
            "Display all voip_addresses matching a key.",
    }
}


arg_help = {
    "mac_address": [
        "mac-address",
        "Enter mac address",
        "Enter mac address (format: aa:11:bb:22:cc:33)"],
    "voip_client_info_code": [
        "voip_client_info_code",
        "Enter voip_client info code",
        "Enter voip_client info code (e.g. phone model)"],
    "voip_client_type_code": [
        "voip_client_type_code",
        "Enter voip_client type code",
        "Enter voip_client type code (soft/hardphone)"],
    "voip_service_type": [
        "service-type",
        "Enter voip service type",
        "Enter voip service type "
        "(i.e. typically a location of a voip service. "
        "See voip service_type_list)"],
    "ou": [
        "ou",
        "Enter OU",
        "Enter the 6-digit code of the organizational unit"],
    "yes_no_sip_enabled": [
        "sip_enabled",
        "sip enabled?"],
    "yesNo": [
        "yes/no",
        "Enter 'yes' or 'no'",
        "Enter 'yes' or 'no'"],
    "voip_address": [
        "voip_address",
        "Enter a voip address identifier",
        "Enter a voip address identifier (id, owner id, etc.)"],
    "voip_extension_full": [
        "extension",
        "Enter full extension (with country prefix)",
        "Enter full extension (with country prefix)"],
    "voip_extension_short": [
        "short_ext",
        "Enter 5-digit extension",
        "Enter 5-digit extension number (internal number)"],
    "voip_owner": [
        "voip_owner",
        "Enter voip owner (person or voip_service)",
        "Enter voip owner designation "
        "(either a person or a voip_service)"],
    "voip_service": [
        "voip_service",
        "Enter a voip service identifier",
        "Enter a voip service identifier (id, description, etc.)"],
    "priority": [
        "priority",
        "Enter priority",
        "Enter contact priority (number > 0)"],
    "contactType": [
        "contact_type",
        "Enter contact type code",
        "Enter contact type code (or :None for default value)"],
    "voip_client": [
        "voip_client",
        "Enter voip client identifier",
        "Enter voip client identifier (id, mac)"],
}
