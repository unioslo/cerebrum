#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2004-2017 University of Oslo, Norway
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

"""Generate Fronter XML-file from FS/Cerebrum.

This script generates an XML file reflecting the (fronter) group structure in
Cerebrum built by the complementary script populate_fronter_groups.py.
p_f_g.py creates the proper groups in Cerebrum (based on the information from
FS) and assigns proper fronter spreads to them. This script loads the groups
from Cerebrum and additional info from FS and creates an XML file that can be
used to populate all of UiO's fronter instances.

Group names are used to merge information from Cerebrum and FS. All of the
fronter groups have a unique name structure (cf. p_f_g.py). Unique FS 'keys'
can be extracted from the groups' names.

Terminology: undenh/undakt/kurs/kursakt/kull are defined in p_f_g.py.
"""

from __future__ import unicode_literals

import getopt
import locale
import os
import re
import sys
import time

from collections import defaultdict
from six import string_types, text_type

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory, make_timer
from Cerebrum.modules.no.uio.fronter_lib import (XMLWriter, UE2KursID,
                                                 key2fields, fields2key,
                                                 get_host_config)
from Cerebrum.modules.no.uio.fronter_lib import semester_number
from Cerebrum.modules.xmlutils.fsxml2object import EduDataGetter


root_sko = '900199'
root_ou_id = 'will be set later'
root_struct_id = 'UiO root node'
group_struct_id = "UREG2000@uio.no imported groups"
group_struct_title = 'Automatisk importerte grupper'
entity2name = None


