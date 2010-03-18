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
from lib.forms.FormBase import CreateForm, EditForm

from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.EmailTargetDAO import EmailTargetDAO
from lib.data.HostDAO import HostDAO
from lib.utils import entity_link, get_database, spine_to_web

class EmailTargetCreateForm(CreateForm):
    action = '/emailtarget/create/'
    title = _('New email target')
    form_class = "edit box"

    Fields = {
        'entity_id': {
            'label': _("Target entity ID"),
            'type': 'hidden',
            'required': True,
        },
        'target_type': {
            'label': _("Target type"),
            'type': 'select',
            'required': True,
        },
        'host_id': {
            'label': _("Host"),
            'type': 'select',
            'required': True,
        },
    }

    def __init__(self, entity_id, *args, **kwargs):
        super(EmailTargetCreateForm, self).__init__(*args, **kwargs)
        self.set_value('entity_id', entity_id)
        self.db = get_database()

    def get_target_type_options(self):
        email_target_types = ConstantsDAO(self.db).get_email_target_types()
        return [(t.id, spine_to_web(t.name)) for t in email_target_types]

    def get_host_id_options(self):
        email_servers = HostDAO(self.db).get_email_servers()
        return [(s.id, spine_to_web(s.name)) for s in email_servers]

    def check(self):
        return self.is_postback()

class EmailTargetEditForm(EditForm, EmailTargetCreateForm):
    action = '/emailtarget/edit/'

    Order = [
        'id',
        'target_type',
        'entity',
        'alias',
    ]

    Fields = {
        'id': {
            'label': _("Email target ID"),
            'type': 'hidden',
            'required': True,
        },
        'target_type': {
            'label': _('Target type'),
            'required': True,
            'type': 'select',
        },
        'entity': {
            'label': _("Associated with entity"),
            'required': False,
            'type': 'text',
        },
        'alias': {
            'label': _('Alias'),
            'required': False,
            'type': 'text',
            'quote': 'reject',
        },
    }

    def __init__(self, id, *args, **kwargs):
        super(EmailTargetCreateForm, self).__init__(*args, **kwargs)
        self.db = get_database()
        self.emailtarget = EmailTargetDAO(self.db).get(id)
        self.set_value('id', self.emailtarget.id)

        if not self.is_postback():
            self.update_values({
                'target_type': self.emailtarget.target_type_id,
                'entity': self.emailtarget.owner.id,
                'alias': self.emailtarget.alias,
            })

    def get_target_type_options(self):
        dao = ConstantsDAO(self.db)
        target_types = dao.get_email_target_types()
        return [(t.id, t.name) for t in target_types]

    def get_title(self):
        return _('Edit %s:') % entity_link(self.emailtarget)

    def check(self):
        return self.is_postback()
