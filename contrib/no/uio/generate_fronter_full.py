#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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


import sys
import locale
import os
import getopt
import time
import re

import cerebrum_path
getattr(cerebrum_path, 'This will shut the linters up', None)

import cereconf
from Cerebrum import Errors
from Cerebrum import Database
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no import access_FS
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no.uio.fronter_lib import XMLWriter


cf_dir = '/cerebrum/dumps/Fronter'
root_sko = '900199'
root_struct_id = 'UiO root node'
group_struct_id = "UREG2000@uio.no imported groups"
group_struct_title = 'Automatisk importerte grupper'


db = const = logger = None 
fronter = fxml = None
include_this_sem = True
fs_dir = None
new_users = None


def get_members(group_name):
    db = Factory.get("Database")()
    group = Factory.get("Group")(db)
    usernames = ()
    try:
        group.find_by_name(group_name)
    except Errors.NotFoundError:
        pass
    else:
        members = group.get_members(get_entity_name=True)
        usernames = tuple([x[1] for x in members])
    return usernames


host_config = {
    'internkurs.uio.no': { 'DBinst': 'DLOUIO.uio.no',
                           'admins':
                           get_members('classfronter-internkurs-drift'),
                           'export': ['All_users'],
                           },
    'tavle.uio.no': {'DBinst': 'DLOOPEN.uio.no',
                     'admins': get_members('classfronter-tavle-drift'),
                     'export': ['All_users'],
                     },
    'kladdebok.uio.no': { 'DBinst': 'DLOUTV.uio.no',
                          'admins':
                          get_members('classfronter-kladdebok-drift'),
                          'export': ['FS'],
                          'plain_users': ['mgrude', 'gunnarfk'],
                          'spread': 'spread_fronter_kladdebok',
                          },
    'petra.uio.no': { 'DBinst': 'DLODEMO.uio.no',
                      'admins': get_members('classfronter-petra-drift'),
                      'export': ['FS', 'All_users'],
                      'spread': 'spread_fronter_petra',
                      },
    'blyant.uio.no': { 'DBinst': 'DLOPROD.uio.no',
                       'admins': get_members('classfronter-blyant-drift'),
                       'export': ['FS', 'All_users'],
                       'spread': 'spread_fronter_blyant',
                       }
    }


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

    def __init__(self, fronter_host, db, const, fs_db, logger=None):
        self.fronter_host = fronter_host
        self.db = db
        self.const = const
        self._fs = FS(fs_db)
        self.logger = logger
        _config = host_config[fronter_host]
        for k in ('DBinst', 'admins', 'export'):
           setattr(self, k, _config[k])
        self.plain_users = _config.get('plain_users', ())
        self.spread = _config.get('spread', None)
        self.supergroups = self.get_supergroup_names()
        self.logger.debug("Fronter: len(self.supergroups)=%i",
                          len(self.supergroups))
        self.kurs2navn = {}
        self.kurs2enhet = {}
        self.enhet2sko = {}
        self.enhet2akt = {}
        self.emne_versjon = {}
        self.emne_termnr = {}
        self.akt2undform = {}

        if 'FS' in [x[0:2] for x in self.export]:
            self.read_kurs_data()

    def get_supergroup_names(self):
        if 'FS' in self.export:
            group = Factory.get("Group")(self.db)
            ret = []
            for e in group.list_all_with_spread(int(getattr(self.const,
                                                            self.spread))):
                group.clear()
                group.find(e['entity_id'])
                ret.append(group.group_name)
            return ret
        elif 'FS_all' in self.export:
            # Ser ikke ut til å være i bruk.
            raise ValueError, "didn't think this was in use"
            # [ Skulle egentlig ha returnert alle grupper som er
            #   direktemedlemmer under
            #   INTERNAL_PREFIX}uio.no:fs:{supergroup} ]
        else:
            # Ingen synkronisering av FS-emner; returner tom liste.
            return []

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
        for enhet in self._fs.undervisning.list_undervisningenheter():
            id_seq = (self.EMNE_PREFIX, enhet['institusjonsnr'],
                      enhet['emnekode'], enhet['versjonskode'],
                      enhet['terminkode'], enhet['arstall'],
                      enhet['terminnr'])
            kurs_id = UE2KursID(*id_seq)

            if kurs.has_key(kurs_id):
                # Alle kurs-IDer som stammer fra undervisningsenheter
                # prefikses med EMNE_PREFIX + ':'.
                enhet_id = ":".join([str(x) for x in id_seq]).lower()
##                 self.logger.debug("read_kurs_data: enhet_id=%s", enhet_id)
                self.kurs2enhet.setdefault(kurs_id, []).append(enhet_id)
                multi_id = ":".join([str(x) for x in(
                    enhet['institusjonsnr'], enhet['emnekode'],
                    enhet['terminkode'], enhet['arstall'])]).lower()
                self.emne_versjon.setdefault(
                    multi_id, {})["v%s" % enhet['versjonskode']] = 1
                self.emne_termnr.setdefault(
                    multi_id, {})[enhet['terminnr']] = 1
                full_sko = "%02d%02d%02d" % (enhet['faknr_kontroll'],
                                             enhet['instituttnr_kontroll'],
                                             enhet['gruppenr_kontroll'])
                if full_sko in ("150030",):
                    # Spesialbehandling av UNIK; til tross for at
                    # dette stedkode-messig bare er en gruppe, skal de
                    # ha en egen korridor.
                    self.enhet2sko[enhet_id] = full_sko
                else:
                    self.enhet2sko[enhet_id] = "%02d%02d00" % (
                        enhet['faknr_kontroll'],
                        enhet['instituttnr_kontroll'])
                emne_tittel = enhet['emnenavn_bokmal']
                if len(emne_tittel) > 50:
                    emne_tittel = enhet['emnenavnfork']
                self.kurs2navn.setdefault(kurs_id, []).append(
                    [enhet['arstall'], enhet['terminkode'], emne_tittel])

        for kurs_id in self.kurs2navn.keys():
            navn_sorted = self.kurs2navn[kurs_id][:]
            navn_sorted.sort(self._date_sort)
            # Bruk navnet fra den eldste enheten; dette navnet vil enten
            # være fra inneværende eller et fremtidig semester
            # pga. utplukket som finnes i dumpfila.
            self.kurs2navn[kurs_id] = navn_sorted[0][2]

        for akt in self._fs.undervisning.list_aktiviteter():
            id_seq = (self.EMNE_PREFIX, akt['institusjonsnr'],
                      akt['emnekode'], akt['versjonskode'],
                      akt['terminkode'], akt['arstall'],
                      akt['terminnr'])
