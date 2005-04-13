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
        
        self.disk_defs = {}
        self.disk_pools = {}
        self.disk_spreads = {}  # defined <disk_spread> tags
        self.group_defs = {}
        self.default_values = {}
        self.profiles = []
        self.profilename2profile = {}
        self.required_spread_order = []
        self.lookup_helper = LookupHelper(autostud.db, logger, autostud.ou_perspective)
        self.using_disk_kvote = False
        sp = StudconfigParser(self)
        parser = xml.sax.make_parser()
        parser.setContentHandler(sp)
        # Don't resolve external entities
        try:
            parser.setFeature(xml.sax.handler.feature_external_ges, 0)
        except xml.sax._exceptions.SAXNotRecognizedException:
            # Older API versions don't try to handle external entities
            pass
        try:
            parser.parse(cfg_file)
        except:
            if self._errors:
                logger.fatal("Got the following errors, and a stack trace: \n"
                             "%s" % "\n".join(self._errors))
            raise
        self.spread_defs = [int(autostud.co.Spread(x)) for x in sp.legal_spreads.keys()]
        self._post_process_config()

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
        ret += "Pools:\n"
        ret += pp.pformat(self.disk_pools)
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
                if k == 'disk' and self._settings.has_key(k):
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

    def _convert_disk_settings(self, config):
        """Update self._settings["disk"] so that it looks like:
        [{spread1: {Either:  'path': int(disk_id),
                    Or:      'prefix': 'prefix'
                    Or:      'pool': 'pool'}},
          spread2: {....}]"""


        def _convert_data(disk):
            """Update 'spreads' and 'path' attributes, and return
            disk-spreads for this disk."""
            # Add 'spreads' attr to disk-setting
            ret = []
            for t in ('path', 'prefix'):
                if disk.has_key(t):
                    try:
                        disk['spreads'] = config.disk_defs[
                            t][disk[t]]['spreads']
                        ret.extend(disk['spreads'])
                    except KeyError:
                        config.add_error(
                            "Tried to use not-defined disk: %s" % disk)
            # Convert 'path'-attrs to disk-id
            if disk.has_key('path'):
                ok = False
                for d in config.autostud.disks.keys():
                    if config.autostud.disks[d][0] == disk['path']:
                        disk['path'] = d
                        ok = True
                if not ok:
                    self.config.add_error("bad disk: %s" % disk)
            return ret

        for d in self._settings.get("disk", []):
            if d.has_key('pool'):
                tmp_spreads = []
                for d2 in config.disk_pools[d['pool']]:
                    tmp_spreads.extend(_convert_data(d2))
                d['spreads'] = dict([(t, 0) for t in tmp_spreads]).keys()
            else:
                _convert_data(d)
        if config._errors:
            return

        tmp = {}
        for disk in self._settings.get("disk", []):
            # We're only interested in the first disk for each single
            # spread.  This allows a sub-profile to override the home
            # in its super without interpreting the target as a 'div
            # disk'

            for s in disk['spreads']:
                if not tmp.has_key(s):
                    for t in ('prefix', 'path', 'pool'):
                        if disk.has_key(t):
                            tmp[s] = {t: disk[t]}
        if not tmp:
            tmp = []
        else:
            self._settings["disk"] = [tmp]

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
        for q in self._settings.get("quarantine", []):
            tmp.append({'quarantine': config.autostud.co.Quarantine(q['navn']),
                        'start_at': int(q.get('start_at', 0)) * 3600 * 24,
                        'scope': q.get('scope', None)})
        self._settings["quarantine"] = tmp  

        self._convert_disk_settings(config)

        # Find all student disks from disk_defs
        for k in ('path', 'prefix'):
            for ddef in config.disk_defs.get(k, {}).keys():
                path = config.disk_defs[k][ddef].get('path', None)
                prefix = config.disk_defs[k][ddef].get('prefix', None)
                for d in config.autostud.disks.keys():
                    v = config.autostud.disks[d]
                    if path:
                        if path == v[0]:
                            config.autostud.student_disk[d] = config.disk_defs[k][ddef]
                    else:
                        if v[0][:len(prefix)] == prefix:
                            config.autostud.student_disk[d] = config.disk_defs[k][ddef]

        for m in lookup_helper.get_lookup_errors():
            self.config.add_error(m)
                
