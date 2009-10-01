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
from lib.utils import legal_date

from lib.templates.FormTemplate import FormTemplate
from lib.templates.SearchTemplate import SearchTemplate

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

class SpineForm(Form):
    def __init__(self, transaction, *args, **kwargs):
        self.transaction = transaction
        super(SpineForm, self).__init__(*args, **kwargs)
