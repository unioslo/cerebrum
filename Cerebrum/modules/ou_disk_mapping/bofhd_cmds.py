# -*- coding: utf-8 -*-
#
# Copyright 2019-2023 University of Oslo, Norway
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
This module contains *ou_disk_mapping* related commands for bofhd.

.. important::
   These classes should not be used directly.  Always make subclasses of
   BofhdCommandBase classes, and add a proper auth class/mixin to the class
   authz.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
import textwrap

import six

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory, NotSet
from Cerebrum.modules.bofhd import parsers
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    SimpleString,
    YesNo,
    get_format_suggestion_table,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.org import perspective_db

from .dbal import OUDiskMapping
from .utils import resolve_disk

logger = logging.getLogger(__name__)


def _text_or_none(value):
    if value is None:
        return None
    return six.text_type(value)


class BofhdOUDiskMappingAuth(BofhdAuth):
    """Auth for ou_disk_mapping commands."""

    def _can_inspect_ou_disk_mapping(self, operator, query_run_any=False):
        """ Check if the operator can inspect ou disk mapping rules. """
        return True

    def _can_modify_ou_disk_mapping(self, operator, ou=None,
                                    query_run_any=False):
        """ Check if the operator can modify disk mapping for a given ou. """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Not allowed to modify ou disk mapping rules")

    def can_show_ou_disk_mapping(self, operator, query_run_any=False):
        """ Check if the operator can inspect disk mappings for a given ou. """
        return self._can_inspect_ou_disk_mapping(
            operator=operator,
            query_run_any=query_run_any,
        )

    def can_search_ou_disk_mapping(self, operator, query_run_any=False):
        """ Check if the operator can search for ou disk mappings. """
        return self._can_inspect_ou_disk_mapping(
            operator=operator,
            query_run_any=query_run_any,
        )

    def can_resolve_ou_disk_mapping(self, operator, query_run_any=False):
        """ Check if the operator can resolve ou disk mappings. """
        return self._can_inspect_ou_disk_mapping(
            operator=operator,
            query_run_any=query_run_any,
        )

    def can_set_ou_disk_mapping(self, operator, ou=None, query_run_any=False):
        """ Check if the operator can set disk mapping for a given ou. """
        return self._can_modify_ou_disk_mapping(
            operator=operator,
            ou=ou,
            query_run_any=query_run_any,
        )

    def can_clear_ou_disk_mapping(self, operator, ou=None,
                                  query_run_any=False):
        """ Check if the operator can clear disk mapping for a given ou. """
        return self._can_modify_ou_disk_mapping(
            operator=operator,
            ou=ou,
            query_run_any=query_run_any,
        )


def get_disk_by_id(db, value):
    disk = Factory.get("Disk")(db)
    disk.find(int(value))
    return disk


def get_disk_by_path(db, value):
    disk = Factory.get("Disk")(db)
    disk.find_by_path(six.text_type(value))
    return disk


def get_ou_by_id(db, value):
    ou = Factory.get("OU")(db)
    ou.find(int(value))
    return ou


def _get_location_code(ou):
    if hasattr(ou, 'get_stedkode'):
        return ou.get_stedkode()
    return None


def _prepare_ou_result(ou, prefix='ou'):
    ou_id = int(ou.entity_id)
    loc = _get_location_code(ou)
    hint = loc if loc else "<id:%d>" % (ou_id,)
    return {
        prefix + '_id': ou_id,
        prefix + '_loc': loc,
        prefix + '_repr': hint,
    }


