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

import cerebrum_path
from Cerebrum.Utils import Factory
ClientAPI = Factory.get_module("ClientAPI")
from gettext import gettext as _
from Cerebrum.web.utils import redirect_object
from Cerebrum.web.utils import queue_message

def add(req, entity, subject, description):
    """Adds a note to some entity"""
    server = req.session['server']
    entity = ClientAPI.fetch_object_by_id(server, entity)
    entity.add_note(subject, description)
    queue_message(req, _("Added note '%s'") % subject)
    return redirect_object(req, entity, seeOther=True)

def delete(req, entity, id):
    """Removes a note"""
    server = req.session['server']
    entity = ClientAPI.fetch_object_by_id(server, entity)
    entity.remove_note(id)
    queue_message(req, _("Deleted note"))
    return redirect_object(req, entity, seeOther=True)

# arch-tag: a346491e-4e47-42c1-8646-391b6375b69f
