# Copyright 2002, 2003 University of Oslo, Norway

import xml.sax

TOPICS_FILE="/cerebrum/dumps/FS/topics.xml"   # TODO: cereconf
STUDCONFIG_FILE="/cerebrum/uiocerebrum/etc/config/studconfig.xml"

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
                    t.setdefault(d, []).extend(self.current_bp[d])
        self.elementstack.pop()

class TopicsParser(xml.sax.ContentHandler):
    """Parses the topics file, storing data in an internal list.  The
    topics file is sorted by fødselsnummer"""

    def __init__(self):
        self.topics = []

    def startElement(self, name, attrs):
        self.t_data = {}
        for k in attrs.keys():
            self.t_data[k.encode('iso8859-1')] = attrs[k.encode('iso8859-1')].encode('iso8859-1')

    def endElement(self, name):
        if name == "topic":
            self.topics.append(self.t_data)

class PersonTopicsData(object):
    # TODO: Merge with TopicsParser, no need for two internal classes here

    def __init__(self, history=None, fnr=None):
        # Ugly memory-wasting, inflexible way:
        self.tp = TopicsParser()
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

        matches = []
        topics.sort(self._topics_sort)
        for t in topics:
            # print "sjekk %s / %s" % (t['emnekode'], t['studieprogramkode'])
            k = autostud.sp.ke['emne'].get(t['emnekode'], None)
            if k is not None:
                matches.append(k)
            k = autostud.sp.ke['studieprogram'].get(t['studieprogramkode'], None)
            if k is not None:
                matches.append(k)

        print "All matches: %s" % matches
        # TODO: Løp gjennom matches, og sett self._dfg++

    def _topics_sort(self, x, y):
        x = x['studienivakode']
        if x >= 100 and x < 300:
            x = 100
        elif x >= 300 and x < 400:
            x = 300
        y = y['studienivakode']
        if y >= 100 and y < 300:
            y = 100
        elif y >= 300 and y < 400:
            y = 300
        return cmp(y, x)
        
    def get_disk(self):
        # TODO: initialize disks with mapping diskname -> num_users
        for d in disks:
            if(self._disk == d[0:len(self._disk)] and disks[d] < max_on_disk):
                return d
        raise ValueError, "Bad disk %s" % disk

    def get_stedkoder(self):
        pass

    def get_dfg(self):
        pass

    def get_filgrupper(self):
        pass

    def get_nettgrupper(self):
        pass


    def get_pquota(self):
        assert self._groups is not None
        
class AutoStud(object):
    """This is the only class that should be directly accessed within
    this package"""
    
    def __init__(self):
        self.sp = StudconfigParser()
        xml.sax.parse(STUDCONFIG_FILE, self.sp)

    def get_topics_list(self, history=None, fnr=None):
        """Use like:
          for topics in foo.get_topics_list:

        topics will contain a list of dicts with lines from the topics
        file for one person.  If fnr is not None, only lines for a
        given user is returned."""
        return PersonTopicsData(fnr=fnr)

    def get_profile(self, topics, groups=None):
        """Returns a Profile object matching the topics, to check
        quotas, groups must also be set."""
        return Profile(self, topics, groups)
