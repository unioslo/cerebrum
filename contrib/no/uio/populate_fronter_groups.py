#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2019 University of Oslo, Norway
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

"""Populer Cerebrum med FS-avledede grupper.

Disse gruppene blir bl.a. brukt ved eksport av data til ClassFronter, og ved
populering av visse NIS (Ifi).

Først litt terminologi:

  - Studieprogram: et studium som normalt leder frem til en grad. Bygges opp
                   ved emner.
  - Emne: den enheten som er byggesteinen i alle studium. Har en omfang, og
          normalt en eller annen form for avsluttende evaluering.
  - Undervisningsenhet (undenh): en instansiering av et emne.
  - Undervisningsaktivitet (undakt): en serie aktivitet knyttet til en
                                     undenh. F.eks. en forelesningsrekke, et
                                     labparti, en serie regneøvinger. Kan også
                                     være en enkel aktivitet.
  - Kurs (evu): Samsvarer med undenh, men er for etter- og videreutdanning
  - Kursaktivitet: Samsvarer med undakt, men er for etter- og videreutdanning
  - Kull: Årsklasse av et studieprogram.

Gruppene er organisert i en tre-struktur.  Øverst finnes en supergruppe; denne
brukes for å holde orden på hvilke grupper som er automatisk opprettet av
dette scriptet, og dermed hvilke grupper som skal slettes i det dataene de
bygger på ikke lenger finnes i FS.  Supergruppen har navnet::

  internal:uio.no:fs:{supergroup}

Denne supergruppen har så medlemmer som også er grupper.
Medlemsgruppene har navn på følgende format::

  internal:uio.no:kurs:<emnekode>
  internal:uio.no:evu:<kurskode>
  internal:uio.no:kull:<studieprogram>

Hver av disse 'enhet-supergruppene' har medlemmer som er grupper med navn på
følgende format::

  internal:uio.no:fs:kurs:<institusjonsnr>:<emnekode>:<versjon>:<sem>:<år>
  internal:uio.no:fs:evu:<kurskode>:<tidsangivelse>
  internal:uio.no:fs:kull:<studieprogram>:<terminkode>:<aar>

Merk at for undenh, så er ikke en tilsvarende 'enhet'-gruppe *helt* ekvivalent
med begrepet undervisningsenhet slik det brukes i FS.  Gruppen representerer
semesteret et gitt kurs startet i (terminnr == 1).  For kurs som strekker seg
over mer enn ett semester vil det derfor i FS finnes multiple
undervisningsenheter, mens gruppen som representerer kurset vil beholde navnet
sitt i hele kurstiden.

'enhet'-gruppene har igjen grupper som medlemmer; disse kan deles i to
kategorier:

  - Grupper (med primærbrukermedlemmer) som brukes ved eksport til
    ClassFronter, har navn på følgende format::

      Rolle ved undenh:     uio.no:fs:<enhetid>:<rolletype>
      Rolle ved undakt:     uio.no:fs:<enhetid>:<rolletype>:<aktkode>
      Ansvar und.enh:       uio.no:fs:<enhetid>:enhetsansvar
      Ansvar und.akt:       uio.no:fs:<enhetid>:aktivitetsansvar:<aktkode>
      Alle stud. v/enh:     uio.no:fs:<enhetid>:student
      Alle stud. v/akt:     uio.no:fs:<enhetid>:student:<aktkode>

  - Ytterligere grupper hvis medlemmer kun er ikke-primære ('sekundære')
    konti. Genereres kun for informatikk-emner, og har navn på formen::

      Ansvar und.enh:       uio.no:fs:<enhetid>:enhetsansvar-sek
      Ansvar und.akt:       uio.no:fs:<enhetid>:aktivitetsansvar-sek:<aktkode>
      Alle stud. v/enh:     uio.no:fs:<enhetid>:student-sek

<rolletype> er en av 12 predefinerte roller (jfr. valid_roles). enhetsansvar
og aktivitetsansvar-gruppene finnes kun for Ifi, som ønsker sine grupper (for
NIS) bygget litt annerledes. Alle slike grupper hvor det er meningen det skal
være accounts, får en passende fronterspread, basert på informasjonen fra
FS. Det er kun slike grupper, hvis fronterspreads vil ha noe å si (dvs. andre
grupper kan også få fronterspreads, men generate_fronter_full.py vil ignorere
dem).

Poenget med å ha dette nokså kompliserte hierarkiet var å tillate
DML/Houston/andre å kunne enkelt si at de vil eksportere en bestemt entitet
til fronter uten å bry seg om gruppene som måtte være generert for denne
entiteten. Dette er ikke mer nødvendig for undenh/undakt/kurs/kursakt, siden
de populeres automatisk, men det *er* nødvendig for kull.

Kullgruppene har også grupper som medlemmer; det er en gruppe med studenter,
samt en gruppe for hver rolle ved kullet::

  Alle stud. på kull:   uio.no:fs:<enhetid>:student
  Rolle ved kull:       uio.no:fs:<enhetid>:<rolletype>

Siden <enhetid> inneholder gruppetypen (kurs, evu og kull), vil det ikke
oppstå navnekollisjon forskjellige enhetgrupper imellom.

I tillegg blir disse nettgruppene laget med spread til Ifi::

  Ansvar und.enh:        g<enhetid>-0          (alle konti)
  Ansvar und.akt:        g<enhetid>-<aktkode>  (alle konti)
  Ansvar enh. og akt.:   g<enhetid>            (alle konti)
  Alle stud. v/enh:      s<enhetid>            (alle konti)
  Alle stud. v/akt:      s<enhetid>-<aktkode>  (primærkonti)
  Alle stud. kun eks:    s<enhetid>-e          (primærkonti)
  Alle akt-ansv:         ifi-g                 (alle konti)
  Alle akt- og enh-ansv: lkurs                 (alle konti)

Som sagt, populering av disse gruppene er litt annerledes. *Alle* med en eller
annen rolle til Ifi-kursene havner i 'g'-ansvarlige-gruppene.
"""

from __future__ import unicode_literals

import argparse
import locale
import logging
import os
import re
import sys

from itertools import izip, repeat

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory, NotSet
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules import Email
from Cerebrum.modules.bofhd.auth import BofhdAuthRole, BofhdAuthOpTarget
from Cerebrum.modules.no.access_FS import roles_xml_parser, make_fs
from Cerebrum.modules.no.fronter_lib import (UE2KursID, key2fields,
                                             str2key, fields2key)
from Cerebrum.modules.xmlutils.fsxml2object import EduGenericIterator
from Cerebrum.modules.xmlutils.fsxml2object import EduDataGetter
from Cerebrum.utils import transliterate

# IVR 2007-11-08 FIXME: Should this be in fronter_lib?
# Roles that are considered at all
valid_roles = ("ADMIN", "DLO", "FAGANSVAR", "FORELESER", "GJESTEFORE",
               "GRUPPELÆRE", "HOVEDLÆRER", "IT-ANSVARL", "LÆRER", "SENSOR",
               "STUDIEKONS", "TOLK", "TILSYN",)
# Roles that are inherited by entities located at a certain sko or at a
# certain stprog.
recursive_roles = ("ADMIN", "DLO", "IT-ANSVARL", "STUDIEKONS", "TILSYN",)

logger = logging.getLogger(__name__)


def make_sko(row, suffix=""):
    """Construct a sko (formatted XXYYZZ) from a db-row.

    suffix is added to the standard names 'faknr', 'instituttnr' and
    'gruppenr' to extract the proper fields from the db-row instance.

    @param row:
      A database row with information including the triplet we are looking
      for.
    @param row: L{db_row}

    @param suffix:
      An optional suffix to add to standard names before extracting the
      corresponding values.
    @param suffix: basestring.
    """
    return "%02d%02d%02d" % tuple(map(int,
                                      (row["faknr" + suffix],
                                       row["instituttnr" + suffix],
                                       row["gruppenr" + suffix])))


def extract_all_roles(enhet_id, roles_mapping, sted, stprog=""):
    """Return a sequence with accounts whose owners have any roles associated
    with enhet_id.

    @param enhet_id:
      enhet for which all the roles are merged.
    @type enhet_id: basestring

    @param roles_mapping:
      cf. L{parse_xml_roles}.
    @type roles_mapping: dict

    @return:
      a list with account_ids.
    @rtype: dict
    """
    result = list()
    key = str2key(enhet_id)
    for coll in (roles_mapping.get(key, dict()),
                 roles_mapping.get("sted:" + sted, dict()),
                 roles_mapping.get("stprog:" + stprog, dict())):
        for role, people in coll.iteritems():
            for p in people:
                if p not in result:
                    result.append(p)

    return result


