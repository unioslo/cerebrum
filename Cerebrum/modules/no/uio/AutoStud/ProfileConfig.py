# -*- coding: utf-8 -*-
#
# Copyright 2003-2023 University of Oslo, Norway
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
This module provides method for parsing the studconfig.xml file and
translating it to an internal datastructure.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import pprint
import sys

from six import python_2_unicode_compatible

from Cerebrum import Errors
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.no.uio.AutoStud.Select import SelectTool
from Cerebrum.modules.no.uio.AutoStud.Util import LookupHelper
from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser

pp = pprint.PrettyPrinter(indent=4)


class Config(object):

    def __init__(self, autostud, logger, cfg_file=None, debug=0):
        self.debug = debug
        self.autostud = autostud
        self._logger = logger
        self._errors = []
        self.group_defs = {}
        self.default_values = {}
        self.profiles = []
        self.profilename2profile = {}
        self.required_spread_order = []
        self.lookup_helper = LookupHelper(autostud.db, logger,
                                          autostud.ou_perspective)

        try:
            sp = StudconfigParser(self, cfg_file)
        except Exception:
            if self._errors:
                logger.fatal("Got the following errors, and a stack trace: \n"
                             "{}".format("\n".join(self._errors)))
            raise
        self.spread_defs = [int(autostud.co.Spread(x))
                            for x in sp.legal_spreads.keys()]
        self._post_process_config()
        self.autostud.disk_tool.post_process()

    def _post_process_config(self):
        # Config parsing complete.  Convert config-settings to
        # database references etc.
        profilename2profile = {}
        self.using_priority = False
        for p in self.profiles:
            if p.name in profilename2profile:
                self.add_error("Duplicate profile-name {}".format(p.name))
            profilename2profile[p.name] = p
            p.post_config(self.lookup_helper, self)
            if p.priority is not None:
                self.using_priority = True
            self.profilename2profile[p.name] = p
        for p in self.profiles:
            p.expand_super(profilename2profile)
            if self.using_priority and p.priority is None:
                self.add_error("Priority used, but not defined for {}".format(
                               p.name))

        self.select_tool = SelectTool(self.profiles, self._logger, self)
        # Change keys in group_defs from name to entity_id
        pg = PosixGroup.PosixGroup(self.autostud.db)
        tmp = {}
        for k in self.group_defs.keys():
            id = self.lookup_helper.get_group(k)
            t = self.group_defs[k]
            try:
                pg.clear()
                pg.find(id)
                t['is_posix'] = True
            except Errors.NotFoundError:
                t['is_posix'] = False
            tmp[id] = t
        self.group_defs = tmp
        if self._errors:
            self._logger.fatal(
                "The configuration file has errors, refusing to "
                "continue: \n{}".format("\n".join(self._errors)))
            sys.exit(1)

    def debug_dump(self):
        ret = "Profile definitions:"
        for p in self.profiles:
            ret += p.debug_dump() + "\n"
        ret += "Select mappings:\n"
        for tag, sm in self.select_tool.select_map_defs.items():
            ret += "  {}\n".format(tag)
            ret += "".join(
                ["    {}\n".format(line for line in repr(sm).split("\n"))]
            )
        return ret

    def add_error(self, msg):
        self._errors.append(msg)


