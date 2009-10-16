# -*- coding: iso-8859-1 -*-

# Copyright 2009 University of Oslo, Norway
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

from lib.data.NoteDAO import NoteDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.utils import entity_link, get_database, spine_to_web

class NoteCreateForm(CreateForm):
    action = '/note/add'
    title = _('Add Note')
    form_class = "edit box"

    Order = [
        'entity_id',
        'subject',
        'body',
    ]

    Fields = {
        'entity_id': {
            'required': True,
            'type': 'hidden',
        },
        'subject': {
            'label': _('Subject'),
            'required': True,
            'type': 'text',
            'quote': 'reject',
        },
        'body': {
            'label': _('Optional Details'),
            'required': False,
            'type': 'textarea',
            'quote': 'reject',
        },
    }

    def init_values(self, entity_id, *args, **kwargs):
        self.set_value('entity_id', entity_id)

    


class NoteEditForm(EditForm, NoteCreateForm):
    action = '/note/edit'
    title = _('Edit Note')
    form_class = "edit box"

    def init_fields(self, *args, **kwargs):
        self.order.append('note_id')
        self.fields['note_id'] = {
            'type': 'hidden',
            'required': True,
        }

    def init_values(self, enitity_id, note_id, *args, **kwargs):
        super().init_values(enitity_id, note_id, *args, **kwargs)
        self.set_value('note_id', note_id)

        db = get_database()
        self.note = NoteDAO(db).get(note_id)

        if not self.is_postback():
            self.update_values({
                'entity_id': self.note.entity_id,
                'subject': self.note.subject,
                'body': self.ou.body,
            })