def process_role(enhet_id, template_id, roles_mapping,
                 parent_id, description, mtype, auto_spread, sted, stprog=""):
    """Create additional groups stemming from roles associated with enhet
    (kurs, kursakt, undenh, undakt) enhet_id.

    @param enhet_id:
      enhet for which all the roles are to be processed (undenh, undakt,
      evukurs, evukursakt, kull).
    @type enhet_id: basestring

    @param template_id:
      template_id is the template for the names we will generate from
      L{roles_mapping} for the given enhet_id. This template is a ':'-separated
      string (much like L{parent_id} or L{enhet_id}), with one 'slot' reserved
      (that 'slot' is '%s', so that the exact name can be interpolated later).

      The name to interpolate is derived from the role names. That is what we
      do here.
    @type template_id: basestring

    @param roles_mapping: mapping from enhet_ids to dicts, where each inner
      dict maps role types to sequences (e.g. 'FAGLÆRER' -> [s1, s2, ...,
      sN]). Each s_i is a dict (faking a L{db_row}) with a fnr.
    @type roles_mapping: dict

    @param parent_id:
      parent_id is the group name for the parent of the enhet_id group.
    @type parent_id: basestring

    @param sted:
      Sko (stedkode) for the place with which L{enhet_id} is associated. Some
      roles are assigned to sko, and inherited by every 'entity' associated
      with that sko.
    @type sted: basestring

    @param stprog:
      Studieprogramkode for the place with which L{enhet_id} is
      associated. Some roles are associated with studieprogramkode, and
      inherited by every kull associated with that studieprogramkode.
    @type stprog: basestring

    description, mtype and auto_spread have the same meaning as in
    L{sync_group}.

    @return: nothing
    """
    stedroller = roles_mapping.get(fields2key("sted", sted), {})
    stprogroller = roles_mapping.get(fields2key("stprog", stprog), {})

    key = str2key(enhet_id)
    logger.debug("Locating roles for enhet_id=%r, template_id=%r, "
                 "key=%r, description=%r",
                 enhet_id, template_id, key, description)
    if ((key not in roles_mapping) and
            (not stedroller) and
            (not stprogroller)):
        logger.debug("No roles for enhet_id=%r found", enhet_id)
        return

    my_roles = roles_mapping.get(key, {})
    for role in valid_roles:
        stedr = stedroller.get(role, list())
        stprogr = stprogroller.get(role, list())
        people = (my_roles.get(role, list()) + stedr + stprogr)
        if not people:
            continue

        group_name = str2key(template_id % role)
        fnrs = dict(izip(dbrows2account_ids(people), repeat(1)))
        logger.debug("Registering %d people with role %s for %s "
                     "(%s sted; %s stprog)",
                     len(fnrs), role, enhet_id, len(stedr), len(stprog))
        sync_group(parent_id, group_name, description % role, mtype, fnrs,
                   auto_spread=auto_spread)


def ordered_uniq(input):
    """Take a list as input and remove (later) duplicates without
    changing the ordering of the elements."""
    output = []
    for el in input:
        if el not in output:
            output.append(el)
    return output


# Somehow a set of users who should not get exported to Fronter appears in
# Fronter. We wanna filter 'em out. It's a hack, but it is faster to
# implement ;)
# Maybee I should have used some other API functions.
def find_accounts_and_persons_to_exclude():
    pe = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)

    r = {'persons': [], 'users': []}
    for x in cereconf.REMOVE_USERS:
        ac.clear()
        ac.find_by_name(x)
        pe.clear()
        pe.find(ac.owner_id)
        r['persons'].append(pe.entity_id)
        for y in pe.get_accounts():
            r['users'].append(y['account_id'])
    return r


def prefetch_primaryusers():
    global fnr2stud_account_id, exclude
    # TBD: This code is used to get account_id for both students and
    # fagansv.  Should we look at affiliation here?
    logger.debug("Getting all primaryusers")

    exclude = find_accounts_and_persons_to_exclude()
    account = Factory.get('Account')(db)
    personid2accountid = {}
    personid2student = {}
    for a in account.list_accounts_by_type():
        p_id = int(a['person_id'])
        a_id = int(a['account_id'])
        # It's a bad hack
        if a_id in exclude['users'] or p_id in exclude['persons']:
            continue
        if a['affiliation'] == co.affiliation_student:
            personid2student.setdefault(p_id, []).append(a_id)
        personid2accountid.setdefault(p_id, []).append(a_id)

    person = Factory.get('Person')(db)
    fnr_source = {}
    for row in person.search_external_ids(id_type=co.externalid_fodselsnr,
                                          fetchall=False):
        p_id = int(row['entity_id'])
        # It's a bad hack
        if p_id in exclude['persons']:
            continue
        fnr = row['external_id']
        src_sys = int(row['source_system'])
        if fnr in fnr_source and fnr_source[fnr][0] != p_id:
            # Multiple person_info rows have the same fnr (presumably
            # the different fnrs come from different source systems).
            logger.error("Persons share fnr, check entities: (%d, %d)",
                         fnr_source[fnr][0], p_id)
            # Determine which person's fnr registration to use.
            source_weight = dict()
            count = len(cereconf.SYSTEM_LOOKUP_ORDER)
            for sysname in cereconf.SYSTEM_LOOKUP_ORDER:
                source_weight[int(getattr(co, sysname))] = count
                count -= 1
            old_weight = source_weight.get(fnr_source[fnr][1], 0)
            if source_weight.get(src_sys, 0) <= old_weight:
                continue
            # The row we're currently processing should be preferred;
            # if the old row has an entry in fnr2account_id, delete
            # it.
            if fnr in fnr2account_id:
                del fnr2account_id[fnr]
        fnr_source[fnr] = (p_id, src_sys)
        if p_id in personid2accountid:
            account_ids = ordered_uniq(personid2accountid[p_id])
            for acc in account_ids:
                account_id2fnr[acc] = fnr
            if p_id in personid2student:
                fnr2stud_account_id[fnr] = ordered_uniq(
                    personid2student[p_id] + account_ids)
            else:
                fnr2stud_account_id[fnr] = account_ids
            fnr2account_id[fnr] = account_ids
    # TODO: We can not make this change in the middle of a term
    fnr2stud_account_id = fnr2account_id
    del fnr_source

    logger.debug("Finished fetching all primaryusers")


def dbrows2account_ids(rows, primary_only=True, prefer_student=False):
    """Return list of primary accounts for the persons identified by
    row(s).  Optionally return a tuple of (primaries, secondaries)
    instead.  The secondaries are a single list, so when more than one
    row is passed, you can't tell which person owns them."""

    def fnr_generator():
        for row in rows:
            yield "%06d%05d" % (int(row['fodselsdato']), int(row['personnr']))

    return fnrs2account_ids(fnr_generator(), primary_only, prefer_student)


def fnrs2account_ids(seq, primary_only=True, prefer_student=False):
    """Just like L{dbrows2account_ids}, except operate on seqs of fnrs."""
    prim = []
    sec = []
    for fnr in seq:
        if fnr in fnr2account_id:
            if prefer_student:
                account_list = fnr2stud_account_id[fnr]
            else:
                account_list = fnr2account_id[fnr]
            prim.append(account_list[0])
            if not primary_only:
                sec.extend(account_list[1:])
    if primary_only:
        return prim
    else:
        return (prim, sec)


def prefetch_all_data(role_file, undenh_file, undakt_file,
                      evu_file, kursakt_file, kull_file, edu_file):
    """Collect all data pertaining to FS role and educational information.

    We build a huge data structure representing the status quo in FS as given
    by the specified files.
    """

    # First all the users (fnrs/account_id mappings)
    prefetch_primaryusers()

    # Then undenh ...
    undenh_info, emne_versjon, emne_termnr = get_undenh(undenh_file, edu_file)
    edu_info = undenh_info

    # Then undakt ...
    # update the structure in-place. undakt are tied up to undenh; there is no
    # way around it (although it makes for bad deps between the functions)
    get_undakt(edu_info, undakt_file, edu_file)

    # Then EVU ...
    edu_info.update(get_evu(evu_file, edu_file))

    # Then EVU-kursakt ...
    # update the structure in-place. kursakt are tied up to evu; there is no
    # way around it (although it makes for bad deps between the functions)
    get_kursakt(edu_info, kursakt_file, edu_file)

    # Finally, kull ...
    edu_info.update(get_kull(kull_file, edu_file))

    role_mapping = parse_xml_roles(role_file)
    return edu_info, role_mapping