db = const = logger = None
fronter = fxml = None
include_this_sem = True
new_users = None


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
    KULL_PREFIX = 'KULL'

    def __init__(self, fronter_host, db, const,
                 undenh_file, undakt_file, evu_file, kursakt_file, kull_file,
                 logger=None):
        timer = make_timer(logger, 'Starting __init__...')
        self.fronter_host = fronter_host
        self.db = db
        self.const = const
        self.logger = logger
        _config = get_host_config(db, fronter_host)
        for k in ('DBinst', 'admins', 'export'):
            setattr(self, k, _config[k])
        self.plain_users = _config.get('plain_users', ())
        self.spread = _config.get('spread', None)
        self.logger.debug("Fronter: leser eksporterbare grupper")
        self.exportable = self.get_exportable_groups()
        self.logger.debug("Fronter: len(self.exportable)=%i",
                          len(self.exportable))
        self.kurs2navn = defaultdict(list)
        self.kurs2enhet = defaultdict(list)
        self.enhet2sko = {}
        self.enhet2akt = defaultdict(list)
        self.emne_versjon = defaultdict(dict)
        self.emne_termnr = defaultdict(dict)
        # Cache av undakt -> romprofil, siden vi ønsker å ha spesialiserte
        # romprofiler.
        self.akt2room_profile = {}

        # A mapping from an internal unique key to 'LMSrommalkode'
        # (i.e. Fronter profile) specified for that particular entity (undenh,
        # undakt, evu, kursakt or kull).
        self.entity2room_profile = dict()
        if 'FS' in [x[0:2] for x in self.export]:
            self.read_kurs_data(undenh_file, undakt_file, evu_file,
                                kursakt_file, kull_file)
        self.logger.debug("entity2room_profile has %d elements",
                          len(self.entity2room_profile))

        # ugh!
        t = time.localtime()[0:3]
        self.year = t[0]
        if t[1] <= 6:
            self.semester = 'VÅR'
        else:
            self.semester = 'HØST'
        timer('... __init__ done.')

    def expand_kull_group(self, g_id):
        """Recursively fetch all group members of group with g_id.

        @param group: Factory.get('Group')(<db>)

        @param g_id:
          Group id for the root of the 'tree' we return.
        @param g_id: basestring.

        @return:
          A dict mapping group names to group_ids.
        @rtype: dict
        """

        result = dict()
        group = Factory.get("Group")(db)
        group.find(g_id)
        for row in group.search_members(group_id=group.entity_id,
                                        member_type=const.entity_group):
            e_id = int(row["member_id"])
            if e_id not in entity2name:
                logger.warn("No name for member id=%s of group name=%s id=%s",
                            e_id, group.group_name, group.entity_id)
                continue
            if e_id in result:
                continue

            group.clear()
            group.find(e_id)
            result[e_id] = group.description
            result.update(self.expand_kull_group(e_id))

        return result

    def get_exportable_groups(self):
        """Return a dict with group names for groups that are to be exported
        to Fronter.

        Such groups have *only* account as members and they will be mapped to
        corresponding groups in Fronter. Additionally, we will generate
        suitable Fronter structure nodes, based on these group names.

        @rtype: dict
        @return
          A dict mapping group names to group_ids and descriptions for all
          groups that are supposed to end up in the Fronter xml file (i.e.
          those that have the right fronter spread).
        """

        if 'FS' in self.export:
            group = Factory.get("Group")(self.db)
            result = dict()
            logger.debug("Fetching exportable groups...")
            for g in group.search(spread=int(getattr(self.const, self.spread))):
                group_name = g['name']
                entity_id = g['group_id']
                if not group_name:
                    continue

                # 'kull' groups are a bit special, since fronter spreads are
                # inherited by group members for any given 'kull'. If a 'kull'
                # group A has a fronter spread and a member B, then B would be
                # registered as well here, as if it had fronter spreads.
                key = self._group_name2key(group_name)
                if key and key.find("kull") == 0:
                    addition = self.expand_kull_group(entity_id)
                    logger.debug("Additional kull groups added: %s",
                                 list(addition.iterkeys()))
                    result.update(addition)

                # result is supposed to contain group names for groups where
                # accounts are members. However, 'kull' groups with fronter
                # spreads are also the ones with group members only. It is
                # harmless to include them in this dictionary.
                result[entity_id] = g['description']
            logger.debug("... done")
            return result
        elif 'FS_all' in self.export:
            # Is this used at all?
            raise ValueError("didn't think this was in use")
        else:
            # No FS-synchronisation; return an empty dict.
            return {}

    def _date_sort(self, x, y):
        """Sort by year, then by semester"""
        if(x[0] != y[0]):
            return cmp(x[0], y[0])
        return cmp(y[1][0], x[1][0])

    def _group_name2key(self, name):
        """Remap a group name to a key that can be compared with FS data.

        Fronter group names are composed of a number of ':'-separated fields.
        There are 5 different group categories:
        undenh/undakt/kurs/kursakt/kull. Every category has a varying number
        of fields.

        A few examples for the 5 categories:

        - undenh:  uio.no:fs:kurs:185:mas4530:1:høst:2007:1:student
        - undakt:  uio.no:fs:kurs:185:mas4530:1:høst:2007:1:dlo:1-1
        - kurs:    uio.no:fs:evu:14-kun2502k:2007-høst:enhetsansvar
        - kursakt: uio.no:fs:evu:14-tolkaut:2005-vår:aktivitetsansvar:1-1
        - kull:    uio.no:fs:kull:realmas:høst:2007:student

        To produce a key (that can later be used to filter FS-data), we strip
        the prefix, and student/enhetsansvar/dlo/etc. (there are about 12
        possibilities there). The keys would then look like this:

        - undenh:  kurs:185:mas4530:1:høst:2007:1
        - undakt:  kurs:185:mas4530:1:høst:2007:1:1-1
        - kurs:    evu:14-kun2502k:2007-høst
        - kursakt: evu:14-tolkaut:2005-vår:1-1
        - kull:    kull:realmas:høst:2007

        NB! Multiple-semester entities are a bit tough, since terminnr part of
        the key has to be ignored on occasions. However, the key for such
        entities will nonetheless contain terminnr.

        @type name: basestring
        @param name:
          Group name for which a key is to be generated.

        @rtype: basestring
        @return:
          Key that can be used to filter FS-data.
        """

        fields = key2fields(name)
        start = 0
        # remove common prefix
        if fields[start] == "internal":
            start += 1
        if fields[start] == "uio.no":
            start += 1
        if fields[start] == "fs":
            start += 1

        # extract the fields for the key
        key = None
        count = len(fields) - start
        if fields[start] == "kurs":
            if count == 8:
                # undenh
                key = fields[start:-1]
            elif count == 9:
                # undakt
                key = fields[start:-2] + [fields[-1], ]
        elif fields[start] == "evu":
            if count == 4:
                # kurs
                key = fields[start:-1]
            elif count == 5:
                # kursakt
                key = fields[start:-2] + [fields[-1], ]
        elif fields[start] == "kull":
            if count == 4:
                # internal:uio.no:fs:kull:...
                key = fields[start:]
            if count == 5:
                # uio.no:fs:kull:...:{dlo,student,etc}
                key = fields[start:-1]
        else:
            self.logger.warn("Ukjent kurstype: <%s> (group name: <%s>) "
                             "(not in 'kull', 'kurs', 'evu')",
                             fields[start], name)
            return None

        # IVR 2007-11-07 FIXME: Not always an error, since we have a lot of
        # "old-style fronter group"-baggage with spreads. They are harmless,
        # but there are a lot of them, and it's probably not a good idea to
        # generate an error message.
        if key is None:
            self.logger.debug("Kunne ikke lage nøkkel av gruppenavn <%s>",
                              name)
            return None

        return fields2key(*key)

    def read_kurs_data(self, undenh_file, undakt_file, evu_file,
                       kursakt_file, kull_file):
        """Fetch FS data and populate internal data structures.

        This method populates a number of internal dicts with names, places,
        etc. pertinent to the entities that end up in the XML file.
        """

        # First we have to load all the keys for all of the exportable
        # groups. The keys connect groups in Cerebrum with the corresponding
        # data in FS.
        kurs = set()
        for group_id in self.exportable:
            group_name = entity2name[group_id]
            key = self._group_name2key(group_name)
            if key is None:
                continue
            self.logger.debug("group_name <%s> => key <%s>", group_name, key)
            kurs.add(key)

        self.logger.debug("len(self.exportable) = %d; len(kurs) = %d",
                          len(self.exportable), len(kurs))

        # Fetch all the undenh
        self._read_undenh_data(kurs, undenh_file)
        # ... and undakt
        self._read_undakt_data(kurs, undakt_file)
        # ... and EVU-kurs
        self._read_evu_data(kurs, evu_file)
        # ... and EVU-kursakt
        self._read_kursakt_data(kurs, kursakt_file)
        # ... and finally kull
        self._read_kull_data(kurs, kull_file)

        # IVR 2007-10-13 TBD: How do we clean up the spreads?
        #
        # - Kull spreads cannot be cleaned up automatically, because they are
        #   assigned manually.
        # - undenh/undakt/kurs/kursakt disappearing from the FS-data keep
        #   their spreads. These should be potentially tracked down and
        #   cleaned up. (I.e. those groups in Cerebrum with fronterspreads but
        #   without any corresponding fronter data should lose their spreads).
    # end read_kurs_data

    def _read_undenh_data(self, kurs, undenh_file):
        """Scan all undenh in FS and populate the internal data structures for
        those undenh that are to be exported.

        NB! Watch out for naming of multisemester subjects (flersemesteremner)

        @param kurs:
          Mapping with keys identifying 'exportable' groups.
        @type kurs: dict
        """

        self.logger.debug("Leser alle undenh fra %s...", undenh_file)
        for undenh in EduDataGetter(undenh_file, logger).iter_undenh():
            id_seq = (self.EMNE_PREFIX, undenh['institusjonsnr'],
                      undenh['emnekode'], undenh['versjonskode'],
                      undenh['terminkode'], undenh['arstall'],
                      undenh['terminnr'])
            # NB! kurs_id != key
            kurs_id = UE2KursID(*id_seq)
            key = fields2key(*id_seq)

            # undenh is not exportable
            if key not in kurs:
                continue

            if undenh["lmsrommalkode"]:
                self.entity2room_profile[key] = undenh["lmsrommalkode"]

            self.logger.debug("registrerer undenh <%s> (key: %s)", id_seq, key)

            self.kurs2enhet[kurs_id].append(key)
            multi_id = fields2key(undenh['institusjonsnr'], undenh['emnekode'],
                                  undenh['terminkode'], undenh['arstall'])
            self.emne_versjon[multi_id]["v%s" % undenh['versjonskode']] = 1
            self.emne_termnr[multi_id][undenh['terminnr']] = 1

            full_sko = "%02d%02d%02d" % (int(undenh['faknr_kontroll']),
                                         int(undenh['instituttnr_kontroll']),
                                         int(undenh['gruppenr_kontroll']))
            if full_sko in ("150030",):
                # UNIK is special; they get their own corridor. It's like that
                # by design.
                self.enhet2sko[key] = full_sko
            else:
                self.enhet2sko[key] = "%02d%02d00" % (
                    int(undenh['faknr_kontroll']),
                    int(undenh['instituttnr_kontroll']))

            emne_tittel = undenh['emnenavn_bokmal']
            if len(emne_tittel) > 50:
                emne_tittel = undenh['emnenavnfork']
            self.kurs2navn[kurs_id].append(
                [undenh['arstall'], undenh['terminkode'], emne_tittel])

        # Once all the names have been collected, we chose the correct name
        # based on date (essential for multisemester subjects
        # (flersemesteremner))
        for kurs_id, names in self.kurs2navn.iteritems():
            names.sort()
            self.kurs2navn[kurs_id] = names[0][2]

        self.logger.debug("Ferdig med undenh data fra FS")

    def _read_undakt_data(self, kurs, undakt_file):
        """Scan all undakt from FS and populate the internal data structures
        for those undakt that are to be exported.

        @param kurs:
          Same as L{_read_undenh_data}.
        @type kurs: dict
        """

        self.logger.debug("Leser alle undakt fra %s...", undakt_file)
        for undakt in EduDataGetter(undakt_file, logger).iter_undakt():
            id_seq = (self.EMNE_PREFIX, undakt['institusjonsnr'],
                      undakt['emnekode'], undakt['versjonskode'],
                      undakt['terminkode'], undakt['arstall'],
                      undakt['terminnr'])
            enhet_id = fields2key(*id_seq)
            key = fields2key(enhet_id, undakt["aktivitetkode"])
            kurs_id = UE2KursID(*id_seq)

            # undakt is not exportable
            if key not in kurs:
                continue

            # IVR 2007-09-23 Make sure that the corresponding undenh also ends
            # up in fronter. If not, the structures in Fronter would look
            # really weird. We have been asked to warn about this.
            if enhet_id not in self.kurs2enhet.get(kurs_id, list()):
                self.logger.warn("undakt <%s> er med i utplukket, men ikke "
                                 "undenh <%s>", key, enhet_id)
                continue

            self.logger.debug("registrerer undakt for <%s> (key: %s)",
                              id_seq, key)

            self.enhet2akt[enhet_id].append(
                (undakt['aktivitetkode'], undakt['aktivitetsnavn'],
                 undakt['terminkode'], undakt['arstall'], undakt['terminnr']))

            if undakt["lmsrommalkode"]:
                self.entity2room_profile[key] = undakt["lmsrommalkode"]

    def _read_evu_data(self, kurs, evu_file):
        """Scan all EVU-kurs and populate the internal data structures
        for those entities that are to be exported.

        @param kurs:
          Same as L{_read_undenh_data}.
        @type kurs: dict
        """

        self.logger.debug("Leser alle EVU-kurs/kursakt fra FS...")
        for evu in EduDataGetter(evu_file, logger).iter_evu():
            id_seq = (self.EVU_PREFIX, evu['etterutdkurskode'],
                      evu['kurstidsangivelsekode'])
            key = fields2key(*id_seq)

            # EVU-kurs without fronter spreads are not going to fronter.
            if key not in kurs:
                continue

            self.logger.debug("registrerer EVU-kurs <%s> (key: %s)",
                              id_seq, key)
            self.kurs2enhet[key].append(key)
            self.enhet2sko[key] = "%02d%02d00" % (
                int(evu['faknr_adm_ansvar']),
                int(evu['instituttnr_adm_ansvar']))
            # The correct name for EVU-kurs is always readily available (as
            # opposed to multisemester subjects (flersemesteremner)).
            self.kurs2navn[key] = evu['etterutdkursnavn']

            if evu["lmsrommalkode"]:
                self.entity2room_profile[key] = evu["lmsrommalkode"]

    def _read_kursakt_data(self, kurs, kursakt_file):
        """Scan all EVU-kursakt and populate the internal data structures for
        those entities that are to be exported.

        @param kurs:
          Same as L{_read_undenh_data}.
        @type kurs: dict
        """

        for kursakt in EduDataGetter(kursakt_file, logger).iter_kursakt():
            id_seq = (self.EVU_PREFIX, kursakt['etterutdkurskode'],
                      kursakt['kurstidsangivelsekode'])
            key = fields2key(*id_seq)
            akt_id = fields2key(key, kursakt["aktivitetskode"])

            # EVU-kurs without fronter spreads are not going to fronter.
            if key not in kurs:
                continue

            # If kursakt has no fronter spreads, ignore it.
            if akt_id not in kurs:
                self.logger.debug("ignorerer EVU-kursakt for <%s> "
                                  "(EVU-kurs %s)", akt_id, key)
                continue

            self.logger.debug("registrerer EVU-kursakt for <%s> (key: %s)",
                              id_seq, akt_id)
            self.enhet2akt[key].append(
                (kursakt['aktivitetskode'], kursakt['aktivitetsnavn']))

            if kursakt["lmsrommalkode"]:
                self.entity2room_profile[key] = kursakt["lmsrommalkode"]

    def _read_kull_data(self, kurs, kull_file):
        """Scan all kull and populate the internal data structures for those
        that are to be exported.

        This one is just like all the other _read_*_data.

        @param kurs:
          Same as L{_read_undenh_data}.
        @type kurs: dict
        """

        self.logger.debug("Leser alle kull fra FS...")
        for kull in EduDataGetter(kull_file, logger).iter_kull():
            id_seq = (self.KULL_PREFIX, kull["studieprogramkode"],
                      kull["terminkode"], kull["arstall"])
            key = fields2key(*id_seq)

            # kull without spreads will be excluded.
            if key not in kurs:
                continue

            self.kurs2enhet[key].append(key)
            self.enhet2sko[key] = "%02d%02d%02d" % (
                int(kull["faknr_studieansv"]),
                int(kull["instituttnr_studieansv"]),
                int(kull["gruppenr_studieansv"]),)
            self.kurs2navn[key] = kull["studiekullnavn"]
            self.logger.debug("registrerer kull <%s> (key: %s)", id_seq, key)

            if kull["lmsrommalkode"]:
                self.entity2room_profile[key] = kull["lmsrommalkode"]

    def pwd(self, p):
        pwtype, password = p.split(":")
        type_map = {'md5': 1,
                    'unix': 2,
                    'nt': 3,
                    'plain': 4,
                    'ldap': 5}
        ret = {'pwencryptiontype': type_map['ldap']}
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


