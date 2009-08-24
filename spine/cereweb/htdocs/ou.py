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

def _get_links():
    return (
        ('search', _('Search')),
        ('tree',   _('Tree')),
        ('create', _('Create')),
    )

def get_perspective(perspective, perspectives):
    if not perspective:
        return [x for x in perspectives if x.name == "Kjernen"][0]
    else:
        return [x for x in perspectives if x.id == int(perspective)][0]

def tree(perspective=None):
    perspectives = ConstantsDAO().get_ou_perspective_types()
    perspective = get_perspective(perspective, perspectives)

    page = OUTreeTemplate()
    page.tree = OuDAO().get_tree(perspective)
    page.perspective = perspective
    page.perspectives = perspectives
    return page.respond()
tree.exposed = True

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

def search(transaction, **vargs):
    """Search for ous and displays result and/or searchform."""
    args = ('name', 'acronym', 'short', 'spread')
    searcher = OUSearcher(transaction, *args, **vargs)
    return searcher.respond() or search_form(searcher.get_remembered())
search = utils.transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    c_dao = ConstantsDAO()
    ou_dao = OuDAO()

    ou = transaction.get_ou(int(id))
    page = OUViewTemplate()
    page.ou = ou_dao.get(id)
    page.ou.history = HistoryDAO().get_entity_history_tail(id)
    page.perspectives = c_dao.get_ou_perspective_types()
    page.affiliations = c_dao.get_affiliation_types()
    page.spreads = c_dao.get_ou_spreads()
    page.trees = ou_dao.get_trees()
    page.id_types = c_dao.get_id_types()
    page.tr = transaction
    page.title = _("OU %s") % _get_display_name(transaction, ou)
    page.set_focus("ou/view")
    page.links = _get_links()
    page.entity_id = int(id)
    page.entity = ou
    return page.respond()
view = utils.transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    ou_dao = OuDAO()
    ou = ou_dao.get(id)
    trees = ou_dao.get_trees()

    page = Main()
    page.title = _("OU ") + utils.entity_link(ou)
    page.set_focus("ou/edit")
    page.links = _get_links()
    page.content = lambda: OUEditTemplate().form(ou, trees)
    return page
edit = utils.transaction_decorator(edit)
edit.exposed = True

def create(transaction, **vargs):
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
    create.tr = transaction
    page.content = create.form

    return page
create = utils.transaction_decorator(create)
create.exposed = True

def make(transaction, name, institution,
         faculty, institute, department, **vargs):
    acronym = vargs.get("acronym", "")
    short_name = vargs.get("short_name", "")
    display_name = vargs.get("display_name", "")
    sort_name = vargs.get("sort_name", "")

    msg=''
    if not name:
        msg=_('Name is empty.')

    if not msg and not instituion:
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
        ou = transaction.get_commands().create_ou(name, institution,
                                        faculty, institute, department)

        if acronym:
            ou.set_acronym(utils.web_to_spine(acronym))
        if short_name:
            ou.set_short_name(utils.web_to_spine(short_name))
        if display_name:
            ou.set_display_name(utils.web_to_spine(display_name))
        if sort_name:
            ou.set_sort_name(utils.web_to_spine(sort_name))

        msg = _("Organization Unit successfully created.")
        utils.commit(transaction, ou, msg=msg)
    else:
        utils.rollback_url('/ou/create', msg, err=True)
make = utils.transaction_decorator(make)
make.exposed = True

def save(transaction, id, name, submit=None, **vargs):
    ou = transaction.get_ou(int(id))

    if submit == "Cancel":
        utils.redirect_object(ou)
        return

    ou.set_name(web_to_spine(name))
    ou.set_acronym(web_to_spine(vargs.get("acronym", "")))
    ou.set_short_name(web_to_spine(vargs.get("short_name", "")))
    ou.set_display_name(web_to_spine(vargs.get("display_name", "")))
    ou.set_sort_name(web_to_spine(vargs.get("sort_name", "")))

    stedkode_map = {
        'countrycode': ou.set_landkode,
        'institution': ou.set_institusjon,
        'faculty': ou.set_fakultet,
        'institute': ou.set_institutt,
        'department': ou.set_avdeling
    }

    parents = {}
    for (key, value) in vargs.items():
        if key in stedkode_map:
            stedkode_map[key](int(value))
        elif key.startswith("parent_"):
            parent = key.replace("parent_", "")
            if value.isdigit():
                # Could also be "root" and "not_in"
                value = int(value)
            parents[parent] = value

    for (perspective, parent) in parents.items():
        perspective = transaction.get_ou_perspective_type(perspective)
        if parent == "root":
            ou.set_parent(None, perspective)
        elif parent == "not_in":
            ou.unset_parent(perspective)
        else:
            parent = transaction.get_ou(parent)
            ou.set_parent(parent, perspective)

    msg = _("Organization Unit successfully modified.")
    utils.commit(transaction, ou, msg=msg)
save = utils.transaction_decorator(save)
save.exposed = True

def delete(transaction, id):
    ou = transaction.get_ou(int(id))
    msg =_("OU '%s' successfully deleted.") % _get_display_name(transaction, ou)
    ou.delete()
    utils.commit_url(transaction, 'index', msg=msg)
delete = utils.transaction_decorator(delete)
delete.exposed = True

def list_aff_persons(transaction, **vargs):
    args = ('id','source')
    searcher = PersonAffiliationsSearcher(transaction, *args, **vargs)
    return searcher.respond() or utils.redirect('/ou/')
list_aff_persons = utils.transaction_decorator(list_aff_persons)
list_aff_persons.exposed = True


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

# arch-tag: 6a071cd0-f0bc-11d9-90c5-0c57c7893102
