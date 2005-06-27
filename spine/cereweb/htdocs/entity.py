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
from Cereweb.Main import Main
from Cereweb.utils import url, queue_message, redirect, redirect_object
from Cereweb.utils import transaction_decorator, object_link

def add_external_id(req, transaction, id, external_id, id_type):
    entity = transaction.get_entity(int(id))
    id_type = transaction.get_entity_external_id_type(id_type)
    source_system = transaction.get_source_system("Manual")
    entity.add_external_id(external_id, id_type, source_system)

    #TODO: Redirect to where we actualy came from.
    redirect_object(req, entity, seeOther=True)
    transaction.commit()
    queue_message(req, _("External id successfully added."))
add_external_id = transaction_decorator(add_external_id)

def remove_external_id(req, transaction, id, external_id, id_type):
    entity = transaction.get_entity(int(id))
    id_type = transaction.get_entity_external_id_type(id_type)
    source_system = transaction.get_source_system("Manual")
    entity.remove_external_id(external_id, id_type, source_system)

    #TODO: Redirect to where we actualy came from.
    redirect_object(req, entity, seeOther=True)
    transaction.commit()
    queue_message(req, _("External id successfully removed."))
remove_external_id = transaction_decorator(remove_external_id)

# arch-tag: 4ae37776-e730-11d9-95c2-2a4ca292867e
