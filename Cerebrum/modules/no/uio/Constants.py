# Copyright 2002, 2003 University of Oslo, Norway
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

"""Access to Cerebrum code values.

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type."""

from Cerebrum import Constants
from Cerebrum.Constants import _AuthoritativeSystemCode,_OUPerspectiveCode

class Constants(Constants.Constants):
    system_lt = _AuthoritativeSystemCode('LT', 'LT')
    system_fs = _AuthoritativeSystemCode('FS', 'FS')
    system_ureg = _AuthoritativeSystemCode('Ureg', 'Imported from ureg')

    perspective_lt = _OUPerspectiveCode('LT', 'LT')
    perspective_fs = _OUPerspectiveCode('FS', 'FS')
