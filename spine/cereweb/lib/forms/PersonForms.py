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
from lib.forms.FormBase import Form

from lib.utils import get_database

from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.OuDAO import OuDAO

class PersonCreateForm(Form):
    def __init__(self, *args, **kwargs):
        super(PersonCreateForm, self).__init__(*args, **kwargs)
        self.db = get_database()

    Order = [
        'ou',
        'status',
        'firstname',
        'lastname',
        'externalid',
        'gender',
        'birthdate',
        'description',
    ]

    Fields = {
        'ou': {
            'label': _('OU'),
            'required': True,
            'type': 'select',
            'quote': 'reject',
        },
        'status': {
            'label': _('Affiliation Type'),
            'required': True,
            'type': 'select',
            'quote': 'reject',
        },
        'firstname': {
            'label': _('First name'),
            'required': True,
            'type': 'text',
            'quote': 'reject',
        },
        'lastname': {
            'label': _('Last name'),
            'required': True,
            'type': 'text',
            'quote': 'reject',
        },
        'gender': {
            'label': _('Gender'),
            'required': True,
            'type': 'select',
        },
        'birthdate': {
            'label': _('Birth date'),
            'required': True,
            'type': 'text',
            'help': _('Date must be in YYYY-MM-DD format.'),
        },
        'externalid': {
            'label': '<abbr title="%s">%s</abbr>' % (_('National Identity Number'), _('NIN')),
            'required': False,
            'type': 'text',
            'help': _('Norwegian "Fødselsnummer", 11 digits'),
        },
        'description': {
            'label': _('Description'),
            'required': False,
            'type': 'text',
            'quote': 'escape',
        }
    }

    def get_status_options(self):
        options = [(t.id, t.name) for t in ConstantsDAO(self.db).get_affiliation_statuses()]
        options.sort(lambda x,y: cmp(x[1], y[1]))
        return options

    def get_ou_options(self):
        return [(t.id, t.name) for t in OuDAO(self.db).get_entities()]

    def get_gender_options(self):
        return [(g.name, g.description) for g in 
                   ConstantsDAO(self.db).get_gender_types()]

    def check_firstname(self, name):
        return self._check_short_string(name)

    def check_lastname(self, name):
        return self._check_short_string(name)

    check_birthdate = Form._check_date

    def check_externalid(self, ssn):
        if len(ssn) <> 11 or not ssn.isdigit():
            self.error_message = 'SSN should be an 11 digit Norwegian Social Security Number'
            return False

        return True

class PersonEditForm(PersonCreateForm):
    Order = [
        'id', 'gender', 'birthdate', 'description', 'deceased'
    ]

    Fields = {
        'id': {
            'label': 'id',
            'required': True,
            'type': 'hidden',
        },
        'gender': {
            'label': _('Gender'),
            'required': True,
            'type': 'select',
        },
        'birthdate': {
            'label': _('Birth date'),
            'required': True,
            'type': 'text',
            'help': 'YYYY-MM-DD',
        },
        'description': {
            'label': _('Description'),
            'required': False,
            'type': 'text',
            'quote': 'escape',
        },
        'deceased': {
            'label': _('Deceased date'),
            'required': False,
            'type': 'text',
            'help': 'YYYY-MM-DD',
        },
    }

    check_deceased = Form._check_date

    def get_title(self):
        return 'Edit ' + getattr(self, 'title', 'person')