def process_kursdata(role_file, undenh_file, undakt_file,
                     evu_file, kursakt_file, kull_file, edu_file):
    global UndervEnhet
    UndervEnhet, role_mapping = prefetch_all_data(role_file, undenh_file,
                                                  undakt_file, evu_file,
                                                  kursakt_file, kull_file,
                                                  edu_file)
    for k in UndervEnhet.keys():
        # Add users to level-3 groups.
        #
        # $enhet here is either an undenh (starting with "kurs:"), or a
        # EVU-kurs (starting with "evu:") or kull (starting with "kull:");
        # populate_enhet_groups decides on its own how to process these 3
        # types.
        populate_enhet_groups(k, role_mapping)

    # netgroups for Ifi
    populate_ifi_groups()

    # fixup level-2 groups.
    #
    # We have to distinguish between undenh, EVU-kurs and kull, since their
    # IDs have a different number of fields.
    logger.info("Oppdaterer enhets-supergrupper:")
    for kurs_id in AffiliatedGroups.keys():
        if kurs_id == auto_supergroup:
            continue

        rest = key2fields(kurs_id)
        type = rest.pop(0)
        if type == 'kurs':
            instnr, emnekode, versjon, termk, aar = rest
            sync_group("%s:%s" % (type, emnekode), kurs_id,
                       "Ikke-eksporterbar gruppe.  Brukes for å definere hvor"
                       " data om kurset <%s> skal eksporteres." % kurs_id,
                       co.entity_group,
                       AffiliatedGroups[kurs_id],
                       auto_spread=False)
        elif type == 'evu':
            kurskode, tidsrom = rest
            logger.debug("Kursid: %s; rest: %s", kurs_id, rest)
            sync_group("%s:%s" % (type, kurskode), kurs_id,
                       "Ikke-eksporterbar gruppe.  Brukes for å definere hvor"
                       " data om emnet <%s> skal eksporteres. " % kurs_id,
                       co.entity_group,
                       AffiliatedGroups[kurs_id],
                       auto_spread=False)
        elif type == 'kull':
            stprog, termkode, aar = rest
            sync_group("%s:%s" % (type, stprog), kurs_id,
                       "Ikke-eksporterbar gruppe. Brukes for å definere hvor"
                       " data om kullet <%s> skal eksporteres." % kurs_id,
                       co.entity_group,
                       AffiliatedGroups[kurs_id],
                       # NotSet, since we do NOT want to change whichever
                       # fronter spreads this kull already has.
                       auto_spread=NotSet)
        else:
            logger.warn("Ukjent kurstype <%s> for kurs <%s>" % (type, kurs_id))

        # sync_group calls insert new entries into AffiliatedGroups; if we
        # remove "our" keys from that dict as soon as we are done, working
        # with AffiliatedGroups gets easier later.
        del AffiliatedGroups[kurs_id]
    logger.info(" ... done")
    if not dryrun:
        logger.debug("Commit changes")
        db.commit()

    # Oppdaterer gruppene på nivå 1.
    #
    # Alle grupper knyttet til en undervisningsenhet skal meldes inn i den
    # u2k-interne emnekode-gruppen.  Man benytter så emnekode-gruppen til
    # å definere eksport-egenskaper for alle grupper tilknyttet en
    # undervisningsenhet.
    logger.info("Oppdaterer emne-supergrupper:")
    for gname in AffiliatedGroups.keys():
        if gname == auto_supergroup:
            continue
        sync_group(fs_supergroup, gname,
                   "Ikke-eksporterbar gruppe.  Brukes for å samle"
                   " kursene knyttet til %s." % gname,
                   co.entity_group,
                   AffiliatedGroups[gname])
    logger.info(" ... done")
    if not dryrun:
        logger.debug("Commit changes")
        db.commit()

    # All supergroups (i.e. containers for other groups) must be members of
    # auto_supergroup, specific to this import. This makes it easier to track
    # down groups automatically created by this import. Without such a
    # mechanism it would be impossible to automatically delete groups that
    # have been created earlier and that are not longer meaningful.
    logger.info("Oppdaterer supergruppe for alle ekstra grupper")
    sync_group(None, auto_supergroup,
               "Ikke-eksporterbar gruppe.  Definerer hvilke andre "
               "automatisk opprettede grupper som refererer til "
               "grupper speilet fra FS.",
               co.entity_group,
               AffiliatedGroups[auto_supergroup], recurse=False)
    logger.info(" ... done")

    logger.info("Oppdaterer supergruppe for alle emnekode-supergrupper")
    sync_group(None, fs_supergroup,
               "Ikke-eksporterbar gruppe.  Definerer hvilke andre grupper "
               "som er opprettet automatisk som følge av FS-import.",
               co.entity_group,
               AffiliatedGroups[fs_supergroup])
    logger.info(" ... done")


def destined_for_lms(entity):
    """Decide if entity gets fronter spreads.

    Several entities from which we create the groups in Cerebrum have an
    attribute controlling the entities' export to Fronter.


    @param entity:
      Entity (undenh, undakt, evukurs, evuakt, kull) in question
    @type entity: L{db_row}.

    @return:
      True, if entity is to receive all fronter spreads, False otherwise.
    @rtype: bool
    """

    return entity["status_eksport_lms"] == 'J'


def get_kull(kull_file, edu_file):
    """Preload kull information.

    This function generates a data structure describing the kull entries that
    will be processed in this run.

    @type kull_file: basestring
    @param kull_file:
      XML file containing a list of all kull considered available/active in
      FS. (The file is typically generated by import_from_FS.py)

    @type edu_file: basestring
    @param edu_file:
      XML file containing information about students' registration for kull
      (among other things).

    @rtype: dict
    @return:
      A mapping from kull ids to all the interesting info about the respective
      kull.
    """

    students = dict()
    logger.debug("Loading student kull info")
    for entry in EduGenericIterator(edu_file, "kull"):
        kull_id = fields2key("kull", entry["studieprogramkode"],
                             entry["terminkode_kull"], entry["arstall_kull"])
        fnr = "%06d%05d" % (int(entry["fodselsdato"]), int(entry["personnr"]))
        students.setdefault(kull_id, list()).append(fnr)
    logger.debug("Done loading student kull info")

    result = dict()
    logger.debug("Loading kull info itself")
    for kull in EduDataGetter(kull_file, logger).iter_kull():
        kull_id = fields2key("kull", kull["studieprogramkode"],
                             kull["terminkode"], kull["arstall"])
        if kull_id in result:
            raise ValueError("Duplikat kull: <%s>" % kull_id)

        tmp = dict((account_id, 1) for account_id in
                   fnrs2account_ids(students.get(kull_id, ()),
                                    prefer_student=True))
        # In general, we do not change the spreads for 'kull' groups, since
        # they are administered manually. NotSet will accomplish just that.
        result[kull_id] = {"fronter_spreads": NotSet,
                           "sted": make_sko(kull, suffix="_studieansv"),
                           "stprog": fields2key(kull["studieprogramkode"]),
                           "kullnavn": kull["studiekullnavn"],
                           "students": tmp}
        logger.debug("kull <%s> med %d studenter", kull_id,
                     len(result[kull_id]['students']))

    logger.debug("Done loading kull info itself")
    return result


def get_undenh(undenh_file, edu_file):
    """Preload undenh information.

    This function generates multiple data structures describing the undenh
    (undervisningsenhet) that will be processed in this run.

    @type undenh_file: basestring
    @param undenh_file:
      XML file containing a list of all undenh considered available/active in
      FS. (The file is typically generated by import_from_FS.py)

    @type edu_file: basestring
    @param edu_file:
      XML file containing information about students' registration for undenh
      (among other things).

    @rtype: a tuple of 3 dicts
    @return:
      3 dictionaries. The first is the mapping from enhet_id to all the
      interesting info about that enhet_id. Obviously, enhet_ids cover undenh
      only.

      The second and third a specially crafted dicts to track undenh spanning
      multiple semesters.
    """

    result = dict()
    emne_versjon = dict()
    emne_termnr = dict()

    logger.debug("Prefetching undenh info...")

    logger.debug("Loading student undenh info...")
    # Build an overview of the students...
    students = dict()
    for entry in EduGenericIterator(edu_file, "undenh"):
        enhet_id = fields2key("kurs", entry['institusjonsnr'],
                              entry['emnekode'], entry['versjonskode'],
                              entry['terminkode'], entry['arstall'],
                              entry['terminnr'])
        fnr = "%06d%05d" % (int(entry["fodselsdato"]), int(entry["personnr"]))
        students.setdefault(enhet_id, list()).append(fnr)
    logger.debug("Done loading student undenh info")

    #
    # Then populate the dict with all the undenh of interest
    logger.debug("Loading undenh info itself...")
    for enhet in EduDataGetter(undenh_file, logger).iter_undenh():
        enhet_id = fields2key("kurs", enhet['institusjonsnr'],
                              enhet['emnekode'], enhet['versjonskode'],
                              enhet['terminkode'], enhet['arstall'],
                              enhet['terminnr'])

        if enhet_id in result:
            raise ValueError("Duplicate undenh: <%s>" % enhet_id)

        primary, secondary = fnrs2account_ids(students.get(enhet_id, ()),
                                              primary_only=False,
                                              prefer_student=True)
        result[enhet_id] = {"aktivitet": dict(),
                            "fronter_spreads": destined_for_lms(enhet),
                            "sted": make_sko(enhet, suffix="_kontroll"),
                            "students": (primary, secondary)}
        multi_id = fields2key(enhet['institusjonsnr'], enhet['emnekode'],
                              enhet['terminkode'], enhet['arstall'])
        # Finnes det flere enn en undervisningsenhet tilknyttet denne
        # emnekoden i inneværende semester?
        emne_versjon.setdefault(multi_id,
                                {})[fields2key(enhet['versjonskode'])] = 1
        emne_termnr.setdefault(multi_id,
                               {})[fields2key(enhet['terminnr'])] = 1
        logger.debug("undenh <%s> med multi-id <%s>, "
                     "CF=%s, pri=%d, sec=%d students",
                     enhet_id, multi_id, result[enhet_id]['fronter_spreads'],
                     len(result[enhet_id]["students"][0]),
                     len(result[enhet_id]["students"][1]))
    logger.debug("Done loading undenh info...")
    del students
    return result, emne_versjon, emne_termnr


