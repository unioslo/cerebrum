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
Cerebrum modules must be included in ``cereconf`` in order to maintain
constraints:

cereconf.CLASS_CLCONSTANTS
    Must include ``Cerebrum.modules.otp.constants/OtpChangeLogConstants``

cereconf.CLASS_PERSON
    Must include ``Cerebrum.modules.otp.mixins/OtpPersonMixin``

"""

# Database module version (see makedb.py)
__version__ = '1.0'
