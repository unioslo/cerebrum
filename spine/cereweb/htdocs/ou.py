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
from lib import utils
from lib.forms import OuCreateForm, OuEditForm, OuPerspectiveEditForm
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.HistoryDAO import HistoryDAO
from lib.data.OuDAO import OuDAO
from lib.AffiliatedPersonSearcher import AffiliatedPersonSearcher
from lib.templates.OUTreeTemplate import OUTreeTemplate
from lib.templates.OUViewTemplate import OUViewTemplate

def get_perspective(perspective, perspectives):
    if not perspective:
        return [x for x in perspectives if x.name == "Kjernen"][0]
    else:
        return [x for x in perspectives if x.id == int(perspective)][0]

@utils.session_required_decorator
def tree(perspective=None):
    db = utils.get_database()
    perspectives = ConstantsDAO(db).get_ou_perspective_types()
    perspective = get_perspective(perspective, perspectives)

    page = OUTreeTemplate()
    page.tree = OuDAO(db).get_tree(perspective)
    page.perspective = perspective
    page.perspectives = perspectives
    return page.respond()
tree.exposed = True
index = tree

@utils.session_required_decorator
def view(id):
    db = utils.get_database()
    c_dao = ConstantsDAO(db)
    ou_dao = OuDAO(db)

    page = OUViewTemplate()
    page.ou = ou_dao.get(id)
    page.ou.history = HistoryDAO(db).get_entity_history_tail(id)
    page.perspectives = c_dao.get_ou_perspective_types()
    page.affiliations = c_dao.get_affiliation_types()
    page.spreads = c_dao.get_ou_spreads()
    page.quarantines = c_dao.get_quarantines()
    page.trees = ou_dao.get_trees()
    page.id_types = c_dao.get_id_types()
    return page.respond()
view.exposed = True

@utils.session_required_decorator
def edit(id, **kwargs):
    form = OuEditForm(id, **kwargs)
    if form.is_correct():
        return save(**form.get_values())
    return form.respond()
edit.exposed = True

@utils.session_required_decorator
def create(**kwargs):
    form = OuCreateForm(**kwargs)
    if form.is_correct():
        return make(**form.get_values())
    return form.respond()
create.exposed = True

clean = lambda x: x and utils.web_to_spine(x.strip()) or None

def make(
        name, fakultet, institutt, avdeling, institusjon, landkode,
        acronym, short_name, display_name, sort_name):

    name = clean(name)
    acronym = clean(acronym)
    short_name = clean(short_name)
    display_name = clean(display_name)
    sort_name = clean(sort_name)
    landkode = int(landkode)
    institusjon = int(institusjon)
    fakultet = int(fakultet)
    institutt = int(institutt)
    avdeling = int(avdeling)

    db = utils.get_database()
    dao = OuDAO(db)
    entity_id = dao.create(
        name,
        fakultet,
        institutt,
        avdeling,
        institusjon,
        landkode,
        acronym,
        short_name,
        display_name,
        sort_name)
    db.commit()

    utils.queue_message(_("Organization Unit successfully created."), title="OU created")
    utils.redirect_entity(entity_id)

def save(
        id, name, fakultet, institutt, avdeling, institusjon, landkode,
        acronym, short_name, display_name, sort_name):
    db = utils.get_database()
    dao = OuDAO(db)

    ou = dao.get(id)
    ou.name = clean(name)
    ou.fakultet = int(fakultet)
    ou.institutt = int(institutt)
    ou.avdeling = int(avdeling)
    ou.institusjon = int(institusjon)
    ou.landkode = int(landkode)
    ou.acronym = clean(acronym)
    ou.short_name = clean(short_name)
    ou.display_name = clean(display_name)
    ou.sort_name = clean(sort_name)
    dao.save(ou)

    db.commit()

    utils.queue_message(_("Organization Unit successfully modified."), title="OU changed")
    utils.redirect_entity(ou)

@utils.session_required_decorator
def edit_perspectives(id, **kwargs):
    form = OuPerspectiveEditForm(id, **kwargs)
    if form.is_correct():
        return save_perspective(**form.get_values())
    return form.respond()
edit_perspectives.exposed = True

@utils.session_required_decorator
def save_perspectives(id, **vargs):
    db = utils.get_database()
    dao = OuDAO(db)

    parents = {}
    for (attr, value) in vargs.items():
        if attr.startswith("parent_"):
            parent = attr.replace("parent_", "")
            if value.isdigit():
                value = int(value)
            elif value == "root":
                value = None
            # Else it is not in and should be unset
            parents[parent] = value

    for (perspective, parent) in parents.items():
        if parent == "not_in":
            dao.unset_parent(ou.id, perspective)
        else:
            dao.set_parent(ou.id, perspective, parent)

    db.commit()
    utils.queue_message(_("Organization Unit successfully modified."), title="OU changed")
    utils.redirect_entity(id)
save_perspectives.exposed = True

@utils.session_required_decorator
def delete(id):
    db = utils.get_database()
    dao = OuDAO(db)
    ou = dao.get(id)
    dao.delete(id)
    db.commit()
    utils.queue_message(_("OU '%s' successfully deleted.") % ou.name, title="Change succeeded")
    utils.redirect('/ou/')
delete.exposed = True

@utils.session_required_decorator
def perform_search(**vargs):
    searcher = AffiliatedPersonSearcher(**vargs)
    if not searcher.has_prerequisite():
        utils.redirect('/ou')

    return searcher.respond()
perform_search.exposed = True