@python_2_unicode_compatible
class ProfileDefinition(object):
    """Represents a profile as defined in the studconfig.xml file"""

    def __init__(self, config, name, logger, super=None):
        self.config = config
        self.name = name
        self.super = super
        self._logger = logger
        self._settings = {}
        self.selection_criterias = {}
        self.priority = None
        self.super_names = []

    def __str__(self):
        return "ProfileDefinition object({})".format(self.name)

    def post_config(self, lookup_helper, config):
        self._convert_to_database_refs(lookup_helper, config)

        # Initially _settings directly contains the actual settings.
        # After we have finished, we expand this so that it contains
        # setting, <name of profile that gave the setting>.  This
        # allows us to detect if the setting originated from the
        # current profile, or if it originated from a super.

        for k, v in self._settings.items():
            self._settings[k] = [(x, self.name) for x in v]

    def expand_super(self, name2profile):
        """Recursively add all settings from parent profiles so that
        we can remove the reference to super."""

        if self.super is not None:
            if self.super not in name2profile:
                self.config.add_error("Illegal super '{}' for '{}'".format(
                    self.super, self.name))
            tmp_super = name2profile[self.super]
            tmp_super.expand_super(name2profile)
            self.super_names = [tmp_super.name] + tmp_super.super_names

            for k in tmp_super._settings.keys():
                if k == 'disk' and self._settings.get(k, None):
                    continue  # We're not interested in disks from super
                self._settings.setdefault(k, []).extend(
                    tmp_super._settings[k])

            if self.priority is None and tmp_super.priority is not None:
                self.priority = tmp_super.priority
            if self.priority != tmp_super.priority:
                self.config.add_error(
                    "priority diff in {} vs {} ({}/{})".format(
                        self.name, tmp_super.name, self.priority,
                        tmp_super.priority)
                )
            self.super = None
            self._settings["spread"] = self._sort_spreads(
                self._settings["spread"])

    def _sort_spreads(self, spreads):
        """On some sites certain spreads requires other spreads, thus
        we must sort them """
        ret = []
        for s in self.config.required_spread_order:
            for tmp_s, tmp_p in spreads:
                if s == tmp_s:
                    ret.append((s, tmp_p))
        return ret

    def _get_steder(self, institusjon, stedkode, scope):
        ret = []
        sko = self.config.lookup_helper.get_stedkode(stedkode, institusjon)
        if scope == 'sub':
            ret.extend(self.config.lookup_helper.get_all_child_sko(sko))
        else:
            ret.append(stedkode)
        return ret

    def add_setting(self, name, attribs):
        if name == "gruppe" and attribs.get("type", None) == "primary":
            self._settings.setdefault("primarygroup", []).append(attribs)
        self._settings.setdefault(name, []).append(attribs)

    def get_settings(self, k):
        return self._settings.get(k, [])

    def add_selection_criteria(self, name, attribs):
        self.selection_criterias.setdefault(name, []).append(attribs)

    def debug_dump(self):
        return (
            "Profile name: '%s', p=%s, supers=%s, settings:\n%s"
            % (self.name, self.priority, self.super_names,
               pp.pformat(self._settings))
        )

    #
    # methods for converting the XML entries to values from the database
    #

    def _convert_to_database_refs(self, lookup_helper, config):
        """Convert references in profil-settings to database values
        where apropriate"""
        for p in self._settings.get("priority", []):
            if self.priority is not None and self.priority != int(p['level']):
                self.config.add_error(
                    "Conflicting priorities in {}".format(self.name))
            self.priority = int(p['level'])
        if self.priority is not None:
            del (self._settings['priority'])
        tmp = []
        for spread in self._settings.get("spread", []):
            tmp.append(lookup_helper.get_spread(spread['system']))
        self._settings["spread"] = tmp
        tmp = []
        for group in self._settings.get("gruppe", []):
            # TODO: Should assert that entry is in group_defs
            tmp.append(lookup_helper.get_group(group['navn']))
        self._settings["gruppe"] = tmp
        tmp = []
        for group in self._settings.get("primarygroup", []):
            tmp.append(lookup_helper.get_group(group['navn']))
        self._settings["primarygroup"] = tmp
        tmp = []
        for stedkode in self._settings.get("stedkode", []):
            tmp2 = lookup_helper.get_stedkode(stedkode['verdi'],
                                              stedkode['institusjon'])
            if tmp2 is not None:
                tmp.append(tmp2)
        self._settings["stedkode"] = tmp
        tmp = []
        for disk_attrs in self._settings.get("disk", []):
            tmp.append(self.config.autostud.disk_tool.
                       get_diskdef_by_select(**disk_attrs))
        self._settings["disk"] = tmp
        tmp = []
        for q in self._settings.get("quarantine", []):
            tmp.append({'quarantine': config.autostud.co.Quarantine(q['navn']),
                        'start_at': int(q.get('start_at', 0)) * 3600 * 24,
                        'scope': q.get('scope', None)})
        self._settings["quarantine"] = tmp
        for m in lookup_helper.get_lookup_errors():
            self.config.add_error(m)