class BofhdOUDiskMappingCommands(BofhdCommandBase):
    """OU Disk Mapping commands."""

    all_commands = {}
    authz = BofhdOUDiskMappingAuth

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            (HELP_GROUP, HELP_CMD, HELP_ARGS),
            get_help_strings(),
        )

    def _find_ou(self, value):
        """
        Lookup org unit.

        This should match the hints given by the help_arg ou-mapping-ou.
        """
        # Try to find the OU the user wants to edit
        ou = self.OU_class(self.db)
        if value.startswith("id:"):
            # Assume we got the entity id of the ou
            try:
                ou.find(int(value[3:]))
            except (ValueError, Errors.NotFoundError):
                raise CerebrumError("Unknown OU id: " + repr(value))
        elif len(value) == 6:
            # Assume we got a stedkode
            try:
                ou.find_sko(value)
            except Errors.NotFoundError:
                raise CerebrumError("Unknown OU location: " + repr(value))
        else:
            raise CerebrumError("Invalid OU value: " + repr(value))
        return ou

    def _find_disk(self, value):
        """
        Lookup disk.

        This should match the hints given by the help_arg ou-mapping-disk.
        """
        # Try to find the disk the users want to set
        try:
            if value.startswith("id:"):
                return get_disk_by_id(self.db, value[3:])
            else:
                # Assume the user wrote a path
                return get_disk_by_path(self.db, value)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown disk: " + repr(value))
        except Exception:
            raise CerebrumError("Invalid disk value: " + repr(value))

    #
    # ou homedir_add <ou> <disk> [aff]
    #
    all_commands["ou_homedir_add"] = Command(
        ("ou", "homedir_add"),
        SimpleString(help_ref="ou-mapping-ou"),
        SimpleString(help_ref="ou-mapping-disk"),
        SimpleString(help_ref="ou-mapping-aff", optional=True),
        fs=FormatSuggestion(
            "Set homedir to %s for affiliation %s@%s",
            ("disk_path", "affiliation_repr", "ou_repr"),
        ),
        perm_filter="can_set_ou_disk_mapping",
    )

    def ou_homedir_add(self, operator, ou_value, disk_value, aff_value=None):
        """
        Add default homedir rule for an org unit.

        :param operator:
        :param ou_value: the org unit to apply this homedir rule to
        :param disk_value: a default disk to use (e.g. /home/)
        :param aff_value: limit rule to a given affiliation or status

        :returns dict:
            client output
        """
        ou = self._find_ou(ou_value)
        self.ba.can_set_ou_disk_mapping(operator.get_entity_id(), ou)

        disk = self._find_disk(disk_value)

        # Look up affiliation
        if aff_value:
            try:
                aff, status = self.const.get_affiliation(aff_value)
            except Errors.NotFoundError:
                raise CerebrumError("Unknown affiliation: " + repr(aff_value))
            aff_str = six.text_type(status if status else aff)
        else:
            aff = status = aff_str = None

        # Set the path and return some information to the user
        ou_rules = OUDiskMapping(self.db)
        ou_rules.add(ou.entity_id, aff, status, disk.entity_id)

        result = _prepare_ou_result(ou)
        result.update({
            "affiliation": aff_str,
            "affiliation_repr": aff_str or "*",
            "disk_id": disk.entity_id,
            "disk_path": disk.path,
        })
        return result

    #
    # ou homedir_remove <ou> [aff]
    #
    all_commands["ou_homedir_remove"] = Command(
        ("ou", "homedir_remove"),
        SimpleString(help_ref="ou-mapping-ou"),
        SimpleString(help_ref="ou-mapping-aff", optional=True),
        fs=FormatSuggestion(
            "Removed homedir for affiliation %s@%s",
            ("affiliation_repr", "ou_repr"),
        ),
        perm_filter="can_clear_ou_disk_mapping",
    )

    def ou_homedir_remove(self, operator, ou_value, aff_value=None):
        """
        Remove default homedir rule for an org unit.

        If you want to remove the homedir for just the OU and any aff and
        status, use:

            ou homedir_remove ou

        For OU with affiliation and wildcard status use:

            ou homedir_remove ou aff

        For OU with affiliation and status use:

            ou homedir_remove ou aff/status

        :param operator:
        :param ou: the org unit to remove homedir rule(s) from
        :param aff_value: remove rule for a given to affiliation

        :returns dict:
            client output
        """

        ou = self._find_ou(ou_value)
        self.ba.can_clear_ou_disk_mapping(operator.get_entity_id(), ou)

        if aff_value:
            try:
                aff, status = self.const.get_affiliation(aff_value)
            except Errors.NotFoundError:
                raise CerebrumError("Unknown affiliation: " + repr(aff_value))
            aff_str = _text_or_none(status) or _text_or_none(aff)
        else:
            aff = status = aff_str = None

        # Clear the path and return some information to the user
        ou_mapping = OUDiskMapping(self.db)
        try:
            disk_id = ou_mapping.get(ou.entity_id, aff, status)['disk_id']
        except (TypeError, Errors.NotFoundError):
            raise CerebrumError("No mapping for %s@id:%s"
                                % (aff_str or "*", ou.entity_id))
        ou_mapping.delete(ou.entity_id, aff, status)

        disk = get_disk_by_id(self.db, disk_id)

        result = _prepare_ou_result(ou)
        result.update({
            "affiliation": aff_str,
            "affiliation_repr": aff_str or "*",
            "disk_id": int(disk.entity_id),
            "disk_path": six.text_type(disk.path),
        })
        return result

    # Format suggestion for `_list_disk_mapping` results.
    _list_disk_mapping_fs = get_format_suggestion_table(
        ("ou_id", "OU", 12, "d", False),
        ("ou_loc", "Stedkode", 8, "s", True),
        ("affiliation", "Affiliation", 26, "s", True),
        ("disk_path", "Disk", 34, "s", True),
        limit_key="limit",
    )

    def _list_disk_mappings(self, limit=0, **params):
        """ Fetch and prepare ou disk mapping search results. """
        ou_mapping = OUDiskMapping(self.db)

        if limit:
            # ask for one more result, so we can detect that our limit is
            # reached
            params['limit'] = limit + 1

        ou = disk = prev_ou_id = prev_disk_id = None
        for i, row in enumerate(ou_mapping.search(**params)):
            if limit and i >= limit:
                yield {'limit': limit}
                break

            aff = (self.const.PersonAffiliation(row['aff_code'])
                   if row['aff_code'] else None)
            status = (self.const.PersonAffStatus(row['status_code'])
                      if row['status_code'] else None)
            aff_str = _text_or_none(status) or _text_or_none(aff)

            # reduce lookups
            if row['ou_id'] != prev_ou_id:
                ou = get_ou_by_id(self.db, row['ou_id'])
            prev_ou_id = row['ou_id']
            if row['disk_id'] != prev_disk_id:
                disk = get_disk_by_id(self.db, row['disk_id'])
            prev_disk_id = row['disk_id']

            result = _prepare_ou_result(ou)
            result.update({
                'affiliation': aff_str,
                'disk_id': disk.entity_id,
                'disk_path': disk.path,
                # useful to identify overrides
                'affiliation_code': _text_or_none(aff),
                'status_code': _text_or_none(status),
            })
            yield result

    #
    # ou homedir_list <ou> <aff> <status>
    #
    all_commands["ou_homedir_list"] = Command(
        ("ou", "homedir_list"),
        SimpleString(help_ref="ou-mapping-ou"),
        YesNo(help_ref="ou-mapping-all", optional=True, default='no'),
        fs=_list_disk_mapping_fs,
        perm_filter="can_show_ou_disk_mapping",
    )

    def ou_homedir_list(self, operator, ou_value, include_duplicates='no'):
        """
        List default homedir rules affecting a given org unit.

        :param operator:
        :param ou_value:
            the org unit to get homedir rule(s) for
        :param include_duplicates:
            show parent rules that are overridden by children

        :returns dict:
            client output
        """
        ou = self._find_ou(ou_value)
        perspective = perspective_db.get_default_perspective(self.const)
        include_duplicates = self._get_boolean(include_duplicates)

        self.ba.can_show_ou_disk_mapping(operator.get_entity_id())

        # some utils to exclude "duplicate" rules
        seen_affs = set()

        def _is_duplicate(result):
            if None in seen_affs:
                # we've already seen a catch-all rule
                return True
            if result['status_code']:
                return (result['status_code'] in seen_affs
                        or result['affiliation_code'] in seen_affs)
            if result['affiliation_code']:
                return result['affiliation_code'] in seen_affs
            # this is a new catch-all rule
            return False

        def _add_result(result):
            if result['status_code']:
                seen_affs.add(result['status_code'])
            elif result['affiliation_code']:
                seen_affs.add(result['affiliation_code'])
            else:
                seen_affs.add(None)

        # iterative lookup to preserve order
        results = []
        for r in self._list_disk_mappings(ou_id=ou.entity_id):
            results.append(r)
            _add_result(r)

        for row in perspective_db.find_parents(self.db, perspective,
                                               ou.entity_id):
            for res in self._list_disk_mappings(ou_id=row['parent_id']):
                if not include_duplicates and _is_duplicate(res):
                    continue
                results.append(res)
                _add_result(res)

        if not results:
            raise CerebrumError("No matching rules for ou: " + repr(ou_value))
        return results

    #
    # ou homedir_search [filter...]
    #
    all_commands["ou_homedir_search"] = Command(
        ("ou", "homedir_search"),
        SimpleString(help_ref='ou-mapping-filter', optional=True, repeat=True),
        fs=_list_disk_mapping_fs,
        perm_filter="can_search_ou_disk_mapping",
    )

    def ou_homedir_search(self, operator, *search_filters):
        """
        Search default homedir rules.

        :param operator:
        :param search_filters: filter results

        :returns list: a list of search results for the client
        """
        self.ba.can_search_ou_disk_mapping(operator.get_entity_id())

        filters = _ou_mapping_parser.parse_items(search_filters)
        search_params = {'limit': 1000}

        if 'ou' in filters:
            ou = self._find_ou(filters['ou'])
            search_params['ou_id'] = ou.entity_id

        if 'disk' in filters:
            disk = self._find_disk(filters['disk'])
            search_params['disk_id'] = disk.entity_id

        if 'affiliation' in filters:
            affiliation = filters['affiliation']
            if affiliation:
                aff, status = self.const.get_affiliation(affiliation)
                search_params.update({
                    'affiliation': aff,
                    'status': NotSet if status is None else status,
                })
            else:
                search_params['affiliation'] = None

        results = list(self._list_disk_mappings(**search_params))
        if not results:
            raise CerebrumError("No matching rules (filters: %r)"
                                % (tuple(filters.keys()),))
        return results

    #
    # ou homedir_resolve <ou> [aff]
    #
    all_commands["ou_homedir_resolve"] = Command(
        ("ou", "homedir_resolve"),
        SimpleString(help_ref='ou-mapping-ou'),
        SimpleString(help_ref='ou-mapping-aff', optional=True),
        fs=FormatSuggestion([
            ("Defalt for %s@%s: %s (%d)",
             ("affiliation", "ou_repr", "disk_path", "disk_id")),
            ("Inherited from ou %s", ("ou_match_repr",))
        ]),
        perm_filter="can_resolve_ou_disk_mapping",
    )

    def ou_homedir_resolve(self, operator, ou_value, aff_value=None):
        """
        Get default homedir according to rules.

        :param operator:
        :param ou_value: the affiliated org unit
        :param aff_value: the affiliation

        :returns dict: client output
        """
        ou_mapping = OUDiskMapping(self.db)
        ou = self._find_ou(ou_value)
        perspective = self.const.OUPerspective(cereconf.DEFAULT_OU_PERSPECTIVE)

        self.ba.can_resolve_ou_disk_mapping(operator.get_entity_id(), ou)

        # Look up affiliation
        if aff_value:
            try:
                aff, status = self.const.get_affiliation(aff_value)
            except Errors.NotFoundError:
                raise CerebrumError("Unknown affiliation: " + repr(aff_value))
            aff_str = six.text_type(status if status else aff)
        else:
            aff = status = aff_str = None

        try:
            disk_match = resolve_disk(ou_mapping, ou.entity_id, aff, status,
                                      perspective)
        except Errors.NotFoundError:
            raise CerebrumError("No match for %s@<id:%d>"
                                % (aff_str, ou.entity_id))

        disk = get_disk_by_id(self.db, disk_match['disk_id'])
        result = _prepare_ou_result(ou)
        result.update({
            "affiliation": aff_str,
            "disk_id": int(disk.entity_id),
            "disk_path": six.text_type(disk.path),
        })
        if ou.entity_id != disk_match['ou_id']:
            parent = get_ou_by_id(self.db, disk_match['ou_id'])
            result.update(_prepare_ou_result(parent, prefix='ou_match'))
        return result


