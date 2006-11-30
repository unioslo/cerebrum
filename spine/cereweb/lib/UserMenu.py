# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import Menu
from SideMenu import SideMenu
from gettext import gettext as _

class UserMenu(SideMenu):
    def __init__(self):
        Menu.Menu.__init__(self)
        self.makeMain()
        self.makeMail()
        self.makeGroup()
        self.makeLogout()
        self.setFocus("main/passwd")

    def makeMain(self):
        self.mainmenu = self.addItem("main", _("Main"), "/user_client")
        self.mainmenu.addItem("passwd", _("Password"), "/user_client/#password", cssid="pass_set")

    def makeMail(self):
        self.mailmenu = self.addItem("mail", _("Mail"), "/user_client/mail")
        self.mailmenu.addItem("vacation", _("Vacation"), "/user_client/mail/#vacation")
        self.mailmenu.addItem("forward", _("Mailforward"), "/user_client/mail/#forward")
        self.mailmenu.addItem("spamlevel", _("Spam level"), "/user_client/mail/#spamlevel")

    def makeGroup(self):
        pass
