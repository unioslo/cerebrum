# -*- coding: utf-8 -*-
#
# Copyright 2006-2019 University of Tromso, Norway
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

from Cerebrum.modules.bofhd.cmd_param import Command
from Cerebrum.modules.bofhd.cmd_param import FormatSuggestion
from Cerebrum.modules.bofhd.cmd_param import PersonId
from Cerebrum.modules.legacy_users import LegacyUsers
from Cerebrum.modules.no.uit.bofhd_uit_cmds import BofhdExtension


def list_legacy_users(db, search_term):
    lu = LegacyUsers(db)
    results = dict()
    for row in lu.search(username=search_term):
        results[row['user_name']] = dict(row)
    for row in lu.search(ssn=search_term):
        results[row['user_name']] = dict(row)
    return list(results.values())


class BofhdUiTExtension(BofhdExtension):

    all_commands = {}

    #
    # UiT special table for reserved usernames. Usernames that is reserved due
    # to being used in legacy systems
    #
    all_commands['misc_list_legacy_user'] = Command(
        ("misc", "legacy_user"),
        PersonId(),
        fs=FormatSuggestion(
            "%-6s %11s %6s %4s ", ('user_name', 'ssn', 'source', 'type'),
            hdr="%-6s %-11s %6s %4s" % ('UserID', 'Personnr', 'Source', 'Type')
        )
    )

    def misc_list_legacy_user(self, operator, personid):
        # TODO: This method leaks personal information
        return list_legacy_users(self.db, personid)