class OuMappingSearchParams(parsers.ParamsParser):
    """ Parse disk mapping search params from user input.

    This class can convert a sequence of strings like
    `("disk:/path/to/foo", "ou:102030", "affiliation:ANSATT")`
    into a dict of search params for the `ou_disk_mapping` module
    """

    fields = {
        'disk': textwrap.dedent(
            """
            Limit to rules for a given disk.

            - `disk:/path/to/disk`
            - `disk:id:1234`  (entity id of disk)
            """
        ).strip(),
        'ou': textwrap.dedent(
            """
            Limit to rules for a given org unit

            - `ou:102030`  (location code, "stedkode")
            - `ou:id:1234`  (entity id of org unit)
            """
        ).strip(),
        'affiliation': textwrap.dedent(
            """
            Limit to rules for a given affiliation or status.

            - `affiliation:STUDENT/aktiv`
            - `affiliation:STUDENT`
            - `affiliation:`  (rule that expicitly match any aff)
            """
        ).strip(),
    }

    parsers = {
        'affiliation': lambda v: v or None,
    }


_ou_mapping_parser = OuMappingSearchParams()
_ou_mapping_help_blurb = """
Each ou-mapping-filter follows a format of <param>:<value>.

Examples
--------
Find rules for disk at /path/to/foo that applies to all affiliation types:

    `ou homedir_search disk:/path/to/foo affiliation:`

Find rules for the org unit with entity id 123:

    `ou homedir_search ou:id:123`

Find rules that applies to active students:

    `ou homedir_search affiliation:STUDENT/aktiv`

Valid filter params
-------------------
{filters}
""".format(
    filters='\n\n'.join(
        '{}:\n{}'.format(f, "\n".join("  " + line for line in h.split("\n")))
        for f, h in _ou_mapping_parser.get_help()),
)


