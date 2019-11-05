# -*- coding: utf-8 -*-
# Copyright 2014 University of Oslo, Norway
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

"""Changelog constants for AD2
"""

from Cerebrum import Constants


class CLConstants(Constants.CLConstants):
    # AD functionality
    ad_attr_add = Constants._ChangeTypeCode(
        'ad_attr', 'add', 'added AD-attribute for %(subject)s',
        ('spread=%(string:spread)s, attr=%(string:attr)s, '
         'value=%(string:value)s',))

    ad_attr_del = Constants._ChangeTypeCode(
        'ad_attr', 'remove', 'removed AD-attribute for %(subject)s',
        ('spread=%(string:spread)s, attr=%(string:attr)s',))
