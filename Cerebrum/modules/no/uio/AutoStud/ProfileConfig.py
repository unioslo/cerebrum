"""This module provides method for parsing the studconfig.xml file and
translating it to an internal datastructure"""

import xml.sax
import pprint
from Cerebrum.modules.no.uio.AutoStud.Util import LookupHelper

class Config(object):
    def __init__(self, autostud, logger, cfg_file=None, debug=0):
        self.debug = debug
        self.autostud = autostud
        self._logger = logger
        
        sp = StudconfigParser(self)
        self.disk_defs = {}
        self.group_defs = {}
        self.profiles = []
        xml.sax.parse(cfg_file, sp)

        # Generate select_mapping dict and expand super profiles
        lookup_helper = LookupHelper(autostud.db, logger)
        profilename2profile = {}
        self.select_mapping = {}
        for p in self.profiles:
            profilename2profile[p.name] = p
            p.expand_profile_settings()
            p.convertToDatabaseRefs(lookup_helper, self)
            p.set_select_mapping(self.select_mapping)
        for p in self.profiles:
            p.expand_super(profilename2profile)

    def debug_dump(self):
        ret = "Mapping of select-criteria to profile:\n"
        ret += self._logger.pformat(self.select_mapping)
        ret += "Profile definitions:"
        for p in self.profiles:
            ret += p.debug_dump()

    def get_matching_profiles(self, select_type, select_key, entry_value):
        """Return a list of ProfileDefinition objects that matches
        this select criteria."""
        
        ret = self.select_mapping.get(select_type, {}).get(
            select_key, {}).get(entry_value, None)
        self._logger.debug("Check matches for %s / %s / %s -> %s" % (
            select_type, select_key, entry_value, str(ret)))
        return ret
        
