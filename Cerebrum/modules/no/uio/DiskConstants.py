# -*- coding: utf-8 -*-
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

from Cerebrum import Constants


class CLConstants(Constants.CLConstants):
    disk_quota_set = Constants._ChangeTypeCode(
        'disk_quota', 'set', 'set disk quota for %(subject)s',
        ('quota=%(int:quota)s',
         'override_quota=%(int:override_quota)s',
         'override_exp=%(string:override_expiration)s',
         'reason=%(string:description)s'))
    disk_quota_clear = Constants._ChangeTypeCode(
        'disk_quota', 'clear', 'clear disk quota for %(subject)s')