def get_undakt(edu_info, undakt_file, edu_file):
    """Preload undakt information.

    This function supplemets a data structure generated by get_undenh with
    data about undakt (undervisningsaktiviteter) that will be processed in
    this run.

    @type edu_info: dict
    @param edu_info:
      A dict built by L{get_undenh} with undenh data. Undakt data are tied to
      the correspoding undenh data. The former cannot exist without the
      latter. It's like that by design.

    @type undakt_file: basestring
    @param undakt_file:
      XML file containing a list of all undakt considered available/active in
      FS. (The file is typically generated by import_from_FS.py)

    @type edu_file: basestring
    @param edu_file:
      XML file containing information about students' registration for undenh
      (among other things).
    """

    logger.debug("Prefetching undakt info...")
    logger.debug("Loading student undakt info...")
    # Build an overview of the students...
    students = dict()
    for entry in EduGenericIterator(edu_file, "undakt"):
        enhet_id = fields2key("kurs", entry['institusjonsnr'],
                              entry['emnekode'], entry['versjonskode'],
                              entry['terminkode'], entry['arstall'],
                              entry['terminnr'], entry['aktivitetkode'])
        fnr = "%06d%05d" % (int(entry["fodselsdato"]), int(entry["personnr"]))
        students.setdefault(enhet_id, list()).append(fnr)
    logger.debug("Done loading student undakt info")

    # Then populate the dict with all the undakt of interest
    logger.debug("Loading undakt info itself...")
    for undakt in EduDataGetter(undakt_file, logger).iter_undakt():
        enhet_id = fields2key("kurs", undakt['institusjonsnr'],
                              undakt['emnekode'], undakt['versjonskode'],
                              undakt['terminkode'], undakt['arstall'],
                              undakt['terminnr'])
        aktkode = fields2key(undakt["aktivitetkode"])
        if enhet_id not in edu_info:
            logger.error("Ikke-eksisterende enhet <%s> har aktiviteter "
                         "(aktkode %s)", enhet_id, aktkode)
            continue

        if aktkode in edu_info[enhet_id]['aktivitet']:
            raise ValueError("Duplikat undervisningsaktivitet <%s:%s>" %
                             (enhet_id, aktkode))

        # Fetch the students from cache, and remap to account-ids. This has to
        # be a dict(), since sync_group expects a dict-like interface.
        cache_key = fields2key(enhet_id, aktkode)
        tmp = dict((account_id, 1) for account_id in
                   fnrs2account_ids(students.get(cache_key, ()),
                                    prefer_student=True))
        edu_info[enhet_id]['aktivitet'][aktkode] = {
            'aktivitetsnavn': undakt['aktivitetsnavn'],
            'fronter_spreads': destined_for_lms(undakt),
            'sted': make_sko(undakt,
                             suffix="_kontroll"),
            'students': tmp}
        logger.debug("undakt <%s> for undenh <%s>; %d student(er) (CF: %s)",
                     aktkode, enhet_id, len(tmp),
                     destined_for_lms(undakt))
    logger.debug("Done loading undakt info")
    del students


def get_evu(evu_file, edu_file):
    """Preload undenh information.

    This function generates multiple data structures describing the evu
    (etter- og videreutdanningskurs) that will be processed in this run.

    @type evu_file: basestring
    @param evu_file:
      XML file containing a list of all evu considered available/active in
      FS. (The file is typically generated by import_from_FS.py)

    @type edu_file: basestring
    @param edu_file:
      XML file containing information about students' registration for evu
      (among other things).

    @rtype: dict
    @return:
      A mapping from evu_id to all the interesting info about that
      evu. Obviously, evu_ids cover evu only.
    """

    result = dict()

    logger.debug("Prefetching evu info...")
    logger.debug("Loading student evu info...")
    # Build an overview of the students...
    students = dict()
    for entry in EduGenericIterator(edu_file, "evu"):
        evu_id = fields2key("evu", entry['etterutdkurskode'],
                            entry['kurstidsangivelsekode'])
        fnr = "%06d%05d" % (int(entry["fodselsdato"]), int(entry["personnr"]))
        students.setdefault(evu_id, list()).append(fnr)
    logger.debug("Done loading student evu info")

    # Then populate the dict with all the evu of interest
    logger.debug("Loading evu info itself...")
    for evu in EduDataGetter(evu_file, logger).iter_evu():
        evu_id = fields2key("evu", evu['etterutdkurskode'],
                            evu['kurstidsangivelsekode'])

        # students' account ids (a dict, since sync_group expects a
        # db_row-like object)
        tmp = dict((account_id, 1) for account_id in
                   fnrs2account_ids(students.get(evu_id, ()),
                                    prefer_student=True))
        result[evu_id] = {"fronter_spreads": destined_for_lms(evu),
                          "sted": make_sko(evu, suffix="_adm_ansvar"),
                          "students": tmp,
                          "aktivitet": dict()}
        logger.debug("EVU-kurs <%s>, %d student(er) (CF: %s)",
                     evu_id, len(tmp), destined_for_lms(evu))
    logger.debug("Done loading evu info itself...")

    return result


def get_kursakt(edu_info, kursakt_file, edu_file):
    """Preload kursakt information.

    This function supplements a data structure generated by get_evu with data
    about kursakt (evu-kursaktiviteter) that will be processed in this run.

    @type edu_info: dict
    @param edu_info:
      A dict built by L{get_evu} with evu data. Kursakt data are tied to the
      correspoding evu data. The former cannot exist without the latter. It's
      like that by design.

    @type kursakt_file: basestring
    @param kursakt_file:
      XML file containing a list of all kursakt considered available/active in
      FS. (The file is typically generated by import_from_FS.py)

    @type edu_file: basestring
    @param edu_file:
      XML file containing information about students' registration for kursakt
      (among other things).
    """

    logger.debug("Prefetching kursakt info...")
    logger.debug("Loading student kursakt info...")
    # Build an overview of the students...
    students = dict()
    for entry in EduGenericIterator(edu_file, "kursakt"):
        kursakt_id = fields2key("evu", entry['etterutdkurskode'],
                                entry['kurstidsangivelsekode'],
                                entry['aktivitetskode'])
        fnr = "%06d%05d" % (int(entry["fodselsdato"]), int(entry["personnr"]))
        students.setdefault(kursakt_id, list()).append(fnr)
    logger.debug("Done loading student kursakt info")

    logger.debug("Loading kursakt info itself...")
    for kursakt in EduDataGetter(kursakt_file, logger).iter_kursakt():
        evu_id = fields2key("evu", kursakt['etterutdkurskode'],
                            kursakt['kurstidsangivelsekode'])
        logger.debug('Processing EVU-kurs: %s', evu_id)
        aktkode = fields2key(kursakt["aktivitetskode"])
        if evu_id not in edu_info:
            logger.error("Ikke-eksisterende EVU-kurs <%s> har aktiviteter "
                         "(aktkode %s)", evu_id, aktkode)
            continue
        if aktkode in edu_info[evu_id]['aktivitet']:
            raise ValueError("Duplikat kursaktivitet <%s:%s>" %
                             (evu_id, aktkode))

        cache_key = fields2key(evu_id, aktkode)

        student_accounts = dict((account_id, 1) for account_id in
                                fnrs2account_ids(students.get(cache_key, ()),
                                                 prefer_student=True))
        tmp = {'aktivitetsnavn': kursakt['aktivitetsnavn'],
               'fronter_spreads': destined_for_lms(kursakt),
               'sted': edu_info[evu_id]['sted'],
               'students': student_accounts}
        edu_info[evu_id].setdefault('aktivitet', {})[aktkode] = tmp

        logger.debug("evuakt <%s> (kurs <%s>); %d student(er) (CF: %s)",
                     aktkode, evu_id, len(student_accounts),
                     destined_for_lms(kursakt))
    logger.debug("Done loading kursakt info itself...")


def account_id2uname(account_id):
    """Remap account_id to an uname, if possible.

    This is an internal help function used in error messages.

    @type account_id: int
    @param account_id:
      account_id to remap

    @rtype: basestring
    @return:
      Uname, if found, None otherwise.
    """

    acc = Factory.get("Account")(db)
    try:
        acc.find(account_id)
        return acc.account_name
    except Errors.NotFoundError:
        return None


