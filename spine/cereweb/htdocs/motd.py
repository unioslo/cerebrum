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
from gettext import gettext as _

import cjson
from lib import utils 
from lib.utils import transaction_decorator
from lib.data.MotdDAO import MotdDAO
from lib.templates.MotdTemplate import MotdTemplate

def get_page(n=None):
    db = utils.get_database()
    
    page = MotdTemplate()
    page.title = _("Messages of the day")
    page.add_jscript("motd.js")
    page.motds = MotdDAO(db).get_latest(n)
    return page

def get(transaction, id):
    message, subject = "",""
    try:
        motd = transaction.get_cereweb_motd(int(id))
        message, subject = motd.get_message(), motd.get_subject()
        ## just decode from spine cjson vil do the rest
        ##message = to_web_encode(message)
        ##subject = to_web_encode(subject)
    except NotFoundError, e:
        pass
    return cjson.encode({'message': message, 'subject': subject})
get = transaction_decorator(get)
get.exposed = True

def all():
    page = get_page()
    return page.respond()
all.exposed = True

def save(transaction, id=None, subject=None, message=None):
    if id: # Delete the old
        try:
            motd = transaction.get_cereweb_motd(int(id))
            motd.delete()
        except NotFoundError, e:
            msg = _("Couldn't find existing motd.");
            utils.rollback_url('/index', msg, err=True)
        except AccessDeniedError, e:
            msg = _("You do not have permission to delete.");
            utils.rollback_url('/index', msg, err=True)
        except ValueError, e:
            pass
    try: # Create the new
        subj = utils.web_to_spine(subject)
        mess = utils.web_to_spine(message)
        transaction.get_commands().create_cereweb_motd(subj, mess)
    except AccessDeniedError, e:
        msg = _("You do not have permission to create.");
        utils.rollback_url('/index', msg, err=True)
    msg = _('Motd successfully created.')
    commit_url(transaction, 'index', msg=msg)
save = transaction_decorator(save)
save.exposed = True

def edit(transaction, id=None):
    if not id:
        subject, message = '',''
    else:
        try: 
            motd = transaction.get_cereweb_motd(int(id))
            subject = motd.get_subject()
            message = motd.get_message()
        except NotFoundError, e:
            redirect('/index')
    page = Main()
    page.title = _("Edit Message")
    page.tr = transaction
    tmpl = MotdTemplate()
    content = tmpl.editMotd('/motd/save', id, subject, message, main=True)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def delete(transaction, id):
    """Delete the Motd from the server."""
    motd = transaction.get_cereweb_motd(int(id))
    msg = _("Motd '%s' successfully deleted.") % utils.spine_to_web(motd.get_subject())
    motd.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True
