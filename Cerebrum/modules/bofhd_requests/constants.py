# coding: utf-8
#
# Copyright 2019-2023 University of Oslo, Norway
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
Constant types and common constants for the bofhd_requests module.

Configuration
--------------
:class:`.Constants` should be included in ``cereconf.CLASS_CONSTANTS`` if the
``mod_bofhd_requests`` database module is present.

History
--------
These constants were moved from ``Cerebrum.modules.bofhd.bofhd_constants`` in
order to isolate functionality related to ``mod_bofhd_requests``.  The original
constants can be seen in:

  Commit: 0f7903195bfc8ac53fee393367fdd2df43261330
  Merge:  0a1a624cf 160e2da9e
  Date:   Tue Apr 9 09:00:59 2019 +0200

"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import Cerebrum.Constants


class _BofhdRequestOpCode(Cerebrum.Constants._CerebrumCode):
    """
    bofhd_request request types (operations).

    These mappings are stored in the auth_role_op_code table.
    """

    _lookup_table = "[:table schema=cerebrum name=bofhd_request_code]"


class Constants(Cerebrum.Constants.Constants):

    BofhdRequestOp = _BofhdRequestOpCode

    # Move operations
    bofh_move_user = _BofhdRequestOpCode(
        "br_move_user",
        "Move user (batch)",
    )
    bofh_move_user_now = _BofhdRequestOpCode(
        "br_move_user_now",
        "Move user",
    )
    bofh_move_student = _BofhdRequestOpCode(
        "br_move_student",
        "Move student",
    )
    bofh_move_request = _BofhdRequestOpCode(
        "br_move_request",
        "Move request",
    )
    bofh_move_give = _BofhdRequestOpCode(
        "br_move_give",
        "Give away user",
    )

    # Various user operations
    bofh_archive_user = _BofhdRequestOpCode(
        "br_archive_user",
        "Archive home directory",
    )
    bofh_delete_user = _BofhdRequestOpCode(
        "br_delete_user",
        "Delete user",
    )
    bofh_quarantine_refresh = _BofhdRequestOpCode(
        "br_quara_refresh",
        "Refresh quarantine",
    )
    bofh_homedir_restore = _BofhdRequestOpCode(
        "br_homedir_rest",
        "Restore users homedir",
    )

    # generate_mail_ldif.py will set the mailPause attribute based on
    # entries in the request queue.
    #
    # Messages will queue up on the old server while mailPause is
    # true.  When the move is done, those messages will make another
    # trip through the main hub before being delivered.
    # Unfortunately, this may mean we get another shadow copy.
    #
    # state_data is optionally a request_id: wait if that request is
    # in queue (typically a create request).  A bofh_email_convert is
    # inserted when done.
    bofh_email_create = _BofhdRequestOpCode(
        "br_email_create",
        "Create user mailboxes",
    )
    bofh_email_delete = _BofhdRequestOpCode(
        "br_email_delete",
        "Delete all user mailboxes",
    )
    bofh_email_convert = _BofhdRequestOpCode(
        "br_email_convert",
        "Convert user mail config",
    )
    bofh_email_restore = _BofhdRequestOpCode(
        "br_email_restore",
        "Restore users mail from backup",
    )

    # Sympa lists
    bofh_sympa_create = _BofhdRequestOpCode(
        "br_sym_create",
        "Create a sympa list",
    )

    bofh_sympa_remove = _BofhdRequestOpCode(
        "br_sym_remove",
        "Remove a sympa list",
    )
