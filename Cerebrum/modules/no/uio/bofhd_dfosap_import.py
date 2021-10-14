# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
This module contains HR-import related utility commands for UiO.
"""
import logging

import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    PersonId,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.dfo.tasks import EmployeeTasks
from Cerebrum.modules.no.uio.bofhd_auth import UioAuth
from Cerebrum.modules.tasks.task_queue import TaskQueue, sql_search


logger = logging.getLogger(__name__)


def format_day(field):
    """ Datetime format for FormatSuggestion. """
    fmt = "yyyy-MM-dd"
    return ":".join((field, "date", fmt))


def _normalize_dfo_pid_input(value):
    """ Try to parse value as a DFO_PID. """
    # 'dfo_pid:<employee-number>', 'dfo:<emplyee-number>'
    if value.partition(':')[0].lower() in ('dfo', 'dfo_pid'):
        return int(value.partition(':')[2].strip())

    # <employee-number>
    if value.strip().isdigit():
        return int(value.strip())

    raise ValueError('Invalid DFO_PID')


def find_by_dfo_pid(db, dfo_pid):
    """ Find Person-object by DFO_PID value. """
    pe = Factory.get('Person')(db)
    co = pe.const
    try:
        pe.find_by_external_id(co.externalid_dfo_pid, dfo_pid)
        return pe
    except Errors.NotFoundError:
        raise CerebrumError('Unknown employee id: ' + repr(dfo_pid))


def get_tasks(db, dfo_pid):
    """ Get tasks associated with a given employee number. """
    # expand employee number to include incorrectly formatted values:
    # - zero prefix
    # - carriage return suffix
    # TODO: Or just normalize the keys as a one-time job?
    keys = tuple(key_fmt % (dfo_pid,) for key_fmt in ('%d', '0%d', '%d\r',
                                                      '0%d\r',))
    tasks = [dict(t) for t in sql_search(db,
                                         queues=EmployeeTasks.queue,
                                         keys=keys)]
    if not tasks:
        raise CerebrumError('No tasks in queue for employee id: '
                            + repr(dfo_pid))
    return tasks


def clear_contact_info(person, source_system):
    """
    Clear contact info from a given source system for a given person.

    :type person: Cerebrum.Person.Person
    :type source_system: Cerebrum.Constants._AutoritativeSystemCode
    """
    to_remove = tuple(
        person.const.ContactInfo(row['contact_type'])
        for row in person.get_contact_info(source=int(source_system)))

    for ctype in to_remove:
        person.delete_contact_info(source=source_system, contact_type=ctype)

    if to_remove:
        logger.info('removed contact info: person_id=%d, types=%s, source=%s',
                    person.entity_id,
                    repr([str(c) for c in to_remove]),
                    source_system)
    return to_remove


def clear_names(person, source_system):
    """
    Clear names from a given source system for a given person.

    :type person: Cerebrum.Person.Person
    :type source_system: Cerebrum.Constants._AutoritativeSystemCode
    """
    to_remove = tuple(
        person.const.PersonName(row['name_variant'])
        for row in person.get_names(source_system=int(source_system)))

    if to_remove:
        person.affect_names(source_system, *to_remove)
        person.write_db()
        logger.info('removed names: person_id=%d, names=%s, source=%s',
                    person.entity_id,
                    repr([str(c) for c in to_remove]),
                    source_system)
    return to_remove


def find_unique_external_ids(person, source_system):
    """
    Identify external id types that are *only* registered in the given
    source system.

    :type person: Cerebrum.Person.Person
    :type source_system: Cerebrum.Constants._AutoritativeSystemCode
    """
    co = person.const

    affected_types = []
    source_map = {}
    for row in person.get_external_id():
        sys = co.AuthoritativeSystem(row['source_system'])
        typ = co.EntityExternalId(row['id_type'])
        val = row['external_id']
        if sys == source_system:
            affected_types.append(typ)
        source_map.setdefault((typ, val), []).append(sys)

    duplicates = []
    for (typ, val), sources in source_map.items():
        if source_system in sources and len(sources) > 1:
            duplicates.append(typ)

    unique = tuple(typ for typ in affected_types
                   if typ not in duplicates)

    return unique


def clear_external_id(person, source_system, exclude_id_types=None):
    """
    Clear external ids from a given source system for a given person.

    :type person: Cerebrum.Person.Person
    :type source_system: Cerebrum.Constants._AutoritativeSystemCode
    :param exclude_id_types:
        An optional tuple of id types to keep.

        Each id type must be a Cerebrum.Constants._EntityExternalIdCode
    """
    co = person.const
    exclude_id_types = exclude_id_types or ()

    id_types = tuple(
        co.EntityExternalId(row['id_type'])
        for row in person.get_external_id(source_system=int(source_system)))
    to_remove = tuple(id_type for id_type in id_types
                      if id_type not in exclude_id_types)
    to_keep = tuple(id_type for id_type in id_types
                    if id_type in exclude_id_types)

    if to_remove:
        person.affect_external_id(source_system, *to_remove)
        person.write_db()
        logger.info('removed external id: person_id=%d, types=%s, source=%s',
                    person.entity_id,
                    repr([str(c) for c in to_remove]),
                    source_system)
    if to_keep:
        logger.debug('kept external id: person_id=%d, types=%s, source=%s',
                     person.entity_id,
                     repr([str(c) for c in to_keep]),
                     source_system)

    return to_remove


class BofhdHrImportAuth(UioAuth):

    def can_dfo_import(self, operator, query_run_any=False):
        has_access = self.is_schoolit(operator)
        if query_run_any or has_access:
            return has_access
        raise PermissionDenied('No access to import queue')

    def can_clear_sap_data(self, operator, query_run_any=False):
        has_access = self.is_superuser(operator)
        if query_run_any or has_access:
            return has_access
        raise PermissionDenied('No access to clear hr data')


class BofhdExtension(BofhdCommonMethods):

    all_commands = {}
    authz = BofhdHrImportAuth

    @classmethod
    def get_help_strings(cls):
        cmd_help = {'person': {}}
        arg_help = {
            'dfo_pid': [
                'dfo_pid',
                'Enter employee number',
                'Enter a valid employee number or a person identifier',
            ],
        }
        for name in cls.all_commands:
            if name in cmd_help['person']:
                continue
            # set command help to first line of docstring
            try:
                doc = getattr(cls, name).__doc__.lstrip()
            except AttributeError:
                continue
            first = doc.splitlines()[0].strip()
            cmd_help['person'][name] = first.rstrip('.')

        return ({}, cmd_help, arg_help)

    def _get_person(self, value):
        try:
            return self.util.get_target(value, restrict_to=['Person'])
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")

    def _get_dfo_pid(self, value):
        """
        Get DFO_PID from user argument.

        This helper function allow users to provide a DFO_PID value directly,
        or fetch a DFO_PID from an existing Person-object.
        """
        try:
            return _normalize_dfo_pid_input(value)
        except ValueError:
            pass

        # other identifiers, e.g. <username>, person:<username>, id:<entity-id>
        try:
            pe = self._get_person(value)
            row = pe.get_external_id(source_system=pe.const.system_dfosap,
                                     id_type=pe.const.externalid_dfo_pid)
            return int(row['external_id'])
        except Exception:
            raise CerebrumError("Invalid DFO_PID: " + repr(value))

    def _get_dfo_person(self, value):
        """
        Get Person from user argument.

        This helper function allow users to look up Person-objects in Cerebrum
        in the usual ways, and additionally by providing a valid DFO_PID.
        """
        try:
            dfo_pid = _normalize_dfo_pid_input(value)
            find_by_dfo_pid(self.db, dfo_pid)
        except ValueError:
            pass

        # other identifiers, e.g. <username>, person:<username>, id:<entity-id>
        return self._get_person(value)

    #
    # person dfo_import <employee>
    #
    all_commands['person_dfo_import'] = Command(
        ("person", "dfo_import"),
        SimpleString(help_ref='dfo_pid'),
        fs=FormatSuggestion(
            'Import qeueued for employee-id %s\n'
            'Hint: Use `person dfo_queue <pid>` to show queue',
            ('key',),
        ),
        perm_filter='can_dfo_import',
    )

    def person_dfo_import(self, operator, lookup_value):
        """ Add an employee to the hr import queue. """
        self.ba.can_dfo_import(operator.get_entity_id())

        dfo_pid = self._get_dfo_pid(lookup_value)
        task = EmployeeTasks.create_manual_task(dfo_pid)
        TaskQueue(self.db).push_task(task)
        return task.to_dict()

    #
    # person dfo_cancel <key>
    #
    all_commands['person_dfo_cancel'] = Command(
        ("person", "dfo_cancel"),
        SimpleString(help_ref='dfo_pid'),
        fs=FormatSuggestion(
            'Import cancelled for employee id %s', ('key',),
        ),
        perm_filter='can_dfo_import',
    )

    def person_dfo_cancel(self, operator, dfo_pid):
        """ Cancel a previously added import task from the hr import queue. """
        self.ba.can_dfo_import(operator.get_entity_id())

        if not dfo_pid.isdigit():
            raise CerebrumError('Invalid employee id: ' + repr(dfo_pid))

        queue = EmployeeTasks.queue
        sub = EmployeeTasks.manual_sub

        try:
            return TaskQueue(self.db).pop_task(queue, sub, dfo_pid).to_dict()
        except Errors.NotFoundError:
            raise CerebrumError('No task for emplyee id %s in %s/%s'
                                % (dfo_pid, queue, sub))
            pass

    #
    # person dfo_queue <employee>
    #
    all_commands['person_dfo_queue'] = Command(
        ("person", "dfo_queue"),
        SimpleString(help_ref='dfo_pid'),
        fs=FormatSuggestion(
            "%12s/%-12s  %8s  %8d  %10s  %10s",
            ('queue', 'sub', 'key', 'attempts',
             format_day('nbf'), format_day('iat')),
            hdr="%12s/%-12s  %8s  %8s  %10s  %10s" % (
                'Queue', 'Sub Queue', 'Key', 'Attempts',
                'Not Before', 'Issued At',
            ),
        ),
        perm_filter='can_dfo_import',
    )

    def person_dfo_queue(self, operator, lookup_value):
        """ Show tasks in the dfo import queues. """
        self.ba.can_dfo_import(operator.get_entity_id())

        dfo_pid = self._get_dfo_pid(lookup_value)
        return get_tasks(self.db, dfo_pid)

    #
    # person clear_sap_affiliations <person>
    #
    all_commands['person_clear_sap_affiliations'] = Command(
        ("person", "clear_sap_affiliations"),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion(
            'Removed %s @ ou_id=%d', ('affiliation', 'ou_id'),
        ),
        perm_filter='can_clear_sap_data',
    )

    def person_clear_sap_affiliations(self, operator, person_id):
        """
        Remove obsolete affiliations from SAP.

        This command removes affiliations from the SAP source system for the
        given *person_id*.
        """
        self.ba.can_clear_sap_data(operator.get_entity_id())

        person = self._get_person(person_id)
        source_system = self.const.system_sap

        to_remove = tuple(
            (person.const.PersonAffiliation(row['affiliation']), row['ou_id'])
            for row in person.get_affiliations()
            if row['source_system'] == int(source_system))

        if not to_remove:
            raise CerebrumError('No affiliations to remove from '
                                + six.text_type(source_system))

        for aff, ou_id in to_remove:
            person.delete_affiliation(ou_id, aff, source_system)
            logger.info('removed aff: person_id=%d aff=%s ou_id=%d, source=%s',
                        person.entity_id, aff, ou_id, source_system)

        return [{
            'person_id': int(person.entity_id),
            'source_system': six.text_type(source_system),
            'affiliation': six.text_type(aff),
            'ou_id': int(ou_id),
        } for aff, ou_id in to_remove]

    #
    # person clear_sap_data <person>
    #
    all_commands['person_clear_sap_data'] = Command(
        ("person", "clear_sap_data"),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion(
            'Removed %s type=%s', ('category', 'type'),
        ),
        perm_filter='can_clear_sap_data',
    )

    def person_clear_sap_data(self, operator, person_id):
        """
        Remove obsolete person info from SAP.

        This command removes contact info, names, and some external ids from
        the SAP source system for a given *person_id*.

        Note:
            - Old employee ids are not removed
            - FNR and PASSNR is only removed if the same info also exists in
              other sources.
        """
        self.ba.can_clear_sap_data(operator.get_entity_id())

        person = self._get_person(person_id)
        source_system = self.const.system_sap
        removed = []

        for c_type in clear_contact_info(person, source_system):
            removed.append({
                'category': 'contact_info',
                'person_id': int(person.entity_id),
                'source_system': six.text_type(source_system),
                'type': six.text_type(c_type),
            })

        for n_var in clear_names(person, source_system):
            removed.append({
                'category': 'person_name',
                'person_id': int(person.entity_id),
                'source_system': six.text_type(source_system),
                'type': six.text_type(n_var),
            })

        keep_id_types = find_unique_external_ids(person, source_system)
        for id_type in clear_external_id(
                person,
                source_system,
                exclude_id_types=keep_id_types):
            removed.append({
                'category': 'external_id',
                'person_id': int(person.entity_id),
                'source_system': six.text_type(source_system),
                'type': six.text_type(id_type),
            })

        if not removed:
            raise CerebrumError('No person info to remove from '
                                + six.text_type(source_system))
        return removed
