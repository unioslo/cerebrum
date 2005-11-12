# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
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

from gettext import gettext as _
from lib.Main import Main
from lib.utils import transaction_decorator
from lib.templates.Email import Email

def index(transaction):
    page = Main()
    page.title = _("Email") 
    page.setFocus("email")
    template = Email()
    content = template.index(transaction)
    page.content = lambda: content
    return page
index = transaction_decorator(index)    
index.exposed = True

# arch-tag: b3739600-040d-11da-97b3-692f6b35af14
