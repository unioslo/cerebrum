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

from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.bofhd.errors import PermissionDenied
from gettext import gettext as _

import cjson
from lib import utils 
from lib.utils import queue_message
from lib.utils import redirect
from lib.utils import session_required_decorator
from lib.utils import is_correct_referer, get_referer_error
from lib.data.MotdDAO import MotdDAO
from lib.Main import Main
from lib.templates.MotdTemplate import MotdTemplate

def get_page(n=None):
    db = utils.get_database()

    page = MotdTemplate()
    page.title = _("Messages of the day")
    page.add_jscript("motd.js")
    page.motds = MotdDAO(db).get_latest(n)
    return page

def _get_motd(motd_id):
    if not motd_id: return None

    db = utils.get_database()

    try:
        return MotdDAO(db).get(motd_id)
    except NotFoundError, e:
        return None

@session_required_decorator
def get(id):
    motd = _get_motd(id)
    if motd is None:
        message, subject = "",""
    else:
        message, subject = motd.message, motd.subject

    return cjson.encode({'message': message, 'subject': subject})
get.exposed = True

@session_required_decorator
def all():
    page = get_page()
    return page.respond()
all.exposed = True

@session_required_decorator
def save(id=None, subject=None, message=None):
    if not is_correct_referer():
        queue_message(get_referer_error(), error=True, title='Save message failed')
        redirect('/index')
        
    db = utils.get_database()
    dao = MotdDAO(db)

    if id:
        _delete(dao, id)

    try:
        subj = utils.web_to_spine(subject)
        mess = utils.web_to_spine(message)
        dao.create(subj, mess)
    except PermissionDenied, e:
        msg = _("You do not have permission to create motd.");
        queue_message(msg, title=_("Change failed"), error=True)
        redirect('/index')
    db.commit()

    msg = _('Motd successfully created.')
    queue_message(msg, title=_("Change succeeded"))
    redirect('/index')
save.exposed = True

@session_required_decorator
def edit(id=None):
    if not is_correct_referer():
        queue_message(get_referer_error(), title=_("Change failed"), error=True)
        redirect('/index')
        
    motd = _get_motd(id)
    if motd is None:
        msg = _("Couldn't find existing motd.");
        queue_message(msg, title=_("Change failed"), error=True)
        redirect('/index')

    subject, message = motd.subject, motd.message

    page = Main()
    page.title = _("Edit Message")
    tmpl = MotdTemplate()
    content = tmpl.editMotd('/motd/save', id, subject, message, main=True)
    page.content = lambda: content
    return page
edit.exposed = True

@session_required_decorator
def delete(id):
    """Delete the Motd from the server."""
    db = utils.get_database()
    dao = MotdDAO(db)
    _delete(dao, id)
    db.commit()

    msg = _("Motd successfully deleted.")
    queue_message(msg, title=_("Change succeded"))
    redirect('/index')
delete.exposed = True

def _delete(dao, motd_id):
    try:
        dao.delete(motd_id)
    except NotFoundError, e:
        msg = _("Couldn't find existing motd.");
        queue_message(msg, title=_("Change failed"), error=True)
        redirect('/index')
    except PermissionDenied, e:
        msg = _("You do not have permission to delete.");
        queue_message(msg, title=_("Change failed"), error=True)
        redirect('/index')
    return True
