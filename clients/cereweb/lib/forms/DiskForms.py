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

from lib.data.DiskDAO import DiskDAO
from lib.data.HostDAO import HostDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.utils import entity_link, get_database, spine_to_web

class DiskCreateForm(Form):
    action = '/disk/create/'

    Order = [
        'host_id',
        'path',
        'description',
    ]

    Fields = {
        'host_id': {
            'label': _('Host'),
            'required': True,
            'type': 'select',
        },
        'path': {
            'label': _('Path'),
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

    def init_values(self, host_id, *args, **kwargs):
        if host_id:
            self.set_value('host_id', int(host_id))

    def get_title(self):
        return _('Create a new disk')

    def get_host_id_options(self):
        db = get_database()
        return [(h.id, spine_to_web(h.name)) for h in
            HostDAO(db).search()]

class DiskEditForm(DiskCreateForm):
    def init_values(self, disk_id, *args, **kwargs):
        self.set_value('id', disk_id)

        db = get_database()
        self.disk = DiskDAO(db).get(disk_id)

        if not self.is_postback():
            self.update_values({
                'path': self.disk.path,
                'description': self.disk.description,
            })

    action = '/disk/edit/'

    Order = [
        'id',
        'path',
        'description',
    ]

    Fields = {
        'id': {
            'label': _("Disk ID"),
            'type': 'hidden',
            'required': True,
        },
        'path': {
            'label': _('Path'),
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
        return _('Edit %s:') % entity_link(self.disk)

    def check(self):
        return self.is_postback()