# A couple of shorthands, to avoid sprinkling the code with magic constants
admin_lite = {
    'gacc': '250',
    'racc': '100', }
view_contacts = {
    'gacc': '100',
    'racc': '0', }

# A mapping with permissions for different contexts:
#
# 'undenh'  - permissions for undenh and EVU-kurs
# 'undakt'  - permissions for undakt and EVU-kursakt
# 'kull'    - permissions for kull
# 'student' - permissions for student groups.
#
# Each sub-dictionary lists roles that we may encounter, and their permissions
# with respect to various fronter constructions (fellesrom, lærerrom and so
# on). Some entries may be missing (i.e. a specific role may not have any
# permissions defined for a specific fronter structure; e.g. 'tolk' has
# no permissions defined for 'larer') This means that that particular role
# does NOT have any permissions wrt the specified group/structure. The code
# must be prepared for such an eventuality.
#
# The same roles in different sub-dictionaries (may) have different set of
# attributes.
# IVR 2007-11-08 TBD: This is soo ugly and huge. There should probably a
# function that asserts the spelling consistency of all the keys.
kind2permissions = {
    #
    # Permissions for undenh/EVU-kurs
    'undenh': {'admin': {'felles': Fronter.ROLE_CHANGE,
                         'larer': Fronter.ROLE_CHANGE,
                         'korridor': admin_lite,
                         'student': view_contacts},
               'dlo':  {'felles': Fronter.ROLE_CHANGE,
                        'larer': Fronter.ROLE_CHANGE,
                        'korridor': admin_lite,
                        'student': view_contacts},
               'fagansvar': {'felles': Fronter.ROLE_CHANGE,
                             'larer': Fronter.ROLE_CHANGE,
                             'korridor': admin_lite,
                             'student': view_contacts},
               'foreleser': {'felles': Fronter.ROLE_DELETE,
                             'larer': Fronter.ROLE_DELETE,
                             'korridor': admin_lite,
                             'student': view_contacts},
               'gjestefore': {'felles': Fronter.ROLE_DELETE,
                              'larer': Fronter.ROLE_DELETE,
                              'korridor': admin_lite,
                              'student': view_contacts},
               'gruppelære': {
                   'felles': Fronter.ROLE_DELETE,
                   'larer': Fronter.ROLE_DELETE,
                   'korridor': admin_lite,
                   'student': view_contacts},
               'hovedlærer': {
                   'felles': Fronter.ROLE_CHANGE,
                   'larer': Fronter.ROLE_CHANGE,
                   'korridor': admin_lite,
                   'student': view_contacts},
               'it-ansvarl': {'felles': Fronter.ROLE_CHANGE,
                              'larer': Fronter.ROLE_CHANGE,
                              'korridor': admin_lite,
                              'student': view_contacts},
               'lærer': {
                   'felles': Fronter.ROLE_CHANGE,
                   'larer': Fronter.ROLE_CHANGE,
                   'korridor': admin_lite,
                   'student': view_contacts},
               'sensor': {'felles': Fronter.ROLE_DELETE,
                          'larer': Fronter.ROLE_DELETE,
                          'korridor': admin_lite,
                          'student': view_contacts},
               'studiekons': {'felles': Fronter.ROLE_CHANGE,
                              'larer': Fronter.ROLE_CHANGE,
                              'korridor': admin_lite,
                              'student': view_contacts},
               'tolk': {'felles': Fronter.ROLE_READ,
                        # 'larer': NOTIMPLEMENTED on purpose
                        # 'korridor': NOTIMPLEMENTED on purpose
                        'student': view_contacts},
               'tilsyn': {'felles': Fronter.ROLE_READ,
                          # 'larer': NOTIMPLEMENTED on purpose
                          # 'korridor': NOTIMPLEMENTED on purpose
                          'student': view_contacts}, },
    #
    # Permissions for undakt/EVU-kursaktivitet
    'undakt': {'admin': {'felles': Fronter.ROLE_CHANGE,
                         'larer': Fronter.ROLE_CHANGE,
                         'undakt': Fronter.ROLE_CHANGE,
                         'korridor': admin_lite,
                         'student': view_contacts},
               'dlo':  {'felles': Fronter.ROLE_CHANGE,
                        'larer': Fronter.ROLE_CHANGE,
                        'undakt': Fronter.ROLE_CHANGE,
                        'korridor': admin_lite,
                        'student': view_contacts},
               'fagansvar': {'felles': Fronter.ROLE_CHANGE,
                             'larer': Fronter.ROLE_CHANGE,
                             'undakt': Fronter.ROLE_CHANGE,
                             'korridor': admin_lite,
                             'student': view_contacts},
               'foreleser': {'felles': Fronter.ROLE_DELETE,
                             'larer': Fronter.ROLE_DELETE,
                             'undakt': Fronter.ROLE_DELETE,
                             'korridor': admin_lite,
                             'student': view_contacts},
               'gjestefore': {'felles': Fronter.ROLE_DELETE,
                              'larer': Fronter.ROLE_DELETE,
                              'undakt': Fronter.ROLE_DELETE,
                              'korridor': admin_lite,
                              'student': view_contacts},
               'gruppelære': {
                   'felles': Fronter.ROLE_DELETE,
                   'larer': Fronter.ROLE_DELETE,
                   'undakt': Fronter.ROLE_DELETE,
                   'korridor': admin_lite,
                   'student': view_contacts},
               'hovedlærer': {
                   'felles': Fronter.ROLE_CHANGE,
                   'larer': Fronter.ROLE_CHANGE,
                   'undakt': Fronter.ROLE_CHANGE,
                   'korridor': admin_lite,
                   'student': view_contacts},
               'it-ansvarl': {'felles': Fronter.ROLE_CHANGE,
                              'larer': Fronter.ROLE_CHANGE,
                              'undakt': Fronter.ROLE_CHANGE,
                              'korridor': admin_lite,
                              'student': view_contacts},
               'lærer': {
                   'felles': Fronter.ROLE_CHANGE,
                   'larer': Fronter.ROLE_CHANGE,
                   'undakt': Fronter.ROLE_CHANGE,
                   'korridor': admin_lite,
                   'student': view_contacts},
               'sensor': {'felles': Fronter.ROLE_DELETE,
                          'larer': Fronter.ROLE_DELETE,
                          'undakt': Fronter.ROLE_DELETE,
                          'korridor': admin_lite,
                          'student': view_contacts},
               'studiekons': {'felles': Fronter.ROLE_CHANGE,
                              'larer': Fronter.ROLE_CHANGE,
                              'undakt': Fronter.ROLE_CHANGE,
                              'korridor': admin_lite,
                              'student': view_contacts},
               'tolk': {'felles': Fronter.ROLE_READ,
                        # 'larer': NOTIMPLEMENTED on purpose
                        'undakt': Fronter.ROLE_READ,
                        # 'korridor': NOTIMPLEMENTED on purpose
                        'student': view_contacts, },
               'tilsyn': {'felles': Fronter.ROLE_READ,
                          # 'larer': NOTIMPLEMENTED on purpose
                          'undakt': Fronter.ROLE_READ,
                          # 'korridor': NOTIMPLEMENTED on purpose
                          'student': view_contacts, }, },
    #
    # Permissions for kull.
    'kull': {'admin': {'kullrom': Fronter.ROLE_CHANGE,
                       'korridor': admin_lite, },
             'dlo':  {'kullrom': Fronter.ROLE_CHANGE,
                      'korridor': admin_lite, },
             'fagansvar': {'kullrom': Fronter.ROLE_CHANGE,
                           'korridor': admin_lite, },
             'foreleser': {'kullrom': Fronter.ROLE_DELETE,
                           'korridor': admin_lite, },
             'gjestefore': {'kullrom': Fronter.ROLE_DELETE,
                            'korridor': admin_lite, },
             'gruppelære': {
                 'kullrom': Fronter.ROLE_DELETE,
                 'korridor': admin_lite, },
             'hovedlærer': {
                 'kullrom': Fronter.ROLE_CHANGE,
                 'korridor': admin_lite, },
             'it-ansvarl': {'kullrom': Fronter.ROLE_CHANGE,
                            'korridor': admin_lite, },
             'lærer': {
                 'kullrom': Fronter.ROLE_CHANGE,
                 'korridor': admin_lite, },
             'sensor': {'kullrom': Fronter.ROLE_DELETE,
                        'korridor': admin_lite, },
             'studiekons': {'kullrom': Fronter.ROLE_CHANGE,
                            'korridor': admin_lite, },
             'tolk': {'kullrom': Fronter.ROLE_READ,
                      # 'korridor': NOTIMPLEMENTED on purpose
                      },
             'tilsyn': {'kullrom': Fronter.ROLE_READ,
                        # 'korridor': NOTIMPLEMENTED on purpose
                        },
             },
    'student': {'undakt': Fronter.ROLE_WRITE,
                'undenh': Fronter.ROLE_WRITE, },
}