##             self.logger.debug("read_kurs_data_getundaktivitet:" +
##                               " %s, %s, %s, %s, %s, %s, %s",
##                               self.EMNE_PREFIX, akt['institusjonsnr'],
##                               akt['emnekode'], akt['versjonskode'],
##                               akt['terminkode'], akt['arstall'],
##                               akt['terminnr'])

            kurs_id = UE2KursID(*id_seq)
##             self.logger.debug("read_kurs_data_getundaktivitet: kurs_id=%s",
##                               kurs_id)
            if kurs.has_key(kurs_id):
                enhet_id = ":".join([str(x) for x in id_seq]).lower()
                akt_id = ":".join((enhet_id, akt["aktivitetkode"])).lower()
##                 self.logger.debug("read_kurs_data: enhet_id=%s", enhet_id)
                self.enhet2akt.setdefault(enhet_id, []).append(
                [akt['aktivitetkode'], akt['aktivitetsnavn']])
                self.akt2undform[akt_id] = akt["undformkode"]

        for evu in self._fs.evu.list_kurs():
            id_seq = (self.EVU_PREFIX, evu['etterutdkurskode'],
                      evu['kurstidsangivelsekode'])
            kurs_id = UE2KursID(*id_seq)
            if kurs.has_key(kurs_id):
                # Alle kurs-IDer som stammer fra EVU-kurs prefikses med "EVU:".
                enhet_id = ":".join(id_seq).lower()
                self.kurs2enhet.setdefault(kurs_id, []).append(enhet_id)
                self.enhet2sko[enhet_id] = "%02d%02d00" % (
                    evu['faknr_adm_ansvar'],
                    evu['instituttnr_adm_ansvar'])
                # Da et EVU-kurs alltid vil bestå av kun en
                # "undervisningsenhet", kan vi sette kursnavnet med en
                # gang (uten å måtte sortere slik vi gjorde over for
                # "ordentlige" undervisningsenheter).
                self.kurs2navn[kurs_id] = evu['etterutdkursnavn']

                for akt in self._fs.evu.get_kurs_aktivitet(
                    evu['etterutdkurskode'], evu['kurstidsangivelsekode']):
                    akt_id = ":".join((enhet_id,
                                       akt["aktivitetskode"])).lower()
                    self.enhet2akt.setdefault(enhet_id, []).append(
                        (akt['etterutdkurskode'], akt['aktivitetsnavn']))
                    self.akt2undform[akt_id] = akt["undformkode"]
        self.logger.debug("read_kurs_data: len(self.kurs2enhet)=%i",
                          len(self.kurs2enhet))

    def pwd(self, p):
        pwtype, password = p.split(":")
        type_map = {'md5': 1,
                    'unix': 2,
                    'nt': 3,
                    'plain': 4,
                    'ldap': 5}
        ret = {'pwencryptiontype': type_map[pwtype]}
        if password:
            ret['password'] = password
        return ret
    
    def useraccess(self, access):
        # TODO: move to config section
        mapping = {
            # Not allowed to log in
            0: 'None',
            # Normal user
            'viewmygroups': 'User',
            'allowlogin': 'User',
            # Admin
            'administrator': 'SysAdmin',
            }
        return mapping[access]

    def profile(self, name=None):
        if name is None:
            return 'UiOstdrom2003'
        return name