class StudconfigParser(xml.sax.ContentHandler):
    """
    Parses the studconfig XML file.  The XML file consists of the
    following elements:
      - profil: defines a profile (a list of settings)
      - select: selects the entries which the profil will be applied to

    Any profiles used as super must have been previously defined, and
    are applied after the profile with the super attribute has been
    applied, thus values from the current profile will appear before
    values from the super."""

    profil_settings = ("stedkode", "gruppe", "spread", "disk", "mail",
                       "printer_kvote", "disk_kvote", "brev", "build",
                       "print_kvote_fritak", "print_betaling_fritak",
                       "priority", "quarantine")

    def __init__(self, config):
        self.elementstack = []
        self._config = config
        self._super = None
        self.legal_spreads = {}
        self._legal_groups = {}
        self._in_profil = None

    def startElement(self, ename, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        ename = ename.encode('iso8859-1')
        self.elementstack.append(ename)

        if len(self.elementstack) == 1 and ename == 'studconfig':
            pass
        elif len(self.elementstack) == 2:
            if ename == 'profil':
                self._in_profil = ProfileDefinition(self._config,
                    tmp['navn'], self._config._logger, super=tmp.get('super', None))
                self._config.profiles.append(self._in_profil)
            elif ename == 'gruppe_oversikt':
                self._default_group_auto = tmp['default_auto']
            elif ename == 'disk_oversikt':
                self._default_disk_max = tmp['default_max']
                self._default_auto = tmp.get('default_auto', None)
                self._default_disk_kvote = tmp.get(
                    'default_disk_kvote',
                    self._config.default_values.get('disk_kvote_value', None))
                self._tmp_disk_spreads = []
            elif ename in ('default_values', 'disk_pools', 'spread_oversikt'):
                pass
            else:
                raise ValueError, "DTD-violation: unknown tag: %s" % self.elementstack
        elif len(self.elementstack) == 3 and self.elementstack[1] == 'default_values':
            for k in tmp.keys():
                self._config.default_values['%s_%s' % (ename, k)] = tmp[k]
            pass
        elif len(self.elementstack) == 3 and self.elementstack[1] == 'spread_oversikt':
            if ename == 'spreaddef':
                self._config.required_spread_order.append(
                    self._config.lookup_helper.get_spread(tmp['kode']))
                self.legal_spreads[tmp['kode']] = 1
            else:
                self._config.add_error(
                    "Unexpected tag %s in spread_oversikt" % ename)
        elif len(self.elementstack) == 3 and self.elementstack[1] == 'gruppe_oversikt':
            if ename == 'gruppedef':
                self._legal_groups[tmp['navn']] = 1
                self._config.group_defs[tmp['navn']] = {
                    'auto': tmp.get('auto', self._default_group_auto)}
            else:
                self._config.add_error(
                    "Unexpected tag %s in gruppe_oversikt" % ename)
        elif len(self.elementstack) == 3 and self.elementstack[1] == 'disk_oversikt':
            if ename == 'disk_spread':
                s = int(self._config.lookup_helper.get_spread(tmp['kode']))
                self._tmp_disk_spreads.append(s)
                self._config.disk_spreads[s] = 1
            elif ename == 'diskdef':
                if not self._tmp_disk_spreads:
                    raise ValueError, "DTD-violation: no disk_spread defined"
                tmp['max'] = tmp.get('max', self._default_disk_max)
                tmp['auto'] = tmp.get('auto', self._default_auto)
                if not tmp['auto'] :
                    self._config.add_error(
                        "Missing auto attribute for %s" % repr(tmp))
                tmp['disk_kvote'] = tmp.get('disk_kvote', self._default_disk_kvote)
                if tmp['disk_kvote'] is not None:
                    self._config.using_disk_kvote = True
                tmp['spreads'] = self._tmp_disk_spreads
                if tmp.has_key('path'):
                    self._config.disk_defs.setdefault('path', {})[tmp['path']] = tmp
                else:
                    self._config.disk_defs.setdefault('prefix', {})[tmp['prefix']] = tmp
            else:
                self._config.add_error(
                    "Unexpected tag %s in disk_oversikt" % ename)
        elif self.elementstack[1] == 'disk_pools':
            if len(self.elementstack) == 3 and ename == 'pool':
                self._tmp_pool_name = tmp['name']
                self._config.disk_pools[self._tmp_pool_name] = []
            elif len(self.elementstack) == 4 and ename == 'disk':
                self._config.disk_pools[self._tmp_pool_name].append(tmp)
        elif self._in_profil:
            if len(self.elementstack) == 3:
                if ename == 'select':
                    pass
                elif ename in self.profil_settings:
                    if ename == 'gruppe' and not self._legal_groups.has_key(tmp['navn']):
                        self._config.add_error("Not in groupdef: %s" % \
                                               tmp['navn'])
                    elif ename == 'spread' and not self.legal_spreads.has_key(tmp['system']):
                        self._config.add_error("Not in spreaddef: %s" % \
                                               tmp['system'])
                    elif ename == 'disk_kvote':
                        self._config.using_disk_kvote = True
                    self._in_profil.add_setting(ename, tmp)
                else:
                    self._config.add_error("Unexpected tag %s in %s" % (
                        ename, repr(self.elementstack)))
            elif (len(self.elementstack) == 4 and
                  self.elementstack[2] == 'select' and
                  ename in SelectTool.select_map_defs):
                if (ename == 'medlem_av_gruppe' and
                    not self._legal_groups.has_key(tmp['navn'])):
                    self._config.add_error("Not in groupdef: %s" % \
                                           tmp['navn'])
                self._in_profil.add_selection_criteria(ename, tmp)
            else:
                self._config.add_error("Unexpected tag '%s', attr=%s in %s" % (
                    ename, str(tmp), repr(self.elementstack)))
        else:
            self._config.add_error("Unexpected tag %s in %s" % (
                ename, repr(self.elementstack)))

    def endElement(self, ename):
        self.elementstack.pop()
        if self._in_profil and ename == 'profil':
            self._in_profil = None

# arch-tag: 8d52e58e-fdc3-456f-a9d0-7fe2d2281398
