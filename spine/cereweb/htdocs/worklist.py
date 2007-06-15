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
from SpineIDL.Errors import NotFoundError
from lib.templates.WorkListTemplate import WorkListTemplate

def get_worklist():
    return cherrypy.session.setdefault('wl_remembered', {})

def add(ids):
    """Adds an element to the list of remembered objects."""
    elms = []
    for i in ids.split(','):
        elm = _get(i)
        _remember(elm)
        elms.append(elm)
    return cjson.encode({'result': 'success', 'objects': elms})
add.exposed = True

def remove(ids):
    """Removes elements from the list of remembered objects."""
    for i in ids.split(','):
        _forget(i)
    return cjson.encode({'result': 'success'})
remove.exposed = True

def get_all():
    """Returns the remembered objects, including information about
    which elements are selected."""
    remembered = get_worklist()
    tr = utils.new_transaction()
    for id_ in remembered.keys():
        try:
            tr.get_entity(int(id_))
        except NotFoundError, e:
            del remembered[id_]
    return cjson.encode({'result': 'success', 'objects': remembered.values()})
get_all.exposed = True

def select(ids=''):
    """Updates the list over selected elements."""
    remembered = get_worklist()
    selected = [x for x in ids.split(',') if x and x != '-1']
    for el in remembered.values():
        if el['id'] in selected:
            el['selected'] = True
        else:
            el['selected'] = False
    return cjson.encode({'result': 'success'})
select.exposed = True

def _get(el):
    tr = utils.new_transaction()
    entity = tr.get_entity(int(el))
    type = utils._spine_type(entity)
    try:
        name = _get_name(entity)
    except:
        name = None
    elm = {'id': el, 'name': name, 'type': type}
    return elm

def _get_name(entity):
    t = entity.get_type().get_name()
    name = 'Unknown'
    if t == 'person':
        name = entity.get_cached_full_name()
    elif t == 'disk':
        name = "%s:%s" % (entity.get_host().get_name(), entity.get_path())
    else:
        name = entity.get_name()
    return name

def _remember(elm):
    remembered = get_worklist()
    remembered[elm['id']] = elm

def _forget(id):
    data = get_worklist()
    try:
        del data[id]
    except KeyError, e:
        pass
    return data

def template(type):
    template = WorkListTemplate()
    type = type.lower()
    if type == 'none':
        content = template.NoneAction()
    elif type == 'ou':
        content = template.OUAction()
    elif type == 'account':
        content = template.AccountAction()
    elif type == 'person':
        content = template.PersonAction()
    elif type == 'group':
        content = template.GroupAction()
    elif type == 'host':
        content = template.HostAction()
    elif type == 'disk':
        content = template.DiskAction()
    else:
        content = template.DefaultAction()

    return ['<html><div id="content">%s</div></html>' % content]
template.exposed = True

