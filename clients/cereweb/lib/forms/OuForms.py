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

from gettext import gettext as _
from lib.forms.FormBase import EditForm, CreateForm

from lib.data.OuDAO import OuDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.utils import entity_link, get_database, spine_to_web

class OuCreateForm(CreateForm):
    action = '/ou/create/'
    title = _('Create a new Organization')

    Order = [
        'name',
        'acronym',
        'short_name',
        'display_name',
        'sort_name',
        'landkode',
        'institusjon',
        'fakultet',
        'institutt',
        'avdeling',
    ]

    Fields = {
        'name': {
            'label': _('Name'),
            'required': True,
            'type': 'text',
            'quote': 'reject',
        },
        'acronym': {
            'label': _('Acronym'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'short_name': {
            'label': _('Short name'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'display_name': {
            'label': _('Display name'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'sort_name': {
            'label': _('Sort name'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'landkode': {
            'label': _('Country code'),
            'required': True,
            'type': 'text',
            'help': _("Identificator"),
        },
        'institusjon': {
            'label': _('Institution'),
            'required': True,
            'type': 'text',
            'help': _("Identificator"),
        },
        'fakultet': {
            'label': _('Faculty'),
            'required': True,
            'type': 'text',
            'help': _("Identificator"),
        },
        'institutt': {
            'label': _('Institute'),
            'required': True,
            'type': 'text',
            'help': _("Identificator"),
        },
        'avdeling': {
            'label': _('Department'),
            'required': True,
            'type': 'text',
            'help': _("Identificator"),
        },
    }

    def _is_int(self, value):
        try:
            int(value)
        except ValueError, e:
            self.error_message = _("Should be numeric value")
            return False
        return True

    check_institusjon = _is_int
    check_fakultet = _is_int
    check_institutt = _is_int
    check_avdeling = _is_int

class OuEditForm(EditForm, OuCreateForm):
    action = '/ou/edit/'
    title = _('Edit Organization')
    form_class = "edit box"

    def init_fields(self, *args, **kwargs):
        self.order.append('id')
        self.fields['id'] = {
            'label': _('Ou ID'),
            'type': 'hidden',
            'required': True,
        }

    def init_values(self, ou_id, *args, **kwargs):
        self.set_value('id', ou_id)

        db = get_database()
        self.ou = OuDAO(db).get(ou_id)

        if not self.is_postback():
            self.update_values({
                'name': self.ou.name,
                'acronym': self.ou.acronym,
                'short_name': self.ou.short_name,
                'display_name': self.ou.display_name,
                'sort_name': self.ou.sort_name,
                'landkode': self.ou.landkode,
                'institusjon': self.ou.institusjon,
                'fakultet': self.ou.fakultet,
                'institutt': self.ou.institutt,
                'avdeling': self.ou.avdeling,
            })

class OuPerspectiveEditForm(EditForm):
    action = '/ou/edit_perspectives/'
    title = _("Edit Organization Perspectives")
    form_class = "edit box"

    Fields = {
        'id': {
            'label': _('Ou ID'),
            'type': 'hidden',
            'required': True,
        }
    }

    def init_form(self, *args, **kwargs):
        self.db = get_database()
        self.ou_dao = OuDAO(self.db)
        self.constants_dao = ConstantsDAO(self.db)

    def init_fields(self, *args, **kwargs):
        dao = self.constants_dao
        for perspective in dao.get_ou_perspective_types():
            name = 'parent_%s' % perspective.name

            self.fields[name] = {
                'label': _("Parent in %s") % perspective.name,
                'type': 'select',
                'required': True,
            }
            self.order.append(name)

            get_options_fn = self.get_parent_options(perspective)
            setattr(self, "get_%s_options" % name, get_options_fn)

    def init_values(self, id, *args, **kwargs):
        self.set_value("id", id)
        self.ou = self.ou_dao.get(id)

    def get_parent_options(self, perspective):
        options = [
            ("not_in", _("Not in perspective")),
            ("root", _("Root node")),
        ]

        def recurse_branch(ou, indent=0, disabled=False):
            # Disable self and children to prevent loops.
            disabled = disabled or self.ou.id == ou.id

            option = (ou.id, ("%s %s" % ("--" * indent, ou.name), disabled))
            options.append(option)

            for child in ou.children:
                recurse_branch(child, indent + 1, disabled)

        def fn():
            tree = self.ou_dao.get_tree(perspective)
            for root in tree:
                recurse_branch(root)

            return options
        return fn