# IVR 2007-11-08 FIXME: OMG! split this monstrosity into something manageable.
def populate_enhet_groups(enhet_id, role_mapping):
    enhet_id = str2key(enhet_id)
    type_id = key2fields(enhet_id)
    type = type_id.pop(0)

    if type == 'kurs':
        Instnr, emnekode, versjon, termk, aar, termnr = type_id

        # Finnes det mer enn en undervisningsenhet knyttet til dette
        # emnet, kun forskjellig på versjonskode og/eller terminnr?  I
        # så fall bør gruppene få beskrivelser som gjør det mulig å
        # knytte dem til riktig undervisningsenhet.
        multi_enhet = []
        multi_id = ":".join((Instnr, emnekode, termk, aar))
        if len(emne_termnr.get(multi_id, {})) > 1:
            multi_enhet.append("%s. termin" % termnr)
        if len(emne_versjon.get(multi_id, {})) > 1:
            multi_enhet.append("v%s" % versjon)
        if multi_enhet:
            enhet_suffix = ", %s" % ", ".join(multi_enhet)
        else:
            enhet_suffix = ""
        logger.debug("Oppdaterer grupper for %s %s %s%s:" % (
            emnekode, termk, aar, enhet_suffix))

        # TODO: generaliser ifi-hack seinare
        # IVR 2008-05-14: itslp added at ifi-drift's request
        if (re.match(r"(dig|inf|in|med-inf|tool|humit|itslp|mat-in)",
                     emnekode.lower()) and
                termk == fs.info.semester.lower() and
                aar == str(fs.info.year)):
            logger.debug(" (ta med Ifi-spesifikke grupper)")
            ifi_hack = True
            netgr_emne = emnekode.lower().replace("-", "")
            alle_ansv = {}  # for gKURS: alle grl og kursledelse
            empty = {}
            if re.search(r'[0123]\d\d\d', emnekode):
                ifi_netgr_lkurs["g%s" % netgr_emne] = 1
        else:
            ifi_hack = False

        # Finnes kurs som går over mer enn et semester, samtidig som
        # at kurset/emnet starter hvert semester.  Utvider strukturen
        # til å ta høyde for at det til enhver tid kan finnes flere
        # kurs av samme type til enhver tid.
        kurs_id = UE2KursID('kurs', Instnr, emnekode,
                            versjon, termk, aar, termnr)
        logger.debug("Lister opp ansvarlige, kurs_id = <%s>, enhet_id = <%s>",
                     kurs_id, enhet_id)
        sted = UndervEnhet[enhet_id]['sted']
        process_role(enhet_id,
                     fields2key(enhet_id, "%s"),
                     role_mapping,
                     kurs_id,
                     "Ansvarlige (%s) %s %s %s%s" % ("%s", emnekode,
                                                     termk,
                                                     aar, enhet_suffix),
                     co.entity_account,
                     # Dersom undenh i seg selv skal eksporteres til Fronter,
                     # så må nødvendigvis grupper med dens ansvarlige gjøre
                     # det også.
                     UndervEnhet[enhet_id]["fronter_spreads"],
                     sted)

        # Ifi vil ha at alle konti til en gruppelærer skal listes opp
        # på lik linje.  Alle ikke-primære konti blir derfor lagt inn i
        # en egen interngruppe, og de to interngruppene blir medlemmer
        # i Ifis nettgruppe.
        if ifi_hack:
            prim, sec = dbrows2account_ids(extract_all_roles(enhet_id,
                                                             role_mapping,
                                                             sted),
                                           primary_only=False)
            # sync_group forventer en dict (ellers kunne vi ha brukt
            # sequence/set)
            enhet_ansv = dict(izip(prim, repeat(1)))
            sync_group(kurs_id,
                       fields2key(enhet_id, "enhetsansvar"),
                       "Ansvarlige %s %s %s%s" % (emnekode, termk,
                                                  aar, enhet_suffix),
                       co.entity_account,
                       enhet_ansv)

            enhet_ansv_sek = dict(izip(sec, repeat(1)))
            sync_group(kurs_id,
                       fields2key(enhet_id, "enhetsansvar-sek"),
                       ("Ansvarlige %s %s %s%s (sekundærkonti)" %
                        (emnekode, termk, aar, enhet_suffix)),
                       co.entity_account,
                       enhet_ansv_sek)
            gname = mkgname(fields2key(enhet_id, "enhetsansvar"),
                            prefix='uio.no:fs:')
            gmem = {gname: 1,
                    "%s-sek" % gname: 1}
            netgr_navn = "g%s-0" % netgr_emne
            sync_group(auto_supergroup, netgr_navn,
                       "Ansvarlige %s %s %s%s" % (emnekode, termk, aar,
                                                  enhet_suffix),
                       co.entity_group,
                       gmem,
                       visible=True)
            add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
            alle_ansv[netgr_navn] = 1
        #
        # Alle nåværende undervisningsmeldte samt nåværende+fremtidige
        # eksamensmeldte studenter.
        logger.debug(" student")
        primary, secondary = UndervEnhet[enhet_id]["students"]
        alle_stud = dict(izip(primary, repeat(1)))

        sync_group(kurs_id,
                   fields2key(enhet_id, "student"),
                   "Studenter %s %s %s%s" % (emnekode, termk,
                                             aar, enhet_suffix),
                   co.entity_account,
                   alle_stud,
                   # Dersom undenh skal eksporteres til fronter selv, så må
                   # også gruppen med studentene gjøre det.
                   auto_spread=UndervEnhet[enhet_id]["fronter_spreads"])
        if ifi_hack:
            alle_stud_sek = {}
            alle_aktkoder = {}
            for account_id in secondary:
                alle_stud_sek[int(account_id)] = 1
            gname = mkgname(fields2key(enhet_id, "student-sek"),
                            prefix='uio.no:fs:')
            sync_group(kurs_id,
                       gname,
                       ("Studenter %s %s %s%s (sekundærkonti)" %
                        (emnekode, termk, aar, enhet_suffix)),
                       co.entity_account,
                       alle_stud_sek)
            # Vi legger sekundærkontoene inn i sKURS, slik at alle
            # kontoene får privelegier knyttet til kurset.  Dette
            # innebærer at alle kontoene får e-post til
            # studenter.KURS, men bare primærkontoen får e-post til
            # studenter.KURS-GRUPPE.  Vi må kanskje revurdere dette
            # senere basert på tilbakemeldinger fra brukerene.
            #
            # TODO: ifi-l, ifi-prof, ifi-h, kullkoder,
            # ifi-mnm5infps-mel ifi-mnm2eld-mel ifi-mnm2infis
            # ifi-mnm5infps ifi-mnm2inf ifi-mnm2eld-sig
            alle_aktkoder[gname] = 1

        # Studenter som både 1) er undervisnings- eller eksamensmeldt,
        # og 2) er med i minst en undervisningsaktivitet, blir meldt
        # inn i dicten 'student_med_akt'.  Denne dicten kan så, sammen
        # med dicten 'alle_stud', brukes for å finne hvilke studenter
        # som er eksamens- eller undervisningsmeldt uten å være meldt
        # til noen aktiviteter.
        student_med_akt = {}

        for aktkode in UndervEnhet[enhet_id].get('aktivitet', {}):
            #
            # Ansvarlige for denne undervisningsaktiviteten.
            logger.debug(" aktivitetsansvar:%s" % aktkode)

            gname = mkgname(fields2key(enhet_id, "%s", aktkode),
                            prefix='uio.no:fs:')
            aktivitet = UndervEnhet[enhet_id]["aktivitet"][aktkode]
            sted = aktivitet["sted"]
            process_role(fields2key(enhet_id, aktkode),
                         gname,
                         role_mapping,
                         kurs_id,
                         "Ansvarlig (%s) %s %s %s%s %s" %
                         ("%s", emnekode, termk, aar, enhet_suffix,
                          aktivitet["aktivitetsnavn"]),
                         co.entity_account,
                         # Hvis aktiviteten skal til fronter, så må også de
                         # ansvarlige for aktiviteten det.
                         aktivitet["fronter_spreads"],
                         sted)

            if ifi_hack:
                akt_ansv = {}
                prim, sec = dbrows2account_ids(
                    extract_all_roles("%s:%s" % (enhet_id, aktkode),
                                      role_mapping, sted),
                    primary_only=False)
                akt_ansv = dict(izip(prim, repeat(1)))
                aktivitet = UndervEnhet[enhet_id]['aktivitet'][aktkode]
                gname = mkgname(fields2key(enhet_id, "aktivitetsansvar"),
                                prefix='uio.no:fs:')
                sync_group(kurs_id,
                           fields2key(gname, aktkode),
                           "Ansvarlige %s %s %s%s %s" % (
                               emnekode, termk, aar, enhet_suffix,
                               aktivitet["aktivitetsnavn"]),
                           co.entity_account,
                           akt_ansv)
                for account_id in sec:
                    akt_ansv[account_id] = 1

                # Sammenhengen mellom aktivitetskode og -navn er
                # uklar.  Hva folk forventer som navn er like vanskelig
                #
                # Noen eksempel:
                #   1   -> "Arbeidslivspedagogikk 2"
                #   3-1 -> "Gruppe 1"
                #   2-2 -> "Øvelser 102"
                #   1-1 -> "Forelesning"
                #
                # På Ifi forutsetter vi formen "<aktivitetstype> N",
                # og plukker derfor ut det andre ordet i strengen for
                # bruk i nettgruppenavnet brukerne vil se.
                #
                # Det kan hende en bedre heuristikk ville være å se
                # etter et tall i navnet og bruke dette, hvis ikke,
                # bruke hele navnet med blanke erstattet av
                # bindestreker.
                aktnavn = aktivitet["aktivitetsnavn"].lower().strip()
                m = re.match(r'\S+ (\d+)', aktnavn)
                if m:
                    aktnavn = m.group(1)
                else:
                    aktnavn = aktnavn.replace(" ", "-")
                    aktnavn = transliterate.for_posix(aktnavn)
                logger.debug("Aktivitetsnavn '%s' -> '%s'" %
                             (aktivitet["aktivitetsnavn"], aktnavn))
                sync_group(kurs_id,
                           "%s-sek:%s" % (gname, aktkode),
                           ("Ansvarlige %s %s %s%s %s (sekundærkonti)" %
                            (emnekode, termk, aar, enhet_suffix, aktnavn)),
                           co.entity_account,
                           akt_ansv)
                gmem = {fields2key(gname, aktkode): 1,
                        "%s-sek:%s" % (gname, aktkode): 1}
                netgr_navn = "g%s-%s" % (netgr_emne, aktnavn)
                sync_group(auto_supergroup,
                           netgr_navn,
                           "Ansvarlige %s-%s %s %s%s" % (emnekode, aktnavn,
                                                         termk, aar,
                                                         enhet_suffix),
                           co.entity_group,
                           gmem,
                           visible=True)
                # midlertidig
                sync_group(auto_supergroup,
                           netgr_navn,
                           "Ansvarlige %s-%s %s %s%s" % (emnekode, aktnavn,
                                                         termk, aar,
                                                         enhet_suffix),
                           co.entity_account,
                           empty,
                           visible=True)
                add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
                alle_ansv[netgr_navn] = 1
                ifi_netgr_g[netgr_navn] = 1

            # Studenter meldt på denne undervisningsaktiviteten.
            logger.debug(" student:%s" % aktkode)
            aktivitet = UndervEnhet[enhet_id]['aktivitet'][aktkode]
            akt_stud = {}
            for account_id in aktivitet['students']:
                if account_id not in alle_stud:
                    account_name = account_id2uname(account_id)
                    logger.warn("Bruker %r er med i undaktivitet <%s>,"
                                " men ikke i undervisningsenhet <%s>",
                                account_name or account_id,
                                "%s:%s" % (enhet_id, aktkode),
                                enhet_id)
                akt_stud[account_id] = 1

            logger.debug("%d studenter ved undakt <%s> for undenh <%s>",
                         len(akt_stud), aktkode, enhet_id)
            student_med_akt.update(akt_stud)
            sync_group(kurs_id,
                       fields2key(enhet_id, "student", aktkode),
                       "Studenter %s %s %s%s %s" %
                       (emnekode, termk, aar, enhet_suffix,
                        aktivitet["aktivitetsnavn"]),
                       co.entity_account,
                       akt_stud,
                       # Hvis aktiviteten skal til fronter
                       # (jfr. status_eksport_lms), så må studentene på
                       # aktiviteten også eksporteres til fronter
                       auto_spread=aktivitet["fronter_spreads"])

            if ifi_hack:
                gname = mkgname(fields2key(enhet_id, "student", aktkode),
                                prefix='uio.no:fs:')
                gmem = {gname: 1}
                netgr_navn = "s%s-%s" % (netgr_emne, aktnavn)
                sync_group(auto_supergroup,
                           netgr_navn,
                           "Studenter %s-%s %s %s%s" % (emnekode, aktnavn,
                                                        termk, aar,
                                                        enhet_suffix),
                           co.entity_group,
                           gmem,
                           visible=True)
                # midlertidig
                sync_group(auto_supergroup,
                           netgr_navn,
                           "Studenter %s-%s %s %s%s" % (emnekode, aktnavn,
                                                        termk, aar,
                                                        enhet_suffix),
                           co.entity_account,
                           empty,
                           visible=True)
                add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
                alle_aktkoder[netgr_navn] = 1

        # ferdig med alle aktiviteter, bare noen få hack igjen ...
        for account_id in student_med_akt.iterkeys():
            if account_id in alle_stud:
                # Ved å fjerne alle som er meldt til minst en
                # aktivitet, ender vi opp med en liste over de som
                # kun er meldt til eksamene.
                del alle_stud[account_id]
        if ifi_hack:
            gname = mkgname(fields2key(enhet_id, "student", "kuneksamen"),
                            prefix='uio.no:fs:')
            sync_group(kurs_id,
                       gname,
                       ("Studenter %s %s %s%s %s" %
                        (emnekode, termk, aar, enhet_suffix, "kun eksamen")),
                       co.entity_account,
                       alle_stud)
            gmem = {gname: 1}
            netgr_navn = "s%s-e" % netgr_emne
            sync_group(auto_supergroup,
                       netgr_navn,
                       "Studenter %s-e %s %s%s" % (emnekode, termk, aar,
                                                   enhet_suffix),
                       co.entity_group,
                       gmem,
                       visible=True)
            # midlertidig
            sync_group(auto_supergroup,
                       netgr_navn,
                       "Studenter %s-e %s %s%s" % (emnekode, termk, aar,
                                                   enhet_suffix),
                       co.entity_account,
                       empty,
                       visible=True)
            add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
            alle_aktkoder[netgr_navn] = 1
            # alle studenter på kurset
            netgr_navn = "s%s" % netgr_emne
            sync_group(auto_supergroup,
                       netgr_navn,
                       "Studenter %s %s %s%s" % (emnekode, termk, aar,
                                                 enhet_suffix),
                       co.entity_group,
                       alle_aktkoder,
                       visible=True)
            # midlertidig
            sync_group(auto_supergroup,
                       netgr_navn,
                       "Studenter %s %s %s%s" % (emnekode, termk, aar,
                                                 enhet_suffix),
                       co.entity_account,
                       empty,
                       visible=True)
            add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
            # alle gruppelærere og kursledelsen
            netgr_navn = "g%s" % netgr_emne
            sync_group(auto_supergroup,
                       netgr_navn,
                       "Ansvarlige %s %s %s%s" % (emnekode, termk, aar,
                                                  enhet_suffix),
                       co.entity_group,
                       alle_ansv,
                       visible=True)
            # midlertidig
            sync_group(auto_supergroup,
                       netgr_navn,
                       "Ansvarlige %s %s %s%s" % (emnekode, termk, aar,
                                                  enhet_suffix),
                       co.entity_account,
                       empty,
                       visible=True)
            add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)

    elif type == 'kull':
        stprog, terminkode, aar = type_id
        kull_id = UE2KursID("kull", stprog, terminkode, aar)
        logger.debug("Oppdaterer grupper for %s:", enhet_id)

        #
        # Alle studenter på kullet
        sync_group(kull_id,
                   fields2key(enhet_id, "student"),
                   "Studenter på kull %s, %s, %s" % (stprog, terminkode, aar),
                   co.entity_account,
                   UndervEnhet[enhet_id].get('students', {}),
                   auto_spread=UndervEnhet[enhet_id]["fronter_spreads"])

        # IVR 2007-08-17: 'Ansvarlige' for kullet: hver rolle får sin egen
        # gruppe.
        sted = UndervEnhet[enhet_id]["sted"]
        program = UndervEnhet[enhet_id]["stprog"]
        process_role(kull_id,
                     fields2key(kull_id, "%s"),
                     role_mapping,
                     kull_id,
                     "Ansvarlige (%s) på kull %s" % ("%s", kull_id),
                     co.entity_account,
                     UndervEnhet[enhet_id]["fronter_spreads"],
                     sted,
                     program)

    elif type == 'evu':
        kurskode, tidsrom = type_id
        kurs_id = UE2KursID("evu", kurskode, tidsrom)
        logger.debug("Oppdaterer grupper for %s: " % enhet_id)
        sted = UndervEnhet[enhet_id]["sted"]
        process_role(enhet_id,
                     fields2key(enhet_id, "%s"),
                     role_mapping,
                     kurs_id,
                     "Ansvarlige (%s) EVU-kurs %s, %s" % ("%s", kurskode,
                                                          tidsrom),
                     co.entity_account,
                     # Samme situasjon som med undenh
                     UndervEnhet[enhet_id]["fronter_spreads"],
                     sted)

        #
        # Alle påmeldte studenter
        logger.debug(" evuStudenter")
        evustud = UndervEnhet[fields2key("evu", kurskode, tidsrom)]['students']
        sync_group(kurs_id,
                   fields2key(enhet_id, "student"),
                   "Studenter EVU-kurs %s, %s" % (kurskode, tidsrom),
                   co.entity_account,
                   evustud,
                   auto_spread=UndervEnhet[enhet_id]["fronter_spreads"])

        for aktkode in UndervEnhet[enhet_id].get('aktivitet', {}).keys():
            aktivitet = UndervEnhet[enhet_id]['aktivitet'][aktkode]
            sted = aktivitet["sted"]
            process_role(fields2key(enhet_id, aktkode),
                         fields2key(enhet_id, "%s", aktkode),
                         role_mapping,
                         kurs_id,
                         "Ansvarlige (%s) EVU-kurs %s, %s: %s" %
                         ("%s", kurskode, tidsrom,
                          aktivitet["aktivitetsnavn"]),
                         co.entity_account,
                         # Samme situasjon som undakt
                         aktivitet["fronter_spreads"],
                         sted)

            # Studenter til denne kursaktiviteten
            logger.debug(" student:%s" % aktkode)
            evu_akt_stud = {}
            for account_id in aktivitet['students']:
                if account_id not in evustud:
                    account_name = account_id2uname(account_id)
                    logger.warn("Bruker %r er med i aktivitet <%s>,"
                                " men ikke i kurset <%s>.",
                                account_name or account_id,
                                "%s:%s" % (enhet_id, aktkode), enhet_id)
                evu_akt_stud[account_id] = 1
            sync_group(kurs_id,
                       fields2key(enhet_id, "student", aktkode),
                       "Studenter EVU-kurs %s, %s: %s" %
                       (kurskode, tidsrom, aktivitet["aktivitetsnavn"]),
                       co.entity_account,
                       evu_akt_stud,
                       auto_spread=aktivitet["fronter_spreads"])
    logger.debug(" done")
    if not dryrun:
        logger.debug("Commit changes")
        db.commit()