def process_undakt_permissions(template, korridor, fellesrom,
                               studentnode, undakt_node):
    """Assign fronter permissions to undakt/evu-kursakt roles.

    Works much like L{process_undenh_permissions}, except for
    undakt/EVU-kursakt.

    @param template:
      A template for nameing the fronter groups (for different roles). A
      typical template would look like this:

          uio.no:fs:kurs:185:noas4103:1:høst:2007:1:%s:1-1

      The role itself (admin, sensor, etc.) will be interpolated.
    @type template: basestring

    @param korridor:
      Same as in L{process_undenh_permissions}.

    @param fellesrom:
      Same as in L{process_undenh_permissions}.

    @param studentnode:
      Student group id for students registered for this undakt/kursakt. E.g.:

          uio.no:fs:kurs:185:nor4308:1:høst:2007:1:student:1-1
    @type studentnode: basestring

    @param undakt_node:
      Fronter room id for this undakt/kursakt. E.g.:

          ROOM/Aktivitet:KURS:185:SVMET1010:1:HØST:2007:1:2-4
    @type undakt_node: basestring
    """

    permissions = kind2permissions['undakt']
    student_permissions = kind2permissions['student']
    for group_name, role_permissions in permissions.iteritems():

        xml_name = (template % group_name).lower()

        # Every group has 'view contacts' on itself.
        new_acl[xml_name][xml_name] = view_contacts

        # The role holders have special permissions in the student group.
        new_acl[studentnode][xml_name] = role_permissions['student']
        # The student group has 'view contacts' on the role holders.
        new_acl[xml_name][studentnode] = view_contacts

        # Role holders may have permissions in the undakt/kursakt room,
        # lærerrom, fellesrom and the corridor:
        if "korridor" in role_permissions:
            new_acl[korridor][xml_name] = role_permissions["korridor"]
        # ... fellesrommet
        if "felles" in role_permissions:
            new_acl[fellesrom][xml_name] = {
                'role': role_permissions["felles"]}
        # ... ann finally undakt/kursakt room
        new_acl[undakt_node][xml_name] = {
            'role': role_permissions["undakt"]}

    # The student group has to have 'view contacts' on itself
    new_acl[studentnode][studentnode] = view_contacts

    # Finally, the student group has permissions in the undakt/kursakt room.
    new_acl[undakt_node][studentnode] = {'role': student_permissions['undakt']}


