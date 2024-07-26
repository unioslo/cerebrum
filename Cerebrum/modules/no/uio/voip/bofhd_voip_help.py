# -*- encoding: utf-8 -*-
#
# Copyright 2010-2024 University of Oslo, Norway
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
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import textwrap


group_help = {
    "voip": "voip-module related commands.",
}


command_help = {
    "voip": {
        "voip_service_new": (
            "Create a new voip service."
        ),
        "voip_service_info": (
            "Display information about a voip service."
        ),
        "voip_service_type_list": (
            "Show available voip_service types."
        ),
        "voip_service_delete": (
            "Remove a voip service from Cerebrum."
        ),
        "voip_service_update": (
            "Update data of a voip service."
        ),
        "voip_service_find": (
            "Find all voip_services matching criteria."
        ),
        "voip_client_new": (
            "Create a new voip client."
        ),
        "voip_client_info": (
            "Display information about a voip client."
        ),
        "voip_client_list_info_code": (
            "Show all available voip_client info codes."
        ),
        "voip_client_list_type_code": (
            "Show all available voip_client type codes."
        ),
        "voip_client_delete": (
            "Delete (completely) a voip_client from Cerebrum."
        ),
        "voip_client_sip_enabled": (
            "Change sipEnabled attribute of a voip_client."
        ),
        "voip_client_secrets_reset": (
            "Reset sip*Secret for a voip_client."
        ),
        "voip_client_new_secret": (
            "Set a new sipSecret for a voip_client."
        ),
        "voip_client_set_info_code": (
            "Set a new info code for a voip_client."
        ),
        "voip_address_list_contact_codes": (
            "List all available contact info codes."
        ),
        "voip_address_add_number": (
            "Register an additional voip number for an owner."
        ),
        "voip_address_delete_number": (
            "Remove a voip number from all associated owners."
        ),
        "voip_address_info": (
            "Display information about a voip address."
        ),
        "voip_address_delete": (
            "Delete a voip_address from Cerebrum."
        ),
        "voip_address_find": (
            "Display all voip_addresses matching a key."
        ),
    }
}


arg_help = {
    "mac_address": [
        "mac-address",
        "Enter mac address",
        "Enter mac address (format: aa:11:bb:22:cc:33)",
    ],
    "voip_client_info_code": [
        "voip_client_info_code",
        "Enter voip_client info code",
        textwrap.dedent(
            """
            Enter voip client info code.

            This is typically the phone model for hardphones.
            Enter "softphone" for softphone clients.

            Use `client list_info_code` to list available values.
            """
        ).lstrip(),

    ],
    "voip_client_type_code": [
        "voip_client_type_code",
        "Enter voip_client type code",
        textwrap.dedent(
            """
            Enter voip client type code.

            Values:

            - voip_softphone
            - voip_hardphone
            """
        ).lstrip(),
    ],
    "voip_service_type": [
        "service-type",
        "Enter voip service type",
        textwrap.dedent(
            """
            Enter voip service type.

            Use `voup service_type_list` to see available values.
            """
        ).lstrip(),
    ],
    "ou": [
        "ou",
        "Enter OU",
        "Enter the 6-digit code of the organizational unit",
    ],
    "yes_no_sip_enabled": [
        "sip_enabled",
        "sip enabled?",
    ],
    "yesNo": [
        "yes/no",
        "Enter 'yes' or 'no'",
        "Enter 'yes' or 'no'",
    ],
    "voip_address": [
        "voip_address",
        "Enter a voip address identifier",
        textwrap.dedent(
            """
            Look up voip address by:

            - [id:]<entity-id> (voip address, voip service, person)
            - <voip number> (e.g. phone number, email)
            - <username>
            - <service descripion>
            """
        ).lstrip(),
    ],
    "voip-address-search": [
        "voip-address-search",
        "Enter a voip address search term",
        textwrap.dedent(
            """
            Search for voip addresses by:

            - <entity-id> (voip address, voip service, person)
            - <voip number> (e.g. phone number, email)
            - <username>
            - <service descripion>
            """
        ).lstrip(),
    ],
    "voip_extension_full": [
        "extension",
        "Enter full extension (with country prefix)",
        "Enter full extension (with country prefix)",
    ],
    "voip_extension_short": [
        "short_ext",
        "Enter 5-digit extension",
        "Enter 5-digit extension number (internal number)",
    ],
    "voip_owner": [
        "voip_owner",
        "Enter voip owner (person or voip_service)",
        textwrap.dedent(
            """
            Enter voip owner designation (either a person or a voip_service).

            Tries to find:

            - [id:]<entity-id> (person)
            - <national-id> (person)
            - <account-name> (person)
            - [id:]<entity-id> (service)
            - <exact description> (service)
            """
        ).lstrip(),
    ],
    "voip_service": [
        "voip_service",
        "Enter a voip service identifier",
        textwrap.dedent(
            """
            Enter a voip service identifier

            - [id:]<entity-id>
            - <exact description>

            Use `voip service_find to get the entity-id from a partial
            description.
            """
        ).lstrip(),
    ],
    "voip-service-desc": [
        "voip-service-desc",
        "Service description",
        textwrap.dedent(
            """
            Enter a description of the service.

            Setting or updating
                When setting the description - use a short, unique, and
                descriptive text.

            Identifying
                When identifying a service - you need the exact description, as
                set previously.
            """
        ).lstrip(),
    ],
    "voip-service-search": [
        "voip-service-search",
        "Service search term",
        textwrap.dedent(
            """
            Enter a search term for find service by.

            Enter digits to search for

            - service entity-id
            - ou entity-id
            - location code (stedkode)

            Otherwise, the search will look for (partially) matching
            descriptions.
            """
        ).lstrip(),
    ],
    "priority": [
        "priority",
        "Enter priority",
        "Enter contact priority (number > 0)",
    ],
    "contactType": [
        "contact_type",
        "Enter contact type code",
        "Enter contact type code (or :None for default value)",
    ],
    "voip_client": [
        "voip_client",
        "Enter voip client identifier",
        textwrap.dedent(
            """
            Enter voip client identifier (id, mac)

            - <entity-id> (without "id:" prefix)
            - <mac-address>
            """
        ).lstrip(),
    ],
    "voip-client-secret": [
        "voip-client-secret",
        "Enter new sip-secret",
        textwrap.dedent(
            """
            Enter a new sip-secret for the client.

            At least 15 characters.
            """
        ).lstrip(),
    ],
}
