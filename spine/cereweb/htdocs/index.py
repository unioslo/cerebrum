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
from Cerebrum.web.templates.MotdViewTemplate import MotdViewTemplate


def index(req, tag="p"):
    page = Main(req)
    page.title = _("Welcome to Cereweb")
    page.setFocus("main")
    motd = MotdViewTemplate()
    page.content = lambda: motd.viewMotds(req)

    return page

# arch-tag: d11bf90a-f730-4568-9234-3fc494982911
