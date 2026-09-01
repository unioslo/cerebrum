# -*- coding: utf-8 -*-
#
# Copyright 2021-2026 University of Oslo, Norway
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

This module provides a way to store multifactor authentication (e.g. TOTP)
secrets in Cerebrum.

Data model
----------
The data model stores *otp payloads* for a given person.

person_id
    The owner of this secret.

otp_type
    Target type for the secret - i.e. which system it is formatted and
    encrypted for.  Two systems may *share* a given ``otp_type``, in theory,
    but most systems will want a secret to be encrypted using a specific key.

otp_payload
    The target payload.  This is the shared secret, but this will *usually* be
    formatted and wrapped in some sort of container, and encrypted.

updated_at
    Insert/update time for this entry.

The idea is that the shared secret belongs to a person, and that the generated
one-time password should apply to all accounts owned by this person.

The shared secret may be formatted and/or encrypted into multiple *otp payload*
values.  Each payload is typically prepared for a given target system, which
is represented with the *otp type*.


Configuration
-------------
If the ``mod_otp.sql`` database schema is present, the following
configuration should be added to ``cereconf``:

``CLASS_CONSTANTS``
    Should include OTP-related constants: :class:`~.constants.OtpConstants`.

    These are the bofhd auth codes, and required for the OTP-related bofhd
    commands in :mod:`.bofhd_otp_cmds`.

``CLASS_CLCONSTANTS``
    Must include :class:`~.constants.OtpChangeTypeConstants` for
    the auditlog, changelog, eventlog, and event publishing mechanism to
    function properly.

``CLASS_PERSON``
    Should include :class:`~.mixins.OtpPersonMixin` in order to maintain
    constraints.

In addition, the following ``cereconf`` settings controls if/how the OTP module
is used:

``OTP_POLICY``
    Must include a tuple of :class:`~.otp_types.OtpType` classes.

    Each class defines a otp type and payload tuple to prepare when setting a
    new otp secret.  Example:
    ::

        OTP_POLICY = (
            "Cerebrum.modules.otp.otp_types/OtpTypeFeideJwe",
            "Cerebrum.modules.otp.otp_types/OtpTypeRadiusJwe",
        )

``CLASS_POSIXLDIF``
    Must include :class:`~.otp_ldif_utils.RadiusOtpMixin` to
    include an attribute with the *radius-otp* payload in LDAP.

``CLASS_ORGLDIF``
    Must include :class:`~.otp_ldif_utils.NorEduOtpMixin` for
    the *feide-ga* payload to be included in the ``norEduPersonAuthnMethod``
    Feide-attribute.


bofhd
------
Add a subclass of :class:`~.bofhd_otp_cmds.OtpCommands` with all the proper
auth mixins to the bofhd config.

To delegate access to ``person otp_set``/``person otp_clear``, add
``person_otp_set`` or ``person_otp_clear`` to an appropriate opset.

See :mod:`.bofhd_otp_cmds` for more details.


Future changes
---------------
We may want to make more of the OtpPolicy configurable - e.g. change the
location/name of the pubkey used for encryption.

In addition we may at some point end up the need for multiple secrets to exist
in parallel.  In which case, we should add support for:

- Multiple, named OtpPolicy objects.   We'll also need to omit or re-implement
  the ``clear_obsolete`` call in :mod:`.otp_types`.

- Labels to identify each distinct secret/policy.  This could be user defined,
  or defined by OtpPolicy, but should probably be stored in a separate
  ``label`` column in ``person_otp_secret``.  The label should be included in
  a `otpauth://` url given to the user when the secret is generated.  It should
  also be included in the label part of the Feide mfa auth attribute.
"""

# Database module version (see makedb.py)
__version__ = '1.0'