class FronterXML(object):
    def __init__(self, fname, cf_dir=None, debug_file=None, debug_level=None,
                 fronter=None, include_password=True):
        self.xml = XMLWriter(fname)
        self.xml.startDocument(encoding='ISO-8859-1')
        self.rootEl = 'enterprise'
        self.DataSource = 'UREG2000@uio.no'
        self.cf_dir = cf_dir
        self.debug_file = debug_file
        self.debug_level = debug_level
        self.fronter = fronter
        self.include_password = include_password
        self.cf_id = self.fronter.fronter_host

    def start_xml_file(self, kurs):
        self.xml.comment("Eksporterer data om følgende emner:\n  " + 
                         "\n  ".join(kurs))
        self.xml.startTag(self.rootEl)
        self.xml.startTag('properties')
        self.xml.dataElement('datasource', self.DataSource)
        self.xml.dataElement('target', "ClassFronter/%s" % self.cf_id)
        # :TODO: Tell Fronter (again) that they need to define the set of
        # codes for the TYPE element.
        # self.xml.dataElement('TYPE', "REFRESH")
        self.xml.dataElement('datetime', time.strftime("%F %T %z"))
        self.xml.endTag('properties')

    def user_to_XML(self, id, recstatus, data):
        """Lager XML for en person"""
        self.xml.startTag('person', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        if self.include_password:
            self.xml.dataElement('userid', id,
                                 self.fronter.pwd(data['PASSWORD']))
        self.xml.startTag('name')
        self.xml.dataElement('fn',
                             " ".join([x for x in (data['GIVEN'],
                                                   data['FAMILY'])
                                       if x]))
        self.xml.startTag('n')
        self.xml.dataElement('family', data['FAMILY'])
        self.xml.dataElement('given', data['GIVEN'])
        self.xml.endTag('n')
        self.xml.endTag('name')
        self.xml.dataElement('email', data['EMAIL'])
        self.xml.emptyTag('systemrole',
                          {'systemroletype':
                           fronter.useraccess(data['USERACCESS'])})
        self.xml.startTag('extension')
        self.xml.emptyTag('emailsettings',
                          {'mail_username': id,
                           'mail_password': 'FRONTERLOGIN',
                           'description': 'UiO-email',
                           'mailserver': 'imap.uio.no',
                           'mailtype': 'imap',
                           'imap_serverdirectory': 'INBOX.',
                           'imap_sentfolder': 'Sent',
                           'imap_draftfolder': 'Drafts',
                           'imap_trashfolder': 'Trash',
                           'use_ssl': 1,
                           'defaultmailbox': 'INBOX',
                           'on_delete_action': 'trash',
                           'is_primary': 1,
                           })
        self.xml.endTag('extension')
        self.xml.endTag('person')

    def group_to_XML(self, id, recstatus, data):
        # Lager XML for en gruppe
        self.xml.startTag('group', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'FronterStructure1.0')
        allow_room = data.get('allow_room', 0)
        if allow_room:
            allow_room = 1
        allow_contact = data.get('allow_contact', 0)
        if allow_contact:
            allow_contact = 2
        self.xml.emptyTag('typevalue',
                          {'level': allow_room | allow_contact})
        self.xml.endTag('grouptype')
        self.xml.startTag('description')
        if (len(data['title']) > 60):
            self.xml.emptyTag('short')
            self.xml.dataElement('long', data['title'])
        else:
            self.xml.dataElement('short', data['title'])
        self.xml.endTag('description')
        self.xml.startTag('relationship', {'relation': 1})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', data['parent'])
        self.xml.endTag('sourcedid')
        self.xml.emptyTag('label')
        self.xml.endTag('relationship')
        self.xml.endTag('group')

    def room_to_XML(self, id, recstatus, data):
        # Lager XML for et rom
        #
        # Gamle rom skal aldri slettes automatisk.
        if recstatus == Fronter.STATUS_DELETE:
            return 
        self.xml.startTag('group', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'FronterStructure1.0')
        self.xml.emptyTag('typevalue', {'level': 4})
        self.xml.endTag('grouptype')
        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'Roomprofile1.0')
        self.xml.emptyTag('typevalue', {'level': data['profile']})
        self.xml.endTag('grouptype')
        self.xml.startTag('description')
        if (len(data['title']) > 60):
            self.xml.emptyTag('short')
            self.xml.dataElement('long', data['title'])
        else:
            self.xml.dataElement('short', data['title'])
        self.xml.endTag('description')
        self.xml.startTag('relationship', {'relation': 1})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', data['parent'])
        self.xml.endTag('sourcedid')
        self.xml.emptyTag('label')
        self.xml.endTag('relationship')
        self.xml.endTag('group')

    def personmembers_to_XML(self, gid, recstatus, members):
        # lager XML av medlemer
        self.xml.startTag('membership')
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', gid)
        self.xml.endTag('sourcedid')
        for uname in members:
            self.xml.startTag('member')
            self.xml.startTag('sourcedid')
            self.xml.dataElement('source', self.DataSource)
            self.xml.dataElement('id', uname)
            self.xml.endTag('sourcedid')
            # This is a person member (as opposed to a group).
            self.xml.dataElement('idtype', '1')
            self.xml.startTag('role', {'recstatus': recstatus,
                                       'roletype': Fronter.ROLE_READ})
            self.xml.dataElement('status', '1')
            self.xml.startTag('extension')
            # Member of group, not room.
            self.xml.emptyTag('memberof', {'type': 1})
            self.xml.endTag('extension')
            self.xml.endTag('role')
            self.xml.endTag('member')
        self.xml.endTag('membership')

    def acl_to_XML(self, node, recstatus, groups):
        self.xml.startTag('membership')
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', node)
        self.xml.endTag('sourcedid')
        for gname in groups.keys():
            self.xml.startTag('member')
            self.xml.startTag('sourcedid')
            self.xml.dataElement('source', self.DataSource)
            self.xml.dataElement('id', gname)
            self.xml.endTag('sourcedid')
            # The following member ids are groups.
            self.xml.dataElement('idtype', '2')
            acl = groups[gname]
            if acl.has_key('role'):
                self.xml.startTag('role', {'recstatus': recstatus,
                                           'roletype': acl['role']})
                self.xml.dataElement('status', '1')
                self.xml.startTag('extension')
                self.xml.emptyTag('memberof', {'type': 2}) # Member of room.
            else:
                self.xml.startTag('role', {'recstatus': recstatus})
                self.xml.dataElement('status', '1')
                self.xml.startTag('extension')
                self.xml.emptyTag('memberof', {'type': 1}) # Member of group.
                self.xml.emptyTag('groupaccess',
                                  {'contactAccess': acl['gacc'],
                                   'roomAccess': acl['racc']})
            self.xml.endTag('extension')
            self.xml.endTag('role')
            self.xml.endTag('member')
        self.xml.endTag('membership')

    def end(self):
        self.xml.endTag(self.rootEl)
        self.xml.endDocument()


