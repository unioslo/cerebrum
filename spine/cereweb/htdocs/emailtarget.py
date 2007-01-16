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

import cherrypy
import sys
from gettext import gettext as _
from lib.Main import Main
from lib.utils import transaction_decorator
from SpineIDL.Errors import NotFoundError
from lib.templates.EmailTargetViewTemplate import EmailTargetViewTemplate

def parse_address(address_obj):
    address = {
        'id': address_obj.get_id(),
        'local': address_obj.get_local_part(),
        'domain': address_obj.get_domain().get_name(),
        'create': address_obj.get_create_date().get_unix(),
        'change': address_obj.get_change_date().get_unix(),
    }
    expire = address_obj.get_expire_date()
    if expire:
        address['expire'] = expire.get_unix()
    else:
        address['expire'] = None
    return address

def parse_target(target_obj, t_id):
    try:
        name = target_obj.get_entity().get_name()
    except AttributeError, e:
        # There exists email targets without a target.
        # FIXME: Shouldn't happen, But for now we'll accept it.
        name = "None"

    target = {
        'id': t_id,
        'type': target_obj.get_type().get_name(),
        'object_type': 'email_target',
	'name': "%s_email_target" % name,
    }

    try:
        primary_obj = target_obj.get_primary_address()
    except NotFoundError, e:
        primary_obj = None
    if primary_obj:
        target['primary'] = parse_address(primary_obj)
    else:
        target['primary'] = None
    for a in target_obj.get_addresses():
        target.setdefault('addresses', []).append(
            parse_address(a))
    return target

def view(transaction, id):
    id = int(id)
    target_obj = transaction.get_email_target(id)
    target = parse_target(target_obj, id)
    page = Main()
    page.title = _("Addresses in ")
    page.setFocus("/email", id)
    template = EmailTargetViewTemplate()
    content = template.view(target)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

