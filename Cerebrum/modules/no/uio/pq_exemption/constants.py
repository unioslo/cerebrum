# -*- coding: utf-8 -*-
#
# Copyright 2019 University of Oslo, Norway
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
"""Constants related to the pq_exemption table"""
from Cerebrum import Constants


class CLConstants(Constants.CLConstants):
    """ChangeLogConstants"""
    printer_quota_exempt_add = Constants._ChangeTypeCode(
        'printer_quota_exempt',
        'add',
        'add printer quota exempt %(subject)s')

    printer_quota_exempt_rem = Constants._ChangeTypeCode(
        'printer_quota_exempt',
        'remove',
        'del printer quota exempt %(subject)s')

    printer_quota_exempt_upd = Constants._ChangeTypeCode(
        'printer_quota_exempt',
        'update',
        'upd printer quota exempt %(subject)s')
