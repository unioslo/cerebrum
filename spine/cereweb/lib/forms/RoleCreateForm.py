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
from lib.forms.FormBase import SpineForm

class RoleCreateForm(SpineForm):
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
