# -*- coding: iso-8859-1 -*-
# Copyright 2003 University of Oslo, Norway
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

from Cerebrum.modules import CLConstants
from Cerebrum import Constants
from CLConstants import _ChangeTypeCode

class NoteConstants(Constants.Constants):
    """Additional changelog constants for the Note module"""

    note_add = _ChangeTypeCode('note', 'add',
            'added note #%(note_id)s, Re: %(subject)s')
    note_del = _ChangeTypeCode('note', 'del',
            'deleted note #%(note_id)s')

# arch-tag: be32060b-7c76-4bc1-bd9e-14ba63bb76c2
