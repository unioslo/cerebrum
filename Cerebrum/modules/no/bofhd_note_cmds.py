# -*- coding: utf-8 -*-
#
# Copyright 2013-2018, University of Oslo, Norway
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
"""Commands for BOFHD EntityNote functionality."""

from Cerebrum.modules import Note
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (Command,
                                              FormatSuggestion,
                                              Id,
                                              SimpleString)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied


def format_time(field):
    fmt = "yyyy-MM-dd HH:mm"            # 16 characters wide
    return ':'.join((field, "date", fmt))


class EntityNoteBofhdAuth(BofhdAuth):

    def can_add_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_remove_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_show_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(operator,
                                              self.const.auth_set_password):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")


class BofhdExtension(BofhdCommonMethods):
    """ Extends bofhd with a 'note' command group. """

    all_commands = {}
    parent_commands = False
    authz = EntityNoteBofhdAuth

    @classmethod
    def get_help_strings(cls):
        group_help = {
            'note': 'Entity note related commands',
        }

        command_help = {
            'note': {
                'note_show': 'Show notes associated with an entity',
                'note_add': 'Add a new note to an entity',
                'note_remove': 'Remove a note associated with an entity',
            },
        }

        # TODO: Missing id:target:entity
        arg_help = {
            'note_id':
                ['note_id', 'Enter note ID',
                 'Enter the ID of the note'],
            'note_subject':
                ['note_subject', 'Enter subject',
                 'Enter the subject of the note'],
            'note_description':
                ['note_description', 'Enter description',
                 'Enter the description of the note'],
        }

        return (group_help, command_help, arg_help)

    #
    # note show <subject-id>
    #
    all_commands['note_show'] = Command(
        ('note', 'show'),
        Id(help_ref='id:target:entity'),
        fs=FormatSuggestion([
            ("%d note(s) found for %s:\n", ("notes_total", "entity_target")),
            ("Note #%d added by %s on %s:\n"
             "%s: %s\n",
             ("note_id", "creator", format_time("create_date"),
              "subject", "description"))
        ]),
        perm_filter='can_show_notes')

    def note_show(self, operator, entity_target):
        self.ba.can_show_notes(operator.get_entity_id())

        entity = self.util.get_target(
            entity_target, default_lookup="account", restrict_to=[]
        )
        enote = Note.EntityNote(self.db)
        enote.find(entity.entity_id)

        notes = enote.get_notes()
        result = []

        if len(notes) is 0:
            return "No notes were found for %s" % (entity_target)
        else:
            result.append({
                'notes_total': len(notes),
                'entity_target': entity_target,
            })

        for note_row in notes:
            note = {}

            for key, value in note_row.items():
                note[key] = value

                if key in ('subject', 'description') and len(value) is 0:
                    note[key] = '<not set>'

            # translate creator_id to username
            acc = self._get_account(note_row['creator_id'], idtype='id')
            note['creator'] = acc.account_name
            result.append(note)

        return result

    #
    # note add <subject-id> <title> <contents>
    #
    all_commands['note_add'] = Command(
        ('note', 'add'),
        Id(help_ref='id:target:entity'),
        SimpleString(help_ref='note_subject'),
        SimpleString(help_ref='note_description'),
        perm_filter='can_add_notes')

    def note_add(self, operator, entity_target, subject, description):
        self.ba.can_add_notes(operator.get_entity_id())

        if len(subject) > 70:
            raise CerebrumError(
                u"Subject field cannot be longer than 70 characters")
        if len(description) > 1024:
            raise CerebrumError(
                u"Description field cannot be longer than 1024 characters")

        entity = self.util.get_target(entity_target, restrict_to=[])
        enote = Note.EntityNote(self.db)
        enote.find(entity.entity_id)
        note_id = enote.add_note(operator.get_entity_id(),
                                 subject,
                                 description)
        return "Note #%s was added to entity %s" % (note_id, entity_target)

    #
    # note remove <subject-id> <note-id>
    #
    all_commands['note_remove'] = Command(
        ('note', 'remove'),
        Id(help_ref='id:target:entity'),
        SimpleString(help_ref='note_id'),
        perm_filter='can_remove_notes')

    def note_remove(self, operator, entity_target, note_id):
        self.ba.can_remove_notes(operator.get_entity_id())

        entity = self.util.get_target(entity_target, restrict_to=[])
        enote = Note.EntityNote(self.db)
        enote.find(entity.entity_id)

        if not note_id.isdigit():
            raise CerebrumError("Note ID must be a numeric value")

        for note_row in enote.get_notes():
            if int(note_row['note_id']) is int(note_id):
                enote.delete_note(note_id)
                return "Note #%s associated with entity %s was removed" % (
                    note_id, entity_target)

        raise CerebrumError("Note #%s is not associated with entity %s" %
                            (note_id, entity_target))
