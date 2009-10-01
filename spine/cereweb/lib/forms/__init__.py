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
import cgi
import cherrypy
from lib.utils import legal_date, html_quote, spine_to_web, object_link
from lib.utils import randpasswd, get_lastname_firstname, entity_link
from lib.templates.FormTemplate import FormTemplate
from lib.templates.SearchTemplate import SearchTemplate

from lib.data.AccountDAO import AccountDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.EntityDAO import EntityDAO
from lib.data.OuDAO import OuDAO

"""
Helper-module for search-pages and search-result-pages in cereweb.
"""

class Form(object):
    Template = FormTemplate
    Order = []
    Fields = {}

    def __init__(self, **values):
        self.fields = self.Fields.copy()
        self.order = self.Order[:]

        self.values = values
        self.init_form()

        self._is_quoted = False
        self._is_quoted_correctly = True

        for key, field in self.fields.items():
            value = self.values.get(key)
            name = field.get('name', '')
            if not name:
               field['name'] = key
            field['value'] = value

    def init_form(self):
        pass

    def get_fields(self):
        res = []
        for key in self.order:
            field = self.fields[key]
            if field['type'] == 'select':
                func = getattr(self, 'get_%s_options' % key)
                field['options'] = func()
            res.append(field)
        return res

    def get_values(self):
        self.quote_all()

        values = {} 
        for key, field in self.fields.items():
            values[key] = field['value']
        return values

    def quote_all(self):
        if self._is_quoted:
            return self._is_quoted_correctly

        self._is_quoted = True

        for key, field in self.fields.items():
            if field['value']:
                if 'escape' == field.get('quote'):
                    self.fields[key]['value'] = cgi.escape(field['value'])
                if 'reject' == field.get('quote'):
                    if field['value'] != cgi.escape(field['value']):
                        self.error_message = _("Field '%s' is unsafe.") % field ['label']
                        self._is_quoted_correctly = False
                        break

        return self._is_quoted_correctly

    def has_prerequisite(self):
        for field in self.fields.values():
            if field['type'] == 'hidden' and not field['value']:
                return False

        return True

    def has_required(self):
        res = True
        for field in self.fields.values():
            if field['required'] and not field['value']:
                res = False
                self.error_message = _("Required field '%s' is empty.") % field['label']
                break
        return res

    def is_correct(self):
        if not self.has_required():
            return False

        if not self.quote_all():
            return False

        correct = True
        for field in self.fields.values():
            if field['value']:
                func = getattr(self, 'check_%s' % field['name'], None)
                if func and not func(field['value']):
                    correct = False
                    message = "Field '%s' " % field['label']
                    self.error_message = message + self.error_message
                    break

        return correct and self.check()

    def get_error_message(self):
        message = getattr(self, 'error_message', False)
        return message and (message, True) or ''

    def check(self):
        """This method should be overloaded and used to handle form-level validation."""
        return True

    def _check_short_string(self, name):
        if len(name) <= 256:
            return True

        self.error_message = 'too long (max. 256 characters).'
        return False

    def _check_date(self, date):
        if legal_date(date):
            return True

        self.error_message = 'not a legal date.'
        return False

    def get_action(self):
        return getattr(self, 'action', '/index')

    def get_method(self):
        return getattr(self, 'action', 'POST')

    def get_title(self):
        return getattr(self, 'title', 'No Title')

    def get_help(self):
        return getattr(self, 'help', [])

    def get_scripts(self):
        return getattr(self, 'scripts', [])

    def _get_page(self):
        scripts = self.get_scripts()

        page = self.Template()
        page.jscripts.extend(scripts)
        page.form_title = self.get_title()
        page.form_action = self.get_action()
        page.form_method = self.get_method()
        page.form_fields = self.get_fields()
        page.form_values = self.get_values()
        page.form_help = self.get_help()
        return page

    def render(self):
        page = self._get_page()
        return page.content()

    def respond(self):
        page = self._get_page()
        return page.respond()
            
class SearchForm(Form):
    Template = SearchTemplate

class PersonCreateForm(Form):
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
        options = [(t.id, t.name) for t in ConstantsDAO().get_affiliation_statuses()]
        options.sort(lambda x,y: cmp(x[1], y[1]))
        return options

    def get_ou_options(self):
        return [(t.id, t.name) for t in OuDAO().get_entities()]

    def get_gender_options(self):
        return [(g.name, g.description) for g in 
                   ConstantsDAO().get_gender_types()]

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

