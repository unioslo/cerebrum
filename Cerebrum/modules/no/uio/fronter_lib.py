#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

import re
import time

from Cerebrum import Group
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum import Database
from xml.sax import saxutils

# TODO: This file should not have UiO hardcoded data in it
SYDRadmins = ['baardj', 'frankjs']
DMLadmins = ['lindaj', 'hallgerb', 'maskoger', 'stefanij', 'jonar',
             'helgeu', 'kaugedal']
AllAdmins = SYDRadmins + DMLadmins
host_config = {
    'internkurs.uio.no': { 'DBinst': 'DLOUIO',
                           'admins': AllAdmins ,
                           'export': ['All_users'],
                           },
    'tavle.uio.no': {'DBinst': 'DLOOPEN',
                     'admins': AllAdmins,
                     'export': ['All_users'],
                     },
    'kladdebok.uio.no': { 'DBinst': 'DLOUTV.uio.no',
                          'admins': AllAdmins + ['hmeland', 'thomash'],
                          'export': ['FS'],
                          'plain_users': ['mgrude', 'gunnarfk'],
                          'spread': 'spread_fronter_dloprod'
                          },
    'petra.uio.no': { 'DBinst': 'DLODEMO',
                      'admins': AllAdmins,
                      'export': ['FS', 'All_users'],
                      },
    'blyant.uio.no': { 'DBinst': 'DLOPROD',
                       'admins': AllAdmins,
                       'export': ['FS', 'All_users'],
                       }
    }
# TODO: Alle steder der vi bruker lower(): sjekk æøå

class AccessFronter(object):
    def __init__(self, db):
        self.db = db

    def ListUserInfo(self):
        return self.db.query("""
SELECT username, password, firstname, lastname, email
FROM persontbl2 p
WHERE username IS NOT NULL AND
      importid IS NOT NULL AND
      EXISTS (SELECT 'x' FROM memberstbl m WHERE m.personid = p.id)""")
    
    def ListGroupInfo(self):
        return self.db.query("""
SELECT c.importid, c.title, c.allowsflag, p.importid AS parent_importid
FROM structuregrouptbl c, structuregrouptbl p
WHERE c.parent = p.id AND
      c.importid IS NOT NULL
UNION
SELECT importid, title, allowsflag, importid
FROM structuregrouptbl
WHERE parent <= 0 AND
      importid IS NOT NULL""")

    def GetGroupMembers(self, gid):
        return self.db.query("""
SELECT p.username
FROM persontbl2 p, memberstbl m
WHERE m.groupid = :gid AND
      m.personid = p.id AND
      p.importid IS NOT NULL""", {'gid': gid})

    def ListAllGroupMembers(self):
        return self.db.query("""
SELECT g.importid, p.username
FROM persontbl2 p, structuregrouptbl g, memberstbl m
WHERE g.importid IS NOT NULL AND
      g.id = m.groupid AND
      p.id = m.personid AND
      p.importid IS NOT NULL""")

    def ListGroupsACL(self):
        return self.db.query("""
SELECT s.importid, g.importid, a.group_access, a.room_access
FROM structuregrouptbl s, structuregrouptbl g, structureacl a
WHERE s.importid IS NOT NULL AND
      s.id = a.structid AND
      g.id = a.groupid AND
      g.importid IS NOT NULL""")

    def ListRoomInfo(self):
        return self.db.query("""
SELECT r.importid AS room, r.title, s.importid AS structid, r.profile
FROM projecttbl2 r, structuregrouptbl s
WHERE r.structureid = s.id AND
      r.importid IS NOT NULL""")

    def ListRoomsACL(self):
        return self.db.query("""
SELECT r.importid, g.importid, a.read_access, a.write_access,
       a.delete_access, a.change_access
FROM projecttbl2 r, structuregrouptbl g, acl a
WHERE r.importid IS NOT NULL AND
      r.id = a.prjid AND
      g.id = a.groupid AND
      g.importid IS NOT NULL""")

