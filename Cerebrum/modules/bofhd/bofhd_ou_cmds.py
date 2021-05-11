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
    """ Auth for entity contactinfo_* commands. """

    def can_set_ou_id(self, operator,
                      entity=None,
                      id_type=None,
                      query_run_any=False):
        """ Check if an operator is allowed to see contact info.

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
        """ Check if an operator is allowed to see contact info.

        :param int operator: entity_id of the authenticated user
        :param entity: A cerebrum entity object (i.e. an ou object)
        :param id_type: An ExternalId constant
        """
        return self.can_set_ou_id(operator, entity=entity,
                                  id_type=id_type, query_run_any=query_run_any)


class OuCommands(BofhdCommandBase):

    all_commands = {}
    authz = OuAuth

    @property
    def util(self):
        # TODO: Or should we inherit from BofhdCommonMethods?
        #       We're not really interested in user_delete, etc...
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

    #
    # ou search <pattern> <language> <spread_filter>
    #
    all_commands['ou_search'] = Command(
        ("ou", "search"),
        SimpleString(help_ref='ou_search_pattern'),
        SimpleString(help_ref='ou_search_language', optional=True),
        Spread(help_ref='spread_filter', optional=True),
        fs=FormatSuggestion(
            [(" %06s    %s", ('stedkode', 'name'))],
            hdr="Stedkode   Organizational unit",
        ),
    )

    def ou_search(self, operator, pattern, language='nb', spread_filter=None):
        if len(pattern) == 0:
            pattern = '%'  # No search pattern? Get everything!
        if spread_filter is not None:
            spread_filter = spread_filter.lower()

        try:
            language = int(self.const.LanguageCode(language))
        except Errors.NotFoundError:
            raise CerebrumError('Unknown language "%s", try "nb" or "en"' %
                                language)

        output = []
        ou = Factory.get('OU')(self.db)

        if re.match(r'[0-9]{1,6}$', pattern):
            fak = [pattern[0:2], ]
            inst = [pattern[2:4], ]
            avd = [pattern[4:6], ]

            if len(fak[0]) == 1:
                fak = [int(fak[0]) * 10 + x for x in range(10)]
            if len(inst[0]) == 1:
                inst = [int(inst[0]) * 10 + x for x in range(10)]
            if len(avd[0]) == 1:
                avd = [int(avd[0]) * 10 + x for x in range(10)]

            # the following loop may look scary, but we will never
            # call get_stedkoder() more than 10 times.
            for f in fak:
                for i in inst:
                    i = i or None
                    for a in avd:
                        a = a or None
                        for r in ou.get_stedkoder(fakultet=f, institutt=i,
                                                  avdeling=a):
                            ou.clear()
                            ou.find(r['ou_id'])

                            if spread_filter:
                                spread_filter_match = False
                                for spread in (
                                        six.text_type(self.const.Spread(s[0]))
                                        for s in ou.get_spread()):
                                    if spread.lower() == spread_filter:
                                        spread_filter_match = True
                                        break

                            acronym = ou.get_name_with_language(
                                 name_variant=self.const.ou_name_acronym,
                                 name_language=language,
                                 default="")
                            name = ou.get_name_with_language(
                                 name_variant=self.const.ou_name,
                                 name_language=language,
                                 default="")

                            if len(acronym) > 0:
                                acronym = "(%s) " % acronym

                            if (not spread_filter or (spread_filter and
                                                      spread_filter_match)):
                                output.append({
                                    'stedkode': '%02d%02d%02d' % (ou.fakultet,
                                                                  ou.institutt,
                                                                  ou.avdeling),
                                    'name': "%s%s" % (acronym, name),
                                })
        else:
            for r in ou.search_name_with_language(
                    entity_type=self.const.entity_ou,
                    name_language=language,
                    name=pattern,
                    exact_match=False):
                ou.clear()
                ou.find(r['entity_id'])

                if spread_filter:
                    spread_filter_match = False
                    for spread in (self.const.Spread(s[0])
                                   for s in ou.get_spread()):
                        if six.text_type(spread).lower() == spread_filter:
                            spread_filter_match = True
                            break

                acronym = ou.get_name_with_language(
                    name_variant=self.const.ou_name_acronym,
                    name_language=language,
                    default="")
                name = ou.get_name_with_language(
                    name_variant=self.const.ou_name,
                    name_language=language,
                    default="")

                if len(acronym) > 0:
                    acronym = "(%s) " % acronym

                if (not spread_filter or (spread_filter and
                                          spread_filter_match)):
                    output.append({
                        'stedkode': '%02d%02d%02d' % (ou.fakultet,
                                                      ou.institutt,
                                                      ou.avdeling),
                        'name': "%s%s" % (acronym, name),
                    })

        if len(output) == 0:
            if spread_filter:
                return ('No matches for "%s" with spread filter "%s"' %
                        (pattern, spread_filter))
            return 'No matches for "%s"' % pattern

        # removes duplicate results
        seen = set()
        output_nodupes = []
        for r in output:
            t = tuple(r.items())
            if t not in seen:
                seen.add(t)
                output_nodupes.append(r)

        return output_nodupes

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

        acronym_nb = ou.get_name_with_language(
            name_variant=self.const.ou_name_acronym,
            name_language=self.const.language_nb,
            default="")
        fullname_nb = ou.get_name_with_language(
            name_variant=self.const.ou_name,
            name_language=self.const.language_nb,
            default="")
        acronym_en = ou.get_name_with_language(
            name_variant=self.const.ou_name_acronym,
            name_language=self.const.language_en,
            default="")
        fullname_en = ou.get_name_with_language(
            name_variant=self.const.ou_name,
            name_language=self.const.language_en,
            default="")

        if len(acronym_nb) > 0:
            acronym_nb = "(%s) " % acronym_nb

        if len(acronym_en) > 0:
            acronym_en = "(%s) " % acronym_en

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

        # To support OU objects without the mixin for stedkode:
        stedkode = '<Not set>'
        if hasattr(ou, 'fakultet'):
            stedkode = '%02d%02d%02d' % (ou.fakultet, ou.institutt,
                                         ou.avdeling)

        output.append({
            'entity_id': ou.entity_id,
            'stedkode': stedkode,
            'name_nb': "%s%s" % (acronym_nb, fullname_nb),
            'name_en': "%s%s" % (acronym_en, fullname_en),
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

        ou_perspective = cereconf.LDAP_OU.get('perspective', None)
        if ou_perspective:
            ou_perspective = self.const.OUPerspective(ou_perspective)
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

                output.append({'email_affiliation': affname,
                               'email_domain': ed.email_domain_name})

        # Add external ids
        for ext_id in ou.get_external_id():
            output.append(
                {
                    'extid': six.text_type(self.const.EntityExternalId(
                        ext_id['id_type'])),
                    'value': six.text_type(ext_id['external_id']),
                    'extid_src': six.text_type(self.const.AuthoritativeSystem(
                        ext_id['source_system']))
                }
            )

        return output

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

    def ou_tree(self, operator, target, ou_perspective=None, language='nb'):
        def _is_root(ou, perspective):
            if ou.get_parent(perspective) in (ou.entity_id, None):
                return True
            return False
        co = self.const
        try:
            language = int(co.LanguageCode(language))
        except Errors.NotFoundError:
            raise CerebrumError('Unknown language "%s", try "nb" or "en"' %
                                language)

        output = []

        perspective = None
        if ou_perspective:
            perspective = co.human2constant(ou_perspective, co.OUPerspective)
        if not ou_perspective and 'perspective' in cereconf.LDAP_OU:
            perspective = co.human2constant(cereconf.LDAP_OU['perspective'],
                                            co.OUPerspective)

        if ou_perspective and not perspective:
            raise CerebrumError(
                "No match for perspective '%s'. Try one of: %s" %
                (ou_perspective,
                 ", ".join(six.text_type(x) for x in
                           co.fetch_constants(co.OUPerspective))))
        if not perspective:
            raise CerebrumError(
                "Unable to guess perspective. Please specify one of: %s" %
                (", ".join(six.text_type(x) for x in
                           co.fetch_constants(co.OUPerspective))))

        target_ou = self.util.get_target(target,
                                         default_lookup='stedkode',
                                         restrict_to=['OU'])
        ou = Factory.get('OU')(self.db)

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
                    'stedkode': '%02d%02d%02d' % (ou.fakultet, ou.institutt,
                                                  ou.avdeling),
                    'name': ou.get_name_with_language(
                        name_variant=co.ou_name,
                        name_language=language,
                        default="")
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
    'ou': 'Organizational unit related commands',
}

CMD_HELP = {
    'ou': {
        'ou_search': 'Search for OUs by name or a partial stedkode',
        'ou_info': 'View information about an OU',
        'ou_tree': 'Show parents/children of an OU',
        'ou_set_id':
            'Add an external id for an OU (can only set IDs with source '
            'Manual)',
        'ou_clear_id':
            'Remove an external id from an OU (can only clear IDs with source '
            'Manual)'
    },
}

CMD_ARGS = {
    'ou_perspective': [
        'perspective',
        'Enter a perspective (usually SAP or FS)',
        'Enter a perspective used for getting the organizational structure.',
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
