# coding: utf-8
#
# Copyright 2018-2026 University of Oslo, Norway
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
Constants related to entity_note.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from Cerebrum.Constants import (
    _ChangeTypeCode,
    CLConstants,
    ConstantsBase,
)
from Cerebrum.modules.bofhd.bofhd_constants import _AuthRoleOpCode


class NoteChangeCodes(CLConstants):
    """
    Note-related change type codes for ChangeLog implementations.
    """

    entity_note_add = _ChangeTypeCode(
        'entity_note', 'add',
        'add entity_note for %(subject)s',
        ('note_id=%(int:note_id)s',),
    )

    entity_note_del = _ChangeTypeCode(
        'entity_note', 'remove',
        'del entity_note for %(subject)s',
        ('note_id=%(int:note_id)s',),
    )


class BofhdNoteConstants(ConstantsBase):
    """
    Note-related constants for bofhd.
    """

    auth_entity_note_add = _AuthRoleOpCode(
        "entity_note_add",
        "Add notes to entities",
    )

    auth_entity_note_remove = _AuthRoleOpCode(
        "entity_note_remove",
        "Remove notes from entities",
    )

    auth_entity_note_show = _AuthRoleOpCode(
        "entity_note_show",
        "View notes on entities",
    )