class IMS_object(object):
    def __init__(self, objtype, **data):
        self.objtype = objtype
        self.data = data.copy()

    def dump(self, xml, recstatus):
        dumper = getattr(self, 'dump_%s' % self.objtype, None)
        if dumper is None:
            raise NotImplementedError, \
                  "Can't dump IMS object of type %s" % (self.objtype,)
        dumper(xml, recstatus)

    def attr_dict(self, required=(), optional=()):
        data = self.data.copy()
        res = {}
        for a in required:
            try:
                res[a] = data.pop(a)
            except KeyError:
                raise ValueError, \
                      "Required <%s> attribute %r not present: %r" % (
                    self.objtype, a, self.data)
        for a in optional:
            if a in data:
                res[a] = data.pop(a)
        # Remaining values in ``data`` should be either sub-objects or
        # DATA.
        return res


class IMSv1_0_object(IMS_object):
    def dump_comments(self, xml, recstatus):
        lang = getattr(self, 'lang', None)
        xml.dataElement('COMMENTS', self.DATA, self.attr_dict())

    def dump_properties(self, xml, recstatus):
        xml.startTag('PROPERTIES', self.attr_dict(optional=('lang',)))
        # TODO: Hva med subelementer som kan forekomme mer enn en gang?
        for subel in ('DATASOURCE', 'TARGET', 'TYPE', 'DATETIME', 'EXTENSION'):
            if subel in self.data:
                self.data[subel].dump(xml, recstatus)
        xml.endTag('PROPERTIES')


def UE2KursID(kurstype, *rest):
    """Lag ureg2000-spesifikk "kurs-ID" av primærnøkkelen til en
    undervisningsenhet eller et EVU-kurs.  Denne kurs-IDen forblir
    uforandret så lenge kurset pågår; den endres altså ikke når man
    f.eks. kommer til et nytt semester.

    Første argument angir hvilken type FS-entitet de resterende
    argumentene stammer fra; enten 'KURS' (for undervisningsenhet) eller
    'EVU' (for EVU-kurs)."""
    kurstype = kurstype.lower()
    if kurstype == 'evu':
        if len(rest) != 2:
            raise ValueError, \
                  "ERROR: EVU-kurs skal identifiseres av 2 felter, " + \
                  "ikke <%s>" % ">, <".join(rest)
        # EVU-kurs er greie; de identifiseres unikt ved to
        # fritekstfelter; kurskode og tidsangivelse, og er modellert i
        # FS uavhengig av semester-inndeling.
        rest = list(rest)
        rest.insert(0, kurstype)
        return ":".join(rest).lower()
    elif kurstype != 'kurs':
        raise ValueError, "ERROR: Ukjent kurstype <%s> (%s)" % (kurstype, rest)

    # Vi vet her at $kurstype er 'KURS', og vet dermed også hvilke
    # elementer som er med i @rest:
    if len(rest) != 6:
        raise ValueError, \
              "ERROR: Undervisningsenheter skal identifiseres av 6 " + \
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
        raise ValueError, \
              "ERROR: Unknown terminkode <%s> for emnekode <%s>." % (
            termk, emnekode)

    # $termnr er ikke del av den returnerte strengen.  Vi har benyttet
    # $termnr for å beregne $termk og $aar ved $termnr == 1; det er
    # altså implisitt i kurs-IDen at $termnr er lik 1 (og dermed
    # unødvendig å ta med).
    ret = "%s:%s:%s:%s:%s:%s" % (kurstype, instnr, emnekode, versjon,
                                 termk, aar)
    return ret.lower()


def init_globals():
    global db, const, logger
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    logger = Factory.get_logger("cronjob")

    cf_dir = '/cerebrum/dumps/Fronter'
    global fs_dir
    fs_dir = '/cerebrum/dumps/FS'

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'rom-profil=',
                                    'uten-dette-semester',
                                    'uten-passord',
                                    'debug-file=', 'debug-level=',
                                    'cf-dir=', 'fs-dir=',
                                    'fs-db-user=', 'fs-db-service=',
                                    ])
    except getopt.GetoptError:
        usage(1)
    debug_file = os.path.join(cf_dir, "x-import.log")
    debug_level = 4
    host = None
    set_pwd = True
    fs_db_user = 'ureg2000'
    fs_db_service = 'FSPROD.uio.no'
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host = val
        elif opt == '--debug-file':
            debug_file = val
        elif opt == '--debug-level':
            debug_level = val
        elif opt == '--uten-dette-semester':
            global include_this_sem
            include_this_sem = False
        elif opt == '--uten-passord':
            set_pwd = False
        elif opt == '--cf-dir':
            cf_dir = val
        elif opt == '--fs-dir':
            fs_dir = val
        elif opt == '--fs-db-user':
            fs_db_user = val
        elif opt == '--fs-db-service':
            fs_db_service = val
        else:
            raise ValueError, "Invalid argument: %r", (opt,)

    fs_db = Database.connect(user=fs_db_user, service=fs_db_service,
                             DB_driver='Oracle')
    global fronter
    # TODO: Bruke dumpfiler fra import_from_FS i stedet for å snakke
    # direkte med FS-databasen.
    fronter = Fronter(host, db, const, fs_db, logger=logger)

    filename = os.path.join(cf_dir, 'test.xml')
    if len(args) == 1:
        filename = args[0]
    elif len(args) <> 0:
        usage(2)

    global fxml
    fxml = FronterXML(filename,
                      cf_dir = cf_dir,
                      debug_file = debug_file,
                      debug_level = debug_level,
                      fronter = fronter,
                      include_password = set_pwd)

    # Finn `uname` -> account-data for alle brukere.
    global new_users
    new_users = get_new_users()


