# -*- coding: utf-8 -*-
#
# Copyright 2019-2026 University of Oslo, Norway
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
Module for attaching notes to entities.

This module adds a simple document-like note object.  Each note consists of a
subject (title, header), and an optional description (content, body).  Notes
are attached to an existing entity.

Notes can be used to add arbitrary documentation to existing objects.  A
typical use-case is to document usage, restrictions, and references for system
accounts.


Add support for notes
=====================
1. Add schema (``design/mod_note.sql``)
2. Add constants
3. Add mixin to appropriate entity types
4. Optionally, add bofhd-commands and/or API endpoints.


Configuration
-------------
``cereconf.CLASS_CLCONSTANTS``
    Must contain the :class:`.note_constants.NoteChangeCodes` class.

    Example:
    ::

        CLASS_CLCONSTANTS = [
          "Cerebrum.modules.entity_note.note_constants/NoteChangeCodes",
          "Cerebrum.Constants/CLConstants",
        ]

``cereconf.CLASS_CONSTANTS``
    Should contain the :class:`.note_constants.BofhdNoteConstants` class.  This
    is required for bofhd command support.

    Example:
    ::

        CLASS_CONSTANTS = [
          "Cerebrum.modules.entity_note.note_constants/BofhdNoteConstants",
          "Cerebrum.Constants/Constants",
        ]

``cereconf.CLASS_*``
    Entity classes with note support should use
    :class:`.note_mixins.EntityNoteMixin` for note support, or at the very
    least the :class:`.note_mixins.EntityNoteCleanupMixin`.  The latter class
    supports ``Entity.delete()`` for entities with notes attached.

    Example:
    ::

        CLASS_ACCOUNT = [
          "Cerebrum.modules.entity_note.note_mixins/EntityNoteMixin",
          "Cerebrum.Account/Account",
        ]


``restconfig.NAMESPACES_EXTRA``
    Should contain the :obj:`.note_api.api` namespace object to add note
    endpoints to the API.

    Example:
    ::

        NAMESPACES_EXTRA = ["Cerebrum.modules.entity_note.note_api:api"]

Bofhd
    Bofhd commands and common authorization rules are implemented in
    :mod:`.bofhd_note_cmds`.  Remember to subclass and mixin custom
    authorization classes, and add the custom command class to the appropriate
    bofhd commands config.


Caveats
=======
Deleting note entities
    Entities with notes attached to them cannot be deleted unless one of the
    note mixins are in use for that entity.

Deleting creator accounts
    Accounts that have been used to *create* notes cannot be deleted unless all
    of their created notes are deleted or moved to another creator.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

__version__ = '1.2'
