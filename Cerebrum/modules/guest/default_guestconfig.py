# -*- coding: utf-8 -*-
#
# Copyright 2014-2019 University of Oslo, Norway
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

This config applies to the .bofhd_guest_cmds module.
"""

# The maximum number of days a guest account can live. The set expire date for
# guest accounts can not be longer than this. It is, however, possible to set
# it lower than this.
GUEST_MAX_DAYS = 30

# The group that stands as the 'owner' of the guest accounts. Note that this is
# the owner group, and not the 'responsible' for the guest, which is a
# different thing which is stored in a trait.
GUEST_OWNER_GROUP = 'guestaccounts'

# The different types of guests. This is a dict where each element is a type
# with the different settings for the given type of guest accounts. The dict's
# keys are the guest group that the account should be added to. Possible
# variables:
#
#  - prefix  : Prefix for the usernames. Used when creating guest accounts.
#              Must be set.
#  - spreads : A list/set/tuple of spreads to add to the guest account at
#              creation. Must be set, but can be empty.
#
GUEST_TYPES = {
    'gjest': {
        'prefix': 'guest-',
        'spreads': tuple(),
    },
}

# The default type of guest account. Must be one of the keys from GUEST_TYPES.
GUEST_TYPES_DEFAULT = 'gjest'

# The maximum number of simultaneously active guest accounts a given person
# could create. Superusers are still able to create more than this.
#
# NOTE: This is actually per account, not per person.
GUEST_MAX_PER_PERSON = 100

# The message that should be sent to guest accounts that are registered with a
# mobile phone number. Needs the followin input variables:
#  - username : The username of the new guest account.
#  - password : The password given to the new guest account.
#  - expire   : The expire date for the guest account, preferably on the
#               format `YYYY-MM-DD'.
GUEST_WELCOME_SMS = """You've been given a guest account
Your username is: %(username)s
Your password is: %(password)s
The account will expire at %(expire)s"""

GUEST_PASSWORD_SMS = """The password for %(username)s has been changed by %(changeby)s.
The new password is: %(password)s"""

# Limit user names to 20 characters, RT #1077796
# sAMAccountName must be less than 20 chars
GUEST_MAX_LENGTH_USERNAME = 19

# Require mobile number when creating a guest
GUEST_REQUIRE_MOBILE = False

# LDAP export stuff

# TODO: Why is this here?
LDAP = {
    'dump_dir': '/cerebrum/var/cache/LDAP/',
    'max_change': 10,
}


# Settings for the contrib/no/uio/generate_guest_ldif.py
# and similar guest ldap exports.
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
