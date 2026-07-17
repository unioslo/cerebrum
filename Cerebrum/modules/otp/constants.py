# -*- coding: utf-8 -*-
#
# Copyright 2021-2024 University of Oslo, Norway
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
OTP module constants.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from Cerebrum.Constants import _ChangeTypeCode, ConstantsBase
from Cerebrum.modules.bofhd.bofhd_constants import _AuthRoleOpCode


class OtpChangeTypeConstants(ConstantsBase):
    """
    OTP-related change type codes for ChangeLog implementations.
    """

    person_otp_add = _ChangeTypeCode(
        'otp', 'add',
        'add otp secret to %(subject)s',
        ('otp_type=%(string:otp_type)s',),
    )

    person_otp_mod = _ChangeTypeCode(
        'otp', 'modify',
        'update otp secret on %(subject)s',
        ('otp_type=%(string:otp_type)s',),
    )

    person_otp_del = _ChangeTypeCode(
        'otp', 'remove',
        'remove otp secret from %(subject)s',
        ('otp_type=%(string:otp_type)s',),
    )


class OtpConstants(ConstantsBase):
    """
    OTP-related constants.
    """

    auth_person_otp_set = _AuthRoleOpCode(
        "person_otp_set",
        "Grant access to set an initial otp secret",
    )

    auth_person_otp_clear = _AuthRoleOpCode(
        "person_otp_clear",
        "Grant access to clear otp secrets"
        " - clear access is also required to re-set otp secrets",
    )