def process_undenh_permissions(template, korridor, fellesrom,
                               studentnode):
    """Assign fronter permissions to undenh/kurs roles.

    This function is called for both undenh and EVU-kurs. The IDs are a bit
    different, but the procedure is otherwise the same.

    @param template:
      A template for generating group names for various roles. E.g.:

          uio.no:fs:kurs:185:rus2122s:1:høst:2007:1:%s

      ... where the role itself (admin, sensor, etc.) is interpolated.
    @type template: basestring

    @param korridor:
      Student corridor id for the given undenh/EVU-kurs. E.g.:

          STRUCTURE/Studentkorridor:KURS:185:SAS1500:1:HØST:2007:1
    @type korridor: basestring

    @param fellesrom:
      Fellesromid for the given undenh/EVU-kurs. E.g.:

          ROOM/Felles:KURS:185:NOR4160:1:HØST:2007:1
    @type fellesrom: basestring

    @param studentnode:
      Student group id for the given undenh/EVU-kurs. E.g.:

          uio.no:fs:kurs:185:lit4000:1:høst:2007:1:student
    """

    permissions = kind2permissions['undenh']
    student_permissions = kind2permissions['student']
    for group_name in permissions:
        role_permissions = permissions[group_name]

        xml_name = (template % group_name).lower()

        # Every group has 'view contacts' on itself.
        new_acl[xml_name][xml_name] = view_contacts

        # Role holders have special permissions in the student corridor.
        if 'korridor' in role_permissions:
            new_acl[korridor][xml_name] = role_permissions['korridor']

        # ... fellesrommet
        if 'felles' in role_permissions:
            new_acl[fellesrom][xml_name] = {'role': role_permissions['felles']}

        # Role holders have special permissions wrt the student group.
        new_acl[studentnode][xml_name] = role_permissions['student']

    # Student groups also have access to fellesrom:
    new_acl[fellesrom][studentnode] = {'role': student_permissions['undenh']}
    # ... and they have 'view contacts' on their own group.
    new_acl[studentnode][studentnode] = view_contacts


def process_kull_permissions(template, korridor, kullrom, studentnode):
    """Assign fronter permissions to 'kull' roles.

    This function is similar to L{process_undenh_permissions}

    @param template:
      Same as in L{process_undenh_permissions}

    @param korridor:
      Studieprogramkorridor for our 'kull'. E.g.:

          STRUCTURE/Studieprogramkorridor:KULL:FOO:BAR:2007
    @param korridor: basestring

    @param kullrom:
      Fronter room for our 'kull'. E.g.:

          ROOM/Studieprogram:KULL:FOO:BAR:2007
    @param rom: basestring

    @param studentnode:
      Student group id for the given 'kull'. E.g.:

          uio.no:fs:kull:foo:bar:2007:student
    @param student
    """

    permissions = kind2permissions['kull']
    for group_name, role_permissions in permissions.iteritems():

        xml_name = (template % group_name).lower()

        # The role holders have 'view contacts' on their own group.
        new_acl[xml_name][xml_name] = view_contacts

        # The role holders have permissions in the corridor...
        if 'korridor' in role_permissions:
            new_acl[korridor][xml_name] = role_permissions['korridor']

        # ... and in the room itself.
        new_acl[kullrom][xml_name] = {'role': role_permissions['kullrom']}

    # baardj thinks that students should not have 'view contacts' on the
    # entire 'kull'.
    # new_acl[studentnode][studentnode] = view_contacts

    # However, students should have write access to the room itself.
    new_acl[kullrom][studentnode] = {'role': fronter.ROLE_WRITE}


class FronterXML(object):
    def __init__(self, fname, cf_dir=None, debug_file=None, debug_level=None,
                 fronter=None, include_password=True):
        self.xml = XMLWriter(fname)
        self.xml.startDocument(encoding='UTF-8')
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
        # self.xml.startTag('extension')
        # self.xml.endTag('extension')
        self.xml.endTag('person')

    def group_to_XML(self, id, recstatus, data):
        # Generate XML-element(s) for one group.
        self.xml.startTag('group', {'recstatus': recstatus})
        self.xml.startTag('sourcedid')
        self.xml.dataElement('source', self.DataSource)
        self.xml.dataElement('id', id)
        self.xml.endTag('sourcedid')
        self.xml.startTag('grouptype')
        self.xml.dataElement('scheme', 'FronterStructure1.0')
        allow_room = data.get('allow_room', 0)
        allow_contact = data.get('allow_contact', 0)
        # Convert booleans allow_room and allow_contact to bits
        allow_room = allow_room and 1 or 0
        allow_contact = allow_contact and 2 or 0
        self.xml.emptyTag('typevalue',
                          {'level': allow_room | allow_contact})
        self.xml.endTag('grouptype')
        self.xml.startTag('description')
        if (len(data['title']) > 90):
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
        # Generate XML-element(s) for one room.
        #
        # Old rooms are never to be deleted.
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
        if (len(data['title']) > 90):
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
        # Generate XML-element representing one membership (in a group)
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
            if 'role' in acl:
                self.xml.startTag('role', {'recstatus': recstatus,
                                           'roletype': acl['role']})
                self.xml.dataElement('status', '1')
                self.xml.startTag('extension')
                self.xml.emptyTag('memberof', {'type': 2})  # Member of room.
            else:
                self.xml.startTag('role', {'recstatus': recstatus})
                self.xml.dataElement('status', '1')
                self.xml.startTag('extension')
                self.xml.emptyTag('memberof', {'type': 1})  # Member of group.
                # Fronter says that this tag should be ommited if the target is
                # a corridor.
                if not (node in new_group and
                        new_group[node]['allow_room'] is True and
                        new_group[node]['allow_contact'] is False):
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


