# Copyright 2002, 2003 University of Oslo, Norway

import xml.sax
import re
from Cerebrum import Group

TOPICS_FILE="/cerebrum/dumps/FS/topics.xml"   # TODO: cereconf
STUDIEPROGS_FILE="/cerebrum/dumps/FS/studprog.xml"   # TODO: cereconf
STUDCONFIG_FILE="/cerebrum/uiocerebrum/etc/config/studconfig.xml"

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum import Disk
import pprint
pp = pprint.PrettyPrinter(indent=4)

class StudconfigParser(xml.sax.ContentHandler):
    """
    Parses the XML file.  The XML file consists of the following
    elements:
      - profil: defines a profile (a list of settings)
      - select: selects the entries which the profil will be applied to

    Creates two dicts:
    - profiles: contains profile definition data which should be
      post-processed by _MapStudconfigData
    - selection2profile: maps selection data to profile data

    Any profiles used as super must have been previously defined, and
    are applied after the profile with the super attribute has been
    applied, thus values from the current profile will appear before
    values from the super."""

    # The way this is currently used, we could also add profildef to
    # the kurs_elements list, however, this would complicate things if
    # we later decide to expand profiles when they are encountered.
    select_elements = ("studieprogram", "evu", "emne", "group")

    profil_settings = ("stedkode", "gruppe", "spread", "disk",
                       "printer_kvote", "disk_kvote", "nivå", "brev")

    def __init__(self, db):
        self.elementstack = []
        self.profiles = {}             # stores profildef's
        self.selection2profile = {}
        for e in self.select_elements:
            self.selection2profile[e] = {}
        self._in_profil = None
        self._in_select = None
        self._in_gruppe_oversikt = None
        self._in_disk_oversikt = None
        self.group_defs = {}
        self.disk_defs = {}
        self.db = db
        self._super = None

    def _apply_profile(self, profile, dest):
        for ename in profile.keys():
            dest.setdefault(ename, []).extend(profile[ename])

    def startElement(self, ename, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        ename = ename.encode('iso8859-1')
        self.elementstack.append(ename)

        if len(self.elementstack) == 2:
            if ename == 'profil':
                self._in_profil = tmp['navn']
                assert not self.profiles.has_key(self._in_profil)
                self.profiles[self._in_profil] = {}
                self._super = tmp.get('super', None)
            elif ename == 'gruppe_oversikt':
                self._in_gruppe_oversikt = 1
                self.default_group_auto = tmp['default_auto']
            elif ename == 'disk_oversikt':
                self._in_disk_oversikt = 1
                self.default_disk_max = tmp['default_max']
        elif self._in_gruppe_oversikt:
            if ename == 'gruppedef':
                self.group_defs[tmp['navn']] = {
                    'auto': tmp.get('auto', self.default_group_auto)}
            else:
                raise SyntaxWarning, "Unexpected tag %s in gruppedef" % ename
        elif self._in_disk_oversikt:
            if ename == 'diskdef':
                tmp['max'] = tmp.get('max', self.default_disk_max)
                if tmp.has_key('path'):
                    self.disk_defs.setdefault('path', {})[tmp['path']] = tmp
                else:
                    self.disk_defs.setdefault('prefix', {})[tmp['prefix']] = tmp
            else:
                raise SyntaxWarning, "Unexpected tag %s in diskdef" % ename
        elif self._in_profil:
            if len(self.elementstack) == 3:
                if ename == 'select':
                    self._in_select = 1
                elif ename in self.profil_settings:
                    self.profiles[self._in_profil].setdefault(ename, []).append(tmp)
                else:
                    raise SyntaxWarning, "Unexpected tag %s on in profil" % ename
            elif self._in_select and ename in self.select_elements:
                self.selection2profile[ename].setdefault(
                    tmp['id'], []).append(self._in_profil)
            else:
                raise SyntaxWarning, "Unexpected tag %s on in profil" % ename
        elif ename == 'config':
            pass
        else:
            raise SyntaxWarning, "Unexpected tag %s on in profil" % ename

    def endElement(self, ename):
        self.elementstack.pop()
        if self._in_select and ename == 'select':
            self._in_select = None
        elif self._in_profil and ename == 'profil':
            if self._super is not None:
                # Add data from super after data in the profile
                for k in self.profiles[self._super].keys():
                    self.profiles[self._in_profil].setdefault(
                        k, []).extend(self.profiles[self._super][k])
            self._in_profil = None
        elif self._in_gruppe_oversikt and ename == 'gruppe_oversikt':
            self._in_gruppe_oversikt = None
        elif self._in_disk_oversikt and ename == 'disk_oversikt':
            self._in_disk_oversikt = None
        elif len(self.elementstack) == 0 and ename == 'config':
            pass

class _MapStudconfigData(object):
    """Map data from StudconfigParser to cerebrum object ids etc."""
    
    def __init__(self, db, autostud):
        self.db = db
        self._sko_cache = {}
        self._group_cache = {}
        self._ou = Factory.get('OU')(self.db)
        self._group = Group.Group(self.db)
        self._autostud = autostud

    def mapData(self, dta):
        # pp.pprint(dta)
        for dtatype in dta.keys():
            for dtakey in dta[dtatype].keys():
                # print "%s" % dtakey
                if dtakey == 'spread':
                    nyspread = []
                    for s in dta[dtatype][dtakey]:
                        nyspread.append(self._get_spread(s['system']))
                    dta[dtatype][dtakey] = nyspread
                elif dtakey == 'stedkode':
                    nyesko = []
                    for s in dta[dtatype][dtakey]:
                          n = self._get_sko(s['verdi'])
                          if n is not None:
                              nyesko.append(n)
                    dta[dtatype][dtakey] = nyesko
                elif dtakey == 'gruppe':
                    nyegrupper = []
                    primargruppe = []
                    for f in dta[dtatype][dtakey]:
                        n = self._get_group(f['navn'])
                        if n is not None:
                            nyegrupper.append(n)
                            if f.get('type', '') == 'primary':
                                primargruppe.append(n)
                    dta[dtatype][dtakey] = nyegrupper 
                    dta[dtatype].setdefault('primargruppe',
                                            []).extend(primargruppe)
                elif dtakey == 'disk':
                    self._process_disks(dta[dtatype][dtakey])
                else:
                    pass

    def _process_disks(self, disks):
        """Map path entries to disk id, and assert that all used disks
        are defined in defdisk"""
        for d in disks:
            if d.has_key('path'):
                for d in self._autostud._disks.keys():
                    if self._autostud._disks[d][0] == self._disk['path']:
                        self._autostud.sp.disk_defs[
                            'path'][d] = self._autostud.sp.disk_defs[self._disk['path']]
                        self._disk['path'] = d
                    else:
                        self._autostud.sp.disk_defs[
                            'prefix'][d['prefix']]['max']
                self._autostud.sp.disk_defs[
                    'prefix'][cereconf.DEFAULT_HIGH_DISK['prefix']]['max']
                self._autostud.sp.disk_defs[
                    'prefix'][cereconf.DEFAULT_LOW_DISK['prefix']]['max']

    def _get_spread(self, name):
        # TODO: Map2const
        return name
                
    def _get_group(self, name):
        if self._group_cache.has_key(name):
            return self._group_cache[name]
        try:
            self._group.clear()
            self._group.find_by_name(name)
            self._group_cache[name] = int(self._group.entity_id)
        except (Errors.NotFoundError, ValueError):
            self._group_cache[name] = None
            print "ukjent gruppe: %s" % name
            pass
        return self._group_cache[name] 

    def _get_sko(self, name):
        #TODO: not quite right, remove once xml file is fixed
        name = name.replace("SV-student", "140000")
        name = name.replace("UV-student", "140000")
        name = name.replace("Jus-student", "140000")
        name = name.replace("MNF-student", "140000")
        name = name.replace("S", "0")
        if(int(name) > 300000):
            name = "140000"
        if self._sko_cache.has_key(name):
            return self._sko_cache[name]
        try:
            fak = int(name[:2])
            inst = int(name[2:4])
            gr = int(name[4:])
            self._ou.clear()
            self._ou.find_stedkode(fak, inst, gr)
            self._sko_cache[name] = int(self._ou.entity_id)
        except (Errors.NotFoundError, ValueError):
            self._sko_cache[name] = None
            print "ukjent sko: %s" % name
            pass
        return self._sko_cache[name]

class TopicsParser(xml.sax.ContentHandler):
    """Parses the topics file, storing data in an internal list.  The
    topics file is sorted by fødselsnummer"""

    def startElement(self, name, attrs):
        self.t_data = {}
        for k in attrs.keys():
            self.t_data[k.encode('iso8859-1')] = attrs[k.encode('iso8859-1')].encode('iso8859-1')

    def endElement(self, name):
        if name == "topic":
            self.topics.append(self.t_data)

    def __init__(self, history=None, fnr=None, topics_file=TOPICS_FILE):
        self.topics = []
        # Ugly memory-wasting, inflexible way:
        self.tp = self
        self.history = history
        self.fnr = fnr
        xml.sax.parse(topics_file, self.tp)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about all topics for the next person."""
        ret = []
        try:
            # TODO: etter gitte dato kriterier skal noen rader kastes
            # hvis fnr er satt, skal vi filtrere
            prev_fodselsdato = prev_personnr = None
            while 1:
                # print "X: %s" % str(self.tp.topics[0])
                if (prev_fodselsdato is None or
                    (self.tp.topics[0]['fodselsdato'] == prev_fodselsdato and
                    self.tp.topics[0]['personnr'] == prev_personnr)):
                    prev_fodselsdato = self.tp.topics[0]['fodselsdato']
                    prev_personnr = self.tp.topics[0]['personnr']
                    ret.append(self.tp.topics.pop(0))
                else:
                    return ret
            return ret
        except IndexError:
            if len(ret) > 0:
                return ret
            raise StopIteration, "End of file"

class StudieprogsParser(xml.sax.ContentHandler):
    """Parses the studieprogs file, storing data in an internal list.  The
    topics file is sorted by fødselsnummer"""

    # TBD: This code is very similar to the TopicsParser.  Unless the
    # format is likely to be changed, the classes should be merged
    # into one
    def startElement(self, name, attrs):
        self.t_data = {}
        for k in attrs.keys():
            self.t_data[k.encode('iso8859-1')] = attrs[k.encode('iso8859-1')].encode('iso8859-1')

    def endElement(self, name):
        if name == "studprog":
            self.studieprogs.append(self.t_data)

    def __init__(self, history=None, fnr=None, studieprogs_file=STUDIEPROGS_FILE):
        self.studieprogs = []
        # Ugly memory-wasting, inflexible way:
        self.sp = self
        self.history = history
        self.fnr = fnr
        xml.sax.parse(studieprogs_file, self.sp)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about all studieprogs for the next person."""
        ret = []
        try:
            # TODO: etter gitte dato kriterier skal noen rader kastes
            # hvis fnr er satt, skal vi filtrere
            prev_fodselsdato = prev_personnr = None
            while 1:
                if (prev_fodselsdato is None or
                    (self.sp.studieprogs[0]['fodselsdato'] == prev_fodselsdato and
                    self.sp.studieprogs[0]['personnr'] == prev_personnr)):
                    prev_fodselsdato = self.sp.studieprogs[0]['fodselsdato']
                    prev_personnr = self.sp.studieprogs[0]['personnr']
                    ret.append(self.sp.studieprogs.pop(0))
                else:
                    return ret
            return ret
        except IndexError:
            if len(ret) > 0:
                return ret
            raise StopIteration, "End of file"

class Profile(object):
    """Profile implements the logic that maps a persons topics (and
    optionaly groups) to the apropriate home, default group etc using
    rules read by the StudconfigParser
    """

    def __init__(self, autostud, topics, groups=None):
        """The logic for resolving conflicts and enumerating settings
        is similar for most attributes, thus we resolve the settings
        applicatble for this profile in the constructor
        """

        # topics may contain data from get_studieprog_list
        self._groups = groups
        self._autostud = autostud

        match_profiles = []
        topics.sort(self._topics_sort)
        if self._autostud.debug > 1:
            print " topics=%s" % ["%s:%s@%s" %
                                   (x.get('emnekode', ""), x['studienivakode'],
                                    x['studieprogramkode']) for x in topics]
        # First find the name of applicable profiles and their level
        for t in topics:
            if t.has_key('emnekode'):
                k = autostud.sp.selection2profile['emne'].get(t['emnekode'], None)
                if k is not None:
                    # TODO: sett nivåkode til nivåkode + 50 for å
                    #   implementere emne > studieprogram på samme nivåkode
                    match_profiles.append((k, 'emne'))
            k = autostud.sp.selection2profile['studieprogram'].get(
                t['studieprogramkode'], None)
            if k is not None:
                match_profiles.append((k, self._normalize_nivakode(t['studienivakode'])))
        if self._autostud.debug > 2:
            print " matches= %s" % match_profiles

        # Flatten settings, and group by level
        grouped_settings = {}           
        for m in match_profiles:
            profiles, level = m
            for profilname in profiles:
                profil = autostud.sp.profiles[profilname]
                for k in profil.keys():
                    lst = grouped_settings.setdefault(level, {}).setdefault(k, [])
                    for p in profil[k]:
                        if p not in lst:
                            lst.append(p)

        # Detect conflicts for singular values
        singular = ('disk', 'primargruppe', 'stedkode')
        levels = grouped_settings.keys()
        levels.sort(lambda a,b: cmp(b,a))
        singular_settings = {}
        self._flat_settings = {}           
        for lvl in levels:
            for k in profil.keys():
                lst = self._flat_settings.setdefault(k, [])
                for s in grouped_settings[lvl].get(k, []):
                    if s not in lst:
                        lst.append(s)
            for s in singular:
                if singular_settings.has_key(s):
                    continue
                # TODO: filter for <diskdef ... bygg="ja/nei"/>
                if len(grouped_settings[lvl].get(s, [])) > 1:
                    singular_settings[s] = lvl      # Conflict
                else:
                    singular_settings[s] = [lvl, grouped_settings[lvl][s]]

        try:
            # If there is a conflict, we choose the first
            self._dfg = self._flat_settings['primargruppe'][0]
        except (KeyError, IndexError):
            raise Errors.NotFoundError, "ingen primærgruppe"

        try:
            if type(singular_settings['stedkode']) is int:
                # TODO: Conflict for stedcode, what is correct behaviour?
                self._email_sko = self._flat_settings['stedkode'][0]
            else:
                self._email_sko = singular_settings['stedkode'][1][0]
        except (KeyError, IndexError):
            raise Errors.NotFoundError, "ingen primærsko"

        if not singular_settings.has_key('disk'):
            raise Errors.NotFoundError, "ingen disk"
        if type(singular_settings['disk']) is int:
            conflict_level = singular_settings['disk']
            if conflict_level >= 300:
                self._disk = cereconf.DEFAULT_HIGH_DISK
            else:
                self._disk = cereconf.DEFAULT_LOW_DISK
        else:
             self._disk = singular_settings['disk'][1][0]

    def _normalize_nivakode(self, niva):
        niva = int(niva)
        if niva >= 100 and niva < 300:
            niva = 100
        elif niva >= 300 and niva < 400:
            niva = 300
        return niva

    def _topics_sort(self, x, y):
        x = self._normalize_nivakode(x['studienivakode'])
        y = self._normalize_nivakode(y['studienivakode'])
        return cmp(y, x)
        
    def get_disk(self, current_disk=None):
        """Return a disk_id matching the current profile.  If the
        account already exists, current_disk should be set to assert
        that the user is not moved to a new disk with the same
        prefix. (i.e from /foo/bar/u11 to /foo/bar/u12)"""

        if current_disk is not None:
            if self._disk.has_key('path'):
                if self._disk['path'] == current_disk:
                    return current_disk
            else:
                disk_path = self._autostud._disks[int(current_disk)][0]
                if self._disk['prefix'] == disk_path[0:len(self._disk['prefix'])]:
                    return current_disk
        
        if self._disk.has_key('path'):
            # TBD: Should we ignore max_on_disk when path is explisitly set?
            return self._disk['path']

        dest_pfix = self._disk['prefix']
        max_on_disk = self._autostud.sp.disk_defs['prefix'][dest_pfix]['max']
        if max_on_disk == -1:
            max_on_disk = 999999
        for d in self._autostud._disks_order:
            tmp_path, tmp_count = self._autostud._disks[d]
            if (dest_pfix == tmp_path[0:len(dest_pfix)]
                and tmp_count < max_on_disk):
                return d
        raise ValueError, "Bad disk %s" % self._disk

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self._autostud._disks[int(old)][1] -= 1
        if new is not None:
            self._autostud._disks[new][1] += 1

    def get_stedkoder(self):
        return self._flat_settings['stedkode']

    def get_dfg(self):
        return self._dfg

    def get_email_sko(self):
        return self._email_sko
    
    def get_grupper(self):
        return self._flat_settings['gruppe']


    def get_pquota(self):
        assert self._groups is not None
        for m in self._flat_settings.get('printer_kvote', []):
            pass # TODO
        raise NotImplementedError, "TODO"
        
class AutoStud(object):
    """This is the only class that should be directly accessed within
    this package"""
    
    def __init__(self, db, cfg_file=STUDCONFIG_FILE, debug=0):
        self.debug = debug
        self._disks = {}
        disk = Disk.Disk(db)
        for d in disk.list():
            self._disks[int(d['disk_id'])] = [d['path'], int(d['count'])]
        self._disks_order = self._disks.keys()
        self._disks_order.sort(self._disk_sort)
        self.sp = StudconfigParser(db)
        xml.sax.parse(cfg_file, self.sp)
        m = _MapStudconfigData(db, self)
        m.mapData(self.sp.profiles)

        if debug > 2:
            print "Parsed studconfig.xml expanded to: "
            pp.pprint(self.sp.selection2profile)

    def _disk_sort(self, x, y):
        regexp = re.compile(r"^(\D+)(\d*)")
        m_x = regexp.match(self._disks[x][0])
        m_y = regexp.match(self._disks[y][0])
        pre_x, num_x = m_x.group(1), m_x.group(2)
        pre_y, num_y = m_y.group(1), m_y.group(2)
        if pre_x <> pre_y:
            return cmp(pre_x, pre_y)
        return cmp(int(num_x), int(num_y))

    def get_topics_list(self, history=None, fnr=None, topics_file=None):
        """Use like:
          for topics in foo.get_topics_list:

        topics will contain a list of dicts with lines from the topics
        file for one person.  If fnr is not None, only lines for a
        given user is returned."""
        if topics_file is None:
            return TopicsParser(fnr=fnr, history=history)
        return TopicsParser(fnr=fnr, history=history, topics_file=topics_file)

    def get_studieprog_list(self, studieprogs_file=None):
        if studieprogs_file is None:
            return StudieprogsParser()
        return StudieprosParser(studieprogs_file=studieprogs_file)

    def get_profile(self, topics, groups=None):
        """Returns a Profile object matching the topics, to check
        quotas, groups must also be set."""
        return Profile(self, topics, groups)
