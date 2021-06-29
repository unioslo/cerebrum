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
""" This module contains ou related commands in bofhd. """
from __future__ import unicode_literals

import logging
import re

import six

import cereconf
from Cerebrum import Errors
from Cerebrum import Metainfo
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_core_help import get_help_strings
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    ExternalIdType,
    FormatSuggestion,
    OU,
    SimpleString,
    Spread,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.help import merge_help_strings
from Cerebrum.modules.bofhd.utils import BofhdUtils


logger = logging.getLogger(__name__)


class OuAuth(BofhdAuth):
    """ Auth for entity ou_* commands. """

    def can_set_ou_id(self, operator,
                      entity=None,
                      id_type=None,
                      query_run_any=False):
        """ Check if an operator is allowed to set ExternalId on OU.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (i.e. an ou object)
        :param id_type: An ExternalId constant
        """
        if self.is_superuser(operator):
            return True
        if query_run_any:
            return False
        raise PermissionDenied("Currently limited to superusers")

    def can_clear_ou_id(self, operator,
                        entity=None,
                        id_type=None,
                        query_run_any=False):
        """ Check if an operator is allowed to clear ExternalId from OU.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (i.e. an ou object)
        :param id_type: An ExternalId constant
        """
        return self.can_set_ou_id(operator, entity=entity,
                                  id_type=id_type, query_run_any=query_run_any)


def _format_ou_sko(ou):
    """ format stedkode from ou object. """
    if any(getattr(ou, attr, None) is None
           for attr in ('fakultet', 'institutt', 'avdeling')):
        # Missing stedkode attrs (i.e. no support, or no stedkode given)
        return None
    else:
        return '%02d%02d%02d' % (ou.fakultet, ou.institutt, ou.avdeling)


