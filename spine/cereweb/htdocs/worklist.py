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

import forgetHTML as html
from Cereweb.WorkList import WorkListElement

def add(req, id, cls, name):
    """Adds an element to the list of remembered objects."""
    if 'wl_remembered' not in req.session:
        req.session['wl_remembered'] = []
    elm = WorkListElement(int(id), cls, name)
    req.session['wl_remembered'].append(elm)

    page = html.SimpleDocument("Worklist: Element added")
    msg = "Element added to worklist: %s, %s: %s" % (id, cls, name)
    page.body.append(html.Division(msg))
    return page

def remove(req, id=None, ids=None):
    """Removes elements from the list of remembered objects."""
    if ids is None:
        ids = []
    else:
        ids = [int(i) for i in ids.split(",") if i]
    
    if id is not None and id not in ids:
        ids.append(int(id))

    for id in ids:
        _remove(req.session, id)
        
    page = html.SimpleDocument("Worklist: Element(s) removed")
    msg = "Element(s) removed from worklist: %s" % ids
    page.body.append(html.Division(msg))
    return page

def selected(req, ids=None, action=""):
    """Updates the list over selected elements."""
    if ids is None:
        selected = req.session['wl_selected'] = []
    else:
        if 'wl_remembered' not in req.session:
            req.session['wl_remembered'] = []

        remembered = req.session['wl_remembered']
        updated = [int(i) for i in ids.split(",") if i]
        selected = [i for i in remembered if i.id in updated]
        req.session['wl_selected'] = selected
    
        if action:
            if 'wl_actions' not in req.session:
                req.session['wl_actions'] = []
            req.session['wl_actions'].append(action)
    
    page = html.SimpleDocument("Worklist: selected elements updated")
    msg = "Selected element(s) updated: %s" % selected
    page.body.append(html.Division(msg))
    return page

def _remove(session, id):
    if 'wl_remembered' in session:
        elm = [i for i in session['wl_remembered'] if i.id == id]
        if elm:
            session['wl_remembered'].remove(elm[0])

# arch-tag: b7928902-fdf6-11d9-87e0-419999ff18a5