class StudconfigParser(object):
    """
    Parses the studconfig XML file.  The XML file consists of the
    following elements:
      - profil: defines a profile (a list of settings)
      - select: selects the entries which the profil will be applied to

    Any profiles used as super must have been previously defined, and
    are applied after the profile with the super attribute has been
    applied, thus values from the current profile will appear before
    values from the super."""

    # TODO: All the checks for unexpected tags can be avoided if we
    # let some utility check the XML file against the DTD

    profil_settings = ("stedkode", "gruppe", "spread", "disk",
                       "mail", "disk_kvote", "brev", "build",
                       "priority", "quarantine")

    def __init__(self, config, cfg_file):
        cfg = ((['studconfig', 'default_values'], self.got_default_values),
               (['studconfig', 'disk_oversikt'], self.got_disk_oversikt),
               (['studconfig', 'gruppe_oversikt', ], self.got_gruppe_oversikt),
               (['studconfig', 'spread_oversikt', ], self.got_spread_oversikt),
               (['studconfig', 'profil', ], self.got_profil),
               (['studconfig', 'disk_pools', ], self.got_disk_pool),
               )
        self._config = config
        self._legal_groups = {}
        self.legal_spreads = {}
        GeneralXMLParser(cfg, cfg_file)

    def got_default_values(self, dta, elem_stack):
        for ename, txt, attrs, children in dta:
            for attr in attrs:
                key = '{}_{}'.format(ename, attr)
                self._config.default_values[key] = attrs[attr]

    def got_disk_oversikt(self, dta, elem_stack):
        tmp_disk_spreads = []
        for ename, txt, attrs, children in dta:
            if ename == 'disk_spread':
                s = int(self._config.lookup_helper.get_spread(attrs['kode']))
                tmp_disk_spreads.append(s)
                self._config.autostud.disk_tool.add_known_spread(s)
            elif ename == 'diskdef':
                if not tmp_disk_spreads:
                    raise ValueError("DTD-violation: no disk_spread defined")
                attrs['max'] = attrs.get(
                    'max', elem_stack[-1][-1]['default_max'])
                attrs['auto'] = attrs.get(
                    'auto', elem_stack[-1][-1].get('default_auto', None))
                attrs['orderby'] = attrs.get(
                    'orderby', elem_stack[-1][-1].get('default_orderby', None))
                if not attrs['auto']:
                    self._config.add_error(
                        "Missing auto attribute for %s" % repr(attrs))
                attrs['disk_kvote'] = attrs.get(
                    'disk_kvote', elem_stack[-1][-1].get(
                        'default_disk_kvote', self._config.default_values.get(
                            'disk_kvote_value', None)))
                if attrs['disk_kvote'] is not None:
                    self._config.using_disk_kvote = True
                attrs['spreads'] = tmp_disk_spreads
                self._config.autostud.disk_tool.add_disk_def(**attrs)
            else:
                self._config.add_error(
                    "Unexpected tag {} in disk_oversikt".format(ename))

    def got_disk_pool(self, dta, elem_stack):
        for ename, txt, attrs, children in dta:
            if ename == 'pool':
                for ename2, txt2, attrs2, children2 in children:
                    if ename2 == 'disk':
                        self._config.autostud.disk_tool.append_to_pool(
                            attrs['name'], orderby=attrs.get('orderby', None),
                            **attrs2)

    def got_gruppe_oversikt(self, dta, elem_stack):
        for ename, txt, attrs, children in dta:
            if ename == 'gruppedef':
                self._legal_groups[attrs['navn']] = 1
                self._config.group_defs[attrs['navn']] = {
                    'auto': attrs.get('auto',
                                      elem_stack[-1][-1]['default_auto'])}
            else:
                self._config.add_error(
                    "Unexpected tag {} in gruppe_oversikt".format(ename))

    def got_spread_oversikt(self, dta, elem_stack):
        for ename, txt, attrs, children in dta:
            if ename == 'spreaddef':
                self._config.required_spread_order.append(
                    self._config.lookup_helper.get_spread(attrs['kode']))
                self.legal_spreads[attrs['kode']] = 1
            else:
                self._config.add_error(
                    "Unexpected tag {} in spread_oversikt".format(ename))

    def got_profil(self, dta, elem_stack):
        in_profil = ProfileDefinition(
            self._config, elem_stack[-1][-1]['navn'], self._config._logger,
            super=elem_stack[-1][-1].get('super', None))

        for ename, txt, attrs, children in dta:
            if ename in self.profil_settings:
                if (ename == 'gruppe'
                        and attrs['navn'] not in self._legal_groups):
                    self._config.add_error("Not in groupdef: {}".format(
                                           attrs['navn']))
                elif (ename == 'spread'
                        and attrs['system'] not in self.legal_spreads):
                    self._config.add_error("Not in spreaddef: {}".format(
                                           attrs['system']))
                elif ename == 'disk_kvote':
                    self._config.autostud.disk_tool.using_disk_kvote = True
                in_profil.add_setting(ename, attrs)
            elif ename == 'select':
                for ename2, txt2, attrs2, children2 in children:
                    if ename2 not in SelectTool.select_map_defs:
                        self._config.add_error(
                            "Unexpected tag '{}', attr={} in {}".format(
                                ename2, str(attrs2), repr(elem_stack)))
                        continue
                    in_profil.add_selection_criteria(ename2, attrs2)
            else:
                self._config.add_error("Unexpected tag {} in {}".format(
                    ename, repr(elem_stack)))
        self._config.profiles.append(in_profil)
