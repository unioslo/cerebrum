# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

import forgetHTML as html
from gettext import gettext as _
from Cerebrum.web.Main import Main

def index(req, tag="p"):
    body = Main(req)
    body.title = _("Cereweb v0.1a")
    table = html.SimpleTable(header="row")
    table.add("Her", "kommer en", "velkomsthilsen")
    table.add("Dette", "er")
    table.add("Ganske", "bra", "altså")
    body.content = table.output

    return body

# arch-tag: ba1f315d-85f5-4454-a01e-28013e464199