class AccountCreateForm(Form):
    def __init__(self, transaction, **values):
        self.transaction = transaction
        super(AccountCreateForm, self).__init__(**values)

    action = '/account/create'

    Order = [
        'owner_id',
        'name',
        '_other',
        'group',
        'expire_date',
        'password0',
        'password1',
        'randpasswd',
    ]

    Fields = {
        'owner_id': {
            'required': True,
            'type': 'hidden',
            'label': _('Owner id'),
        },
        'name': {
            'label': _('Select username'),
            'required': True,
            'type': 'select',
        },
        '_other': {
            'label': _('Enter username'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
        'expire_date': {
            'label': _('Expire date'),
            'required': False,
            'type': 'text',
            'help': _('Date must be in YYYY-MM-DD format.'),
        },
        'group': {
            'label': _('Primary group'),
            'required': False,
            'cls': 'ac_group',
            'type': 'text',
            'quote': 'reject',
        },
        'password0': {
            'label': _('Enter password'),
            'required': False,
            'type': 'password',
        },
        'password1': {
            'label': _('Re-type password'),
            'required': False,
            'type': 'password',
        },
        'randpasswd': {
            'label': _('Random password'),
            'required': False,
            'type': 'radio',
            'name': 'randpwd',
            'value': [randpasswd() for i in range(10)],
        },
    }

    def init_form(self):
        self.owner = self.values.get("owner_entity")
        self.type = self.owner.type_name
        self.name = self.owner.name

    def get_name_options(self):
        usernames = AccountDAO().suggest_usernames(self.owner)
        return [(username, username) for username in usernames]

    def get_title(self):
        return "%s %s" % (_('Owner is'), entity_link(self.owner))

    check_expire_date = Form._check_date

    def check(self):
        pwd0 = self.fields['password0'].get('value', '')
        pwd1 = self.fields['password1'].get('value', '')
            
        if (pwd0 and pwd1) and (pwd0 == pwd1) and (len(pwd0) < 8):
            self.error_message = 'The password must be 8 chars long.'
            return False

        msg = 'The two passwords differ.'
        if (pwd0 and pwd1) and (pwd0 != pwd1):
            self.error_message = msg
            return False

        if (pwd0 and not pwd1) or (not pwd0 and pwd1):
            self.error_message = msg
            return False

        return True

class NonPersonalAccountCreateForm(AccountCreateForm):
    Fields = AccountCreateForm.Fields.copy()
    Fields['np_type'] = {
        'label': _('Account type'),
        'required': True,
        'type': 'select',
    }
    Fields['join'] = {
        'label': _('Join %s'),
        'type': 'checkbox',
        'required': False,
    }

    def init_form(self):
        fields['join']['label'] = fields['join']['label'] % self.name

    Order = AccountCreateForm.Order[:]
    Order.append('np_type')
    Order.append('join')
        
    def get_np_type_options(self):
        account_types = ConstantsDAO().get_account_types()
        return [(t.id, t.description) for t in account_types]

class RoleCreateForm(Form):
    def init_form(self):
        self.order = [
            'group', 'op_set', 'target_type', 'target',
        ]
        self.fields = {
            'group': {
                'label': _('Select group'),
                'required': True,
                'type': 'select',
            },
            'op_set': {
                'label': _('Select op_set'),
                'required': True,
                'type': 'select',
            },
            'target_type': {
                'label': _('Select target type'),
                'required': True,
                'value': 'entity',
                'type': 'select',
            },
            'target': {
                'label': _('Select target'),
                'required': True,
                'type': 'select',
            },
        }

    def get_group_options(self):
        searcher = self.transaction.get_group_searcher()
        searcher.set_name_like('cereweb_*')
        return [(t.get_id(), t.get_name()) for t in searcher.search()]

    def get_op_set_options(self):
        searcher = self.transaction.get_auth_operation_set_searcher()
        return [(t.get_id(), t.get_name()) for t in searcher.search() if not t.get_name().endswith('client')]

    def get_target_options(self):
        searcher = self.transaction.get_ou_searcher()
        return [(t.get_id(), t.get_name()) for t in searcher.search()]

    def get_target_type_options(self):
        return [
            ('global', 'global'),
            ('entity', 'entity'),
            ('self', 'self'),
        ]