class FronterUtils(object):
    def UE2KursID(type, *rest):
        """Lag ureg2000-spesifikk "kurs-ID" av primærnøkkelen til en
        undervisningsenhet eller et EVU-kurs.  Denne kurs-IDen forblir
        uforandret så lenge kurset pågår; den endres altså ikke bår man
        f.eks. kommer til et nytt semester.

        Første argument angir hvilken type FS-entitet de resterende
        argumentene stammer fra; enten 'KURS' (for undervisningsenhet) eller
        'EVU' (for EVU-kurs)."""
        type = type.lower()
        if type == 'evu':
            if len(rest) != 2:
                raise ValueError, "ERROR: EVU-kurs skal identifiseres av 2 felter, "+\
                      "ikke <%s>" % ">, <".join(rest)
            # EVU-kurs er greie; de identifiseres unikt ved to
            # fritekstfelter; kurskode og tidsangivelse, og er modellert i
            # FS uavhengig av semester-inndeling.
            rest = list(rest)
            rest.insert(0, type)
            return ":".join(rest).lower()
        elif type != 'kurs':
            raise ValueError, "ERROR: Ukjent kurstype <%s> (%s)" % (type, rest)

        # Vi vet her at $type er 'KURS', og vet dermed også hvilke
        # elementer som er med i @rest:
        if len(rest) != 6:
            raise ValueError, "ERROR: Undervisningsenheter skal identifiseres av 6 "+\
                  "felter, ikke <%s>" % ">, <".join(rest)

        instnr, emnekode, versjon, termk, aar, termnr = rest
        termnr = int(termnr)
        aar = int(aar)
        tmp_termk = re.sub('[^a-zA-Z0-9]', '_', termk).lower()
        # Finn $termk og $aar for ($termnr - 1) semestere siden:
        if (tmp_termk == 'h_st'):
            if (termnr % 2) == 1:
                termk = 'høst'
            else:
                termk = 'vår'
            aar -= int((termnr - 1) / 2)
        elif tmp_termk == 'v_r':
            if (termnr % 2) == 1:
                termk = 'vår'
            else:
                termk = 'høst'
            aar -= int(termnr / 2)
        else:
            # Vi krysser fingrene og håper at det aldri vil benyttes andre
            # verdier for $termk enn 'vår' og 'høst', da det i så fall vil
            # bli vanskelig å vite hvilket semester det var "for 2
            # semestere siden".
            raise ValueError, "ERROR: Unknown terminkode <%s> for emnekode <%s>." % (
                termk, emnekode)

        # $termnr er ikke del av den returnerte strengen.  Vi har benyttet
        # $termnr for å beregne $termk og $aar ved $termnr == 1; det er
        # altså implisitt i kurs-IDen at $termnr er lik 1 (og dermed
        # unødvendig å ta med).
        ret = "%s:%s:%s:%s:%s:%s" % (type, instnr, emnekode, versjon, termk, aar)
        return ret
    UE2KursID = staticmethod(UE2KursID)

