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
        self.disk_spreads = {}  # defined <disk_spread> tags
        self.group_defs = {}
        self.known_select_criterias = {'medlem_av_gruppe': {},
                                       'person_affiliation': {}}
        self.default_values = {}
        self.profiles = []
        self.required_spread_order = []
        self.lookup_helper = LookupHelper(autostud.db, logger, autostud.ou_perspective)
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

        # Generate select_mapping dict and expand super profiles
        profilename2profile = {}
        self.select_mapping = {}
        self.using_priority = False
        for p in self.profiles:
            if profilename2profile.has_key(p.name):
                self.add_error("Duplicate profile-name %s" % p.name)
            profilename2profile[p.name] = p
            p.expand_profile_settings()
            p.convertToDatabaseRefs(self.lookup_helper, self)
            p.set_select_mapping(self.select_mapping)
            if p.priority is not None:
                self.using_priority=True
        for p in self.profiles:
            p.expand_super(profilename2profile)
            p.settings["spread"] = self._sort_spreads(p.settings["spread"])
            if self.using_priority and p.priority is None:
                self.add_error("Priority used, but not defined for %s" % \
                               p.name)
        # Change keys in group_defs from name to entity_id
        pg = PosixGroup.PosixGroup(autostud.db)
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
            logger.fatal("The configuration file has errors, refusing to "
                         "continue: \n%s" % "\n".join(self._errors))
            sys.exit(1)

    def debug_dump(self):
        ret = "Mapping of select-criteria to profile:\n"
        ret += pp.pformat(self.select_mapping)
        ret += "Profile definitions:"
        for p in self.profiles:
            ret += p.debug_dump()+"\n"
        return ret

    def _sort_spreads(self, spreads):
        """On some sites certain spreads requires other spreads, thus
        we must sort them """
        ret = []
        for s in self.required_spread_order:
            if s in spreads:
                ret.append(s)
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
        self.settings = {}
        self.selection_criterias = {}
        self.priority = None

    def __repr__(self):
        return "Profile object(%s)" % self.name

    def expand_profile_settings(self):
        pass
    
    def expand_super(self, name2profile):
        """Recursively add all settings from parent profiles so that
        we can remove the reference to super."""
        if self.super is not None:
            if not name2profile.has_key(self.super):
                self.config.add_error("Illegal super '%s' for '%s'" % (
                    self.super, self.name))
            tmp_super = name2profile[self.super]
            tmp_super.expand_super(name2profile)
            for k in tmp_super.settings.keys():
                if k == 'disk' and self.settings.has_key(k):
                    break  # We're not interested in disks from super
                self.settings.setdefault(k, []).extend(tmp_super.settings[k])
            if self.priority is None and tmp_super.priority is not None:
                self.priority = tmp_super.priority
            if self.priority != tmp_super.priority:
                self.config.add_error("priority diff in %s vs %s (%s/%s)" % (
                    self.name, tmp_super.name, self.priority,
                    tmp_super.priority))
            self.super = None

    def set_select_mapping(self, mapping):
        """Expands the select mapping (in Config) to map to this
        profile for apropriate select criterias.  The format of the
        mapping is like:

         {'aktiv': {
           'studieprogram': {
             'AKSU6117': [ Profile object(TF_høyeregrad)]}}}
        """
        for select_type in self.selection_criterias.keys():
            for s_criteria in self.selection_criterias[select_type]:
                map_data = StudconfigParser.select_map_defs[select_type]
                if map_data[0] == StudconfigParser.NORMAL_MAPPING:
                    tmp = s_criteria.get(map_data[1], None)
                    mapping.setdefault(select_type, {}).setdefault(
                        map_data[1], {}).setdefault(tmp, []).append(self)
                elif map_data[0] == StudconfigParser.SPECIAL_MAPPING:
                    if select_type in('aktivt_sted', 'evu_sted'):
                        # nivaa is not used by evu_sted, but it doesn't hurt
                        # to include it
                        tmp = ":".join((s_criteria['stedkode'],
                                        s_criteria['institusjon'],
                                        s_criteria['scope'],
                                        s_criteria.get('nivaa_min', ''),
                                        s_criteria.get('nivaa_max', '')))
                        tmp = mapping.setdefault(
                            select_type, {}).setdefault(tmp, {})
                        tmp.setdefault('profiles', []).append(self)
                        if not tmp.has_key('steder'):
                            tmp['steder'] = self._get_steder(
                                s_criteria['institusjon'],
                                s_criteria['stedkode'],
                                s_criteria['scope'])
                        tmp['nivaa_min'] = s_criteria.get('nivaa_min', None)
                        tmp['nivaa_max'] = s_criteria.get('nivaa_max', None)
                    elif select_type == 'medlem_av_gruppe':
                        mapping.setdefault(
                            select_type, {}).setdefault(s_criteria['group_id'], []).append(self)
                    elif select_type == 'person_affiliation':
                        mapping.setdefault(
                            select_type, {}).setdefault((
                            s_criteria['affiliation_id'], s_criteria['status_id']), []).append(self)
                    elif select_type == 'match_any':
                        mapping.setdefault(
                            select_type, []).append(self)
                    else:
                        self.config.add_error(
                            "Unknown special mapping %s" % select_type)

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
            self.settings.setdefault("primarygroup", []).append(attribs)
        self.settings.setdefault(name, []).append(attribs)

    def add_selection_criteria(self, name, attribs):
        self.selection_criterias.setdefault(name, []).append(attribs)

    def debug_dump(self):
        return "Profile name: '%s', p=%s, settings:\n%s" % (
            self.name, self.priority, pp.pformat(self.settings))

    #
    # methods for converting the XML entries to values from the database
    #

    def _convert_disk_settings(self, config):
        """Update self.settings["disk"] so that it looks like:
        [{spread1: {Either:  'path': int(disk_id),
                    Or:      'prefix': 'prefix'}},
          spread2: {....}]"""

        tmp = {}
        for disk in self.settings.get("disk", []):
            try:
                for t in ('prefix', 'path'):
                    if disk.has_key(t): # Assert that disk is in disk_defs
                        try:
                            config.disk_defs[t][disk[t]]
                        except KeyError:
                            self.config.add_error(
                                "bad disk: %s=%s" % (t, disk[t]))
                            self.settings['disk'].remove(disk)
                            raise  # python should have labeled break/continue
            except KeyError:
                continue
                    
            if disk.has_key('path'):    # Store disk-id as path
                ok = False
                for d in config.autostud.disks.keys():
                    if config.autostud.disks[d][0] == disk['path']:
                        disk['path'] = d
                        ok = True
                if not ok:
                    self.config.add_error("bad disk: %s" % disk)
                    self.settings['disk'].remove(disk)
                    continue

            # We're only interested in the first disk for each single
            # spread.  This allows a sub-profile to override the home
            # in its super without interpreting the target as a 'div
            # disk'

            for s in disk['spreads']:
                if not tmp.has_key(s):
                    for t in ('prefix', 'path'):
                        if disk.has_key(t):
                            tmp[s] = {t: disk[t]}
        if not tmp:
            tmp = []
        else:
            self.settings["disk"] = [tmp]

    def convertToDatabaseRefs(self, lookup_helper, config):
        for p in self.settings.get("priority", []):
            if self.priority is not None and self.priority != int(p['level']):
                self.config.add_error(
                    "Conflicting priorities in %s" % self.name)
            self.priority = int(p['level'])
        if self.priority is not None:
            del(self.settings['priority'])
        tmp = []
        for spread in self.settings.get("spread", []):
            tmp.append(lookup_helper.get_spread(spread['system']))
        self.settings["spread"] = tmp
        tmp = []
        for group in self.settings.get("gruppe", []):
            # TODO: Should assert that entry is in group_defs
            tmp.append(lookup_helper.get_group(group['navn']))
        self.settings["gruppe"] = tmp  
        tmp = []
        for group in self.settings.get("primarygroup", []):
            tmp.append(lookup_helper.get_group(group['navn']))
        self.settings["primarygroup"] = tmp  
        tmp = []
        for stedkode in self.settings.get("stedkode", []):
            tmp2 = lookup_helper.get_stedkode(stedkode['verdi'],
                                              stedkode['institusjon'])
            if tmp2 is not None:
                tmp.append(tmp2)
        self.settings["stedkode"] = tmp
        tmp = []
        for q in self.settings.get("quarantine", []):
            tmp.append({'quarantine': config.autostud.co.Quarantine(q['navn']),
                        'start_at': int(q.get('start_at', 0)) * 3600 * 24})
        self.settings["quarantine"] = tmp  

        self._convert_disk_settings(config)

        tmp = []
        for group in self.selection_criterias.get("medlem_av_gruppe", []):
            id = lookup_helper.get_group(group['navn'])
            if id:
                tmp.append({'group_id': id })
                config.known_select_criterias['medlem_av_gruppe'][group['navn']] = id
        self.selection_criterias["medlem_av_gruppe"] = tmp  
        
        tmp = []
        for aff_info in self.selection_criterias.get("person_affiliation", []):
            affiliation = config.autostud.co.PersonAffiliation(
                aff_info['affiliation'])
            if not aff_info.has_key('status'):
                for aff_status in config.autostud.co.fetch_constants(
                    config.autostud.co.PersonAffStatus):
                    tmp.append({'affiliation_id': int(affiliation),
                                'status_id': int(aff_status)})
            else:
                aff_status = config.autostud.co.PersonAffStatus(affiliation,
                                                                aff_info['status'])
                tmp.append({'affiliation_id': int(affiliation), 
                            'status_id': int(aff_status)})
        self.selection_criterias["person_affiliation"] = tmp
        for t in tmp:
            config.known_select_criterias['person_affiliation'][
                (t['affiliation_id'], t['status_id'])] = True

        # Find all student disks from disk_defs
        for k in ('path', 'prefix'):
            for ddef in config.disk_defs.get(k, {}).keys():
                path = config.disk_defs[k][ddef].get('path', None)
                prefix = config.disk_defs[k][ddef].get('prefix', None)
                for d in config.autostud.disks.keys():
                    v = config.autostud.disks[d]
                    if path:
                        if path == v[0]:
                            config.autostud.student_disk[d] = 1
                    else:
                        if v[0][:len(prefix)] == prefix:
                            config.autostud.student_disk[d] = 1

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

    NORMAL_MAPPING='*NORMAL_FLAG*'
    SPECIAL_MAPPING='*SPECIAL_FLAG*'
    # select_map_defs defines how to determine if data in
    # merged_persons.xml matches a select criteria in studconfig.xml
    #
    # With NORMAL_MAPPING, a '*' will match any entry.  If other
    # special processing should occour, the SPECIAL_MAPPING flag must
    # be set, and relevant code added to
    # ProfileHandler.ProfileMatcher and ProfileDefinition.set_select_mapping
    select_map_defs = {
        ## SX = studconfig.xml, MX = merged_persons.xml
        ## <SX:select-tag>: [MAPPING_TYPE, <SX:match-attribute>,
        ##                   <MX:studinfo-tag>, [<MX:match-attribute>]]
        ## match-attributes are OR'ed
        ##
        ## When MAPPING_TYPE != NORMAL_MAPPING, the rest of the
        ## corresponding values may depend on the specific
        ## implemetation for the SPECIAL_MAPPING

        "tilbud": [NORMAL_MAPPING, 'studieprogram', 'tilbud',
                   ['studieprogramkode']],
        "studierett": [NORMAL_MAPPING, 'studieprogram', 'opptak',
                       ['studieprogramkode', 'status']],
        "aktiv": [NORMAL_MAPPING, 'studieprogram', 'aktiv',
                  ['studieprogramkode']],
        "privatist_studieprogram": [NORMAL_MAPPING, 'studieprogram',
                                    'privatist_studieprogram',
                                    ['studieprogramkode']],
        "emne": [NORMAL_MAPPING, 'emnekode', 'eksamen', ['emnekode']],
        "privatist_emne": [NORMAL_MAPPING, 'emnekode',
                           'privatist_emne', ['emnekode']],
        "aktivt_sted": [SPECIAL_MAPPING, 'stedkode', 'aktiv',
                        'studieprogramkode'],
        "evu_sted": [SPECIAL_MAPPING, 'stedkode', 'evu',
                        'studieprogramkode'],
        "medlem_av_gruppe": [SPECIAL_MAPPING],
        "person_affiliation": [SPECIAL_MAPPING],
        "match_any": [SPECIAL_MAPPING],
        }

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
                self._tmp_disk_spreads = []
            elif ename == 'default_values':
                pass
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
                tmp['spreads'] = self._tmp_disk_spreads
                if tmp.has_key('path'):
                    self._config.disk_defs.setdefault('path', {})[tmp['path']] = tmp
                else:
                    self._config.disk_defs.setdefault('prefix', {})[tmp['prefix']] = tmp
            else:
                self._config.add_error(
                    "Unexpected tag %s in disk_oversikt" % ename)
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
                    elif ename == 'disk':
                        try:
                            if tmp.has_key('path'):
                                tmp['spreads'] = self._config.disk_defs[
                                    'path'][tmp['path']]['spreads']
                            else:
                                tmp['spreads'] = self._config.disk_defs[
                                    'prefix'][tmp['prefix']]['spreads']
                        except KeyError:
                            self._config.add_error(
                                "Tried to use not-defined disk: %s" % tmp)
                    self._in_profil.add_setting(ename, tmp)
                else:
                    self._config.add_error("Unexpected tag %s in %s" % (
                        ename, repr(self.elementstack)))
            elif (len(self.elementstack) == 4 and
                  self.elementstack[2] == 'select' and
                  ename in self.select_map_defs):
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
