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

from account import _get_links
from gettext import gettext as _
from lib.Main import Main
from lib import utils
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.HistoryDAO import HistoryDAO
from lib.data.OuDAO import OuDAO
from lib.Searchers import OUSearcher, PersonAffiliationsSearcher
from lib.Searchers import PersonAffiliationsOuSearcher
from lib.templates.SearchTemplate import SearchTemplate
from lib.templates.SearchResultTemplate import SearchResultTemplate
from lib.templates.OUCreateTemplate import OUCreateTemplate
from lib.templates.OUTreeTemplate import OUTreeTemplate
from lib.templates.OUEditTemplate import OUEditTemplate
from lib.templates.OUViewTemplate import OUViewTemplate
import SpineIDL.Errors

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
    page.trees = ou_dao.get_trees()
    page.id_types = c_dao.get_id_types()
    return page.respond()
view.exposed = True

def _get_links():
    return (
        ('tree', _('Tree')),
        ('create', _('Create')),
    )

@utils.session_required_decorator
def edit(id):
    db = utils.get_database()
    ou_dao = OuDAO(db)
    ou = ou_dao.get(id)
    trees = ou_dao.get_trees()

    page = Main()
    page.title = _("OU ") + utils.entity_link(ou)
    page.set_focus("ou/edit")
    page.links = _get_links()
    page.content = lambda: OUEditTemplate().form(ou, trees)
    return page
edit.exposed = True

@utils.session_required_decorator
def create(**vargs):
    page = Main()
    page.title = _("OU")
    page.set_focus("ou/create")
    page.links = _get_links()

    # Store given parameters for the create-form
    values = {}
    values['name'] = vargs.get("name", "")
    values['acronym'] = vargs.get("acronym", "")
    values['short_name'] = vargs.get("short_name", "")
    values['sort_name'] = vargs.get("sort_name", "")

    create = OUCreateTemplate(searchList=[{'formvalues': values}])
    page.content = create.form

    return page
create.exposed = True

@utils.session_required_decorator
def make(name, institution, faculty, institute, department, **vargs):
    clean = lambda x: x and utils.web_to_spine(x) or None
    acronym = clean(vargs.get("acronym", ""))
    short_name = clean(vargs.get("short_name", ""))
    display_name = clean(vargs.get("display_name", ""))
    sort_name = clean(vargs.get("sort_name", ""))

    msg=''
    if not name:
        msg=_('Name is empty.')

    if not msg and not institution:
        msg=_('Institution is empty.')

    if not msg and not faculty:
        msg=_('Faculty is empty.')

    if not msg and not institute:
        msg=_('Institute is empty.')

    if not msg and not department:
        msg=_('Department is empty.')

    if not msg:
        institution = int(institution)
        faculty = int(faculty)
        institute = int(institute)
        department = int(department)
        name = utils.web_to_spine(name.strip())

        entity_id = _create_ou(name, institution, faculty, institute, department,
                   acronym, short_name, display_name, sort_name)

        utils.queue_message(_("Organization Unit successfully created."), title="OU created")
        utils.redirect_entity(entity_id)
    else:
        utils.rollback_url('/ou/create', msg, err=True)
make.exposed = True

def _create_ou(
        name, institution, faculty, institute, department,
        acronym, short_name, display_name, sort_name):

    db = utils.get_database()
    dao = OuDAO(db)
    entity_id = dao.create(
        name,
        institution,
        faculty,
        institute,
        department,
        acronym,
        short_name,
        display_name,
        sort_name)
    db.commit()

    return entity_id

@utils.session_required_decorator
def save(id, name, **vargs):
    db = utils.get_database()
    dao = OuDAO(db)

    ou = dao.get(id)
    ou.name = utils.web_to_spine(name)
    ou.acronym = utils.web_to_spine(vargs.get("acronym", ""))
    ou.short_name = utils.web_to_spine(vargs.get("short_name", ""))
    ou.display_name = utils.web_to_spine(vargs.get("display_name", ""))
    ou.sort_name = utils.web_to_spine(vargs.get("sort_name", ""))

    stedkode_map = {
        'contrycode': 'landkode',
        'institution': 'institusjon',
        'faculty': 'fakultet',
        'institute': 'institutt',
        'department': 'avdeling',
    }

    parents = {}
    for (key, value) in vargs.items():
        if key in stedkode_map:
            attr = stedkode_map[key]
            setattr(ou, attr, int(value))
        elif key.startswith("parent_"):
            parent = key.replace("parent_", "")
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

    dao.save(ou)
    db.commit()

    utils.queue_message(_("Organization Unit successfully modified."), title="OU changed")
    utils.redirect_entity(ou)
save.exposed = True

@utils.session_required_decorator
def delete(id):
    db = utils.get_database()
    dao = OuDAO(db)
    ou = dao.get(id)
    dao.delete(id)
    db.commit()
    utils.queue_message(_("OU '%s' successfully deleted.") % ou.name)
    utils.redirect('/ou/')
delete.exposed = True

def _get_display_name(transaction, ou):
    display_name = ou.get_display_name()
    if display_name:
        return utils.spine_to_web(display_name)
    else:
        return utils.spine_to_web(ou.get_name())

def perform_search(transaction, **vargs):
    args = ('id', 'source', 'affiliation', 'recursive','withoutssn')
    searcher = PersonAffiliationsOuSearcher(transaction, *args, **vargs)
    return searcher.respond() or search_form(searcher.get_remembered())
perform_search = utils.transaction_decorator(perform_search)
perform_search.exposed = True

def search_form(remembered):
    page = SearchTemplate()
    page.title = _("OU")
    page.set_focus("ou/search")
    page.links = _get_links()

    page.search_fields = [("name", _("Name")),
                          ("acronym", _("Acronym")),
                          ("short", _("Short name")),
                          ("spread", _("Spread name"))
                          ]
    page.search_action = '/ou/search'

    page.search_title = _('OU(s)')
    page.form_values = remembered
    return page.respond()