def populate_ifi_groups():
    sync_group(auto_supergroup, "ifi-g", "Alle gruppelærere for Ifi-kurs",
               co.entity_group, ifi_netgr_g, visible=True)
    add_spread_to_group("ifi-g", co.spread_ifi_nis_ng)
    sync_group(auto_supergroup, "lkurs", "Alle laveregradskurs ved Ifi",
               co.entity_group, ifi_netgr_lkurs, visible=True)
    add_spread_to_group("lkurs", co.spread_ifi_nis_ng)


def sync_group(affil, gname, descr, mtype, memb, visible=False, recurse=True,
               auto_spread=NotSet):
    """Update/create a fronter group with new information.

    Locate (and create if necessary) a group representing an entity (corridor,
    rom, etc.) in Fronter.

    @type affil: basestring
    @param affil:
      Parent for gname in the internal group structure (?)

    @type gname: basestring
    @param gname:
      Basis for constructing the group name. For invisible groups, it is
      prefixed with 'uio:fs'.

    @type descr: basestring
    @param descr:
      Description of the group to register in group_info in Cerebrum.

    @type mtype: A suitable constant object
    @param mtype:
      Constant describing member types in memb. Can be group or account

    @type memb: dict
    @param memb:
      Dictionary with member ids to add to gname.

    @type auto_spread: bool or NotSet
    @param auto_spread:
      auto_spread decides whether to adjust fronter spreads belonging to
      L{gname} automatically. Some groups receive and lose fronter spreads
      automatically (cf. eksport_status_lms from FS). Others are updated
      manually and should not be touched.

      NotSet means that the spread information should be left alone.
      False means that fronter spreads should be removed.
      True meands that fronter spreads should be added.
    """

    logger.debug("sync_group(%s; %s; %s; %s; %s; %s; %s); auto_spread=%s" %
                 (affil, gname, descr, mtype, memb.keys(), visible, recurse,
                  auto_spread is NotSet and "NotSet" or auto_spread))
    if mtype == co.entity_group:  # memb has group_name as keys
        members = {}
        for tmp_gname in memb.keys():
            grp = get_group(tmp_gname)
            members[int(grp.entity_id)] = 1
    else:  # memb has account_id as keys
        members = memb.copy()
    if visible:
        # visibility implies that the group name should be used as is.
        correct_visib = co.group_visibility_all
        if not affil == auto_supergroup:
            raise ValueError("All visible groups must be members of the "
                             "supergroup for automatic groups")
    else:
        gname = mkgname(gname, 'uio.no:fs:')
        correct_visib = co.group_visibility_none
        if (
                # level 0; $gname is the supergroup
                affil is None or
                # $gname is at level 1
                affil == fs_supergroup or
                # $gname is at level 2
                re.search(r'^(evu|kurs|kull):[^:]+$', affil, re.I)):
            # The aforementioned groups are for internal usage only;
            # they are used to control the hierarchy and export.
            gname = mkgname(gname)
            correct_visib = co.group_visibility_internal
    if affil is not None:
        AffiliatedGroups.setdefault(affil, {})[gname] = 1
    known_FS_groups[gname] = 1

    try:
        group = get_group(gname)
    except Errors.NotFoundError:
        group = Factory.get('Group')(db)
        group.clear()
        group.populate(
            creator_id=group_creator,
            visibility=correct_visib,
            name=gname,
            description=descr,
            group_type=co.group_type_lms,
        )
        group.write_db()
    else:
        # If group already exists, update its information...
        if group.visibility != correct_visib:
            logger.fatal("Group <%s> has wrong visibility." % gname)

        if group.description != descr:
            group.description = descr
            group.write_db()

        if group.is_expired():
            # Extend the group's life by 6 months
            from mx.DateTime import now, DateTimeDelta
            group.expire_date = now() + DateTimeDelta(6 * 30)
            group.write_db()

        for row in group.search_members(group_id=group.entity_id,
                                        member_type=mtype,
                                        member_filter_expired=False):
            member = int(row["member_id"])
            # make sure to filter 'em out
            if member in members and member not in exclude['users']:
                del members[member]
            else:
                logger.debug("sync_group(): Deleting member %d" % member)
                group.remove_member(member)
                #
                # Supergroups will only contain groups that have been
                # automatically created by this script, hence it is
                # safe to automatically destroy groups that are no
                # longer member of their supergroup.
                if (mtype == co.entity_group and
                        correct_visib == co.group_visibility_internal and
                        member not in known_FS_groups):
                    # IVR 2009-02-25 TBD: It has been decided (by baardj, jazz
                    # and ivr) that deletion *cannot* be implemented until it
                    # is THOROUGHLY and precisely specified. Until such
                    # specification is forthcoming, no deletion should be
                    # performed (recursive or otherwise).
                    # destroy_group(member, recurse=recurse)
                    pass

    for member in members.keys():
        # We don't wanna add some users
        if member not in exclude['users']:
            group.add_member(member)

    # Finally fixup fronter spreads, if we have to.
    if auto_spread is not NotSet:
        logger.debug("Group %s changes fronter spreads", gname)
        if auto_spread:
            add_spread_to_group(gname, co.spread_fronter_dotcom)
        else:
            remove_spread_from_group(gname, co.spread_fronter_dotcom)
    else:
        logger.debug("Spreads for group %s are unchanged", gname)


