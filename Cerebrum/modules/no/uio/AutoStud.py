# Copyright 2002, 2003 University of Oslo, Norway

import xml.sax
from Cerebrum import Group

TOPICS_FILE="/cerebrum/dumps/FS/topics.xml"   # TODO: cereconf
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
      - profildef: defines a profile (a list of settings)
      - kurs_elements: also defines a list of settings, but for a
        given kurs
      - bruk_profil: apply one or more profiles, as well as other
        settings to a list of kurs_elements.  Any settings in a
        kurs_element overrides previous settings.

    All profildef's are stored in a dict; they are not resolved by the
    parser (hvis vi skal bruke profiler i kurs_element overrides, må
    vi gjøre det).

    For each type of kurs_element, the setting for the corresponding
    ke is stored in self.ke like:

      'annetprogram': {   'home': [ { 'value': '/uio/hume/YYY'}],
                          'profil': [   { 'name': 'dummy-profil'}]}

    Conflict resolving: When several values are set for the same
    datatype, they are sorted by precedense.  Thus for the example
    below, ['foo', 'bar'] is returned for home
      <bruk_profil>
        <home value="foo"/>
        <studieprogram ...>
          <home value="bar"/>
        </studieprogram>
      </bruk_profil>

    """

    # The way this is currently used, we could also add profildef to
    # the kurs_elements list, however, this would complicate things if
    # we later decide to expand profiles when they are encountered.
    kurs_elements = ("studieprogram", "evu", "emne", "group")
    # singular_elements = ("home", )

    def __init__(self):
        self.elementstack = []
        self.profiles = {}      # stores profildef's
        self.ke = {}            # stores settings for this kurs_element
        for k in self.kurs_elements:
            self.ke[k] = {}
        self.prdefname = None

    def _apply_profile(self, profile, dest):
        for ename in profile.keys():
            dest.setdefault(ename, []).extend(profile[ename])

    def startElement(self, ename, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        ename = ename.encode('iso8859-1')
        self.elementstack.append(ename)

        if (len(self.elementstack) > 1 and   # Overrides for a given kurs_element
            self.elementstack[-2] in self.kurs_elements):
            # store data like: self.ke['emne']['dummyemne']['home'].append(tmp)
            t = self.ke[self.elementstack[-2]]
            if ename == 'profil':
                self._apply_profile(self.profiles[tmp['name']], t[self.current_ke])
            else:
                t[self.current_ke].setdefault(ename, []).append(tmp)
        elif ename in self.kurs_elements:
            self.current_ke = tmp['id']
            self.ke[ename].setdefault(self.current_ke, {})
            if self.elementstack[-2] == "bruk_profil":
                self.current_bp_users.append((ename, tmp['id']))
        elif len(self.elementstack) == 2:  # At the 2nd level of tag nesting
            if ename == "profildef":
                self.prdefname = tmp['name']
                self.profiles[tmp['name']] = {}
            elif ename == "bruk_profil":
                # delay application of settings until the tag is closed
                self.current_bp_users = []
                self.current_bp = {}
            else:
                print "Unknown tag: %s" % ename
        elif len(self.elementstack) == 3:
            if self.elementstack[-2] == "profildef":
                self.profiles[self.prdefname].setdefault(ename, []).append(tmp)
            elif self.elementstack[-2] == "bruk_profil":
                # We remember what kurs/emner uses this profileset,
                # and set the data in endElement
                self.current_bp.setdefault(ename, []).append(tmp)
        elif ename == "config":
            pass
        else:
            print "Unexpected tag=%s level=%i" % (ename, len(self.elementstack))

    def endElement(self, ename):
        if ename == "profildef":
            self.prdefname = None
        elif ename == "bruk_profil":
            for d in self.current_bp.keys():
                self.current_bp[d].reverse()
            for ktype, kid in self.current_bp_users:
                t = self.ke.setdefault(ktype, {}).setdefault(kid, {})
                for d in self.current_bp.keys():
                    if d == 'profil':
                        for p in self.current_bp['profil']:
                            self._apply_profile(self.profiles[p['name']], t)
                    else:
                        t.setdefault(d, []).extend(self.current_bp[d])
        self.elementstack.pop()

class _MapStudconfigData(object):
    """Map data from StudconfigParser to cerebrum object ids etc."""
    
    def __init__(self, db):
        self.db = db
        self._sko_cache = {}
        self._group_cache = {}
        self._ou = Factory.get('OU')(self.db)
        self._group = Group.Group(self.db)

    def mapData(self, dta):
        for dtatype in dta.keys():
            for dtakey in dta[dtatype].keys():
                if dta[dtatype][dtakey].has_key('SKO'):
                    nyesko = []
                    for s in dta[dtatype][dtakey]['SKO']:
                          n = self._get_sko(s['value'])
                          if n is not None:
                              nyesko.append(n)
                    dta[dtatype][dtakey]['SKO'] = nyesko
                for t in ('Filgruppe', 'Primærgruppe'):
                    nyegrupper = []
                    for f in dta[dtatype][dtakey].get(t, []):
                        n = self._get_group(f['value'])
                        if n is not None:
                            nyegrupper.append(n)
                    dta[dtatype][dtakey][t] = nyegrupper 
                if dta[dtatype][dtakey].has_key('Nettgruppe'):
                    pass

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

    def __init__(self, history=None, fnr=None):
        self.topics = []
        # Ugly memory-wasting, inflexible way:
        self.tp = self
        self.history = history
        self.fnr = fnr
        xml.sax.parse(TOPICS_FILE, self.tp)

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

class Profile(object):
    """Profile implements the logic that maps a persons topics (and
    optionaly groups) to the apropriate home, default group etc using
    rules read by the StudconfigParser
    """

    def __init__(self, autostud, topics, groups=None):
        self._topics = topics
        self._groups = groups
        self._autostud = autostud
        self._stedkoder = {}
        self._filgrupper = {}
        self._nettgrupper = {}
        self.autogroups = []

        self._matches = []
        topics.sort(self._topics_sort)
        if self._autostud.debug > 1:
            print "Topics: %s" % topics
        for t in topics:
            k = autostud.sp.ke['emne'].get(t['emnekode'], None)
            if k is not None:
                # TODO: sett nivåkode til nivåkode + 50 for å
                #   implementere emne > studieprogram på samme nivåkode
                self._matches.append((k, 'emne'))
            k = autostud.sp.ke['studieprogram'].get(t['studieprogramkode'], None)
            if k is not None:
                self._matches.append((k, self._normalize_nivakode(t['studienivakode'])))

        singular = ('home', 'SKO', 'Primærgruppe')
        found = {}
        home_conflict = 0
        if self._autostud.debug > 1:
            print "Matches: %s" % self._matches
        for m in self._matches:
            spec, level = m
            for t in spec.get('SKO', []):
                self._stedkoder[t] = 1
            for t in spec.get('Primærgruppe', []):
                self._filgrupper[t] = 1
            for t in spec.get('Filgruppe', []):
                self._filgrupper[t] = 1
            for t in spec.get('Netgruppe', []):
                self._nettgrupper[t['value']] = 1
            for s in singular:
                if spec.has_key(s):
                    if found.has_key(s):
                        if found[s][0] <> spec[s]:
                            # conflict, has multiple values for single-value attribute
                            if found[s][1] > level:
                                pass
                            elif found[s][1] < level:
                                found[s] = (spec[s], level)
                            else:     # Same studienivåkode
                                if s == 'home':
                                    home_conflict = level
                                else:
                                    # Use the first in the alphabet
                                    if found[s][0] > spec[s]:
                                        found[s] = (spec[s], level)
                    else:
                        found[s] = (spec[s], level)
        try:
            self._dfg = found['Primærgruppe'][0][0]
        except (KeyError, IndexError):
            raise Errors.NotFoundError, "ingen primærgruppe"
        try:
            self._email_sko = found['SKO'][0][0]
        except (KeyError, IndexError):
            raise Errors.NotFoundError, "ingen primærsko"
        self.max_on_disk = 400  # TODO: set this properly
        try:
            # TODO:
            cereconf.DEFAULT_HIGH_DISK, cereconf.DEFAULT_LOW_DISK = "/uio/platon/div-h","/uio/platon/div-l"
            if home_conflict >= 300:
                self._disk = cereconf.DEFAULT_HIGH_DISK
            elif home_conflict > 1:
                self._disk = cereconf.DEFAULT_LOW_DISK
            else:
                self._disk = found['home'][0][0]['value']
        except KeyError:
            raise Errors.NotFoundError, "ingen disk"

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
        
    def get_disk(self):
        for d in self._autostud._disks.keys():
            dta = self._autostud._disks[d]
            if(self._disk == dta[0][0:len(self._disk)] and dta[1] < self.max_on_disk):
                return d
        raise ValueError, "Bad disk %s" % self._disk

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self._autostud._disks[old][1] -= 1
        if new is not None:
            self._autostud._disks[new][1] += 1

    def get_stedkoder(self):
        return self._stedkoder.keys()

    def get_dfg(self):
        return self._dfg

    def get_email_sko(self):
        return self._email_sko
    
    def get_filgrupper(self):
        return self._filgrupper.keys()

    def get_nettgrupper(self):
        return self._nettgruper.keys()

    def get_pquota(self):
        assert self._groups is not None
        for m in self._matches:
            spec, level = m
            for t in spec.get('pquota', []):
                pass # TODO
        raise NotImplementedError, "TODO"
        
class AutoStud(object):
    """This is the only class that should be directly accessed within
    this package"""
    
    def __init__(self, db, debug=0):
        self.debug = debug
        self._disks = {}
        disk = Disk.Disk(db)
        for i in disk.list():
            disk.clear()
            disk.find(i['disk_id'])
            count = 42  # TODO: set this to N users on disk
            self._disks[int(disk.entity_id)] = [disk.path, count]
        self.sp = StudconfigParser()
        xml.sax.parse(STUDCONFIG_FILE, self.sp)
        m = _MapStudconfigData(db)
        m.mapData(self.sp.ke)
        if debug > 2:
            print "Parsed studconfig.xml expanded to: "
            pp.pprint(self.sp.ke)

    def get_topics_list(self, history=None, fnr=None):
        """Use like:
          for topics in foo.get_topics_list:

        topics will contain a list of dicts with lines from the topics
        file for one person.  If fnr is not None, only lines for a
        given user is returned."""
        return TopicsParser(fnr=fnr)

    def get_profile(self, topics, groups=None):
        """Returns a Profile object matching the topics, to check
        quotas, groups must also be set."""
        return Profile(self, topics, groups)
