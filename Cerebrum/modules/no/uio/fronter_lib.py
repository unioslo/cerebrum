#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

from Cerebrum import Group
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum import Database

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
SELECT c.importid, c.title, c.allowsflag, p.importid
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
SELECT r.importid, r.title, s.importid, r.profile
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

    def __init__(self, fronterHost, db, const, fs_db):
        self._fronterHost = fronterHost
        self._fs = FS(fs_db)
        self.db = db
        self.const = const
        for k in host_config[fronterHost].keys():
            setattr(self, k, host_config[fronterHost][k])
        self.supergroups = self.GetSuperGroupnames()
        fronter_db = Database.connect(user='fronter',
                                      service=self.DBinst,
                                      DB_driver='Oracle')
        self._accessFronter = AccessFronter(fronter_db)

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
        for enhet in self._fs.GetUndervEnhetAll():
            kurs_id = UE2KursID(EMNE_PREFIX, Instnr, emnekode, versjon,
                                termk, aar, termnr)
        if kurs.has_key(kurs_id):
            # Alle kurs-IDer som stammer fra undervisningsenheter
            # prefikses med EMNE_PREFIX + ':'.
            enhet_id = join(":", EMNE_PREFIX, Instnr, emnekode, versjon,
                            termk, aar, termnr)
            kurs2enhet.setdefault(kurs_id, []).append(enhet_id)
            multi_id = join(":", Instnr, emnekode, termk, aar)
            emne_versjon[multi_id]["v%s" % versjon] = 1
            emne_termnr[multi_id][termnr] = 1
            enhet2sko[enhet_id] = "%02d%02d00" % (skoF, skoI)
            kurs2navn.setdefault(kurs_id, []).append([aar, termk, emnenavn])

        for kurs_id in kurs2navn.keys():
            navn_sorted = kurs2navn[kurs_id][:].sort(self._date_sort)
            # Bruk navnet fra den eldste enheten; dette navnet vil enten
            # være fra inneværende eller et fremtidig semester
            # pga. utplukket som finnes i dumpfila.
            kurs2navn[kurs_id] = navn_sorted[0][2]

        for akt in self._fs.GetUndAktivitet():
            kurs_id = UE2KursID(EMNE_PREFIX, Instnr, emnekode, versjon,
                                termk, aar, termnr)
            if kurs.has_key(kurs_id):
                enhet_id = ":".join((EMNE_PREFIX, Instnr, emnekode, versjon,
                                     termk, aar, termnr))
            enhet2akt.setdefault(enhet_id, []).append([aktkode, navn])

        for evu in self._fs.GetEvuInfo():
            kurs_id = UE2KursID(EVU_PREFIX, evukode, kurstidkode)
            if kurs.has_key(kurs_id):
                # Alle kurs-IDer som stammer fra EVU-kurs prefikses med "EVU:".
                enhet_id = join(":", EVU_PREFIX, evukode, kurstidkode)
                kurs2enhet[kurs_id].append(enhet_id)
                enhet2sko[enhet_id] = "%02d%02d00" % (skoF, skoI)
                # Da et EVU-kurs alltid vil bestå av kun en
                # "undervisningsenhet", kan vi sette kursnavnet med en
                # gang (uten å måtte sortere slik vi gjorde over for
                # "ordentlige" undervisningsenheter).
                kurs2navn[kurs_id] = evunavn

        for evukurs in self._fs.GetEvuKurs():
            for evukursakt in self._fs.GetAktivitetEvuKurs(
                evukurs['kurskode'], evukurs['tidsrom']):
                kurs_id = UE2KursID(EVU_PREFIX, evukode, kurstidkode)
                if kurs.has_key(kurs_id):
                    enhet_id = join(":", EVU_PREFIX, evukode, kurstidkode)
                    enhet2akt[enhet_id].append([aktkode, navn])


    def get_fronter_users(self):
        """Return a dict with info on all users in Fronter"""
        users = {}
        for user in self._accessFronter.ListUserInfo():
            if not user['uname']:
                print "Undefined Fronter username: <undef> => [%s,%s,%s,%s]" % (
                      user['pwd'], user['fname'], user['lname'], user['email'])
                continue
            if not user['pwd']:
                user['pwd'] = 'plain:'
            users[uname] = {'PASSWORD': user['pwd'] or 'plain:',
                            'GIVEN': user['fname'] or '',
                            'FAMILY': user['lname'] or '',
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
                if users.has_key(gm['uname']):
                    users[gm['uname']]['USERACCESS'] = gid2access[gid]
        return users

    def useraccess(self, access):
        # TODO: move to config section
        mapping = {0: 1,                # Not allowed to log in
                   'viewmygroups': 2,   # Normal user
                   'allowlogin': 2,     # Normal user
                   'administrator': 3}  # Admin
        return mapping[access]

    def get_fronter_group(self):
        # In Fronter, groups and structure shares the same data structures
        # internally.  Thus, both groups and structure are defined by using
        # IMS <GROUP> elements.
        #
        # Additionally, the <GROUP> element is (ab)used for creating "rooms".
        group = {}
        for gi in self._accessFronter.ListGroupInfo():
            if re.search(r'^STRUCTURE/(Enhet|Studentkorridor):', gi['id']):
                #     Hovedkorr. enh:     STRUCTURE/Enhet:<ENHETID>
                #     Undv.korr. enh:     STRUCTURE/Studentkorridor:<ENHETID>
                rest = id.split(":")
                corr_type = rest.pop(0)
                if not (rest[0].startswith(EMNE_PREFIX) or rest[0].startswith(EVU_PREFIX)):
                    rest.insert(0, EMNE_PREFIX)
            id = "%s:%s" % (corr_type, UE2KursID(rest))
            group[id] = {'title': gi['title'],
                         'parent': gi['parent'],
                         'allow_room': (gi['allow'] & 1),
                         'allow_contact': (gi['allow'] & 2),
                         'CFid': gi['id'],
                         }
        return group

    def get_fronter_rooms(self):
        rooms = {}
        for ri in self._accessFronter.ListRoomInfo():
            rest = ri['room'].split(":")
            room_type = rest.pop(0)
            if not (rest[0].startswith(EMNE_PREFIX) or rest[0].startswith(EVU_PREFIX)):
                rest.insert(0, EMNE_PREFIX)
            
            if room_type == 'ROOM/Aktivitet':
                aktkode = rest.pop(0)
                room = ":".join((room_type, UE2KursID(rest), aktkode))
            else:
                room = "%s:%s" % (room_type, UE2KursID(rest))
            rooms[room] = {'title': ri['title'],
                           'parent': ri['structid'],
                           'profile': ri['profileid'],
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
                newgroup.sub(r'^uio\.no:fs:', 'uio.no:fs:%s:' % EMNE_PREFIX.lower())

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
                newgroup.sub(r'^uio\.no:fs:', 'uio.no:fs:%s:'  % EMNE_PREFIX.lower())

            if (current_rooms.has_key(r['room']) and (
                current_groups.has_key(r['group']) or
                current_groups.has_key(newgroup))):
                acl[room][group] = {'role': role}
        return acl

class FronterXML(object):
    def __init__(self):
        pass

    def start_xml_file(self, kurs2enhet):
        self.xml.comment("Eksporterer data om følgende emner:\n  " + 
                    "\n  ".join(kurs2enhet.keys()))
        self.xml.startTag(rootEl)
        self.xml.startTag('PROPERTIES')
        self.xml.dataElement('DATASOURCE', DataSource)
        self.xml.dataElement('TARGET', "ClassFronter/CF_id@uio.no")
        # :TODO: Tell Fronter (again) that they need to define the set of
        # codes for the TYPE element.
        # self.xml.dataElement('TYPE', "REFRESH")
        self.xml.dataElement('DATETIME', "%04d-%02d-%02d" % (year, mon, mday))
        self.xml.startTag('EXTENSION')
        self.xml.emptyTag('DEBUG', {
            'debugdest': 0, # File
            'logpath': DebugFile,
            'debuglevel': DebugLevel})
        self.xml.emptyTag('DATABASESETTINGS', {
            'database': 0,	# Oracle
            'jdbcfilename': "CF_dir/CF_id.dat"})
        self.xml.endTag('EXTENSION')
        self.xml.endTag('PROPERTIES')

    def user_to_XML(self, id, recstatus, data):
        """Lager XML for en person"""
        self.xml.startTag('PERSON', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == STATUS_ADD or recstatus == STATUS_UPDATE):
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
        if recstatus == fronter.STATUS_DELETE:
            return
        self.xml.startTag('GROUP', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == fronter.STATUS_ADD or recstatus == fronter.STATUS_UPDATE):
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
            self.xml.dataElement('SOURCE', DataSource)
            self.xml.dataElement('ID', data['parent'])
            self.xml.endTag('SOURCEDID')
            self.xml.emptyTag('LABEL')
            self.xml.endTag('RELATIONSHIP')
        self.xml.endTag('GROUP')

    def room_to_XML(self, id, recstatus, data):
        # Lager XML for et rom
        #
        # Gamle rom skal aldri slettes automatisk.
        if recstatus == fronter.STATUS_DELETE:
            return 
        self.xml.startTag('GROUP', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == STATUS_ADD or recstatus == STATUS_UPDATE):
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
                                                     fronter._accessFronter.GetProfileId('UiOstdrom2003'))})
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
            self.xml.dataElement('SOURCE', DataSource)
            self.xml.dataElement('ID', data['parent'])
            self.xml.endTag('SOURCEDID')
            self.xml.emptyTag('LABEL')
            self.xml.endTag('RELATIONSHIP')
        self.xml.endTag('GROUP')

    def personmembers_to_XML(self, gid, recstatus, members):
        # lager XML av medlemer
        self.xml.startTag('MEMBERSHIP')
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', DataSource)
        self.xml.dataElement('ID', gid)
        self.xml.endTag('SOURCEDID')
        for uname in members:
            self.xml.startTag('MEMBER')
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', DataSource)
            self.xml.dataElement('ID', uname)
            self.xml.endTag('SOURCEDID')
            self.xml.dataElement('IDTYPE', 1)	# The following member ids are persons.
            self.xml.startTag('ROLE', {'recstatus': recstatus,
                                       'roletype': fronter.ROLE_READ})
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
        self.xml.dataElement('SOURCE', DataSource)
        self.xml.dataElement('ID', node)
        self.xml.endTag('SOURCEDID')
        for gname in groups.keys():
            self.xml.startTag('MEMBER')
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', DataSource)
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
        self.xml.endTag(rootEl)
        self.xml.end()
        
