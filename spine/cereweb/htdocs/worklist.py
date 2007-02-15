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

from lib import cjson
from lib import utils

def _get(_id):
    tr = utils.new_transaction()
    entity = tr.get_entity(int(_id))
    type = utils._spine_type(entity)
    try:
        name = entity.get_name()
    except:
        name = None
    elm = {'id': _id, 'name': name, 'type': type}
    return elm

def get(id=None):
    """Returns the info about the given id."""
    if not id or id == 'undefined':
        elm = cherrypy.session.setdefault('wl_remembered', {})
    else:
        elm = _get(id)
    return cjson.encode(elm)
get.exposed = True

def add(id, cls, name):
    """Adds an element to the list of remembered objects."""
    data = _remember(id, cls, name)
    return cjson.encode(data)
add.exposed = True

def remove(id=None, ids=None):
    """Removes elements from the list of remembered objects."""
    if ids is None:
        ids = []
    else:
        ids = [i for i in ids.split(",") if i]
    
    if id is not None and id not in ids:
        ids.append(id)

    for id in ids:
        data = _forget(id)
    return cjson.encode(data)
remove.exposed = True

def selected(ids=None):
    """Updates the list over selected elements."""
    if ids is None:
        selected = cherrypy.session['wl_selected'] = []
    else:
        remembered = cherrypy.session.setdefault('wl_remembered', {})
        updated = [i for i in ids.split(",") if i]
        selected = [i for i in remembered.keys() if i in updated]
        cherrypy.session['wl_selected'] = selected
    
    data = cherrypy.session.setdefault('wl_remembered', {})
    for id in selected:
        data[id]['selected'] = True
    return cjson.encode(data)
selected.exposed = True

def _remember(id, cls=None, name=None):
    data = cherrypy.session.setdefault('wl_remembered', {})

    if not cls:
        elm = _get(id)
    elif not name:
        elm = _get(id)
    else:
        elm = {'id': id, 'name': name, 'type': cls}

    data[elm['id']] = elm
    return data

def _forget(id):
    data = cherrypy.session.setdefault('wl_remembered', {})
    try:
        del data[id]
    except KeyError, e:
        pass
    return data