def init_globals():
    global db, const, logger
    logger = Factory.get_logger("cronjob")
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    cf_dir = '/cerebrum/var/cache/Fronter'
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'rom-profil=',
                                    'uten-dette-semester',
                                    'uten-passord',
                                    'debug-file=', 'debug-level=',
                                    'cf-dir=',
                                    "undenh-file=",
                                    "undakt-file=",
                                    "evu-file=",
                                    "kursakt-file=",
                                    "kull-file=",
                                    ])
    except getopt.GetoptError:
        usage(1)
    debug_file = os.path.join(cf_dir, "x-import.log")
    debug_level = 4
    host = None
    set_pwd = True
    undenh_file = undakt_file = evu_file = kursakt_file = kull_file = None
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
        elif opt in ("--undenh-file",):
            undenh_file = val
        elif opt in ("--undakt-file",):
            undakt_file = val
        elif opt in ("--evu-file",):
            evu_file = val
        elif opt in ("--kursakt-file",):
            kursakt_file = val
        elif opt in ("--kull-file",):
            kull_file = val
        else:
            raise ValueError("Invalid argument: %r" % (opt,))

    global root_ou_id
    root_ou_id = _get_ou(root_sko).entity_id

    global entity2name
    group = Factory.get("Group")(db)
    entity2name = dict((x["entity_id"], x["entity_name"]) for x in
                       group.list_names(const.account_namespace))
    entity2name.update((x["entity_id"], x["entity_name"]) for x in
                       group.list_names(const.group_namespace))

    global fronter
    # TODO: Use the data files from FS instead of fetching data directly from
    # the FS database
    assert undenh_file
    # assert undakt_file and evu_file and kursakt_file and kull_file

    fronter = Fronter(host, db, const,
                      undenh_file, undakt_file, evu_file, kursakt_file,
                      kull_file, logger=logger)

    filename = os.path.join(cf_dir, 'test.xml')
    if len(args) == 1:
        filename = args[0]
    elif len(args) != 0:
        usage(2)

    global fxml
    fxml = FronterXML(filename,
                      cf_dir=cf_dir,
                      debug_file=debug_file,
                      debug_level=debug_level,
                      fronter=fronter,
                      include_password=set_pwd)

    # Get uname -> account-data mapping for all users.
    global new_users
    new_users = get_new_users()


def list_users_for_fronter_export():  # TODO: rewrite this
    ret = []
    posix_user = Factory.get('PosixUser')(db)
    email_addrs = posix_user.getdict_uname2mailaddr()
    logger.debug("list_users_for_fronter_export got %d emailaddrs",
                 len(email_addrs))
    for row in posix_user.list_extended_posix_users(const.auth_type_md5_crypt):
        tmp = {'email': email_addrs.get(row['entity_name'],
                                        '@'.join((row['entity_name'],
                                                  'ulrik.uio.no'))),
               'uname': row['entity_name']}
        tmp['fullname'] = row['name']
        ret.append(tmp)
    return ret


# Somehow a set of users who should not get exported to Fronter appears in
# Fronter. We wanna filter 'em out. It's a hack, but it is faster to
# implement ;)
# Maybee I should have used some other API functions.
def find_accounts_to_exclude():
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)

    r = []
    for x in cereconf.REMOVE_USERS:
        ac.clear()
        ac.find_by_name(x)
        pe.clear()
        pe.find(ac.owner_id)
        for y in pe.get_accounts():
            ac.clear()
            ac.find(y['account_id'])
            r.append(ac.account_name)
    return r


def get_new_users():
    # Fetch userinfo in Cerebrum.
    exclude = find_accounts_to_exclude()
    users = {}
    for user in list_users_for_fronter_export():
        # This script will fail otherwise. Perhaps a better solution is
        # possible?
        if user['uname'] in exclude:
            continue
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
            new_groupmembers['All_users'].add(user['uname'])
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
    if isinstance(id, string_types):
        group.find_by_name(id)
    else:
        group.find(id)
    return group


def _get_ou(identification):
    """Return a Factory.get('OU') instance corresponding to an id.

    @type identification: basestring or int
    @param identification:
      Id for the OU to locate. It can either be a sko or an internal ou_id.

    @rtype: instance of Factory.get('OU') or None
    @return:
      An object associated with the given id, or None, if no such object
      exists.
    """

    ou = Factory.get("OU")(db)
    try:
        if isinstance(identification, basestring):
            ou.find_stedkode(int(identification[0:2]),
                             int(identification[2:4]),
                             int(identification[4:6]),
                             cereconf.DEFAULT_INSTITUSJONSNR)
        else:
            ou.find(int(identification))

        return ou
    except Errors.NotFoundError:
        return None
# end _get_ou


def get_sted(stedkode=None, entity_id=None):
    """Return an OU by SKO or ou_id.

    If the OU is not marked as publishable, the first parent OU marked as
    publishable is returned.

    """
    sted = _get_ou(stedkode or entity_id)
    # Only publishable OUs should be returned; if no such OU can be found by
    # moving towards the root of the OU tree, return None.
    if sted.has_spread(const.spread_ou_publishable):
        return sted
    elif (sted.fakultet, sted.institutt, sted.avdeling) == (15, 0, 30):
        # Special treatment of UNIK; even though 15-0-30 is not publishable,
        # return it anyway, so that they get their own corridor.
        return sted
    # Not publishable, move one step up in the OU structure:
    parent_id = sted.get_parent(const.perspective_sap)
    if parent_id is not None and parent_id != sted.entity_id:
        return get_sted(entity_id=parent_id)
    return None


def register_supergroups():
    """Register groups (with accounts) for fronter.

    Register a few static nodes and all fronter groups with account
    members. The last category is precisely the one with groups with fronter
    spreads. We build the rest of the fronter structure from these group
    names.
    """

    timer = make_timer(logger, 'Starting register_supergroups...')
    register_group("Universitetet i Oslo", root_struct_id, root_struct_id)
    register_group(group_struct_title, group_struct_id, root_struct_id)
    if 'All_users' in fronter.export:
        # Webinterfacet mister litt pusten når man klikker på gruppa
        # All_users (dersom man f.eks. ønsker å gi alle brukere rettighet
        # til noe); oppretter derfor en dummy-gruppe som kun har den
        # /egentlige/ All_users-gruppa som medlem.
        sg_id = "All_users_supergroup"
        register_group("Alle brukere", sg_id, root_struct_id,
                       allow_room=False, allow_contact=False)
        register_group("Alle brukere (STOR)", 'All_users', sg_id,
                       allow_room=False, allow_contact=True)

    group = Factory.get('Group')(db)
    group_members = defaultdict(set)
    timer2 = make_timer(logger, '   getting all group members...')
    for row in group.search_members(group_id=fronter.exportable.keys(),
                                    member_type=const.entity_account):
        group_members[row['group_id']].add(row['member_id'])
    timer2('   ... done getting all group members.')

    for group_id, group_description in fronter.exportable.iteritems():
        group_name = entity2name[group_id]
        members = group_members[group_id]
        if not members:
            # On one hand, we should allow some leeway wrt erroneous spreads
            # in Cerebrum (and we have a lot of historic data with fronter
            # spreads given to the (now) wrong groups).
            # On the other hand, perhaps having wrong spreads should be
            # reported somehow?
            logger.debug("gruppe <%s> har ingen account-medlemmer",
                         group_name)
            continue

        parent = fronter._group_name2key(group_name).split(':')
        ktype = parent[0].lower()

        if ktype == fronter.EMNE_PREFIX.lower():
            parent_struct_id = 'Emnegrupper %s %s' % (parent[4], parent[5])
        elif ktype == fronter.EVU_PREFIX.lower():
            parent_struct_id = 'EVUkursgrupper %s' % parent[2]
        elif ktype == fronter.KULL_PREFIX.lower():
            parent_struct_id = 'Kullgrupper %s' % ' '.join(parent[2:4])
        else:
            parent_struct_id = 'UREG2000@uio.no imported groups'

        if parent_struct_id not in new_group:
            register_group(parent_struct_id, parent_struct_id, group_struct_id,
                           allow_room=False, allow_contact=True)

        register_group(group_description, group_name,
                       parent_struct_id, allow_room=False,
                       allow_contact=True)

        # All groups have "view contacts" on themselves.
        new_acl[group_name][group_name] = view_contacts
        for member_id in members:
            uname = entity2name.get(member_id)
            if uname is None:
                logger.warn("Member id=%s of group name=%s id=%s has no name",
                            member_id, group_name, group_id)
                continue

            if uname in new_users:
                if new_users[uname]['USERACCESS'] != 'administrator':
                    new_users[uname]['USERACCESS'] = 'allowlogin'
                    new_groupmembers[group_name].add(uname)
    timer('... done register_supergroups')