def list_users_for_fronter_export():  # TODO: rewrite this
    ret = []
    posix_user = PosixUser.PosixUser(db)
    email_addrs = posix_user.getdict_uname2mailaddr()
    logger.debug("list_users_for_fronter_export got %d emailaddrs",
                 len(email_addrs))
    for row in posix_user.list_extended_posix_users(
        const.auth_type_md5_crypt):
        tmp = {'email': email_addrs.get(row['entity_name'],
                                        '@'.join((row['entity_name'],
                                                  'ulrik.uio.no'))),
               'uname': row['entity_name']}
        if row['gecos'] is None:
            tmp['fullname'] = row['name']
        else:
            tmp['fullname'] = row['gecos']            
        ret.append(tmp)
    return ret


def get_new_users():
    # Hent info om brukere i cerebrum
    users = {}
    for user in list_users_for_fronter_export():
##         print user['fullname']
        # lagt inn denne testen fordi scriptet feilet uten, har en liten
        # følelse av det burde løses på en annen måte
        if user['fullname'] is None:
            continue
        names = re.split('\s+', user['fullname'].strip())
        user_params = {'FAMILY': names.pop(),
                       'GIVEN': " ".join(names),
                       'EMAIL': user['email'],
                       'USERACCESS': 0,
                       'PASSWORD': 'unix:',
                       }

        if 'All_users' in fronter.export:
            user_params['USERACCESS'] = 'allowlogin'

        if user['uname'] in fronter.admins:
            user_params['USERACCESS'] = 'administrator'

        # The 'plain_users' setting can be useful for debugging.
        if user['uname'] in fronter.plain_users:
            user_params['PASSWORD'] = "plain:%s" % user['uname']
        users[user['uname']] = user_params

    logger.debug("get_new_users returns %i users", len(users))
    return users


def get_group(id):
    group = Factory.get('Group')(db)
    if isinstance(id, str):
        group.find_by_name(id)
    else:
        group.find(id)
    return group


def get_sted(stedkode=None, entity_id=None):
    sted = Factory.get('OU')(db)
    if stedkode is not None:
        sted.find_stedkode(int(stedkode[0:2]),
                           int(stedkode[2:4]),
                           int(stedkode[4:6]),
                           cereconf.DEFAULT_INSTITUSJONSNR)
    else:
        sted.find(entity_id)
    # Only OUs where katalog_merke is set should be returned; if no
    # such OU can be found by moving towards the root of the OU tree,
    # return None.
    if sted.katalog_merke == 'T':
        return sted
    elif (sted.fakultet, sted.institutt, sted.avdeling) == (15, 0, 30):
        # Special treatment of UNIK; even though katalog_merke isn't
        # set for this OU, return it, so that they get their own
        # corridor.
        return sted
    parent_id = sted.get_parent(const.perspective_lt)
    if parent_id is not None and parent_id <> sted.entity_id:
        return get_sted(entity_id = parent_id)
    return None


def register_supergroups():
    register_group("Universitetet i Oslo", root_struct_id, root_struct_id)
    register_group(group_struct_title, group_struct_id, root_struct_id)
    if 'All_users' in fronter.export:
        # Webinterfacet mister litt pusten når man klikker på gruppa
        # All_users (dersom man f.eks. ønsker å gi alle brukere rettighet
        # til noe); oppretter derfor en dummy-gruppe som kun har den
        # /egentlige/ All_users-gruppa som medlem.
        sg_id = "All_users_supergroup"
        register_group("Alle brukere", sg_id, root_struct_id, False, False)
        register_group("Alle brukere (STOR)", 'All_users', sg_id, False, True)

    for sgname in fronter.supergroups:
        # $sgname er på nivå 2 == Kurs-ID-gruppe.  Det er på dette nivået
        # eksport til ClassFronter er definert i Ureg2000.
        try:
            group = get_group(sgname)
        except Errors.NotFoundError:
            continue
        for member_type, group_id in \
            group.list_members(member_type = const.entity_group)[0]:
	    # $gname er på nivå 3 == gruppe med brukere som medlemmer.
	    # Det er disse gruppene som blir opprettet i ClassFronter
	    # som følge av eksporten.
            group = get_group(group_id)
            register_group(group.description, group.group_name,
                           group_struct_id, False, True)
            #
            # All groups should have "View Contacts"-rights on
            # themselves.
            new_acl.setdefault(group.group_name, {})[group.group_name] = {
                'gacc': '100',   # View Contacts
                'racc': '0'} 	 # None
            #
            # Groups populated from FS aren't expanded recursively
            # prior to export.
            for row in \
                group.list_members(member_type = const.entity_account,
                                   get_entity_name = True)[0]:
                uname = row[2]
                if new_users.has_key(uname):
                    if new_users[uname]['USERACCESS'] != 'administrator':
                        new_users[uname]['USERACCESS'] = 'allowlogin'
                    new_groupmembers.setdefault(group.group_name,
                                                {})[uname] = 1


new_acl = {}
new_groupmembers = {}


new_rooms = {}
def register_room(title, room_id, parent_id, profile_name=None):
    new_rooms[room_id] = {
        'title': title,
        'parent': parent_id,
        'CFid': room_id,
        'profile': fronter.profile(profile_name)}


new_group = {}
def register_group(title, group_id, parent_id,
                   allow_room=False, allow_contact=False):
    """Adds info in new_group about group."""
    CF_id = group_id
    if re.search(r'^STRUCTURE/(Enhet|Studentkorridor):', group_id):
        rest = group_id.split(":")
        corr_type = rest.pop(0)

        if not rest[0] in (fronter.EMNE_PREFIX, fronter.EVU_PREFIX):
            rest.insert(0, fronter.EMNE_PREFIX)
        group_id = "%s:%s" % (corr_type, UE2KursID(*rest))
    new_group[group_id] = {'title': title,
                           'parent': parent_id,
                           'allow_room': allow_room,
                           'allow_contact': allow_contact,
                           'CFid': CF_id,
                           }


