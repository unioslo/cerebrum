# -*- coding: utf-8 -*-
#
# Copyright 2014-2024 University of Oslo, Norway
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
Default configuration for guest users.

This config applies to:

- :mod:`Cerebrum.modules.guest.bofhd_guest_cmds`
- ``contrib/no/uio/generate_guest_ldif.py``
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

#
# Guest business logic
#

# Max lifetime for guest accounts, in days.
#
# All new guest accounts have an active `expire_date` set fairly short into the
# future.  Guest accounts can have a *shorter* lifethime than this threshold,
# but not longer.
#
GUEST_MAX_DAYS = 30


# Guest account owner group.
#
# A group to be used as the owner of all guest acocunts by default.  Any member
# of this group is given superuser-like permissions over guest accounts.
#
# This group should *not* be used to indicate who is responsible for the guest
# - this is done in a separate trait.
#
GUEST_OWNER_GROUP = "guestaccounts"


# Guest type definitions.
#
# Defines guest account name prefixes, and guest account default spreads.
#
# prefix (str, mandatory)
#     Prefix for the usernames. Used when creating guest accounts.
#
# spreads (collection, mandatory)
#     A set of spreads to add to the guest account at creation.  Must be set,
#     but it can be an empty collection.
#
# Example:
#   {
#       'student': {
#           'prefix': "guest-student-",
#           'spread': ("student@AD",)
#       },
#       'employee': {
#           'prefix': "guest-employee-",
#           'spread': ("employee@AD",),
#       },
#   }
#
GUEST_TYPES = {
    'gjest': {
        'prefix': "guest-",
        'spreads': tuple(),
    },
}


# The default guest account type.
#
# Must be one of the keys from GUEST_TYPES.  This will be presented as the
# default choice when using the `guest create` command prompt.
#
GUEST_TYPES_DEFAULT = "gjest"


# Max number of guests a person can create
#
# The maximum number of simultaneously active guest accounts a given person
# can create.  Superusers are still able to create more than this.
#
# NOTE: This is actually per account, not per person.
#
GUEST_MAX_PER_PERSON = 100


# Welcome SMS template
#
# This is the message that is be sent to users of new guest accounts with a
# mobile number.  The template is formatted with string interpolation, and
# should expect three named values:
#
# username (str):
#     The username of the new guest account.
#
# password (str)
#     The password given to the new guest account.
#
# expire (str)
#     The expire date for the guest account, formatted as YYYY-MM-DD.
#
GUEST_WELCOME_SMS = """
You've been given a guest account
Your username is: %(username)s
Your password is: %(password)s
The account will expire at %(expire)s
""".strip()


# Password SMS template
#
# Template for message sent on password reset.  Similar to GUEST_WELCOME_SMS,
# but with different named values:
#
# username (str):
#     The username of the guest account.
#
# changeby (str)
#     Username of the operator that reset the password.
#
# password (str)
#     The new password given to the guest account.
#
GUEST_PASSWORD_SMS = """
The password for %(username)s has been changed by %(changeby)s.
The new password is: %(password)s
""".strip()


# Max length of generated guest account names.
#
# The default limit is set to 19, as sAMAccountName must be less than 20 chars
# (see RT #1077796)
#
GUEST_MAX_LENGTH_USERNAME = 19


# Require mobile number
#
# If set to True, new guest accounts *must* have a mobile number for
# receiving SMS messages.
#
GUEST_REQUIRE_MOBILE = False


#
# LDAP export stuff
#

# Common LDAP settings
#
# Any LDAP config module must have an LDAP setting with some defaults.  This is
# where Cerebrum.modules.LDIFutils.LDIFWriter looks for `dump_dir` and
# `max_change`.
#
LDAP = {
    'dump_dir': '/cerebrum/var/cache/LDAP/',
    'max_change': 10,
}


# Settings for the `contrib/no/uio/generate_guest_ldif.py`
# and similar guest ldap exports.
#
LDAP_GUESTS = {
    # 'dn': 'dc=no',
    'file': 'guests.ldif',
    # 'auth_attr': {
    #     'userPassword': [
    #         ('crypt3-DES', '{crypt}%s'),
    #     ],
    # },
    'objectClass': [],
    'spread': None,
}
