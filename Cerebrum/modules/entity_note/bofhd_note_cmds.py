# -*- coding: utf-8 -*-
#
# Copyright 2013-2026, University of Oslo, Norway
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
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import textwrap

import six

from Cerebrum.modules.bofhd import parsers
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.bofhd_utils import format_time
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    Id,
    SimpleString,
    get_format_suggestion_table,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.Utils import Factory
from Cerebrum.utils import date_compat
from Cerebrum.utils import text_utils

from . import note_db


class EntityNoteBofhdAuth(BofhdAuth):

    def can_add_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_entity_note_add):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_remove_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_entity_note_remove):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_show_notes(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        if self._has_operation_perm_somewhere(
                operator,
                self.const.auth_entity_note_show):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Permission denied")

    def can_search_notes(self, operator, filters=None, query_run_any=False):
        return self.can_show_notes(operator, query_run_any=query_run_any)


class BofhdNoteCommands(BofhdCommonMethods):
    """ Extends bofhd with a 'note' command group. """

    all_commands = {}
    parent_commands = False
    authz = EntityNoteBofhdAuth

    @classmethod
    def get_help_strings(cls):
        return merge_help_strings(
            get_help_strings(),
            (_help_grp, _help_cmd, _help_arg),
        )

    #
    # note show <entity>
    #
    all_commands['note_show'] = Command(
        ('note', 'show'),
        Id(help_ref='id:target:entity'),
        fs=FormatSuggestion([
            # stats
            ("%d note(s) found for entity id=%d:\n",
             ("notes_total", "entity_id")),
            # notes
            ("Note #%d added by %s on %s:\n"
             "%s: %s\n",
             ("note_id", "creator", format_time("create_date"),
              "subject", "description"))
        ]),
        perm_filter='can_show_notes',
    )

    def note_show(self, operator, _entity):
        entity = self.util.get_target(_entity, default_lookup="account",
                                      restrict_to=[])

        self.ba.can_show_notes(operator.get_entity_id())

        notes = list(note_db.sql_search_notes(self.db,
                                              entity_id=int(entity.entity_id)))
        if not notes:
            raise CerebrumError("No notes for entity id=%d"
                                % (entity.entity_id,))

        result = []

        # add stats
        result.append({
            'notes_total': len(notes),
            'entity_id': int(entity.entity_id),
        })

        # add notes
        for note_row in notes:
            note = dict(note_row)
            for k in ('subject', 'description'):
                note[k] = note[k] or '<not set>'

            # translate creator_id to username
            acc = _get_account_by_id(self.db, note['creator_id'])
            note['creator'] = acc.account_name
            result.append(note)

        return result

    #
    # note add <entity> <subject> <body>
    #
    all_commands['note_add'] = Command(
        ('note', 'add'),
        Id(help_ref='id:target:entity'),
        SimpleString(help_ref='note-subject'),
        SimpleString(help_ref='note-body'),
        fs=FormatSuggestion(
            "Note #%s was added to entity id=%d",
            ('note_id', 'entity_id'),
        ),
        perm_filter='can_add_notes',
    )

    def note_add(self, operator, _entity, subject, body):
        entity = self.util.get_target(_entity, restrict_to=[])
        if len(subject) > 70:
            raise CerebrumError(
                "Subject field cannot be longer than 70 characters")
        if len(body) > 1024:
            raise CerebrumError(
                "Description field cannot be longer than 1024 characters")

        self.ba.can_add_notes(operator.get_entity_id())
        # TODO: Check for entity_note mixin support in entity before adding?

        row = note_db.sql_add_note(
            self.db,
            entity_id=int(entity.entity_id),
            creator_id=int(operator.get_entity_id()),
            subject=subject,
            description=body,
        )
        return _row_to_note(row)

    #
    # note remove <entity> <note-id>
    #
    all_commands['note_remove'] = Command(
        ('note', 'remove'),
        Id(help_ref='id:target:entity'),
        SimpleString(help_ref='note-id'),
        fs=FormatSuggestion(
            "Note #%d associated with entity id=%d was removed",
            ('note_id', 'entity_id'),
        ),
        perm_filter='can_remove_notes',
    )

    def note_remove(self, operator, _entity, _note_id):
        entity = self.util.get_target(_entity, restrict_to=[])
        note_id = parse_note_id(_note_id)

        self.ba.can_remove_notes(operator.get_entity_id())

        params = {'entity_id': int(entity.entity_id), 'note_id': note_id}
        results = note_db.sql_delete_notes(self.db, **params)
        return _row_to_note(_get_one_note(results, **params))

    def _search_notes(self, filter_d, limit=100):
        """
        Search for notes.

        :param dict filter_d: task search params (see note_db.sql_search_notes)
        :param int limit: max number of tasks to get
        :returns generator:
            Generates matching note dicts.

            If there are more than <limit> matching tasks, the list of
            results will be truncated, and a final sentinel item
            `{'limit': <limit>}` will be included.
        """
        filter_d = dict(filter_d)
        filter_d['limit'] = limit + 1
        for i, row in enumerate(note_db.sql_search_notes(self.db, **filter_d)):
            if i < limit:
                yield _row_to_note(row)
            else:
                # if there are more than `limit` results, we add a
                # sentinel value to indicate that not all matches were
                # included.
                yield {'limit': limit}
                break

    # Table presentation of _search_notes/_row_to_note results.
    _search_note_list_fs = get_format_suggestion_table(
        ("note_id", "Note Id", 7, "d", False),
        ("entity_id", "Entity Id", 9, "d", False),
        ("creator_id", "Creator Id", 10, "d", False),
        (format_time("date"), "Date", 16, "s", False),
        ("subject_short", "Subject", 30, "s", True),
        limit_key='limit',
    )

    #
    # note search [filter...]
    #
    all_commands['note_search'] = Command(
        ("note", "search"),
        SimpleString(help_ref='note-filter', optional=True, repeat=True),
        fs=_search_note_list_fs,
        perm_filter="can_search_notes",
    )

    def note_search(self, operator, *search_filters):
        """ Search for notes. """
        # parse args
        raw_filters = _note_filter_parser.parse_items(search_filters)
        filters = _note_filter_parser.map_params(self.db, self.const,
                                                 raw_filters)

        # check authz
        self.ba.can_search_notes(operator.get_entity_id(), filters)

        # search for notes
        results = list(self._search_notes(filters))
        if results:
            return results
        raise CerebrumError("No matching notes (filters: %s)"
                            % (", ".join(filters.keys()),))

    #
    # note list <entity-id> [filter...]
    #
    all_commands['note_list'] = Command(
        ("note", "list"),
        Id(help_ref='id:target:entity'),
        SimpleString(help_ref='note-filter', optional=True, repeat=True),
        fs=_search_note_list_fs,
        perm_filter="can_show_notes",
    )

    def note_list(self, operator, _entity, *search_filters):
        """ List notes for a given entity, with optional filters. """
        # parse args
        entity = self.util.get_target(_entity, restrict_to=[])
        raw_filters = _note_filter_parser.parse_items(search_filters)
        filters = _note_filter_parser.map_params(self.db, self.const,
                                                 raw_filters)
        filters.update({'entity_id': int(entity.entity_id)})

        # check authz
        self.ba.can_show_notes(operator.get_entity_id())

        # search for notes
        results = list(self._search_notes(filters))
        if results:
            return results
        raise CerebrumError("No matching notes for entity id=%d (filters: %s)"
                            % (entity.entity_id, ", ".join(filters.keys()),))

    #
    # note details <note-id>
    #
    # Get note details - shows a single note in an email-like manne
    #
    all_commands['note_details'] = Command(
        ("note", "details"),
        SimpleString(help_ref='note-id'),
        fs=FormatSuggestion(
            textwrap.dedent(
                """
                Note Id:      %d
                Creator:      %s (%d)
                Entity Id:    %d
                Entity Type:  %s
                Date:         %s
                Subject:      %s

                %s
                """
            ).strip(),
            (
                "note_id",
                "creator_name", "creator_id",
                "entity_id",
                "entity_type",
                format_time("date"),
                "subject",
                "body",
            )
        ),
        perm_filter="can_show_notes",
    )

    def note_details(self, operator, _note_id):
        """ Show a given note + note metadata. """
        # parse args
        note_id = parse_note_id(_note_id)

        # check authz
        self.ba.can_show_notes(operator.get_entity_id())

        # find and format note
        params = {'note_id': note_id}
        rows = note_db.sql_search_notes(self.db, **params)
        result = _row_to_note(_get_one_note(rows, **params))

        creator = _get_account_by_id(self.db, result['creator_id'])
        entity = _get_entity_by_id(self.db, result['entity_id'])
        result.update({
            'creator_name': creator.account_name,
            'entity_type': six.text_type(
                self.const.EntityType(entity.entity_type)
            ),
        })
        return result


#
# Simple helpers
#


def parse_note_id(value):
    error = CerebrumError("Invalid note id: " + repr(value))
    try:
        note_id = int(value)
    except (TypeError, ValueError):
        raise error
    if note_id < 0:
        raise error
    return note_id


def _get_account_by_id(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(int(account_id))
    return ac


def _get_entity_by_id(db, entity_id):
    en = Factory.get("Entity")(db)
    en.find(int(entity_id))
    return en


def _row_to_note(row):
    """ format a note object for command reposnses. """
    return {
        'note_id': row['note_id'],
        'entity_id': row['entity_id'],
        'creator_id': row['creator_id'],
        'date': date_compat.get_datetime_tz(row['create_date']),
        'subject': row['subject'],
        'subject_short': text_utils.truncate(row['subject'], 30, "..."),
        'body': row['description'],
    }


def _get_one_note(rows, **keys):
    """ helper to extract a single result by *note_id*. """
    rows = list(rows)
    if len(rows) > 1:
        raise RuntimeError("Got more than one row!")
    if len(rows) < 1:
        if keys:
            message = (
                "No note with "
                + ", ".join(("%s=%r" % (k, v) for k, v in keys.items()))
            )
        else:
            message = "No matching note"
        raise CerebrumError(message)
    return rows[0]


#
# Search helpers
#


class NoteSearchParams(parsers.ParamsParser):
    """
    Parse entity note search params from user input.

    This class can convert a sequence of strings like
    `("subject:foo*", "before:2022-01-21")`
    into a dict of search params for the entity_note bofhd commands.

    Typical use:
    ::

        parser = NoteSearchParams()
        user_input = ["subject:*foo*", "before:now", ...]
        raw_filters = parser.parse_items(user_input)
        search_args = parser.map_params(db, const, raw_filters)
        results = note_db.sql_search_notes(db, **search_args)
    """

    fields = {
        'before': "Limit to notes created before <datetime>",
        'after': "Limit to notes created after <datetime>",
        'subject': "Limit to notes with a subject matching <ipattern>",
        'body': "Limit to notes with a body matching <ipattern>",
        # 'entity': "Limit to notes for a a given <entity>",
        # 'creator': "Limit to notes created by <entity>",
    }
    params = {
        'before': 'created_before',
        'after': 'created_after',
        'subject': 'subject_ilike',
        'body': 'description_ilike',
    }

    parsers = {
        'before': parsers.parse_datetime,
        'after': parsers.parse_datetime,
        'subject': parsers.parse_ipattern,
        'body': parsers.parse_ipattern,
    }

    multivalued = frozenset(())

    @classmethod
    def translate_entity(cls, db, lookup):
        # TODO: Implement some common utils for this
        # key, _, value = lookup.partition(":")
        raise NotImplementedError("entity lookup not supported yet")

    @classmethod
    def map_params(cls, db, const, params):
        params = dict(params)

        # Translate entity - not yet implemented
        entity_lookup = params.pop('entity_lookup', None)
        if entity_lookup:
            params['entity_id'] = [cls.translate_entity(db, v)
                                   for v in entity_lookup]

        target_lookup = params.pop('target_lookup', None)
        if target_lookup:
            params['creator_id'] = [cls.translate_entity(db, v)
                                    for v in target_lookup]

        return params


_note_filter_parser = NoteSearchParams()


#
# Help texts
#


_help_grp = {
    'note': "Entity note related commands",
}
_help_cmd = {
    'note': {
        'note_show': "Show all notes attached to an entity",
        'note_add': "Add a new note to an entity",
        'note_remove': "Remove a note from an entity",
        'note_search': "List or search for notes",
        'note_list': "List notes attached to a given entity",
        'note_details': "Show a note + note metadata",

    },
}
_help_arg = {
    'note-id': [
        "note-id",
        "Enter note ID",
        "The ID of a given note",
    ],
    'note-subject': [
        "note-subject",
        "Enter note subject",
        "The note title or subject line.  Limited to 70 characters.",
    ],
    'note-body': [
        "note-body",
        "Enter note",
        "The note body or contents.  Limited to 1024 characters.",
    ],
    'note-filter': [
        "note-filter",
        "Enter filter",
        textwrap.dedent(
            """
            Each note-filter follows a format of <param>:<value>.

            Example:  Find all notes created before a given date,
            with a given subject line pattern.

                `note search before:2025-01-01 "subject:*foo bar*"`

            Valid filter <param> values
            ----------------------------
            {filters}


            Valid <datetime> values
            -----------------------
            {datetime}


            Matching with <ipattern>
            ------------------------
            {ipattern}


            """
        ).format(
            filters="\n".join(
                " - {}: {}".format(f, h)
                for f, h in _note_filter_parser.get_help()
            ),
            # TODO: Add entity lookup blurb when implemented
            datetime=parsers.parse_datetime_help_blurb.strip(),
            ipattern=parsers.parse_ipattern_help_blurb.strip(),
        )
    ],
}
