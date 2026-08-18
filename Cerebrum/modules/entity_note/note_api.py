# -*- coding: utf-8 -*-
#
# Copyright 2024-2026 University of Oslo, Norway
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
"""
API for managing notes on entities.

This module provides a ``flask_restx.Namespace`` with endpoints and data models
for dealing with notes.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging

from flask_restx import Namespace
from flask_restx import Resource
from flask_restx import abort

from Cerebrum.rest.api import auth
from Cerebrum.rest.api import db
from Cerebrum.rest.api import fields
from Cerebrum.rest.api import utils
from Cerebrum.utils import date as date_utils
from Cerebrum.utils import textnorm
from Cerebrum.utils import date_compat

from . import note_db
from . import note_mixins


api = Namespace(
    "notes",
    description="Entity notes",
)
""" API namespace for notes. """

logger = logging.getLogger(__name__)


#
# Note models and model helpers.
#

NoteRef = api.model("EntityNoteRef", {
    'id': fields.base.Integer(
        description="Unique note id",
        example=1234,
    ),
    'href': fields.href(
        ".entity-note",
        example="/path/to/notes/1234",
    ),
    "subject": fields.base.String(
        min_length=1,
        max_length=70,
        description="Note subject line (max 70 chars)",
        example="Description/Usage",
    ),
    'created_at': fields.DateTimeTz(
        dt_format='iso8601',
        description="Note create datetime",
        example="2026-07-02T12:26:03+02:00",
    ),
})
"""
API model for referencing a note.

Metadata and reference to a given note.
"""


def _row_to_ref(row):
    """
    Translate entity_note into NoteRef data.

    :param row: a dict-like entity_note row.
    :returns dict: A dict with data for NoteRef
    """
    return {
        'id': int(row['note_id']),
        'created_at': date_compat.get_datetime_tz(row['create_date']),
        'subject': row['subject'],
    }


NoteFilters = api.model("NoteFilters", {
    'creator_id': fields.base.Integer(example=108),
    'entity_id': fields.base.Integer(example=108),
    'before': fields.DateTimeTz(
        dt_format='iso8601',
        description="Note create datetime",
        example="2026-07-02T12:26:03+02:00",
    ),
    'after': fields.DateTimeTz(
        dt_format='iso8601',
        description="Note create datetime",
        example="2026-07-02T12:26:03+02:00",
    ),
    "subject": fields.base.String(example="subj*"),
    'body': fields.base.String(example="*body*"),
})
""" API model for note search filters. """


# A list of search results
NoteRefList = api.model("EntityNoteRefList", {
    'filters': fields.base.Nested(
        NoteFilters,
        description="Filters used for this list",
    ),
    'items': fields.base.List(
        fields.base.Nested(NoteRef),
        description="Matching item references",
    )
})
"""
API model for note search results.

Includes a list of matching :data:`.NoteRef`, and the :data:`.NoteFilters` used
to generate the list.
"""


NoteEntityRef = api.model("EntityNoteEntityRef", {
    'id': fields.base.Integer(
        description="Entity Id",
        example=108,
    ),
    'type': fields.base.String(
        description="Entity type",
        example="account",
    ),
    'name': fields.base.String(
        description="Entity name (if available)",
        example="foo-system",
    ),
    'href': fields.base.String(
        description="Url to entity (if available)",
        example="/v1/accounts/foo-system",
    ),
})
"""
API model for referencing an entity.

Used to represent the :data:`Note` entity and creator attributes.
"""


def _entity_to_ref(entity):
    """
    Translate cerebrum entity into NoteEntityRef data.

    :param entity: a populated Entity object.
    :returns dict: A dict with data for NoteEntityRef.
    """
    entity_id = int(entity.entity_id)
    entity_name = utils.get_entity_name(entity)
    entity_type = db.const.get_constant(db.const.EntityType,
                                        entity.entity_type)
    entity_href = utils.href_from_entity_type(entity_type, entity_id,
                                              entity_name)
    return {
        'id': entity_id,
        'type': entity_type,
        'name': entity_name,
        'href': entity_href,
    }


# Full note - NoteRef + NoteEntityRef + body
Note = api.inherit("EntityNote", NoteRef, {
    "body": fields.base.String(
        description="Note body",
        example="\n".join((
            "System account for system Foo.",
            "Only used for file + file group ownership",
            "No interactive use.",
        ))
    ),
    "creator": fields.base.Nested(NoteEntityRef),
    "entity": fields.base.Nested(NoteEntityRef),
})
"""
API model for a note.

