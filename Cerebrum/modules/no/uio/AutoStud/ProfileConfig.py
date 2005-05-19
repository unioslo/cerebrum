# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

"""This module provides method for parsing the studconfig.xml file and
translating it to an internal datastructure"""

import sys
import xml.sax
import pprint
from Cerebrum.modules.no.uio.AutoStud.Util import LookupHelper
from Cerebrum.modules.no.uio.AutoStud.Select import SelectTool
from Cerebrum.modules import PosixGroup
from Cerebrum import Errors

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
        self.lookup_helper = LookupHelper(autostud.db, logger, autostud.ou_perspective)

        try:
            sp = StudconfigParser(self, cfg_file)
        except:
            if self._errors:
                logger.fatal("Got the following errors, and a stack trace: \n"
                             "%s" % "\n".join(self._errors))
            raise
        self.spread_defs = [int(autostud.co.Spread(x)) for x in sp.legal_spreads.keys()]
        self._post_process_config()
        self.autostud.disk_tool.post_process()

    def _post_process_config(self):
        # Config parsing complete.  Convert config-settings to
        # database references etc.
        profilename2profile = {}
        self.using_priority = False
        for p in self.profiles:
            if profilename2profile.has_key(p.name):
                self.add_error("Duplicate profile-name %s" % p.name)
            profilename2profile[p.name] = p
            p.post_config(self.lookup_helper, self)
            if p.priority is not None:
                self.using_priority=True
            self.profilename2profile[p.name] = p
        for p in self.profiles:
            p.expand_super(profilename2profile)
            if self.using_priority and p.priority is None:
                self.add_error("Priority used, but not defined for %s" % \
                               p.name)
            
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
            self._logger.fatal("The configuration file has errors, refusing to "
                               "continue: \n%s" % "\n".join(self._errors))
            sys.exit(1)

    def debug_dump(self):
        ret = "Profile definitions:"
        for p in self.profiles:
            ret += p.debug_dump()+"\n"
        ret += "Select mappings:\n"
        for tag, sm in self.select_tool.select_map_defs.items():
            ret += "  %s\n" % tag
            ret += "".join(["    %s\n" % line for line in str(sm).split("\n")])
        return ret

    def add_error(self, msg):
        self._errors.append(msg)

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

    def __repr__(self):
        return "Profile object(%s)" % self.name

    def post_config(self, lookup_helper, config):
        self._convertToDatabaseRefs(lookup_helper, config)

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
            if not name2profile.has_key(self.super):
                self.config.add_error("Illegal super '%s' for '%s'" % (
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
                self.config.add_error("priority diff in %s vs %s (%s/%s)" % (
                    self.name, tmp_super.name, self.priority,
                    tmp_super.priority))
            self.super = None
            self._settings["spread"] = self._sort_spreads(self._settings["spread"])

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
        return "Profile name: '%s', p=%s, supers=%s, settings:\n%s" % (
            self.name, self.priority, self.super_names, pp.pformat(self._settings))

    #
    # methods for converting the XML entries to values from the database
    #

    def _convertToDatabaseRefs(self, lookup_helper, config):
        """Convert references in profil-settings to database values
        where apropriate"""
        for p in self._settings.get("priority", []):
            if self.priority is not None and self.priority != int(p['level']):
                self.config.add_error(
                    "Conflicting priorities in %s" % self.name)
            self.priority = int(p['level'])
        if self.priority is not None:
            del(self._settings['priority'])
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
        tmp_spreads = []
        for disk_attrs in self._settings.get("disk", []):
            ddef = self.config.autostud.disk_tool.get_diskdef_by_select(
                **disk_attrs)
            if [x for x in ddef.spreads if x not in tmp_spreads]:
                # We're only interested in the first disk for each
                # single spread.  This allows a sub-profile to
                # override the home in its super without interpreting
                # the target as a 'div disk'
                tmp.append(ddef)
                tmp_spreads.extend(ddef.spreads)
        self._settings["disk"] = tmp
        tmp = []
        for q in self._settings.get("quarantine", []):
            tmp.append({'quarantine': config.autostud.co.Quarantine(q['navn']),
                        'start_at': int(q.get('start_at', 0)) * 3600 * 24,
                        'scope': q.get('scope', None)})
        self._settings["quarantine"] = tmp  
        for m in lookup_helper.get_lookup_errors():
            self.config.add_error(m)

class GeneralXMLParser(xml.sax.ContentHandler):
    """This is a general SAX-based XML parser capable of generating
    callbacks once requested information has been parsed.  The cfg
    constructor parameter has the format::

      cfg = ((['tag1, 'tag1_1'], got_tag1_1_callback))

    Once parsing of tag1_1 has been completed, the callback function
    is called with the arguments dta, elem_stack.  elem_stack contains
    a list of (entity_name, attrs_dict) tuples up to the root XML
    node.  dta contains a list of (entity_name, attrs_dict, children)
    tuples inside the requested tag.  children has the same format as
    dta, thus if one use something like cfg = ((['root_tag'], cb)),
    the dta in the callback would contain a parsed tree of the entire
    XML file.

    The parser is only suitable for XML files that does not contain
    text parts outside the tags.
    """

    def __init__(self, cfg, xml_file):
        self._elementstack = []
        self.top_elementstack = []
        self.cfg = cfg
        self._in_dta = None

        parser = xml.sax.make_parser()
        parser.setContentHandler(self)
        # Don't resolve external entities
        try:
            parser.setFeature(xml.sax.handler.feature_external_ges, 0)
        except xml.sax._exceptions.SAXNotRecognizedException:
            # Older API versions don't try to handle external entities
            pass
        parser.parse(xml_file)

    def startElement(self, ename, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        ename = ename.encode('iso8859-1')
        self._elementstack.append(ename)
        if not self._in_dta:
            self.top_elementstack.append((ename, tmp))
            for loc, cb in self.cfg:
                if loc == self._elementstack:
                    self._in_dta = loc
                    self._cb = cb
                    self._start_pos = []
                    self._tmp_pos = self._start_pos
                    self._child_stack = [self._start_pos]
                    break
        else:
            children = []
            self._child_stack.append(children)
            self._tmp_pos.append((ename, tmp, children))
            self._tmp_pos = children

    def endElement(self, ename):
        if self._in_dta == self._elementstack:
            self._cb(self._start_pos, self.top_elementstack)
            self._in_dta = None
            self.top_elementstack.pop()
        elif not self._in_dta:
            self.top_elementstack.pop()
        else:
            self._child_stack.pop()
            if self._child_stack:
                self._tmp_pos = self._child_stack[-1]

        self._elementstack.pop()

    def dump_tree(dta, lvl=0):
        for ename, attrs, children in dta:
            print "%s%s %s" % (" " * lvl * 2, ename, attrs)
            GeneralXMLParser.dump_tree(children, lvl+1)
    dump_tree = staticmethod(dump_tree)

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

    profil_settings = ("stedkode", "gruppe", "spread", "disk", "mail",
                       "printer_kvote", "disk_kvote", "brev", "build",
                       "print_kvote_fritak", "print_betaling_fritak",
                       "priority", "quarantine")

    def __init__(self, config, cfg_file):
        cfg = ((['studconfig', 'default_values'], self.got_default_values),
               (['studconfig', 'disk_oversikt'], self.got_disk_oversikt),
               (['studconfig', 'gruppe_oversikt',], self.got_gruppe_oversikt),
               (['studconfig', 'spread_oversikt',], self.got_spread_oversikt),
               (['studconfig', 'profil',], self.got_profil),
               (['studconfig', 'disk_pools',], self.got_disk_pool),
               )
        self._config = config
        self._legal_groups = {}
        self.legal_spreads = {}
        GeneralXMLParser(cfg, cfg_file)

    def got_default_values(self, dta, elem_stack):
        for ename, attrs, children in dta:
            for a in attrs:
                self._config.default_values['%s_%s' % (ename, a)] = attrs[a]

    def got_disk_oversikt(self, dta, elem_stack):
        tmp_disk_spreads = []
        for ename, attrs, children in dta:
            if ename == 'disk_spread':
                s = int(self._config.lookup_helper.get_spread(attrs['kode']))
                tmp_disk_spreads.append(s)
                self._config.autostud.disk_tool.add_known_spread(s)
            elif ename == 'diskdef':
                if not tmp_disk_spreads:
                    raise ValueError, "DTD-violation: no disk_spread defined"
                attrs['max'] = attrs.get(
                    'max', elem_stack[-1][-1]['default_max'])
                attrs['auto'] = attrs.get(
                    'auto', elem_stack[-1][-1].get('default_auto', None))
                if not attrs['auto'] :
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
                    "Unexpected tag %s in disk_oversikt" % ename)

    def got_disk_pool(self, dta, elem_stack):
        for ename, attrs, children in dta:
            if ename == 'pool':
                for ename2, attrs2, children2 in children:
                    if ename2 == 'disk':
                        self._config.autostud.disk_tool.append_to_pool(
                            attrs['name'], **attrs2)
                        
    def got_gruppe_oversikt(self, dta, elem_stack):
        for ename, attrs, children in dta:
            if ename == 'gruppedef':
                self._legal_groups[attrs['navn']] = 1
                self._config.group_defs[attrs['navn']] = {
                    'auto': attrs.get('auto',
                                      elem_stack[-1][-1]['default_auto'])}
            else:
                self._config.add_error(
                    "Unexpected tag %s in gruppe_oversikt" % ename)
    
    def got_spread_oversikt(self, dta, elem_stack):
        for ename, attrs, children in dta:
            if ename == 'spreaddef':
                self._config.required_spread_order.append(
                    self._config.lookup_helper.get_spread(attrs['kode']))
                self.legal_spreads[attrs['kode']] = 1
            else:
                self._config.add_error(
                    "Unexpected tag %s in spread_oversikt" % ename)

    def got_profil(self, dta, elem_stack):
        in_profil = ProfileDefinition(
            self._config, elem_stack[-1][-1]['navn'], self._config._logger,
            super=elem_stack[-1][-1].get('super', None))

        for ename, attrs, children in dta:
            if ename in self.profil_settings:
                if ename == 'gruppe' and not self._legal_groups.has_key(
                    attrs['navn']):
                    self._config.add_error("Not in groupdef: %s" % \
                                           attrs['navn'])
                elif ename == 'spread' and not self.legal_spreads.has_key(
                    attrs['system']):
                    self._config.add_error("Not in spreaddef: %s" % \
                                           attrs['system'])
                elif ename == 'disk_kvote':
                    self._config.autostud.disk_tool.using_disk_kvote = True
                in_profil.add_setting(ename, attrs)
            elif ename == 'select':
                for ename2, attrs2, children2 in children:
                    if not ename2 in SelectTool.select_map_defs:
                        self._config.add_error(
                            "Unexpected tag '%s', attr=%s in %s" % (
                            ename2, str(attrs2), repr(elem_stack)))
                        continue
                    in_profil.add_selection_criteria(ename2, attrs2)
            else:
                self._config.add_error("Unexpected tag %s in %s" % (
                    ename, repr(self.elementstack)))
        self._config.profiles.append(in_profil)

# arch-tag: 8d52e58e-fdc3-456f-a9d0-7fe2d2281398