def destroy_group(gname, max_recurse=2, recurse=True):
    gr = get_group(gname)
    # if recurse:
    #     # 2004-07-01: Deletion of groups has been disabled until we've
    #     # managed to come up with a deletion process that can be
    #     # committed at multiple checkpoints, rather than having to
    #     # wait with commit until we're completely done.
    #     logger.debug("destroy_group(%s/%d, %d) [DISABLED]"
    #                  % (gr.group_name, gr.entity_id, max_recurse))
    #     return
    logger.debug("destroy_group(%s/%d, %d) [After get_group]"
                 % (gr.group_name, gr.entity_id, max_recurse))
    if recurse and max_recurse < 0:
        logger.fatal("destroy_group(%s): Recursion too deep" % gr.group_name)
        sys.exit(3)

    if gr.get_extensions():
        logger.fatal("destroy_group(%s): Group is %r",
                     gr.group_name, gr.get_extensions())
        sys.exit(4)

    # If this group is a member of other groups, remove those
    # memberships.
    for r in gr.search(member_id=gr.entity_id, indirect_members=False):
        parent = get_group(r['group_id'])
        logger.info("removing %s from group %s" % (gr.group_name,
                                                   parent.group_name))
        parent.remove_member(gr.entity_id)

    # If a e-mail target is of type multi and has this group as its
    # destination, delete the e-mail target and any associated
    # addresses.  There can only be one target per group.
    et = Email.EmailTarget(db)
    try:
        et.find_by_email_target_attrs(target_type=co.email_target_multi,
                                      target_entity_id=gr.entity_id)
    except Errors.NotFoundError:
        pass
    else:
        logger.debug("found email target referencing %s" % gr.group_name)
        ea = Email.EmailAddress(db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            logger.debug("deleting address %s@%s" %
                         (r['local_part'], r['domain']))
            ea.delete()
        et.delete()
    # Fetch group's members
    gr_members = gr.search_members(group_id=gr.entity_id,
                                   member_type=co.entity_group,
                                   member_filter_expired=False)
    logger.debug("destroy_group() subgroups: %r" % (gr_members,))
    # Remove any spreads the group has
    for row in gr.get_spread():
        gr.delete_spread(row['spread'])
    # Remove any references to the group as an authorization target.
    aot = BofhdAuthOpTarget(db)
    ar = BofhdAuthRole(db)
    for r in aot.list(entity_id=gr.entity_id, target_type="group"):
        aot.clear()
        aot.find(r['op_target_id'])
        # We remove all auth_role entries first so that there are no
        # references to this op_target_id, just in case someone adds a
        # foreign key constraint later.
        for role in ar.list(op_target_id=r["op_target_id"]):
            ar.revoke_auth(role['entity_id'], role['op_set_id'],
                           r['op_target_id'])
        aot.delete()
    # Remove any authorization roles the group posesses.
    for r in ar.list(entity_ids=[gr.entity_id]):
        ar.revoke_auth(gr.entity_id, r['op_set_id'], r['op_target_id'])
        # Also remove targets if this was the last reference from
        # auth_role.
        remaining = ar.list(op_target_id=r['op_target_id'])
        if len(remaining) == 0:
            aot.clear()
            aot.find(r['op_target_id'])
            aot.delete()
    # Delete the parent group (which implicitly removes all membership
    # entries representing direct members of the parent group)
    gr.delete()
    # Destroy any subgroups (down to level max_recurse).  This needs
    # to be done after the parent group has been deleted, in order for
    # the subgroups not to be members of the parent anymore.
    if recurse:
        for subg in gr_members:
            destroy_group(int(subg["member_id"]), max_recurse - 1)


def add_spread_to_group(group, spread):
    gr = get_group(group)
    if not gr.has_spread(spread):
        gr.add_spread(spread)
        logger.debug("Adding spread %s to %s" % (spread, group))


def remove_spread_from_group(group, spread):
    gr = get_group(group)
    if gr.has_spread(spread):
        gr.delete_spread(spread)
        logger.debug("Removing spread %s from %s" % (spread, group))


def get_group(id):
    gr = Factory.get('Group')(db)
    if isinstance(id, basestring):
        gr.find_by_name(id)
    else:
        gr.find(id)
    return gr


def get_account(name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(name)
    return ac


def mkgname(id, prefix='internal:'):
    if id.startswith(prefix):
        return id.lower()
    return (prefix + id).lower()


def parse_xml_roles(fname):
    """Parse a files with FS roles and return a dict structured thus::

      map = { K1 : D1={ X1: [ S_1, S_2, ... S_k ],
                        X2: [ ... ], },
              ...
              Kn : Dn={ X1: [ S_1, ..., S_kn ], }

    ... where each K_i is a key falling into one of these 7 categories:
    undakt, undenh, kursakt, evu, kull, sted and stprog; each key K_i
    identifies an instance of undakt/undenh/kursakt/evu/kull.

    Each D_i is (again) a dictionary mapping specific roles (X_i being the
    keys 'ADMIN', 'DLO', and so on) to sequences of S_i; and each S_i is
    a mapping structured thus::

      map2 = { 'fodselsdato' : ...,
               'personnr'    : ..., }

    S_i are an attempt to mimic db_rows (output from this function is used
    elsewhere where such keys are required).

    This structure is pretty complicated, but we need to hold *all* roles in
    memory while processing fronter groups (a sequential scan of the file for
    each undenh/undakt/etc. is out of the question).
    """

    detailed_roles = dict()
    stats = {'elem': 0}

    def element_to_role(element, data):
        stats['elem'] += 1
        kind = data[roles_xml_parser.target_key]
        if len(kind) > 1:
            logger.warn("role[%d]: cannot decide on role kind for: %r",
                        stats['elem'], kind)
            return
        kind = kind[0]

        # IVR 2007-11-08 ivr, jazz and baardj agreed that "timeplan"-roles
        # have to be treated the same as undakt roles when it comes to
        # fronter.
        if kind in ("undakt", "undenh", "timeplan",):
            key = ("kurs",
                   data["institusjonsnr"],
                   data["emnekode"],
                   data["versjonskode"],
                   data["terminkode"],
                   data["arstall"],
                   data["terminnr"])
            if kind in ("undakt", "timeplan"):
                key = key + (data["aktivitetkode"],)
        elif kind in ("kursakt", "evu"):
            key = ("evu",
                   data["etterutdkurskode"],
                   data["kurstidsangivelsekode"])
            if kind == "kursakt":
                key = key + (data["aktivitetkode"],)
        elif kind in ("kull",):
            key = ("kull",
                   data["studieprogramkode"],
                   data["terminkode"],
                   data["arstall"])
        elif kind in ("sted",):
            key = ("sted", make_sko(data))
            logger.debug("role[%d]: recursive role (%s): %r -> %r",
                         stats['elem'],
                         data["rollekode"] in recursive_roles and
                         "used" or "ignored",
                         key, data["rollekode"])
            if data["rollekode"] not in recursive_roles:
                return
        elif kind in ("stprog",):
            key = ("stprog", data["studieprogramkode"])
            logger.debug("role[%d]: recursive role (%s): %r -> %r",
                         stats['elem'],
                         data["rollekode"] in recursive_roles and
                         "used" or "ignored",
                         key, data["rollekode"])
            if data["rollekode"] not in recursive_roles:
                return
        else:
            logger.warn("role[%d]: wrong role entry, kind=%r, fodselsdato=%r",
                        stats['elem'], kind, data["fodselsdato"])
            return

        key = fields2key(*key)
        if data["rollekode"] in valid_roles:
            logger.debug("role[%d]: role=%r, unit=%r, fodselsdato=%r given",
                         stats['elem'], data["rollekode"], key,
                         data["fodselsdato"])
            detailed_roles.setdefault(key, dict()).setdefault(
                data["rollekode"], list()).append({
                    "fodselsdato": int(data["fodselsdato"]),
                    "personnr": int(data["personnr"]),
                })
        else:
            logger.debug("role[%d]: role=%r, unit=%r, fodselsdato=%r is not "
                         "recognized and will be ignored",
                         stats['elem'], data["rollekode"], key,
                         data["fodselsdato"])

    logger.info("Parsing role file %s", fname)
    roles_xml_parser(fname, element_to_role)
    logger.info("Parsing roles complete")

    return detailed_roles


DEFAULT_COMMIT = True


def readable_file_type(filename):
    if not os.path.isfile(filename):
        raise ValueError("No file %r" % (filename, ))
    if not os.access(filename, os.R_OK):
        raise ValueError("Unable to read %r" % (filename, ))
    return filename


def main(inargs=None):
    global fs, db, co, emne_versjon, emne_termnr, account_id2fnr
    global fnr2account_id, fnr2stud_account_id, AffiliatedGroups
    global known_FS_groups, fs_supergroup, auto_supergroup
    global group_creator, UndervEnhet
    global ifi_netgr_g, ifi_netgr_lkurs, dryrun

    # TODO: This shouldn't be need anymore?
    # Upper/lowercasing of Norwegian letters.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))
    parser = argparse.ArgumentParser()

    db_commit = parser.add_argument_group('Database')
    commit_mutex = db_commit.add_mutually_exclusive_group()
    commit_mutex.add_argument(
        '--dryrun',
        dest='commit',
        action='store_false',
        help='Run in dryrun mode' + ('' if DEFAULT_COMMIT else ' (default)'))
    commit_mutex.add_argument(
        '--commit',
        dest='commit',
        action='store_true',
        help='Commit changes to the database' + ('' if not DEFAULT_COMMIT
                                                 else ' (default)'))
    commit_mutex.set_defaults(commit=DEFAULT_COMMIT)

    Cerebrum.logutils.options.install_subparser(parser)

    # TODO: Require all these? I *think* they are required...
    fs_files = parser.add_argument_group('Files',
                                         'XML data files from import_FS')
    fs_files.add_argument(
        '--role-file',
        type=readable_file_type,
        help='Roller',
        metavar='FILE')
    fs_files.add_argument(
        '--undenh-file',
        type=readable_file_type,
        help='Undervisningsenheter',
        metavar='FILE')
    fs_files.add_argument(
        '--undakt-file',
        type=readable_file_type,
        help='Undervisningsaktiviteter',
        metavar='FILE')
    fs_files.add_argument(
        '--evu-file',
        type=readable_file_type,
        help='EVU-kurs',
        metavar='FILE')
    fs_files.add_argument(
        '--kursakt-file',
        type=readable_file_type,
        help='EVU-kursaktiviteter',
        metavar='FILE')
    fs_files.add_argument(
        '--kull-file',
        type=readable_file_type,
        help='Kull',
        metavar='FILE')
    fs_files.add_argument(
        '--edu-file',
        type=readable_file_type,
        help='edu_info?',
        metavar='FILE')

    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start of script %s', parser.prog)
    logger.debug("args: %r", args)

    #
    # Initialize globals
    #
    fs = make_fs()
    db = Factory.get('Database')()
    db.cl_init(change_program='CF_gen_groups')
    co = Factory.get('Constants')(db)

    dryrun = not args.commit

    emne_versjon = {}
    emne_termnr = {}
    account_id2fnr = {}
    # Both fnr2account_id and fnr2stud_account_id are keyed by fnr and
    # have an array of every account ID's of that person sorted by
    # priority as their value, but in fnr2stud_account_id the accounts
    # with affiliation STUDENT will appear before other affiliations.
    fnr2stud_account_id = {}
    fnr2account_id = {}
    AffiliatedGroups = {}
    known_FS_groups = {}
    UndervEnhet = {}
    # these keep state across calls to populate_enhet_groups()
    ifi_netgr_g = {}
    ifi_netgr_lkurs = {}

    # Contains the tree of FS-groups.
    fs_supergroup = "{supergroup}"
    # Contains groups that refer to the groups above. Flat structure.
    auto_supergroup = "{autogroup}"
    group_creator = get_account(cereconf.INITIAL_ACCOUNTNAME).entity_id

    process_kursdata(
        args.role_file,
        args.undenh_file,
        args.undakt_file,
        args.evu_file,
        args.kursakt_file,
        args.kull_file,
        args.edu_file)

    if args.commit:
        logger.info("Committing all changes...")
        db.commit()
    else:
        logger.info("Dry run. Rolling back all changes...")
        db.rollback()

    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
