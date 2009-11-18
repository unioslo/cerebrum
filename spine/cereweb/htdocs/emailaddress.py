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
from lib.utils import redirect
from lib.utils import queue_message, session_required_decorator
from lib.utils import web_to_spine, get_database
from lib.utils import parse_date, redirect_entity
from lib.forms import EmailAddressEditForm, EmailAddressCreateForm
from lib.data.EmailTargetDAO import EmailTargetDAO
from lib.data.EmailAddressDAO import EmailAddressDAO

@session_required_decorator
def edit(*args, **kwargs):
    """
    Creates a page with the form for editing a host.
    """
    form = EmailAddressEditForm(*args, **kwargs)
    if form.is_correct():
        return save(**form.get_values())
    return form.respond()
edit.exposed = True

@session_required_decorator
def create(*args, **kwargs):
    """
    Creates a page with the form for editing a host.
    """
    form = EmailAddressCreateForm(*args, **kwargs)
    if form.is_correct():
        return make(**form.get_values())
    return form.respond()
create.exposed = True

@session_required_decorator
def delete(address_id, target_id):
    db = get_database()
    dao = EmailAddressDAO(db)
    dao.delete(address_id)
    db.commit()

    queue_message(
        _('Email address successfully deleted.'),
        title=_("Change succeeded"))
    redirect_entity(target_id)
delete.exposed = True

def save(target_id, **kwargs):
    """Saves the information for the host."""
    db = get_database()
    dao = EmailTargetDAO(db)

    queue_message(
        _("Save is not implemented yet."),
        title=_("Change failed"))
    redirect_entity(target_id)

def make(target_id, local, domain, expire):
    local_part = web_to_spine(local.strip())
    expire_date = parse_date(expire)

    db = get_database()
    dao = EmailAddressDAO(db)
    dao.create(target_id, domain, local_part, expire_date)
    db.commit()

    queue_message(_("Email address successfully created."), title=_("Change succeeded"))
    redirect_entity(target_id)

@session_required_decorator
def setprimary(address_id, target_id):
    db = get_database()
    dao = EmailTargetDAO(db)
    dao.set_primary_address(target_id, address_id)
    db.commit()

    queue_message(
        _("Email address successfully set as primary."),
        title=_("Change succeeded"))
    redirect_entity(target_id)
setprimary.exposed = True