new_acl = defaultdict(dict)
new_groupmembers = defaultdict(set)
new_rooms = {}
new_group = {}


def register_room(title, room_id, parent_id, profile_name=None):
    new_rooms[room_id] = {
        'title': title,
        'parent': parent_id,
        'profile': fronter.profile(profile_name)}


def register_group(title, group_id, parent_id,
                   allow_room=False, allow_contact=False):
    """Adds info in new_group about group."""
    new_group[group_id] = {'title': title,
                           'parent': parent_id,
                           'allow_room': allow_room,
                           'allow_contact': allow_contact,
                           }


def build_structure(sko, allow_room=False, allow_contact=False):
    # Build a group (structure node, actually) for a sko recursively.
    if sko == root_sko:
        return root_struct_id
    if not sko:
        return None

    struct_id = "STRUCTURE/Sko:185:%s" % sko
    if (struct_id not in new_group or
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
            parent_sted = None
            p = sted.get_parent(const.perspective_sap)
            if p:
                parent_sted = get_sted(entity_id=p)

            if parent_sted is None:
                if sted.get_parent(const.perspective_sap) != root_ou_id:
                    logger.warn("Stedkode <%s> er uten foreldre; bruker %s" %
                                (sko, root_sko))
                parent = build_structure(root_sko)
            else:
                parent = build_structure("%02d%02d%02d" % (
                    parent_sted.fakultet,
                    parent_sted.institutt,
                    parent_sted.avdeling))
        except Errors.NotFoundError:
            logger.warn("Stedkode <%s> er uten foreldre; bruker %s" %
                        (sko, root_sko))
            parent = build_structure(root_sko)

        ou_name = sted.get_name_with_language(name_variant=const.ou_name,
                                              name_language=const.language_nb,
                                              default="")
        register_group(ou_name, struct_id, parent, allow_room, allow_contact)
    return struct_id


def make_profile(*rest):
    """Make a room profile (for undakt).

    DML requested non-standard room profiles for undakt, to be fetched from
    fs.undaktivitet.lmsrommalkode. Those undakt that actually have such a
    profile registered in FS will get it in Fronter as well. Otherwise we fall
    back to the default profile.
    """

    key = ":".join(rest)
    return fronter.entity2room_profile.get(key)


def process_single_enhet_id(enhet_id, struct_id, emnekode,
                            enhet_node, undervisning_node,
                            termin_suffix="", process_akt_data=False):
    # There is a bunch of rooms for various undakt/kursakt associated
    # with given undenh/kurs.
    for akt in fronter.enhet2akt.get(enhet_id, []):
        try:
            aktkode, aktnavn, aktterminkode, aktaar, akttermnr = akt
        except ValueError:
            # This can only happen with undenh/akt that have been inserted
            # manually to test fronter functionality. It's no big deal that
            # they fail.
            aktkode, aktnavn = akt
            logger.info("Under henting av tidsdata for aktivitet i "
                        "'process_single_enhet_id': ValueError: "
                        "'%s' '%s' '%s' from <%s>" %
                        (emnekode, aktkode, aktnavn, akt))

        aktstud = "uio.no:fs:%s:student:%s" % (enhet_id.lower(),
                                               aktkode.lower())
        akt_rom_id = "ROOM/Aktivitet:%s:%s" % (enhet_id.upper(),
                                               aktkode.upper())
        template_id = "uio.no:fs:%s:%s:%s" % (enhet_id.lower(), "%s",
                                              aktkode.lower())
        fellesrom_id = "ROOM/Felles:%s" % struct_id
        process_undakt_permissions(template_id, undervisning_node,
                                   fellesrom_id, aktstud, akt_rom_id)

        # Hvis denne enheten har blitt flagget med "process_akt_data",
        # så er det nokså mulig at tilhørende aktiviteter kommer fra
        # ulike semestre, og at aktivitetene må derfor selv designere
        # sitt år, terminkode og terminnummer. For alle andre, så er
        # det greit å bruke samme verdi for alle aktiviteter innen
        # enheten.
        if process_akt_data:
            termin_suffix = " %s-%s-%s" % (aktaar, aktterminkode, akttermnr)
            logger.debug("Bruker '%s' som termin_suffix for '%s - %s'" %
                         (termin_suffix, emnekode.upper(), aktnavn))
        akt_tittel = "%s - %s%s" % (emnekode.upper(), aktnavn, termin_suffix)
        register_room(akt_tittel, akt_rom_id, enhet_node,
                      make_profile(enhet_id, aktkode))


def process_kurs2enhet():
    timer = make_timer(logger, 'Starting process_kurs2enhet...')
    # TODO: some code-duplication has been reduced by adding
    # process_single_enhet_id.  Recheck that the reduction is correct.
    # It should be possible to move more code to that subroutine.
    for kurs_id in fronter.kurs2enhet.keys():
        ktype = kurs_id.split(":")[0].lower()
        if ktype == fronter.EMNE_PREFIX.lower():
            enhet_sorted = fronter.kurs2enhet[kurs_id][:]
            enhet_sorted.sort(fronter._date_sort)
            # Use the oldest undenh as enh_id.
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
            # Create structure nodes that allow to have rooms right "under"
            # them.
            sko_node = build_structure(fronter.enhet2sko[enh_id])
            sko_part = sko_node.split('/')[1]

            multi_enhet = []
            multi_id = ":".join((Instnr, emnekode, termk, aar))
            multi_termin = False

            # process_akt_data brukes som flagg til
            # process_single_enhet_id (som kalles nedenfor) for de
            # enheter som kan ha aktiviteter med varierende semestre,
            # og hvor man derfor må ha mer finkornet prosessering av
            # aktivitets-data.
            process_akt_data = False

            # Fixup multisemester entity names (flersemesteremner)
            naa_aar = fronter.year
            naa_termk = fronter.semester
            if int(termnr) != 1:
                if termk.upper() != naa_termk:
                    logger.debug("Termnr: '%s'" % termnr)
                    logger.debug("Fant 'forskuttert' enhet: %s - %s %s %s %s. "
                                 "termin" %
                                 (emnekode.upper(), fronter.kurs2navn[kurs_id],
                                  termk.upper(), aar, termnr))
                    termk = naa_termk
                    aar = text_type(naa_aar)
                    # termnr usually string, but need to temporarily int it to
                    # calculate
                    termnr = int(termnr) - 1
                    process_akt_data = True

            tittel = "%s - %s, %s %s" % (emnekode.upper(),
                                         fronter.kurs2navn[kurs_id],
                                         termk.upper(), aar)
            if (
                    # Det finnes flere und.enh. i semesteret angitt av
                    # 'terminkode' og 'arstall' hvor både 'institusjonsnr' og
                    # 'emnekode' er like, men 'terminnr' varierer.
                    len(fronter.emne_termnr[multi_id]) > 1 or
                    # Det finnes mer enn en und.enh. som svarer til samme
                    # "kurs", e.g. både 'høst 2004, terminnr=1' og 'vår
                    # 2005, terminnr=2' finnes.
                    len(enhet_sorted) > 1 or
                    # Denne und.enh. har terminnr større enn 1, slik at
                    # det er sannsynlig at det finnes und.enh. fra
                    # tidligere semester som hører til samme "kurs".
                    int(termnr) > 1):
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

            # We register a corridor for them rooms
            sem, aar = struct_id.lower().split(":")[4:6]
            korr_name = "Kurs %s %s" % (sem, aar)
            korr_node = "STRUCTURE/Kurs:%s:%s:%s" % (sem, aar, sko_part)
            register_group(korr_name, korr_node, sko_node, allow_room=True)

            # All exported undenhs have one 'fellesrom'.
            if multi_termin:
                term_title = "%s-%s-%s" % (aar, termk, termnr)
            else:
                term_title = "%s-%s" % (aar, termk)

            fellesrom_id = "ROOM/Felles:%s" % struct_id
            register_room("%s - Fellesrom %s" % (emnekode.upper(), term_title),
                          fellesrom_id, korr_node, make_profile(enh_id))

            for enhet_id in fronter.kurs2enhet[kurs_id]:
                termin_suffix = ""
                if multi_termin:
                    # term-suffix now added above for all courses
                    pass

                enhstud = "uio.no:fs:%s:student" % enhet_id.lower()
                template_id = "uio.no:fs:%s:%s" % (enhet_id.lower(), "%s")
                process_undenh_permissions(template_id, korr_node,
                                           fellesrom_id, enhstud)
                process_single_enhet_id(enhet_id, struct_id,
                                        emnekode, korr_node, korr_node,
                                        " %s%s" % (term_title, termin_suffix),
                                        process_akt_data)
        elif ktype == fronter.EVU_PREFIX.lower():
            for enhet_id in fronter.kurs2enhet[kurs_id]:
                kurskode, tidskode = enhet_id.split(":")[1:3]
                # Create structure nodes that allow rooms associated with them.
                sko_node = build_structure(fronter.enhet2sko[enhet_id])
                sko_part = sko_node.split('/')[1]
                struct_id = enhet_id.upper()
                tittel = "%s - %s, %s" % (kurskode.upper(),
                                          fronter.kurs2navn[kurs_id],
                                          tidskode.upper())
                enhstud = "uio.no:fs:%s:student" % enhet_id.lower()

                # EVU-kurs and undenh are alike when it comes to permissions
                template_id = "uio.no:fs:%s:%s" % (enhet_id.lower(), "%s")
                fellesrom_id = "ROOM/Felles:%s" % struct_id

                # We register a corridor for them rooms
                tid = enhet_id.upper().split(":")[2]
                korr_name = "Evu kurs %s" % tid
                korr_node = "STRUCTURE/Kurs:%s:%s" % (tid, sko_part)
                register_group(korr_name, korr_node, sko_node, allow_room=True)

                process_undenh_permissions(template_id, korr_node,
                                           fellesrom_id, enhstud)

                # Just like undenh, EVU-kurs have one fellesrom and one
                # lærerrom.
                register_room("%s - Fellesrom" % kurskode.upper(),
                              fellesrom_id, korr_node, make_profile(enhet_id))
                process_single_enhet_id(enhet_id, struct_id,
                                        kurskode, korr_node, korr_node)

        elif ktype == fronter.KULL_PREFIX.lower():
            for enhet_id in fronter.kurs2enhet[kurs_id]:
                stprog, termkode, aar = enhet_id.split(":")[1:4]

                sko_node = build_structure(fronter.enhet2sko[enhet_id])
                struct_id = enhet_id.upper()
                # We'll only make one corridor for each studieprogram
                stprog_node = "STRUCTURE/Studieprogramkorridor:%s" % (
                    stprog.upper())
                kull_node = "ROOM/Studieprogram:%s" % struct_id

                # TODO: Should we test if it is allready created? Will we
                # achieve better performance?
                register_group("Studieprogramkorridor for %s" % (stprog,),
                               stprog_node, sko_node, allow_room=True)

                snumber = semester_number(aar, termkode,
                                          fronter.year, fronter.semester)
                if snumber > 0:
                    room_title = ("Kullrom for %s, %s, %s. semester - %s %s" %
                                  (fronter.kurs2navn[kurs_id], stprog,
                                   snumber,
                                   fronter.semester.upper(), fronter.year))
                else:
                    room_title = ("Kullrom for %s, %s, start - %s %s" %
                                  (fronter.kurs2navn[kurs_id], stprog,
                                   aar, termkode))

                register_room(room_title,
                              kull_node, stprog_node,
                              make_profile(enhet_id))

                kullstud = "uio.no:fs:%s:student" % enhet_id.lower()

                template_id = "uio.no:fs:%s:%s" % (enhet_id.lower(), "%s")
                process_kull_permissions(template_id, stprog_node,
                                         kull_node, kullstud)
                process_single_enhet_id(enhet_id, struct_id, stprog,
                                        None, None)

        else:
            raise ValueError("Unknown type <%s> for course <%s>" %
                             (ktype, kurs_id))
    timer('... done process_kurs2enhet')


def usage(exitcode):
    print "Usage: generate_fronter_full.py OUTPUT_FILENAME"
    sys.exit(exitcode)

# This stuff can sort the groups by dependency.
# It is terribly slow. We should not need to use this.
#   def sort_groups(groups):
#       logger.info('Starting sort')
#       grpkeys = groups.keys()
#       s = []

#       # Makin' a list of groups without children
#       for x in grpkeys:
#           childless = True
#           for y in grpkeys:
#               if x == groups[y]['parent']:
#                   childless = False
#           if childless:
#               s.append(x)
#       logger.info('Childless nodes collected')

#       # Sorting the groups
#       r = []
#       for x in s:
#           tmp = []
#           t = x
#           while groups[t]['parent'] != t and t not in r:
#               tmp.append(t)
#               t = groups[t]['parent']
#           if t not in r:
#               tmp.append(t)
#           r.extend(tmp[::-1])
#       logger.info('Sort finished')
#       return r


def main():
    # Proper upper/lower casing of Norwegian letters.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    init_globals()
    register_supergroups()
    process_kurs2enhet()

    fxml.start_xml_file(fronter.kurs2enhet.keys())

    # Generate <person>-elements
    timer = make_timer(logger, 'Writing users to xml...')
    for uname, data in new_users.iteritems():
        fxml.user_to_XML(uname, fronter.STATUS_ADD, data)
    timer('... done writing users.')

    timer = make_timer(logger, 'Writing groups to xml...')
    for gname, data in new_group.iteritems():
        fxml.group_to_XML(gname, fronter.STATUS_ADD, data)
    timer('... done writing groups.')

    timer = make_timer(logger, 'Writing rooms to xml...')
    for room_id, data in new_rooms.iteritems():
        fxml.room_to_XML(room_id, fronter.STATUS_ADD, data)
    timer('... done writing rooms.')

    timer = make_timer(logger, 'Writing groupmembers to xml...')
    for gname, members in new_groupmembers.iteritems():
        fxml.personmembers_to_XML(gname, fronter.STATUS_ADD,
                                  members)
    timer('... done writing groupmembers.')

    timer = make_timer(logger, 'Writing acls to xml...')
    for struct_id, data in new_acl.iteritems():
        fxml.acl_to_XML(struct_id, fronter.STATUS_ADD, data)
    timer('... done writing acls.')
    fxml.end()

    logger.info("generate_fronter_full is done")


if __name__ == '__main__':
    main()
