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
from Cerebrum.Database import IntegrityError
from lib.utils import queue_message, session_required_decorator
from lib.utils import redirect, get_database, redirect_entity
from lib.utils import is_correct_referer, get_referer_error

from lib.templates.EmailTargetViewTemplate import EmailTargetViewTemplate
from lib.forms import EmailTargetEditForm, EmailTargetCreateForm
from lib.data.EmailTargetDAO import EmailTargetDAO

@session_required_decorator
def view(id):
    db = get_database()
    target_dao = EmailTargetDAO(db)

    page = EmailTargetViewTemplate()
    page.title = _("Email account")
    page.set_focus("emailtarget/view")
    page.target = target_dao.get(id)
    return page.respond()
view.exposed = True

@session_required_decorator
def edit(*args, **kwargs):
    """
    Creates a page with the form for editing a host.
    """
    form = EmailTargetEditForm(*args, **kwargs)
    if form.is_correct():
        if is_correct_referer():
            return save(**form.get_values())
        else:
            queue_message(get_referer_error(), error=True, title='Edit failed')
    return form.respond()
edit.exposed = True

@session_required_decorator
def create(*args, **kwargs):
    """
    Creates a page with the form for editing a host.
    """
    form = EmailTargetCreateForm(*args, **kwargs)
    if form.is_correct():
        if is_correct_referer():
            return make(**form.get_values())
        else:
            queue_message(get_referer_error(), error=True, title=_('Create failed'))
    return form.respond()
create.exposed = True

def save(id, entity, target_type, alias):
    """Saves the information for the host."""
    db = get_database()
    dao = EmailTargetDAO(db)
    dao.save(int(id), int(entity), int(target_type), alias)
    db.commit()

    queue_message(
        _("Email target saved."),
        title=_("Change succeeded"))
    redirect_entity(id)

def make(entity_id, target_type, host_id):
    db = get_database()
    dao = EmailTargetDAO(db)
    try:
        dao.create(entity_id, target_type, host_id)
        db.commit()
        queue_message(
            _("Added email target successfully."),
            title=_("Change succeeded"))
    except IntegrityError, e:
        queue_message(_('An emailtarget already exist at this host.'), error=True, title=_('Add emailtarget failed'))
    redirect_entity(entity_id)

@session_required_decorator
def delete(id, entity_id=None):
    db = get_database()
    try:
        dao = EmailTargetDAO(db)
        dao.delete(id)
        db.commit()

        queue_message(
            _('Email target successfully deleted.'),
            title=_("Change succeeded"))
    except IntegrityError, e:
        queue_message(
            _('This emailtarget contains the primary email-address and cannot be deleted.'),
            error=True,
            title=_('Could not delete emailtarget'))
    if entity_id:
        redirect_entity(entity_id)
    redirect('/index')
delete.exposed = True
