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

from lib.data.HostDAO import HostDAO
from lib.utils import entity_link, get_database, spine_to_web

class HostCreateForm(Form):
    action = '/host/create/'

    Order = [
        'name',
        'description',
    ]

    Fields = {
        'name': {
            'label': _('Name'),
            'required': True,
            'type': 'text',
            'quote': 'reject',
        },
        'description': {
            'label': _('Description'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
    }

    def get_title(self):
        return _('Create a new host')

class HostEditForm(HostCreateForm):
    def init_values(self, host_id, *args, **kwargs):
        self.set_value('id', host_id)

        db = get_database()
        self.host = HostDAO(db).get(host_id)
        if not self.is_postback():
            self.update_values({
                'name': self.host.name,
                'description': self.host.description,
            })

    action = '/host/edit/'

    Order = [
        'id',
        'name',
        'description',
    ]

    Fields = {
        'id': {
            'label': _("Host ID"),
            'type': 'hidden',
            'required': True,
        },
        'name': {
            'label': _('Name'),
            'required': True,
            'type': 'text',
            'quote': 'reject',
        },
        'description': {
            'label': _('Description'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
    }

    def get_title(self):
        return _('Edit %s:') % entity_link(self.host)

    def check(self):
        return self.is_postback()