Includes metadata (:data:`.NoteRef`), entity references
(:data:`.NoteEntityRef`) and the note body.
"""


def _row_to_note(row):
    """
    Translate entity_note into Note data.

    :param row: a dict-like entity_note row.
    :returns dict: A dict with data for NoteEntityRef.
    """
    data = _row_to_ref(row)
    entity = _entity_to_ref(utils.get_entity(row['entity_id']))
    creator = _entity_to_ref(utils.get_entity(row['creator_id']))
    data.update({
        'body': row['description'],
        'creator': creator,
        'entity': entity,
    })
    return data


#
# Validators and helpers
#


def _has_note_support(entity):
    """ Check if a given entity can have notes attached to it. """
    return isinstance(entity, note_mixins.EntityNoteMixin)


def _parse_date(raw_value):
    """ Parse date/datetime for use in before/after filters. """
    parsers = (
        lambda v: date_utils.parse_datetime(v),
        lambda v: date_utils.parse_date(v),
        lambda v: datetime.datetime.combine(
            datetime.datetime.today(),
            date_utils.parse_time(v)),
    )

    for parse_value in parsers:
        try:
            return parse_value(raw_value)
        except ValueError:
            pass
    raise ValueError("Invalid date/datetime: " + repr(raw_value))


def _parse_creator_id(raw_value):
    """ Validate that a given entity_id exists. """
    lookup_id = int(raw_value)
    try:
        entity = utils.get_entity(lookup_id)
    except utils.EntityLookupError:
        raise ValueError("Entity not found")
    return int(entity.entity_id)


def _parse_entity_id(raw_value):
    """ Validate that a given entity_id exists and has note support. """
    lookup_id = int(raw_value)
    try:
        entity = utils.get_entity(lookup_id)
    except utils.EntityLookupError:
        raise ValueError("Entity not found")
    if not _has_note_support(entity):
        raise ValueError("No note support for entity")
    return int(entity.entity_id)


def _parse_new_subject(raw_value):
    """ Normalize and validate *subject* for new notes. """
    value = textnorm.normalize_text(raw_value.strip())
    if "\n" in value:
        # TODO: Check for other non-printable chars?
        raise ValueError("no newlines")
    if len(value) > 70:
        raise ValueError("too long (max 70 chars)")
    if len(value) < 1:
        raise ValueError("too short (min 1 char)")
    return value


def _parse_new_body(raw_value):
    """ Normalize and validate *body* for new notes. """
    value = textnorm.normalize_text(raw_value)
    if not value.strip():
        return None
    return value


#
# /notes/
#
# List/search for notes, or create new notes.
#


@api.route("/", endpoint="entity-note-list")
class EntityNotes(Resource):
    """
    Endpoint for all entity notes.
    """

    note_search_parser = api.parser()
    note_search_parser.add_argument(
        "entity_id",
        type=_parse_entity_id,
        required=False,
        help="Only include notes for this entity id."
    )
    note_search_parser.add_argument(
        "creator_id",
        type=_parse_creator_id,
        required=False,
        help="Only include notes created by this account id.",
    )
    note_search_parser.add_argument(
        "after",
        type=_parse_date,
        required=False,
        help=(
            "Only include notes created after this date"
            " (ISO-8601 datetime, date, or time)."
        ),
    )
    note_search_parser.add_argument(
        "before",
        type=_parse_date,
        required=False,
        help=(
            "Only include notes created before this date"
            " (ISO-8601 datetime, date, or time)."
        ),
    )
    note_search_parser.add_argument(
        "subject",
        type=str,
        required=False,
        help=(
            "Only include notes with this subject"
            " (supports case-insensitive glob-like patterns)."
        ),
    )
    note_search_parser.add_argument(
        "body",
        type=str,
        required=False,
        help=(
            "Only include notes with this content"
            " (supports case-insensitive glob-like patterns)."
        ),
    )

    @auth.require()
    @api.expect(note_search_parser)
    @api.marshal_with(NoteRefList, code=200)
    @api.response(400, "Invalid search parameter(s)")
    def get(self):
        """
        Get list of entity notes.

        The list may be filtered using optional query parameters.

        :rtype: tuple[dict, int]
        :returns:
            Returns a results dict, and a HTTP status code.
        """
        args = self.note_search_parser.parse_args()

        search_params = {
            param: args[inarg] for inarg, param in (
                ('entity_id', 'entity_id'),
                ('creator_id', 'creator_id'),
                ('before', 'created_before'),
                ('after', 'created_after'),
                ('subject', 'subject_ilike'),
                ('body', 'description_ilike'),
            )
            if args[inarg] is not None
        }

        filters = dict(args)
        results = [
            _row_to_ref(row)
            for row in note_db.sql_search_notes(db.connection, **search_params)
        ]
        results.sort(key=lambda r: r['id'])
        return {
            'filters': filters,
            'items': results,
        }

    new_note_parser = api.parser()
    new_note_parser.add_argument(
        "entity_id",
        location=("form", "json"),
        required=True,
        type=_parse_entity_id,
        help="Note for entity_id.",
    )
    new_note_parser.add_argument(
        "subject",
        location=("form", "json"),
        required=True,
        type=_parse_new_subject,
        help="Note subject.",
    )
    new_note_parser.add_argument(
        "body",
        location=("form", "json"),
        required=False,
        type=_parse_new_body,
        help="Note body.",
    )

    @auth.require()
    @api.expect(new_note_parser)
    @api.marshal_with(Note, code=201, description="Note created")
    @api.response(400, "Invalid note parameter(s)")
    @db.autocommit
    def post(self):
        """
        Create a new note.

        :rtype: tuple[dict, int]
        :returns:
            Returns the newly created note, and a HTTP status code.
        """
        args = self.new_note_parser.parse_args()

        row = note_db.sql_add_note(
            db=db.connection,
            entity_id=int(args['entity_id']),
            creator_id=int(auth.account.entity_id),
            subject=args['subject'],
            description=args['body'],
        )
        return _row_to_note(row), 201


#
# /notes/<id>
#
# Look up a specific note (detailed), or delete a specific note.
#


def _get_one(rows):
    # Check and return a single row from queries that should only return
    # exactly one note row.
    rows = list(rows)
    if len(rows) > 1:
        raise RuntimeError("Found more than one note by id")
    if len(rows) < 1:
        abort(404, "Note not found")
    return rows[0]


@api.route("/<int:id>", endpoint="entity-note")
class EntityNote(Resource):
    """
    Endpoint for a given entity note.
    """

    @auth.require()
    @api.marshal_with(Note, code=200, description="Note found")
    @api.response(404, "Note not found")
    def get(self, id):
        """
        Get a note by note id.

        :param int id: The note id to look up

        :rtype: dict
        :returns:
            Returns the note with the given note id.
        """
        note_row = _get_one(note_db.sql_search_notes(db.connection,
                                                     note_id=int(id)))
        return _row_to_note(note_row)

    @auth.require()
    @api.response(204, "Note deleted")
    @api.response(404, "Note not found")
    @db.autocommit
    def delete(self, id):
        """
        Delete a note by note id.

        :param int id: The note id to delete

        :rtype: tuple[NoneType, int]
        :returns:
            An empty result and a HTTP status code.
        """
        _get_one(note_db.sql_delete_notes(db.connection, note_id=int(id)))
        return None, 204