def build_structure(sko, allow_room=False, allow_contact=False):
    # rekursiv bygging av sted som en gruppe
    if sko == root_sko:
        return root_struct_id
    if not sko:
        return None

    struct_id = "STRUCTURE/Sko:185:%s" % sko
    if ((not new_group.has_key(struct_id)) or
        (allow_room and not new_group[struct_id]['allow_room']) or
	(allow_contact and not new_group[struct_id]['allow_contact'])):
	# Insert ancestors first; by not passing $allow_* on up the
	# tree, we're causing nodes that are created purely as
	# ancestors to allow neither rooms nor contacts.
        sted = get_sted(stedkode=sko)
        if sted is None:
            # This shouldn't happen, but if it does, there's not much
            # we can do to salvage the situation.  Bail out by
            # returning None.
            return None
        try:
            parent_sted = get_sted(
                entity_id=sted.get_parent(const.perspective_lt))
        except Errors.NotFoundError:
	    logger.warn("Stedkode <%s> er uten foreldre; bruker %s" %
                        (sko, root_sko))
	    parent = build_structure(root_sko)
        else:
            parent = build_structure("%02d%02d%02d" % (
                parent_sted.fakultet,
                parent_sted.institutt,
                parent_sted.avdeling))
	register_group(sted.name, struct_id, parent, allow_room, allow_contact)
    return struct_id


def make_profile(enhet_id, aktkode):
    """
    Lag en profil basert på undformkode.

    CF vil ha det slik at en profil for et *nytt* rom, skal være avhengig av
    undformkode som finnes i
    fs.{undaktivitet,kursaktivtet}.undformkode. Dette gjelder ikke alle
    undformkodene, kun et lite utvalg, og dette utvalget er dessverre
    hardkodet (vi får dessverre ingen behagelig tabell i FS/CF som vi kan
    bruke).

    NB! Vi returnerer en id (som skal plasseres rett i XML dump) for det
    aktuelle utvalget av undformkoder. Dersom en slik id ikke finnes,
    returnerer vi None.
    """

    # Revert the UNDFORMKODE -> profile selection logic for now
    # (2005-08), as the owner of the ClassFronter system isn't ready
    # for it yet.
    return None

    undformkode2cfname = {
        "FOR"     : "UiOforelesning",
        "GR"      : "UiOgruppe",
        "KOL"     : "UiOkollokvie",
        "KURS"    : "UiOkurs",
        "LAB"     : "UiOlaboratorie",
        "OBLOPPG" : "UiOoblig",
        "PRO"     : "UiOprosjekt",
        "ØV"      : "UiOøving",
        }

    akt_id = ":".join((enhet_id, aktkode))
    undformkode = fronter.akt2undform.get(akt_id)
    if undformkode not in undformkode2cfname:
        return None
    profile_id = undformkode2cfname[undformkode]
    return profile_id


def process_single_enhet_id(enhet_id, struct_id, emnekode,
                            groups, enhet_node, undervisning_node,
                            termin_suffix=""):
    # I tillegg kommer så evt. rom knyttet til de
    # undervisningsaktivitetene studenter kan melde seg på.
    for akt in fronter.enhet2akt.get(enhet_id, []):
        aktkode, aktnavn = akt

        aktans = "uio.no:fs:%s:aktivitetsansvar:%s" % (
            enhet_id.lower(), aktkode.lower())
        groups['aktansv'].append(aktans)
        aktstud = "uio.no:fs:%s:student:%s" % (
            enhet_id.lower(), aktkode.lower())
        groups['aktstud'].append(aktstud)

        # Aktivitetsansvarlig skal ha View Contacts på studentene i
        # sin aktivitet.
        new_acl.setdefault(aktstud, {})[aktans] = {'gacc': '100',
                                                   'racc': '0'}
        # ... og omvendt.
        new_acl.setdefault(aktans, {})[aktstud] = {'gacc': '100',
                                                   'racc': '0'}

        # Alle med ansvar for (minst) en aktivitet tilknyttet
        # en undv.enhet som hører inn under kurset skal ha
        # tilgang til kursets undervisningsrom-korridor samt
        # lærer- og fellesrom.
        new_acl.setdefault(undervisning_node, {})[aktans] = {
            'gacc': '250',		# Admin Lite
            'racc': '100'}		# Room Creator
        new_acl.setdefault("ROOM/Felles:%s" % struct_id, {})[aktans] = {
            'role': fronter.ROLE_CHANGE}
        new_acl.setdefault("ROOM/Larer:%s" % struct_id, {})[aktans] = {
            'role': fronter.ROLE_CHANGE}

        # Alle aktivitetsansvarlige skal ha "View Contacts" på
        # gruppen All_users dersom det eksporteres en slik.
        if 'All_users' in fronter.export:
            new_acl.setdefault('All_users', {})[aktans] = {'gacc': '100',
                                                           'racc': '0'}

        akt_rom_id = "ROOM/Aktivitet:%s:%s" % (enhet_id.upper(),
                                               aktkode.upper())
        akt_tittel = "%s - %s%s" % (emnekode.upper(), aktnavn, termin_suffix)
        register_room(akt_tittel, akt_rom_id, enhet_node,
                      make_profile(enhet_id, aktkode))
        
        new_acl.setdefault(akt_rom_id, {})[aktans] = {
            'role': fronter.ROLE_CHANGE}
        new_acl.setdefault(akt_rom_id, {})[aktstud] = {
            'role': fronter.ROLE_WRITE}

    # Til slutt deler vi ut "View Contacts"-rettigheter på kryss og
    # tvers.
    for gt in groups.keys():
        other_gt = {'enhansv': ['enhstud', 'aktansv', 'aktstud'],
                    'enhstud': ['enhansv', 'aktansv'],
                    'aktansv': ['enhansv', 'aktansv', 'enhstud'],
                    'aktstud': ['enhansv'],
                   }
        for g in groups[gt]:
            # Alle grupper skal ha View Contacts på seg selv.
            new_acl.setdefault(g, {})[g] = {'gacc': '100',
                                            'racc': '0'}
            #
            # Alle grupper med gruppetype $gt skal ha View
            # Contacts på alle grupper med gruppetype i
            # $other_gt{$gt}.
            for o_gt in other_gt[gt]:
                for og in groups[o_gt]:
                    new_acl.setdefault(og, {})[g] = {'gacc': '100',
                                                     'racc': '0'}