class ProfileDefinition(object):
    """Represents a profile as defined in the studconfig.xml file"""
    
    def __init__(self, name, logger, super=None):
        self.name = name
        self.super = super
        self._logger = logger
        self.settings = {}
        self.selection_criterias = {}

    def __repr__(self):
        return "Profile object(%s)" % self.name

    def expand_profile_settings(self):
        pass
    
    def expand_super(self, name2profile):
        """Recursively add all settings from parent profiles so that
        we can remove the reference to super."""
        if self.super is not None:
            if not name2profile.has_key(self.super):
                raise KeyError, "Illegal super '%s' for '%s'" % (self.super, self.name)
            tmp_super = name2profile[self.super]
            tmp_super.expand_super(name2profile)
            for k in tmp_super.settings.keys():
                self.settings.setdefault(k, []).extend(tmp_super.settings[k])
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
                for use_id in StudconfigParser.select_elements[select_type]:
                    tmp = s_criteria.get(use_id, None)
                    if tmp is not None:
                        mapping.setdefault(select_type, {}).setdefault(
                            use_id, {}).setdefault(tmp, []).append(self)

    def add_setting(self, name, attribs):
        if name == "gruppe" and attribs.get("type", None) == "primary":
            self.settings.setdefault("primarygroup", []).append(attribs)
        self.settings.setdefault(name, []).append(attribs)

    def add_selection_criteria(self, name, attribs):
        self.selection_criterias.setdefault(name, []).append(attribs)

    def debug_dump(self):
        return "Profile name: '%s', settings:\n%s" % (
            self.name, self._logger.pformat(self.settings))

    #
    # methods for converting the XML entries to values from the database
    #

    def convertToDatabaseRefs(self, lookup_helper, config):
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
            tmp.append(lookup_helper.get_stedkode(stedkode['verdi']))
        self.settings["stedkode"] = tmp
        tmp = []
        for disk in self.settings.get("disk", []):
            tmp = [disk]
            for t in ('prefix', 'path'):
                if disk.has_key(t): # Assert that disk is in disk_defs
                    try:
                        config.disk_defs[t][disk[t]]
                    except KeyError:
                        self._logger.warn("bad disk: %s=%s" % (t, disk[t]))
            if disk.has_key('path'):    # Store disk-id as path
                for d in config.autostud.disks.keys():
                    if config.autostud.disks[d][0] == disk['path']:
                        disk['path'] = d
            break   # Only interested in the first disk
        self.settings["disk"] = tmp
                
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

    select_elements = {"aktiv": ['studieprogram'],
                       "privatist_emne": ['emne', 'studieprogram'],
                       "privatist_studieprogram": ['studieprogram'],
                       "fagperson": ['stedkode'],
                       "tilbud": ['studieprogram'],
                       "opptak": ['studieprogram'],
                       "alumni": ['studieprogram'],
                       "permisjon": ['fraverskode'],
                       "evu": ['stedkode'],
                       "regkort": [],
                       "eksamen": ['emne']}

    def get_value_for_select_id(entry, id_type):
        """The ids in StudconfigParser.select_elements sometimes
        points to entries that are not directly represented in the FS
        dump.  This method extracts the value of the requested type
        from an entry from FS """

        if(id_type == 'studieprogram'):
            return entry.get('studieprogramkode', None)
        if(id_type == 'emne'):
            return entry.get('emnekode', None)
        if(id_type == 'stedkode'):   # TODO
            return None
        raise ValueError, "Bad id_type %s" % id_type

    get_value_for_select_id = staticmethod(get_value_for_select_id)

    profil_settings = ("stedkode", "gruppe", "spread", "disk", "mail",
                       "printer_kvote", "disk_kvote", "nivå", "brev", "build")

    def __init__(self, config):
        self.elementstack = []
        self._config = config
        self._in_profil = None
        self._in_select = None
        self._in_gruppe_oversikt = None
        self._in_disk_oversikt = None
        self._super = None

    def startElement(self, ename, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        ename = ename.encode('iso8859-1')
        self.elementstack.append(ename)

        if len(self.elementstack) == 2:
            if ename == 'profil':
                self._in_profil = ProfileDefinition(
                    tmp['navn'], self._config._logger, super=tmp.get('super', None))
                self._config.profiles.append(self._in_profil)
            elif ename == 'gruppe_oversikt':
                self._in_gruppe_oversikt = 1
                self._default_group_auto = tmp['default_auto']
            elif ename == 'disk_oversikt':
                self._in_disk_oversikt = 1
                self._default_disk_max = tmp['default_max']
        elif self._in_gruppe_oversikt:
            if ename == 'gruppedef':
                self._config.group_defs[tmp['navn']] = {
                    'auto': tmp.get('auto', self._default_group_auto)}
            else:
                raise SyntaxWarning, "Unexpected tag %s in gruppedef" % ename
        elif self._in_disk_oversikt:
            if ename == 'diskdef':
                tmp['max'] = tmp.get('max', self._default_disk_max)
                if tmp.has_key('path'):
                    self._config.disk_defs.setdefault('path', {})[tmp['path']] = tmp
                else:
                    self._config.disk_defs.setdefault('prefix', {})[tmp['prefix']] = tmp
            else:
                raise SyntaxWarning, "Unexpected tag %s in diskdef" % ename
        elif self._in_profil:
            if len(self.elementstack) == 3:
                if ename == 'select':
                    self._in_select = 1
                elif ename in self.profil_settings:
                    self._in_profil.add_setting(ename, tmp)
                else:
                    raise SyntaxWarning, "Unexpected tag %s on in profil" % ename
            elif self._in_select and ename in self.select_elements:
                self._in_profil.add_selection_criteria(ename, tmp)
            else:
                raise SyntaxWarning, "Unexpected tag %s on in profil" % ename
        elif ename == 'config':
            pass
        elif ename in ('spreaddef',):
            pass
        else:
            raise SyntaxWarning, "Unexpected tag %s on in profil" % ename

    def endElement(self, ename):
        self.elementstack.pop()
        if self._in_select and ename == 'select':
            self._in_select = None
        elif self._in_profil and ename == 'profil':
            self._in_profil = None
        elif self._in_gruppe_oversikt and ename == 'gruppe_oversikt':
            self._in_gruppe_oversikt = None
        elif self._in_disk_oversikt and ename == 'disk_oversikt':
            self._in_disk_oversikt = None
        elif len(self.elementstack) == 0 and ename == 'config':
            pass