class OuCommands(BofhdCommandBase):

    all_commands = {}
    authz = OuAuth

    # Get default ou-perspective from cereconf.DEFAULT_OU_PERSPECTIVE,
    # with fallback to cereconf.LDAP_OU['perspective']
    default_ou_perspective = getattr(
        cereconf, 'DEFAULT_OU_PERSPECTIVE',
        getattr(cereconf, 'LDAP_OU', {}).get('perspective'))

    default_ou_language = 'nb'

    @property
    def util(self):
        try:
            return self.__util
        except AttributeError:
            self.__util = BofhdUtils(self.db)
            return self.__util

    @classmethod
    def get_help_strings(cls):
        """Get help strings."""
        return merge_help_strings(
            get_help_strings(),
            (CMD_GROUP, CMD_HELP, CMD_ARGS),
        )

    def _get_perspective(self, perspective=None):
        """ Fetch a given perspective code, or the default ou perspective. """
        if not perspective:
            perspective = self.default_ou_perspective
        code = self.const.human2constant(perspective, self.const.OUPerspective)
        try:
            int(code)
        except (TypeError, Errors.NotFoundError):
            perspectives = (
                six.text_type(x)
                for x in self.const.fetch_constants(self.const.OUPerspective))
            raise CerebrumError("Invalid perspective %s. Try one of: %s" %
                                (repr(perspective), ", ".join(perspectives)))
        return code

    def _get_language(self, language=None):
        """ Fetch a given language code, or the default ou language. """
        if not language:
            language = self.default_ou_language
        code = self.const.human2constant(language, self.const.LanguageCode)
        try:
            int(code)
        except (TypeError, Errors.NotFoundError):
            suggest = ('nb', 'en')
            raise CerebrumError("Invalid language %s. Try one of: %s" %
                                (repr(language), ", ".join(suggest)))
        return code

    #
    # ou search <type> <pattern> <language> <spread_filter>
    #
    all_commands['ou_search'] = Command(
        ("ou", "search"),
        SimpleString(help_ref='ou_search_type'),
        SimpleString(help_ref='ou_search_pattern'),
        SimpleString(help_ref='ou_search_language', optional=True),
        Spread(help_ref='spread_filter', optional=True),
        fs=FormatSuggestion(
            # 9 chars, as None is usually rendered as '<not set>'
            [(" %-9s  %s", ('stedkode', 'name'))],
            hdr=" %-9s  %s" % ("Stedkode", "Organizational unit"),
        ),
    )

    def _ou_search_by_sko(self, pattern):
        """ ou search helper - search for ou by stedkode pattern. """
        fak = [pattern[0:2], ]
        inst = [pattern[2:4], ]
        avd = [pattern[4:6], ]

        if len(fak[0]) == 1:
            fak = [int(fak[0]) * 10 + x for x in range(10)]
        if len(inst[0]) == 1:
            inst = [int(inst[0]) * 10 + x for x in range(10)]
        if len(avd[0]) == 1:
            avd = [int(avd[0]) * 10 + x for x in range(10)]

        ou = Factory.get('OU')(self.db)
        # the following loop may look scary, but we will never
        # call get_stedkoder() more than 10 times.
        for f in fak:
            for i in inst:
                i = i or None
                for a in avd:
                    a = a or None
                    for r in ou.get_stedkoder(fakultet=f, institutt=i,
                                              avdeling=a):
                        yield int(r['ou_id'])

    def _ou_search_by_name(self, pattern, language):
        """ ou search helper - search for ou by name pattern. """
        ou = Factory.get('OU')(self.db)
        for r in ou.search_name_with_language(
                entity_type=self.const.entity_ou,
                name_language=language,
                name=pattern,
                exact_match=False):
            yield int(r['entity_id'])

    def _ou_search_by_orgreg_id(self, pattern):
        """ ou seach helper - seach for ou by orgreg id. """
        ou = Factory.get('OU')(self.db)
        for r in ou.search_external_ids(id_type=self.const.externalid_dfo_ou_id,
                                        external_id=pattern,
                                        fetchall=False):
            yield int(r["entity_id"])


    def _ou_search_spread_match(self, ou, spread_filter):
        """ ou search helper - check if ou spreads matches spread_filter. """
        if not spread_filter:
            # no filtering
            return True

        spread_filter = spread_filter.lower()
        for spread in (six.text_type(self.const.Spread(s[0]))
                       for s in ou.get_spread()):
            if spread.lower() == spread_filter:
                return True
        return False

    def ou_search(self, operator, search_type, pattern,
                  language=default_ou_language, spread_filter=None):
        """ Search for a given ou by name, stedkode or OrgReg-ID """

        if not pattern:
            pattern = '%'

        language = self._get_language(language)

        search_type = search_type.lower()
        if search_type == "name":
            candidates = self._ou_search_by_name(pattern, language)

        elif search_type == "sko" or search_type == "stedkode":
            candidates = self._ou_search_by_sko(pattern)

        elif "orgreg" in search_type or search_type == "dfo_ou_id":
            candidates = self._ou_search_by_orgreg_id(pattern)

        output = []
        ou = Factory.get('OU')(self.db)
        for ou_id in set(candidates):
            ou.clear()
            ou.find(ou_id)
            if self._ou_search_spread_match(ou, spread_filter):
                output.append({
                    'ou_id': ou.entity_id,
                    'stedkode': _format_ou_sko(ou),
                    'name': self._format_ou_name_full(ou, language),
                })

        # handle no results
        if len(output) == 0:
            if spread_filter:
                raise CerebrumError(
                    'No matches for %s with spread filter %s' %
                    (repr(pattern), repr(spread_filter)))
            raise CerebrumError('No matches for %s' % repr(pattern))

        return sorted(output, key=lambda r: (r['stedkode'], r['ou_id']))


    #
    # ou info <stedkode/entity_id>
    #
    all_commands['ou_info'] = Command(
        ("ou", "info"),
        OU(help_ref='ou_stedkode_or_id'),
        fs=FormatSuggestion([
            ("Stedkode:      %s\n"
             "Entity ID:     %i\n"
             "Name (nb):     %s\n"
             "Name (en):     %s\n"
             "Quarantines:   %s\n"
             "Spreads:       %s",
             ('stedkode', 'entity_id', 'name_nb', 'name_en', 'quarantines',
              'spreads')),
            ("Contact:       (%s) %s: %s %s",
             ('contact_source', 'contact_type', 'contact_value', 'from_ou')),
            ("Address:       (%s) %s: %s%s%s %s %s",
             ('address_source', 'address_type', 'address_text',
              'address_po_box', 'address_postal_number', 'address_city',
              'address_country')),
            ("Email domain:  affiliation %-7s @%s",
             ('email_affiliation', 'email_domain')),
            ("External id:   %s: %s [from %s]",
             ("extid", "value", "extid_src"))
        ]))

    def ou_info(self, operator, target):
        output = []

        ou = self.util.get_target(target,
                                  default_lookup='stedkode',
                                  restrict_to=['OU'])

        name_nb = self._format_ou_name_full(ou, self.const.language_nb)
        name_en = self._format_ou_name_full(ou, self.const.language_en)

        quarantines = []
        for q in ou.get_entity_quarantine(only_active=True):
            quarantines.append(
                six.text_type(self.const.Quarantine(q['quarantine_type'])))
        if len(quarantines) == 0:
            quarantines = ['<none>']

        spreads = []
        for s in ou.get_spread():
            spreads.append(six.text_type(self.const.Spread(s['spread'])))
        if len(spreads) == 0:
            spreads = ['<none>']

        output.append({
            'entity_id': ou.entity_id,
            'stedkode': _format_ou_sko(ou),
            'name_nb': name_nb,
            'name_en': name_en,
            'quarantines': ', '.join(quarantines),
            'spreads': ', '.join(spreads)
        })

        for c in ou.get_contact_info():
            output.append({
                'contact_source': six.text_type(
                    self.const.AuthoritativeSystem(c['source_system'])),
                'contact_type': six.text_type(
                    self.const.ContactInfo(c['contact_type'])),
                'contact_value': c['contact_value'],
                'from_ou': ''
            })

        if self.default_ou_perspective:
            ou_perspective = self._get_perspective()
            from_ou_str = '(inherited from parent OU, entity_id:{})'
            for it_contact in ou.local_it_contact(ou_perspective):
                if it_contact['from_ou_id'] == ou.entity_id:
                    continue
                output.append({
                    'contact_source': six.text_type(
                        self.const.AuthoritativeSystem(
                            it_contact['source_system'])),
                    'contact_type': six.text_type(
                        self.const.ContactInfo(it_contact['contact_type'])),
                    'contact_value': it_contact['contact_value'],
                    'from_ou': from_ou_str.format(it_contact['from_ou_id'])
                })

        for a in ou.get_entity_address():
            if a['country'] is not None:
                a['country'] = ', ' + a['country']
            else:
                a['country'] = ''

            if a['p_o_box'] is not None:
                a['p_o_box'] = "PO box %s, " % a['p_o_box']
            else:
                a['p_o_box'] = ''

            if len(a['address_text']) > 0:
                a['address_text'] += ', '

            output.append({
                'address_source': six.text_type(
                    self.const.AuthoritativeSystem(a['source_system'])),
                'address_type': six.text_type(
                    self.const.Address(a['address_type'])),
                'address_text': a['address_text'].replace("\n", ', '),
                'address_po_box': a['p_o_box'],
                'address_city': a['city'],
                'address_postal_number': a['postal_number'],
                'address_country': a['country']
            })

        try:
            meta = Metainfo.Metainfo(self.db)
            email_info = meta.get_metainfo('sqlmodule_email')
        except Errors.NotFoundError:
            email_info = None
        if email_info:
            eed = Email.EntityEmailDomain(self.db)
            try:
                eed.find(ou.entity_id)
            except Errors.NotFoundError:
                pass
            ed = Email.EmailDomain(self.db)
            for r in eed.list_affiliations():
                affname = "<any>"
                if r['affiliation']:
                    affname = six.text_type(
                        self.const.PersonAffiliation(r['affiliation']))
                ed.clear()
                ed.find(r['domain_id'])

                output.append({
                    'email_affiliation': affname,
                    'email_domain': ed.email_domain_name,
                })

        # Add external ids
        for ext_id in ou.get_external_id():
            output.append({
                'extid': six.text_type(
                    self.const.EntityExternalId(ext_id['id_type'])),
                'value': six.text_type(ext_id['external_id']),
                'extid_src': six.text_type(
                    self.const.AuthoritativeSystem(ext_id['source_system']))
            })

        return output

    #
    # ou names <stedkode/entity_id> [language]
    #
    all_commands['ou_names'] = Command(
        ("ou", "names"),
        OU(help_ref='ou_stedkode_or_id'),
        fs=FormatSuggestion(
            [("%-12s  %-6s  %s", ('type', 'lang', 'value'))],
            hdr='%-12s  %-6s  %s' % ('Type', 'Lang', 'Value'),
        ),
    )

    def ou_names(self, operator, target):
        """ list names for a given ou. """
        ou = self.util.get_target(target,
                                  default_lookup='stedkode',
                                  restrict_to=['OU'])
        results = []
        for row in ou.search_name_with_language(
                entity_id=int(ou.entity_id),
                entity_type=self.const.entity_ou):
            results.append({
                'type': six.text_type(
                    self.const.EntityNameCode(row['name_variant'])),
                'lang': six.text_type(
                    self.const.LanguageCode(row['name_language'])),
                'value': row['name'],
            })
        if not results:
            raise CerebrumError('No names for ou_id=%s' % repr(ou.entity_id))
        return sorted(results, key=lambda r: (r.get('type'), r.get('lang')))

    #
    # ou tree <stedkode/entity_id> <perspective> <language>
    #
    all_commands['ou_tree'] = Command(
        ("ou", "tree"),
        OU(help_ref='ou_stedkode_or_id'),
        SimpleString(help_ref='ou_perspective', optional=True),
        SimpleString(help_ref='ou_search_language', optional=True),
        fs=FormatSuggestion([("%s%s %s", ('indent', 'stedkode', 'name'))])
    )

    def ou_tree(self, operator, target,
                ou_perspective=default_ou_perspective,
                language=default_ou_language):
        def _is_root(ou, perspective):
            if ou.get_parent(perspective) in (ou.entity_id, None):
                return True
            return False

        language = self._get_language(language)
        perspective = self._get_perspective(ou_perspective)

        output = []

        target_ou = self.util.get_target(target,
                                         default_lookup='stedkode',
                                         restrict_to=['OU'])
        ou = Factory.get('OU')(self.db)

        # TODO: generalize and use Cerebrum.modules.no.orgera.ou_utils to find
        # parents and children
        data = {
            'parents': [],
            'target': [target_ou.entity_id],
            'children': []
        }

        prev_parent = None

        try:
            while True:
                if prev_parent:
                    ou.clear()
                    ou.find(prev_parent)

                    if _is_root(ou, perspective):
                        break

                    prev_parent = ou.get_parent(perspective)
                    data['parents'].insert(0, prev_parent)
                else:
                    if _is_root(target_ou, perspective):
                        break

                    prev_parent = target_ou.get_parent(perspective)
                    data['parents'].insert(0, prev_parent)
        except Exception:
            raise CerebrumError("Error getting OU structure for %s."
                                "Is the OU valid?" % target)

        for c in target_ou.list_children(perspective):
            data['children'].append(c)

        for d in data:
            if d == 'target':
                indent = '* ' + (len(data['parents']) - 1) * '  '
            elif d == 'children':
                indent = (len(data['parents']) + 1) * '  '
                if len(data['parents']) == 0:
                    indent += '  '

            for num, item in enumerate(data[d]):
                ou.clear()
                ou.find(item)

                if d == 'parents':
                    indent = num * '  '

                output.append({
                    'indent': indent,
                    'stedkode': _format_ou_sko(ou),
                    'name': self._format_ou_name_full(ou, language),
                })

        return output

    #
    # ou set_id <stedkode/entity_id> <id-type> <id-value>
    #
    all_commands['ou_set_id'] = Command(
        ("ou", "set_id"),
        OU(),
        ExternalIdType(),
        SimpleString(help_ref='external_id_value'),
        perm_filter='can_set_ou_id'
    )

    def ou_set_id(self, operator, stedkode, id_type, id_value):
        id_type = self.const.EntityExternalId(id_type)
        try:
            int(id_type)
        except Errors.NotFoundError:
            raise CerebrumError("No such external id")
        ou = self._get_ou(stedkode=stedkode)

        self.ba.can_set_ou_id(operator.get_entity_id(),
                              entity=ou,
                              id_type=id_type)

        source_system = self.const.system_manual
        ou.affect_external_id(source_system, id_type)
        ou.populate_external_id(source_system, id_type, id_value)
        ou.write_db()
        return "OK, set external_id: '%s' for ou: '%s'" % (id_value, stedkode)

    #
    # ou clear_id <stedkode/entity_id> <id-type>
    #
    all_commands['ou_clear_id'] = Command(
        ("ou", "clear_id"),
        OU(),
        ExternalIdType(),
        perm_filter='can_clear_ou_id'
    )

    def ou_clear_id(self, operator, stedkode, id_type):
        id_type = self.const.EntityExternalId(id_type)
        try:
            int(id_type)
        except Errors.NotFoundError:
            raise CerebrumError("No such external id")
        ou = self._get_ou(stedkode=stedkode)

        self.ba.can_clear_ou_id(operator.get_entity_id(),
                                entity=ou,
                                id_type=id_type)

        source_system = self.const.system_manual
        if ou.get_external_id(source_system=source_system, id_type=id_type):
            ou.affect_external_id(source_system, id_type)
            ou.write_db()
            return "OK, deleted external_id: '%s' for ou: '%s'" % (id_type,
                                                                   stedkode)
        return ("Could not find manually set external_id: '%s' to delete "
                "for ou: '%s'" % (id_type, stedkode))


