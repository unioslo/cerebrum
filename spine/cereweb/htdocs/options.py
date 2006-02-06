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

import cherrypy

from gettext import gettext as _
from lib.Main import Main
from lib.utils import transaction_decorator, commit_url
from lib.utils import redirect, queue_message
from lib.Options import Options, restore_to_default
from lib.templates.OptionsTemplate import OptionsTemplate

def index(transaction):
    """Creates form for editing user-specific options for cereweb."""
    page = Main()
    page.title = _('Options for cereweb')
    page.setFocus('options')
    
    template = OptionsTemplate()
    content = template.options(cherrypy.session['options'])
    page.content = lambda: content
    return page
index = transaction_decorator(index)
index.exposed = True

def save(transaction, restore=None, **vargs):
    """Save changes done to options."""
    if restore:
        return restore_defaults()
    
    options = cherrypy.session['options']
    
    # set checkboxes to False
    for section in options.sections():
        for key, value in options.items(section):
            if key.endswith('_type') and value == "checkbox":
                options.set(section, key[:-5], "False")
    
    for key, value in vargs.items():
        if '.' not in key:
            continue

        section, key = key.split('.', 1)
        if not options.has_section(section):
            continue
        if not options.has_option(section, key):
            continue

        if options.has_option(section, key+'_type'):
            if options.get(section, key+'_type') == "checkbox":
                value = (value == "on") and "True" or "False"
        
        options.set(section, key, value)
    
    options.save()
    
    msg = _('Options saved successfully.')
    commit_url(transaction, 'index', msg=msg)
save = transaction_decorator(save)
save.exposed = True

def restore_defaults(transaction):
    """Restore options to default values."""
    user = cherrypy.session['options']._get_user(transaction)
    restore_to_default(transaction, user)
    transaction.commit()

    session = cherrypy.session['session']
    username = cherrypy.session['username']
    cherrypy.session['options'] = Options(session, username)
    
    queue_message(_('Options restored to defaults successfully.'))
    redirect('index')
restore_defaults = transaction_decorator(restore_defaults)
restore_defaults.exposed = True

# arch-tag: cc666fb4-4f37-11da-8022-96dbb4fc55eb