class Fronter(object):
    STATUS_ADD = 1
    STATUS_UPDATE = 2
    STATUS_DELETE = 3

    ROLE_READ = '01'
    ROLE_WRITE = '02'
    ROLE_DELETE = '03'
    ROLE_CHANGE = '07'

    EMNE_PREFIX = 'KURS'
    EVU_PREFIX = 'EVU'

    def __init__(self, fronterHost, db, const, fs_db, logger=None):
        self._fronterHost = fronterHost
        self._fs = FS(fs_db)
        self.db = db
        self.const = const
        self.logger = logger
        for k in host_config[fronterHost].keys():
            setattr(self, k, host_config[fronterHost][k])
        self.supergroups = self.GetSuperGroupnames()
        fronter_db = Database.connect(user='fronter',
                                      service=self.DBinst,
                                      DB_driver='Oracle')
        self._accessFronter = AccessFronter(fronter_db)
        self.kurs2navn = {}
        self.kurs2enhet = {}
        self.enhet2sko = {}
        self.enhet2akt = {}

    def GetSuperGroupnames(self):
        if 'FS' in self.export:
            group = Group.Group(self.db)
            ret = []
            for e in group.list_all_with_spread(
                int(getattr(self.const, self.spread))):
                group.clear()
                group.find(e['entity_id'])
                ret.append(group.entity_id)
            return ret
        elif 'FS_all' in self.export:
            raise ValueError, "didn't think this was in use"
            # Ser ikke ut til å være i bruk
            return # alle direktemedlem grupper under INTERNAL_PREFIX}uio.no:fs:{supergroup}

    def _date_sort(self, x, y):
        """Sort by year, then by semester"""
        if(x[0] != y[0]):
            return cmp(x[0], y[0])
        return cmp(y[1][0], x[1][0])

    def read_kurs_data(self):
        #
        # @supergroups inneholder nå navnet på de gruppene fra nivå 2 i
        # hierarkiet av FS-avledede grupper som er markert for eksport til
        # CF-instansen vi nå bygger eksport-XML til:
        #
        # Nivå 0: Supergruppe, brukes for å samle alle FS-avledede grupper.
        # Nivå 1: Emnekode-grupper eller EVU-kurs-grupper, subgrupper av
        #         supergruppa på nivå 0.
        # Nivå 2: KursID-grupper, brukes til å legge inn eksport av et
        #         gitt kurs til ClassFronter.
        # Nivå 3: Grupper for lærere/studenter på hver av det spesifiserte
        #         kursets aktiviteter etc.
        #
        kurs = {}
        for group in self.supergroups:
            # Om man stripper vekk de tre første elementene av $group (dvs
            # "({u2k-internal}):uio.no:fs"), vil man sitte igjen med en
            # "kurs-ID", f.eks.
            #
            #   kurs:185:jurprig:1:vår:2001
            #   kurs:185:diavhf:1:høst:2001
            #   evu:14-latkfu:2001-2002
            #
            # Med utgangspunkt i disse kurs-IDene kan man bestemme hvilke
            # nåværende (og evt. fremtidige) undervisningsenheter (med
            # tilhørende und.aktiviteter) og EVU-kurs (med tilhørende
            # EVU-aktiviteter) som skal taes med i eksporten.
            #
            kurs_id = ":".join(group.split(':')[3:]).lower()
            kurs[kurs_id] = 1

        #
        # Vi har nå skaffet oss oversikt over hvilke Kurs-IDer som skal
        # eksporteres, og kan benytte dette til å plukke ut data om de
        # aktuelle undervisningsenhetene/EVU-kursene (og tilhørende
        # aktiviteter) fra ymse dumpfiler.
        #
        for enhet in self._fs.GetUndervEnhetAll()[1]:
            id_seq = (self.EMNE_PREFIX, enhet['institusjonsnr'],
                      enhet['emnekode'], enhet['versjonskode'],
                      enhet['terminkode'], enhet['arstall'],
                      enhet['terminnr'])
            kurs_id = FronterUtils.UE2KursID(*id_seq)

            if kurs.has_key(kurs_id):
                # Alle kurs-IDer som stammer fra undervisningsenheter
                # prefikses med EMNE_PREFIX + ':'.
                enhet_id = ":".join(id_seq)
                self.kurs2enhet.setdefault(kurs_id, []).append(enhet_id)
                multi_id = ":".join(
                    enhet['institusjonsnr'], enhet['emnekode'],
                      enhet['terminkode'], enhet['arstall'])
                emne_versjon[multi_id]["v%s" % enhet['versjonskode']] = 1
                emne_termnr[multi_id][enhet['terminnr']] = 1
                self.enhet2sko[enhet_id] = "%02d%02d00" % (skoF, skoI)
                self.kurs2navn.setdefault(kurs_id, []).append(
                    [enhet['arstall'], enhet['terminkode'],
                     enhet['emnenavn_bokmal']])

        for kurs_id in self.kurs2navn.keys():
            navn_sorted = self.kurs2navn[kurs_id][:].sort(self._date_sort)
            # Bruk navnet fra den eldste enheten; dette navnet vil enten
            # være fra inneværende eller et fremtidig semester
            # pga. utplukket som finnes i dumpfila.
            self.kurs2navn[kurs_id] = navn_sorted[0][2]

        for akt in self._fs.GetUndAktivitet()[1]:
            id_seq = (self.EMNE_PREFIX, akt['institusjonsnr'],
                      akt['emnekode'], akt['versjonskode'],
                      akt['terminkode'], akt['arstall'],
                      akt['terminnr'])

            kurs_id = FronterUtils.UE2KursID(*id_seq)
            if kurs.has_key(kurs_id):
                enhet_id = ":".join(id_seq)
            self.enhet2akt.setdefault(enhet_id, []).append(
                [akt['aktivitetkode'], akt['aktivitetsnavn']])

        for evu in self._fs.GetEvuKurs()[1]:
            id_seq = (self.EVU_PREFIX, evu['etterutdkurskode'],
                      evu['kurstidsangivelsekode'])
            kurs_id = FronterUtils.UE2KursID(*id_seq)
            if kurs.has_key(kurs_id):
                # Alle kurs-IDer som stammer fra EVU-kurs prefikses med "EVU:".
                enhet_id = ":".join(id_seq)
                self.kurs2enhet[kurs_id].append(enhet_id)
                self.enhet2sko[enhet_id] = "%02d%02d00" % (skoF, skoI)
                # Da et EVU-kurs alltid vil bestå av kun en
                # "undervisningsenhet", kan vi sette kursnavnet med en
                # gang (uten å måtte sortere slik vi gjorde over for
                # "ordentlige" undervisningsenheter).
                self.kurs2navn[kurs_id] = evu['etterutdkursnavn']

        for evukurs in self._fs.GetEvuKurs()[1]:
            for evukursakt in self._fs.GetAktivitetEvuKurs(
                evukurs['etterutdkurskode'], evukurs['kurstidsangivelsekode'])[1]:
                id_seq = (self.EVU_PREFIX, evukursakt['etterutdkurskode'],
                          evukursakt['kurstidsangivelsekode'])
                kurs_id = FronterUtils.UE2KursID(*id_seq)
                if kurs.has_key(kurs_id):
                    enhet_id = ":".join(id_seq)
                    self.enhet2akt[enhet_id].append([evukursakt['etterutdkurskode'],
                                                     evukursakt['aktivitetsnavn']])


    def get_fronter_users(self):
        """Return a dict with info on all users in Fronter"""
        users = {}
        for user in self._accessFronter.ListUserInfo():
            if not user['username']:
                print "Undefined Fronter username: <undef> => [%s,%s,%s,%s]" % (
                      user['password'], user['firstname'], user['lastname'], user['email'])
                continue
            if not user['password']:
                user['password'] = 'plain:'
            users[user['username']] = {'PASSWORD': user['password'] or 'plain:',
                                       'GIVEN': user['firstname'] or '',
                                       'FAMILY': user['lastname'] or '',
                                       'EMAIL': user['email'] or '',
                                       'USERACCESS': 0 # Default
                                       }

        # Set correct access for these users.
        gid2access = {7: 'viewmygroups',
                      4: 'allowlogin',
                      1: 'administrator'}
        # Walk through group ids in descending order (we assume that
        # membership in a group with lower group ID should take
        # preference).
        keys = gid2access.keys()
        keys.sort()
        keys.reverse()
        for gid in keys:
            for gm in self._accessFronter.GetGroupMembers(gid):
                if users.has_key(gm['username']):
                    users[gm['username']]['USERACCESS'] = gid2access[gid]
        return users

    def pwd(self, p):
        type, pwd = p.split(":")
        type_map = {'md5': 1,
                    'unix': 2,
                    'nt': 3,
                    'plain': 4}
        ret = {'passwordtype': type_map[type]}
        if pwd:
            ret['password'] = pwd
        return ret
    
    def useraccess(self, access):
        # TODO: move to config section
        mapping = {0: 1,                # Not allowed to log in
                   'viewmygroups': 2,   # Normal user
                   'allowlogin': 2,     # Normal user
                   'administrator': 3}  # Admin
        return mapping[access]

    def get_fronter_groups(self):
        # In Fronter, groups and structure shares the same data structures
        # internally.  Thus, both groups and structure are defined by using
        # IMS <GROUP> elements.
        #
        # Additionally, the <GROUP> element is (ab)used for creating "rooms".
        group = {}
        for gi in self._accessFronter.ListGroupInfo():
            if re.search(r'^STRUCTURE/(Enhet|Studentkorridor):', gi['importid']):
                #     Hovedkorr. enh:     STRUCTURE/Enhet:<ENHETID>
                #     Undv.korr. enh:     STRUCTURE/Studentkorridor:<ENHETID>
                rest = gi['importid'].split(":")
                corr_type = rest.pop(0)
                if not (rest[0].startswith(self.EMNE_PREFIX) or rest[0].startswith(self.EVU_PREFIX)):
                    rest.insert(0, self.EMNE_PREFIX)
            id = "%s:%s" % (corr_type, FronterUtils.UE2KursID(*rest))
            group[id] = {'title': gi['title'],
                         'parent': gi['parent_importid'],
                         'allow_room': (int(gi['allowsflag']) & 1),
                         'allow_contact': (int(gi['allowsflag']) & 2),
                         'CFid': gi['importid'],
                         }
        return group

    def get_fronter_rooms(self):
        rooms = {}
        for ri in self._accessFronter.ListRoomInfo():
            rest = ri['room'].split(":")
            room_type = rest.pop(0)
            if not rest[0] in (self.EMNE_PREFIX, self.EVU_PREFIX):
                rest.insert(0, self.EMNE_PREFIX)
            
            if room_type == 'ROOM/Aktivitet':
                aktkode = rest.pop()
                room = ":".join((room_type, FronterUtils.UE2KursID(*rest), aktkode))
            else:
                room = "%s:%s" % (room_type, FronterUtils.UE2KursID(*rest))
            rooms[room] = {'title': ri['title'],
                           'parent': ri['structid'],
                           'profile': ri['profile'],
                           'CFid': ri['room']
                           }
        return rooms

    def get_fronter_groupmembers(self):
        groupmembers = {}
        for m in self._accessFronter.ListAllGroupMembers():
            if current_groups.has_key(m['gname']):
                groupmembers.setdefault(m['gname'], {})[m['uname']] = 1
        return groupmembers

    def get_fronter_acl(self):
        acl = {}
        for a in self._accessFronter.ListGroupsACL():
            # Any access granted to groups with the old naming scheme
            # should be removed.
            newgroup = a['group']
            if re.search(r'^uio\.no:fs:\d', newgroup):
                newgroup.sub(r'^uio\.no:fs:', 'uio.no:fs:%s:' % self.EMNE_PREFIX.lower())

            # Place all access-entries for node `$struct' in one hash (we
            # don't really need to look up all the nodes for which a
            # specific group has rights, so changing the order of the two
            # hash keys would make things harder).
            if (current_groups.has_key(a['struct']) and (
                current_groups.has_key(a['group']) or
                current_groups.has_key(newgroup))):
                acl[a['struct']][a['group']] = {'gacc': a['gaccess'], 'racc': a['raccess']}
        for r in self._accessFronter.ListRoomsACL():
            role = ((r['change'] & fronter.ROLE_CHANGE) |
                    (r['delete'] & fronter.ROLE_DELETE) |
                    (r['write'] & fronter.ROLE_WRITE) |
                    (r['read'] & fronter.ROLE_READ))
            newgroup = r['group']
            if re.search(r'^uio\.no:fs:\d', newgroup):
                newgroup.sub(r'^uio\.no:fs:', 'uio.no:fs:%s:'  % self.EMNE_PREFIX.lower())

            if (current_rooms.has_key(r['room']) and (
                current_groups.has_key(r['group']) or
                current_groups.has_key(newgroup))):
                acl[room][group] = {'role': role}
        return acl