#
# Help texts
#

CMD_GROUP = {
    'ou': 'Organizational Unit commands',
}

CMD_HELP = {
    'ou': {
        'ou_clear_id':
            'Remove an external id from an OU (can only clear IDs with source '
            'Manual)',
        'ou_info': 'View information about an OU',
        'ou_names': 'Show all names for an OU',
        'ou_search': 'Search for OUs by name, partial stedkode, or OrgReg-ID',
        'ou_set_id':
            'Add an external id for an OU (can only set IDs with source '
            'Manual)',
        'ou_tree': 'Show parents/children of an OU',
    },
}

CMD_ARGS = {
    'ou_perspective': [
        'perspective',
        'Enter a perspective (usually SAP or FS)',
        'Enter a perspective used for getting the organizational structure.',
    ],
    'ou_search_type': [
        'type',
        'Enter OU search type (name/stedkode/OrgReg-ID)',
        'Enter type of OU identifier (name/stedkode/OrgReg-ID)'
        ' to be used in the search ',
    ],
    'ou_search_language': [
        'language',
        'Enter a language code (nb/en)',
        ('Enter a language code (nb/en) to be used for searching and'
         ' displaying OU names and acronyms.'),
    ],
    'ou_search_pattern': [
        'pattern',
        'Enter search pattern',
        ('Enter a string (% works as a wildcard) or a partial stedkode'
         ' to search for.'),
    ],
    'ou_stedkode_or_id': [
        'ou',
        'Enter OU stedkode/id',
        ('Enter a 6-digit stedkode of an organizational unit, or id:?'
         ' to look up by entity ID.'),
     ],
}