def _get_shortdoc(fn):
    """ Get first line of docsting. """
    doc = (fn.__doc__ or "")
    for line in doc.splitlines():
        line = line.strip().rstrip(".")
        if line:
            return line
    return ""


HELP_GROUP = {}

HELP_CMD = {
    "ou": {
        "ou_homedir_add": _get_shortdoc(
            BofhdOUDiskMappingCommands.ou_homedir_add),
        "ou_homedir_list": _get_shortdoc(
            BofhdOUDiskMappingCommands.ou_homedir_list),
        "ou_homedir_remove": _get_shortdoc(
            BofhdOUDiskMappingCommands.ou_homedir_remove),
        "ou_homedir_search": _get_shortdoc(
            BofhdOUDiskMappingCommands.ou_homedir_search),
        "ou_homedir_resolve": _get_shortdoc(
            BofhdOUDiskMappingCommands.ou_homedir_resolve),
    },
}

HELP_ARGS = {
    "ou-mapping-ou": [
        "ou-mapping-ou",
        "Enter org unit",
        textwrap.dedent(
            """
            Org unit to apply mapping rule to.

            Can either be a location code (stedkode), or an internal org unit
            id.

            - 102030
            - id:1234

            Disk mapping rules are inherited by sub org units without their own
            rules.
            """
        ).strip(),
    ],
    "ou-mapping-aff": [
        "ou-mapping-aff",
        "Enter affiliation",
        textwrap.dedent(
            """
            Limit disk mapping rule to affiliation.

            Can either be an affiliation, or an affiliation status.  E.g.:

            - STUDENT
            - ANSATT/tekadm
            """
        ).strip(),
    ],
    "ou-mapping-disk": [
        "ou-mapping-disk",
        "Enter disk",
        textwrap.dedent(
            """
            Default disk to use for this ou mapping rule.

            The disk must exist in Cerebrum.  Use `disk list <host>` to list
            avaliable disks at a given host.  Supported values:

            - <disk-path> (e.g. `/path/to/disk`, `/uio/kant/foo`)
            - id:<disk-id> (e.g. `id:1234`)
            """
        ).strip(),
    ],
    'ou-mapping-filter': [
        'ou-mapping-filter',
        'Enter a ou mapping search filter',
        _ou_mapping_help_blurb,
    ],
    "ou-mapping-all": [
        "ou-mapping-all",
        "Include all rules (yes/no)",
        textwrap.dedent(
            """
            Include all parent rules.

            This will include rules that will never take effect, as they are
            overridden by more specific rules.  Useful when refactoring disk
            mapping rules.

            - "yes" to include all rules
            - "no" to only include rules that may effect the given org unit
            """
        ).strip(),
    ],
}