class XMLWriter(object):   # TODO: Move to separate file
    # TODO: should produce indented XML for easier readability
    def __init__(self, fname):
        self.gen = saxutils.XMLGenerator(file(fname, 'w'))

    def startTag(self, tag, attrs={}):
        a = {}
        for k in attrs.keys():   # saxutils don't like integers as values
            a[k] = "%s" % attrs[k]
        self.gen.startElement(tag, a)

    def endTag(self, tag):
        self.gen.endElement(tag)
        self.gen._out.write("\n")

    def emptyTag(self, tag, attrs={}):
        self.startTag(tag, attrs)
        self.gen.endElement(tag)

    def dataElement(self, tag, data):
        self.gen.startElement(tag, {})
        self.gen.characters(data)
        self.gen.endElement(tag)

    def comment(self, data):  # TODO: implement
        pass
    
    def startDocument(self):
        self.gen.startDocument()

    def endDocument(self):
        self.gen.endDocument()

class FronterXML(object):
    def __init__(self, fname, cf_dir=None, debug_file=None, debug_level=None,
                 fronter=None):
        self.xml = XMLWriter(fname)
        self.xml.startDocument()
        self.rootEl = 'ENTERPRISE'
        self.DataSource = 'UREG2000@uio.no'
        self.cf_dir = cf_dir
        self.debug_file = debug_file
        self.debug_level = debug_level
        self.fronter=fronter

    def start_xml_file(self, kurs2enhet):
        self.xml.comment("Eksporterer data om følgende emner:\n  " + 
                    "\n  ".join(kurs2enhet.keys()))
        self.xml.startTag(self.rootEl)
        self.xml.startTag('PROPERTIES')
        self.xml.dataElement('DATASOURCE', self.DataSource)
        self.xml.dataElement('TARGET', "ClassFronter/CF_id@uio.no")
        # :TODO: Tell Fronter (again) that they need to define the set of
        # codes for the TYPE element.
        # self.xml.dataElement('TYPE', "REFRESH")
        self.xml.dataElement('DATETIME', time.strftime("%Y-%m-%d"))
        self.xml.startTag('EXTENSION')
        self.xml.emptyTag('DEBUG', {
            'debugdest': 0, # File
            'logpath': self.debug_file,
            'debuglevel': self.debug_level})
        self.xml.emptyTag('DATABASESETTINGS', {
            'database': 0,	# Oracle
            'jdbcfilename': "%s/CF_id.dat" % self.cf_dir})
        self.xml.endTag('EXTENSION')
        self.xml.endTag('PROPERTIES')

    def user_to_XML(self, id, recstatus, data):
        """Lager XML for en person"""
        self.xml.startTag('PERSON', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == Fronter.STATUS_ADD or recstatus == Fronter.STATUS_UPDATE):
            self.xml.startTag('NAME')
            self.xml.dataElement('FN', "%s %s " % (data['GIVEN'], data['FAMILY']))
            self.xml.startTag('N')
            self.xml.dataElement('FAMILY', data['FAMILY'])
            self.xml.dataElement('GIVEN', data['GIVEN'])
            self.xml.endTag('N')
            self.xml.endTag('NAME')
            self.xml.dataElement('EMAIL', data['EMAIL'])
            # Tror ikke vi skal ha noen ekstra <DATASOURCE> her.
            self.xml.startTag('EXTENSION')
            self.xml.emptyTag('PASSWORD', data['PASSWORD'])
            self.xml.emptyTag('EMAILCLIENT', {'clienttype': data['EMAILCLIENT']})
            self.xml.emptyTag('USERACCESS', {'accesstype': data['USERACCESS']})
            self.xml.endTag('EXTENSION')
        self.xml.endTag('PERSON')

    def group_to_XML(self, id, recstatus, data):
        # Lager XML for en gruppe
        if recstatus == Fronter.STATUS_DELETE:
            return
        self.xml.startTag('GROUP', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == Fronter.STATUS_ADD or recstatus == Fronter.STATUS_UPDATE):
            self.xml.startTag('GROUPTYPE')
            self.xml.dataElement('SCHEME', 'FronterStructure1.0')
            allow_room = data.get('allow_room', 0)
            if allow_room:
                allow_room = 1
            allow_contact = data.get('allow_contact', 0)
            if allow_contact:
                allow_contact = 2
            self.xml.emptyTag('TYPEVALUE',
                              {'level': allow_room | allow_contact})
            self.xml.endTag('GROUPTYPE')
            self.xml.startTag('DESCRIPTION')
            if (len(data['title']) > 60):
                self.xml.emptyTag('SHORT')
                self.xml.dataElement('LONG', data['title'])
            else:
                self.xml.dataElement('SHORT', data['title'])
            self.xml.endTag('DESCRIPTION')
            self.xml.startTag('RELATIONSHIP', {'relation': 1})
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', self.DataSource)
            self.xml.dataElement('ID', data['parent'])
            self.xml.endTag('SOURCEDID')
            self.xml.emptyTag('LABEL')
            self.xml.endTag('RELATIONSHIP')
        self.xml.endTag('GROUP')

    def room_to_XML(self, id, recstatus, data):
        # Lager XML for et rom
        #
        # Gamle rom skal aldri slettes automatisk.
        if recstatus == Fronter.STATUS_DELETE:
            return 
        self.xml.startTag('GROUP', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == Fronter.STATUS_ADD or recstatus == Fronter.STATUS_UPDATE):
            self.xml.startTag('GROUPTYPE')
            self.xml.dataElement('SCHEME', 'FronterStructure1.0')
            self.xml.emptyTag('TYPEVALUE', {'level': 4})
            self.xml.endTag('GROUPTYPE')
            if (recstatus == STATUS_ADD):
                # Romprofil settes kun ved opprettelse av rommet, og vil
                # aldri senere tvinges tilbake til noen bestemt profil.
                self.xml.startTag('GROUPTYPE')
                self.xml.dataElement('SCHEME', 'Roomprofile1.0')
                self.xml.emptyTag('TYPEVALUE',
                                  {'level': data.get('profile',
                                                     self.fronter._accessFronter.GetProfileId('UiOstdrom2003'))})
                self.xml.endTag('GROUPTYPE')

            self.xml.startTag('DESCRIPTION')
            if (len(data['title']) > 60):
                self.xml.emptyTag('SHORT')
                self.xml.dataElement('LONG', data['title'])
            else:
                self.xml.dataElement('SHORT', data['title'])

            self.xml.endTag('DESCRIPTION')
            self.xml.startTag('RELATIONSHIP', {'relation': 1})
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', self.DataSource)
            self.xml.dataElement('ID', data['parent'])
            self.xml.endTag('SOURCEDID')
            self.xml.emptyTag('LABEL')
            self.xml.endTag('RELATIONSHIP')
        self.xml.endTag('GROUP')

    def personmembers_to_XML(self, gid, recstatus, members):
        # lager XML av medlemer
        self.xml.startTag('MEMBERSHIP')
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', gid)
        self.xml.endTag('SOURCEDID')
        for uname in members:
            self.xml.startTag('MEMBER')
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', self.DataSource)
            self.xml.dataElement('ID', uname)
            self.xml.endTag('SOURCEDID')
            self.xml.dataElement('IDTYPE', 1)	# The following member ids are persons.
            self.xml.startTag('ROLE', {'recstatus': recstatus,
                                       'roletype': Fronter.ROLE_READ})
            self.xml.dataElement('STATUS', 1)
            self.xml.startTag('EXTENSION')
            self.xml.emptyTag('MEMBEROF', {'type': 1}) # Member of group, not room.
            self.xml.endTag('EXTENSION')
            self.xml.endTag('ROLE')
            self.xml.endTag('MEMBER')
        self.xml.endTag('MEMBERSHIP')

    def acl_to_XML(self, node, recstatus, groups):
        self.xml.startTag('MEMBERSHIP')
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', node)
        self.xml.endTag('SOURCEDID')
        for gname in groups.keys():
            self.xml.startTag('MEMBER')
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', self.DataSource)
            self.xml.dataElement('ID', gname)
            self.xml.endTag('SOURCEDID')
            self.xml.dataElement('IDTYPE', 2)	# The following member ids are groups.
            acl = groups[gname]
            if acl.has_key('role'):
                self.xml.startTag('ROLE', {'recstatus': recstatus,
                                           'roletype': acl['role']})
                self.xml.dataElement('STATUS', 1)
                self.xml.startTag('EXTENSION')
                self.xml.emptyTag('MEMBEROF', {'type': 2}) # Member of room.
            else:
                self.xml.startTag('ROLE', {'recstatus': recstatus})
                self.xml.dataElement('STATUS', 1)
                self.xml.startTag('EXTENSION')
                self.xml.emptyTag('MEMBEROF', {'type': 1}) # Member of group.
                self.xml.emptyTag('GROUPACCESS',
                                  {'contactAccess': acl['gacc'],
                                   'roomAccess': acl['racc']})
            self.xml.endTag('EXTENSION')
            self.xml.endTag('ROLE')
            self.xml.endTag('MEMBER')
        self.xml.endTag('MEMBERSHIP')

    def end(self):
        self.xml.endTag(self.rootEl)
        self.xml.endDocument()
        
