# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
OTP multifactor authentication module.

This module provides a way to store multifactor authentication (e.g.  TOTP)
secrets in Cerebrum.


Data model
----------
The general idea is that any one given person has *one* TOTP secret, which
can be encrypted and stored for multiple target systems (otp_type).

The secret can be updated - and when it is updated, *all* existing otp
entries for that person is removed, and the new secrets are inserted.

person_id
    a person this secret applies to

otp_type
    target type for the secret - i.e. which system it is formatted and
    encrypted for.

otp_payload
    the target payload

updated_at
    insert/update time for this entry.


Configuration
-------------
If the related ``mod_otp.sql`` database schema is present, the following
configuration must be added to ``cereconf``:

cereconf.CLASS_CLCONSTANTS
    Must include ``Cerebrum.modules.otp.constants/OtpChangeLogConstants`` for
    the auditlog, changelog, eventlog, and event publishing mechanism to
    function properly.

cereconf.CLASS_PERSON
    Must include ``Cerebrum.modules.otp.mixins/OtpPersonMixin`` in order to
    maintain constraints.

In addition, the following ``cereconf`` settings controls if/how the OTP module
is used:

cereconf.OTP_POLICY
    Must include a tuple of ``Cerebrum.modules.otp.otp_types/OtpType`` classes.
    Each class defines a otp_type/otp_payload tuple to prepare when setting a
    new otp secret.

cereconf.CLASS_POSIXLDIF
    Must include ``Cerebrum.modules.otp.otp_ldif_utils/RadiusOtpMixin`` to
    include an attribute with the radius-otp payload in LDAP.

cereconf.CLASS_ORGLDIF
    Must include ``Cerebrum.modules.otp.otp_ldif_utils/NorEduOtpMixin`` for
    the 'feide-ga' payload to be included in the Feide-attribute
    ``norEduPersonAuthnMethod``.


Future changes
--------------
We may want to make more of the OtpPolicy configurable - e.g. change the
location/name of the pubkey used for encryption.

In addition we may at some point end up the need for multiple secrets to exist
in parallel.  In which case, we should add support for:

- Multiple, named OtpPolicy objects.   We'll also need to omit or re-implement
  the `clear_obsolete` call in py:module:`.otp_types`.

- Labels to identify each distinct secret/policy.  This could be user defined,
  or defined by OtpPolicy, but should probably be stored in a separate
  ``label`` column in ``person_otp_secret``.  The label should be included in
  a `otpauth://` url given to the user when the secret is generated.  It should
  also be included in the label part of the Feide mfa auth attribute.
"""

# Database module version (see makedb.py)
__version__ = '1.0'