def process_kurs2enhet():
    # TODO: some code-duplication has been reduced by adding
    # process_single_enhet_id.  Recheck that the reduction is correct.
    # It should be possible to move more code to that subroutine.
    for kurs_id in fronter.kurs2enhet.keys():
        ktype = kurs_id.split(":")[0].lower()
        if ktype == fronter.EMNE_PREFIX.lower():
            enhet_sorted = fronter.kurs2enhet[kurs_id][:]
            enhet_sorted.sort(fronter._date_sort)
            # Bruk eldste enhet som $enh_id
            enh_id = enhet_sorted[0]
            enhet = enh_id.split(":", 1)[1]

            # For å ta høyde for at noen flersemesterkurs allerede
            # hadde eksportert enkelte av sine undervisningsenheter
            # til ClassFronter uten at elementene fikk ID som
            # samsvarte med kursets oppstartssemester, fikk kurs med
            # oppstart før høsten 2005 dannet struct_id ut fra den
            # eldste undervisningsenheten i samme kurs som allerede
            # var lagt inn i Fronter.  Det var altså ikke nødvendigvis
            # en "terminnr==1"-enhet som ble til struct_id.
            #
            # For kurs som starter høsten 2005 eller senere, derimot,
            # blir struct_id dannet direkte fra kurs_id, slik at alle
            # struct_id-er samsvarer med "terminnr==1"-enheten.
            #
            termkode, arstall = kurs_id.split(":")[-2:]
            arstall = int(arstall)
            if (arstall == 2005 and termkode == 'høst') or arstall > 2005:
                struct_id = kurs_id.upper() + ":1"
            else:
                struct_id = enh_id.upper()

            Instnr, emnekode, versjon, termk, aar, termnr = enhet.split(":")
            # Opprett strukturnoder som tillater å ha rom direkte under
            # seg.
            sko_node = build_structure(fronter.enhet2sko[enh_id])
            enhet_node = "STRUCTURE/Enhet:%s" % struct_id
            undervisning_node = "STRUCTURE/Studentkorridor:%s" % struct_id

            tittel = "%s - %s, %s %s" % (emnekode.upper(),
                                         fronter.kurs2navn[kurs_id],
                                         termk.upper(), aar)
            multi_enhet = []
            multi_id = ":".join((Instnr, emnekode, termk, aar))
            multi_termin = False
            if (# Det finnes flere und.enh. i semesteret angitt av
                # 'terminkode' og 'arstall' hvor både 'institusjonsnr'
                # og 'emnekode' er like, men 'terminnr' varierer.
                len(fronter.emne_termnr[multi_id]) > 1
                # Det finnes mer enn en und.enh. som svarer til samme
                # "kurs", e.g. både 'høst 2004, terminnr=1' og 'vår
                # 2005, terminnr=2' finnes.
                or len(enhet_sorted) > 1
                # Denne und.enh. har terminnr større enn 1, slik at
                # det er sannsynlig at det finnes und.enh. fra
                # tidligere semester som hører til samme "kurs".
                or int(termnr) > 1):
                #
                # Dersom minst en av testene over slår til, er det her
                # snakk om et "flersemesteremne" (eller i alle fall et
                # emne som i noen varianter undervises over flere
                # semestere).  Ta med terminnr-angivelse i tittelen på
                # kursets hovedkorridor, og semester-angivelse i
                # aktivitetsrommenes titler.
                multi_enhet.append("%s. termin" % termnr)
                multi_termin = True
            if len(fronter.emne_versjon[multi_id]) > 1:
                multi_enhet.append("v%s" % versjon)
            if multi_enhet:
                tittel += ", " + ", ".join(multi_enhet)

            register_group(tittel, enhet_node, sko_node, 1)
            register_group("%s - Undervisningsrom" % emnekode.upper(),
                           undervisning_node, enhet_node, 1);

            # Alle eksporterte kurs skal i alle fall ha ett fellesrom og
            # ett lærerrom.
            register_room("%s - Fellesrom" % emnekode.upper(),
                          "ROOM/Felles:%s" % struct_id,
                          enhet_node)
            register_room("%s - Lærerrom" % emnekode.upper(),
                          "ROOM/Larer:%s" % struct_id,
                          enhet_node)

            for enhet_id in fronter.kurs2enhet[kurs_id]:
                termin_suffix = ""
                if multi_termin:
                    # Finn 'terminkode' og 'arstall' fra enhet_id, og
                    # bruk dette som tittelsuffiks for enhetens
                    # aktivitetsrom.
                    ue_id = enhet_id.split(":")
                    termin_suffix = " %s %s" % (ue_id[4].upper(), # terminkode
                                                ue_id[5], # aar
                                                )
                enhans = "uio.no:fs:%s:enhetsansvar" % enhet_id.lower()
                enhstud = "uio.no:fs:%s:student" % enhet_id.lower()
                # De ansvarlige for undervisningsenhetene som hører til et
                # kurs skal ha tilgang til kursets undv.rom-korridor.
                new_acl.setdefault(undervisning_node, {})[enhans] = {
                    'gacc': '250',		# Admin Lite
                    'racc': '100'}		# Room Creator

                # Alle enhetsansvarlige skal ha "View Contacts" på gruppen
                # All_users dersom det eksporteres en slik.
                if 'All_users' in fronter.export:
                    new_acl.setdefault('All_users', {})[enhans] = {
                        'gacc': '100',
                        'racc': '0'}

                # Gi studenter+lærere i alle undervisningsenhetene som
                # hører til kurset passende rettigheter i felles- og
                # lærerrom.
                new_acl.setdefault("ROOM/Felles:%s" % struct_id,
                                   {}).update({
                    enhans: {'role': fronter.ROLE_CHANGE},
                    enhstud: {'role': fronter.ROLE_WRITE}
                    })
                new_acl.setdefault("ROOM/Larer:%s" % struct_id,
                                   {})[enhans] = {
                    'role': fronter.ROLE_CHANGE}

                groups = {'enhansv': [enhans],
                          'enhstud': [enhstud],
                          'aktansv': [],
                          'aktstud': [],
                         }
                process_single_enhet_id(enhet_id, struct_id,
                                        emnekode, groups,
                                        enhet_node, undervisning_node,
                                        termin_suffix)
        elif ktype == fronter.EVU_PREFIX.lower():
            # EVU-kurs er modellert helt uavhengig av semester-inndeling i
            # FS, slik at det alltid vil være nøyaktig en enhet-ID for
            # hver EVU-kurs-ID.  Det gjør en del ting nokså mye greiere...
            for enhet_id in fronter.kurs2enhet[kurs_id]:
                kurskode, tidskode = enhet_id.split(":")[1:3]
                # Opprett strukturnoder som tillater å ha rom direkte under
                # seg.
                sko_node = build_structure(fronter.enhet2sko[enhet_id])
                struct_id = enhet_id.upper()
                enhet_node = "STRUCTURE/Enhet:%s" % struct_id
                undervisning_node = "STRUCTURE/Studentkorridor:%s" % struct_id
                tittel = "%s - %s, %s" % (kurskode.upper(),
                                          fronter.kurs2navn[kurs_id],
                                          tidskode.upper())
                register_group(tittel, enhet_node, sko_node, 1)
                register_group("%s  - Undervisningsrom" % kurskode.upper(),
                               undervisning_node, enhet_node, 1)
                enhans = "uio.no:fs:%s:enhetsansvar" % enhet_id.lower()
                enhstud = "uio.no:fs:%s:student" % enhet_id.lower()
                new_acl.setdefault(undervisning_node, {})[enhans] = {
                    'gacc': '250',		# Admin Lite
                    'racc': '100'}		# Room Creator

                # Alle enhetsansvarlige skal ha "View Contacts" på gruppen
                # All_users dersom det eksporteres en slik.
                if 'All_users' in fronter.export:
                    new_acl.setdefault('All_users', {})[enhans] = {
                        'gacc': '100',
                        'racc': '0'}

                # Alle eksporterte emner skal i alle fall ha ett
                # fellesrom og ett lærerrom.
                register_room("%s - Fellesrom" % kurskode.upper(),
                              "ROOM/Felles:%s" % struct_id, enhet_node)
                new_acl.setdefault("ROOM/Felles:%s" % struct_id,
                                   {})[enhans] = {
                    'role': fronter.ROLE_CHANGE}
                new_acl.setdefault("ROOM/Felles:%s" % struct_id,
                                   {})[enhstud] = {
                    'role': fronter.ROLE_WRITE}
                register_room("%s - Lærerrom" % kurskode.upper(),
                              "ROOM/Larer:%s" % struct_id, enhet_node)
                new_acl.setdefault("ROOM/Larer:%s" % struct_id,
                                   {})[enhans] = {
                    'role': fronter.ROLE_CHANGE}
                groups = {'enhansv': [enhans],
                          'enhstud': [enhstud],
                          'aktansv': [],
                          'aktstud': [],
                          }
                process_single_enhet_id(enhet_id, struct_id,
                                        kurskode, groups,
                                        enhet_node, undervisning_node)
        else:
            raise ValueError, \
                  "Unknown type <%s> for course <%s>" % (ktype, kurs_id)


