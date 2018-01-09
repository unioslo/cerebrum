#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015-2018 University of Oslo, Norway
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
"""Generates a JSON file with events."""

import cereconf
getattr(cereconf, 'linter', 'must be silent')

from Cerebrum.Utils import Factory

logger = Factory.get_logger('cronjob')


def _parse_selection_criteria(db, criteria):
    """Parse criterias for selection.

    I.e: the string spread:add@account,person will be converted to:
    (co.spread_add, [co.entity_account, co.entity_person])

    :param Cerebrum.database.Database db: A Database object.
    :param basestring criteria: The criteria to parse.
    :rtype: tuple(Cerebrum.Constants._ChangeTypeCode,
                  list(Cerebrum.Constants._EntityTypeCode,))
    :return: A tuple consisting of the change type, and a list of entity types
        this should be filtered on."""
    t = criteria.split('@')
    types = []
    try:
        for x in t[1].split(','):
            types.append(_parse_code(db, x))
    except IndexError:
        pass
    return (_parse_code(db, t[0]), types)


def _parse_code(db, constant):
    """Parse and error-check a constant.

    :param Cerebrum.database.Database db: A Database object.
    :param basestring constant: The string representation of the constant.
    :rtype: Cerebrum.Constant
    :return: The instantiated constant."""
    from Cerebrum import Errors

    class UndefinedConstantException(Exception):
        pass

    co = Factory.get('Constants')(db)
    try:
        if isinstance(constant, basestring):
            ct = co.human2constant(constant)
        else:
            ct = co.ChangeType(constant)
        int(ct)
    except (Errors.NotFoundError, TypeError):
        raise UndefinedConstantException('The constant %s is not defined',
                                         constant)
    return ct


def convert_events(db, events):
    """Convert an event to a dict.

    :param Cerebrum.database.Database db: A database object.
    :param list events: A list of event rows.
    :rtype: list
    :return: A list of converted events."""
    def _unpickle(msg):
        import pickle
        try:
            cp = pickle.loads(msg.get('change_params'))
        except (TypeError, EOFError):
            cp = None
        msg['change_params'] = cp
        return msg

    def _get_entity_type(db, entity_id):
        from Cerebrum import Errors
        entity = Factory.get("Entity")(db)
        constants = Factory.get("Constants")(db)
        try:
            ent = entity.get_subclassed_object(id=entity_id)
            return constants.EntityType(ent.entity_type)
        except Errors.NotFoundError:
            return None

    def _convert(msg):
        msg = _unpickle(dict(msg))
        ct = _parse_code(db, msg.get('change_type_id'))

        # TODO: Restructure something, this is prone to break
        from Cerebrum.modules.event_publisher import change_type_to_message
        return change_type_to_message(
            db,
            ct,
            msg.get('subject_entity'),
            msg.get('dest_entity'),
            msg.get('change_params'))

    return [_convert(event) for event in events]


def get_events(db, cl, criterias, key):
    """Get a list of events satisfying a criteria.

    :param Cerebrum.database.Database db: A database object.
    :param Cerebrum.modules.CLHandler cl: A CLHandler object.
    :param dict criterias: The criteria to list changes by.
    :param basestring key: The key to acknowledge changes with.
    :rtype: list
    :return: A list of change rows."""
    def _c(x):
        cl.confirm_event(x)
        return x

    def _filter(event, et):
        if not et:
            return True
        from Cerebrum import Errors
        en = Factory.get('Entity')(db)
        try:
            en.find(event['subject_entity'])
            subject_type = en.entity_type
        except Errors.NotFoundError:
            subject_type = None
        try:
            en.clear()
            en.find(event['dest_entity'])
            dest_type = en.entity_type
        except Errors.NotFoundError:
            dest_type = None

        if subject_type in et or dest_type in et:
            return True
        else:
            return False

    r = []
    for (ct, et) in [_parse_selection_criteria(db, x) for x in criterias]:
        for event in cl.get_events(key, ct):
            if _filter(event, et):
                r.append(_c(event))
    return r


def dump_json(filename, events):
    """Dump a list of events to JSON-file.

    Objects of type mx.DateTime.DateTimeType are serialized by calling str().

    :param list(<Cerebrum.extlib.db_row.row>) events: List of events.
    :param basestring filename: File to write to. Prints to stdout if None."""
    import json

    class Encoder(json.JSONEncoder):
        def default(self, obj):
            from mx.DateTime import DateTimeType

            if isinstance(obj, DateTimeType):
                return str(obj)
            return json.JSONEncoder.default(self, obj)

    if filename:
        with open(filename, 'w') as f:
            json.dump(events, f, cls=Encoder, indent=4, sort_keys=True)
    else:
        print(json.dumps(events, cls=Encoder, indent=4, sort_keys=True))


def main(args=None):
    """Main script runtime.

    This parses arguments, handles the database transaction and performes the
    export.

    :param list args: List of arguments used to configure
    """
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('--file',
                        dest='filename',
                        metavar='filename',
                        help='Write export data to <filename>')
    parser.add_argument('--criteria',
                        nargs='*',
                        metavar='criteria',
                        help='Criteria for collection of events. I.e. '
                             'spread:add@account,person. This will collect '
                             'all spread:add events performed on accounts and '
                             'persons. The entity-type part of the criteria '
                             'can be ommited.')
    parser.add_argument('--change-key',
                        dest='change_key',
                        metavar='change-key',
                        default=parser.prog.split('.')[0],
                        help='Change key to mark exported events with: '
                             'Default: program name.')
    parser.add_argument('--commit',
                        dest='commit',
                        action='store_true',
                        default=False,
                        help='Run in commit mode. Exported changes are '
                             'confirmed.')

    args = parser.parse_args(args)

    logger.info("START with args: %s" % str(args.__dict__))

    db = Factory.get('Database')()
    from Cerebrum.modules.CLHandler import CLHandler
    cl = CLHandler(db)

    dump_json(args.filename,
              convert_events(
                  db,
                  get_events(db, cl, args.criteria, args.change_key)))

    if args.commit:
        cl.commit_confirmations()

    logger.info("DONE")


if __name__ == '__main__':
    main()