def usage(exitcode):
    print "Usage: generate_fronter_full.py OUTPUT_FILENAME"
    sys.exit(exitcode)


def main():
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    init_globals()

    fxml.start_xml_file(fronter.kurs2enhet.keys())

    # Registrer en del semi-statiske strukturnoder.  Sørger også for
    # at alle brukere som er medlem i eksporterte kurs blir gitt
    # innloggingsrettigheter.
    register_supergroups()

    # Spytt ut <person>-elementene.
    for uname, data in new_users.iteritems():
        fxml.user_to_XML(uname, fronter.STATUS_ADD, data)

    logger.info("process_kurs2enhet()")
    process_kurs2enhet()

    for gname, data in new_group.iteritems():
        fxml.group_to_XML(gname, fronter.STATUS_UPDATE, data)
    for room_id, data in new_rooms.iteritems():
        fxml.room_to_XML(room_id, fronter.STATUS_UPDATE, data)

    for gname, members_as_dict in new_groupmembers.iteritems():
        fxml.personmembers_to_XML(gname, fronter.STATUS_UPDATE,
                                  members_as_dict.keys())
    for struct_id, data in new_acl.iteritems():
        fxml.acl_to_XML(struct_id, fronter.STATUS_UPDATE, data)
    fxml.end()


if __name__ == '__main__':
    main()

# arch-tag: e834ec44-6e76-4616-b4a9-aaf56a279b2b
