#!/usr/bin/env python2.2
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

"""Populer Cerebrum med FS-avledede grupper.

Disse gruppene blir så brukt ved eksport av data til ClassFronter.

 Navngiving:
   Gruppene er organisert i en tre-struktur.  Øverst finnes en
   supergruppe; denne brukes for å holde orden på hvilke grupper som
   er automatisk opprettet av dette scriptet, og dermed hvilke grupper
   som skal slettes i det dataene de bygger på ikke lenger finnes i
   FS.  Supergruppen har navnet

     internal:uio.no:fs:{supergroup}

   Denne supergruppen har så medlemmer som også er grupper.
   Medlemsgruppene har navn på følgende format:

     internal:uio.no:kurs:<emnekode>
     internal:uio.no:evu:<kurskode>

   Hver av disse "kurs-supergruppene" har medlemmer som er grupper med
   navn på følgende format:

     internal:uio.no:fs:kurs:<institusjonsnr>:<emnekode>:<versjon>:<sem>:<år>
     internal:uio.no:fs:evu:<kurskode>:<tidsangivelse>

   Det er disse "undervisningsenhet"-gruppene som brukes til å markere
   eksport til ClassFronter (ved at de tildeles passende spread).

   Merk at en undervisningsenhetsgruppe ikke er *helt* ekvivalent med
   begrepet undervisningsenhet slik det brukes i FS.  Gruppen
   representerer semesteret et gitt kurs startet i (terminnr == 1).
   For kurs som strekker seg over mer enn ett semester vil det derfor
   i FS finnes multiple undervisningsenheter, mens gruppen som
   representerer kurset vil beholde navnet sitt i hele kurstiden.

   Undervisningsenhetgruppene har igjen grupper som medlemmer; disse
   kan deles i to kategorier:

     Grupper (med primærbrukermedlemmer) som brukes ved eksport til
     ClassFronter, har navn på følgende format:
   
       Ansvar und.enh:       uio.no:fs:<enhetid>:enhetsansvar
       Ansvar und.akt:       uio.no:fs:<enhetid>:aktivitetsansvar:<aktkode>
       Alle stud. v/enh:     uio.no:fs:<enhetid>:student
       Alle stud. v/akt:     uio.no:fs:<enhetid>:student:<aktkode>

     Ytterligere grupper hvis medlemmer kun er ikke-primære
     ("sekundære") konti.  Genereres kun for informatikk-emner, og har
     navn på formen:

       Ansvar und.enh:       uio.no:fs:<enhetid>:enhetsansvar-sek
       Ansvar und.akt:       uio.no:fs:<enhetid>:aktivitetsansvar-sek:<aktkode>
       Alle stud. v/enh:     uio.no:fs:<enhetid>:student-sek

 I tillegg blir disse nettgruppene laget med spread til Ifi:
 
    Ansvar und.enh:        g<enhetid>-0          (alle konti)
    Ansvar und.akt:        g<enhetid>-<aktkode>  (alle konti)
    Ansvar enh. og akt.:   g<enhetid>            (alle konti)
    Alle stud. v/enh:      s<enhetid>            (alle konti)
    Alle stud. v/akt:      s<enhetid>-<aktkode>  (primærkonti)
    Alle stud. kun eks:    s<enhetid>-e          (primærkonti)
    Alle akt-ansv:         ifi-g                 (alle konti)
    Alle akt- og enh-ansv: lkurs                 (alle konti)

"""

import sys
import getopt
import re
import locale

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.modules.no.uio.fronter_lib import FronterUtils

def prefetch_primaryusers():
    # TBD: This code is used to get account_id for both students and
    # fagansv.  Should we look at affiliation here?
    account = Factory.get('Account')(db)
    personid2accountid = {}
    for a in account.list_accounts_by_type():
        p_id = int(a['person_id'])
        a_id = int(a['account_id'])
        personid2accountid.setdefault(p_id, []).append(a_id)

    person = Factory.get('Person')(db)
    fnr_source = {}
    for row in person.list_external_ids(id_type=co.externalid_fodselsnr):
        p_id = int(row['person_id'])
        fnr = row['external_id']
        src_sys = int(row['source_system'])
        if fnr_source.has_key(fnr) and fnr_source[fnr][0] <> p_id:
            # Multiple person_info rows have the same fnr (presumably
            # the different fnrs come from different source systems).
            logger.error("Multiple persons share fnr %s: (%d, %d)" % (
                fnr, fnr_source[fnr][0], p_id))
            # Determine which person's fnr registration to use.
            source_weight = {int(co.system_fs): 4,
                             int(co.system_manual): 3,
                             int(co.system_lt): 2,
                             int(co.system_ureg): 1}
            old_weight = source_weight.get(fnr_source[fnr][1], 0)
            if source_weight.get(src_sys, 0) <= old_weight:
                continue
            # The row we're currently processing should be preferred;
            # if the old row has an entry in fnr2account_id, delete
            # it.
            if fnr2account_id.has_key(fnr):
                del fnr2account_id[fnr]
        fnr_source[fnr] = (p_id, src_sys)
        if personid2accountid.has_key(p_id):
            account_ids = personid2accountid[p_id]
            for acc in account_ids:
                account_id2fnr[acc] = fnr
            fnr2account_id[fnr] = account_ids
    del fnr_source

def fnrs2account_ids(rows, primary_only=True):
    """Return list of primary accounts for the persons identified by
    row(s).  Optionally return a tuple of (primaries, secondaries)
    instead.  The secondary accounts are _not_ sorted according to
    priority."""
    ret = []
    sec = []
    for r in rows:
        fnr = "%06d%05d" % (
            int(r['fodselsdato']), int(r['personnr']))
        if fnr2account_id.has_key(fnr):
            prim_acc = fnr2account_id[fnr][0]
            ret.append(prim_acc)
            if not primary_only:
                # Each account can be associated with more than one
                # affiliation, and so occur more than once in the list.
                # This is also true for the primary account name, but
                # when we remove it from the dict after populating it
                # with every account, we remove all occurences of it.
                account = {}
                for a in fnr2account_id[fnr]:
                    account[a] = None
                del account[prim_acc]
                sec += account.keys()
    if primary_only:
        return ret
    else:
        return (ret, sec)

def process_kursdata():
    logger.debug("Getting all primaryusers")
    prefetch_primaryusers()
    logger.debug(" ... done")
    get_undervisningsenheter()    # Utvider UndervEnhet med mer data
    get_undervisningsaktiviteter()
    get_evukurs_aktiviteter()
    # logger.debug(UndervEnhet)

    for k in UndervEnhet.keys():
        # Legger inn brukere i gruppene på nivå 3.
        #
        # $enhet er her enten en undervisningsenhet (starter med "kurs:")
        # eller en EVU-enhet (starter med "evu:"); vi overlater til
        # populate_enhet_groups å behandle forskjellige type enheter på
        # passende vis.
        populate_enhet_groups(k)

    # Nettgrupper for Ifi med data på tvers av enheter
    populate_ifi_groups()

    # Oppdaterer gruppene på nivå 2.
    #
    # Må skille mellom EVU-kurs og vanlige kurs da identifikatorene deres
    # har forskjellig antall felter i $kurs_id.
    #
    logger.info("Oppdaterer enhets-supergrupper:")
    for kurs_id in AffiliatedGroups.keys():
        if kurs_id == auto_supergroup:
            continue
        rest = kurs_id.split(":")
        type = rest.pop(0).lower()
        if type == 'kurs':
            instnr, emnekode, versjon, termk, aar = rest
            sync_group("%s:%s" % (type, emnekode), kurs_id,
                       "Ikke-eksporterbar gruppe.  Brukes for å definere hvor"+
                       " data om kurset <%s> skal eksporteres." % kurs_id,
                       co.entity_group,
                       AffiliatedGroups[kurs_id])
        elif type == 'evu':
            kurskode, tidsrom = rest
            sync_group("%s:%s" % (type, kurskode), kurs_id,
                       "Ikke-eksporterbar gruppe.  Brukes for å definere hvor"+
                       " data om emnet <%s> skal eksporteres. " % kurs_id,
                       co.entity_group,
                       AffiliatedGroups[kurs_id])
        else:
            logger.warn("Ukjent kurstype <%s> for kurs <%s>" % (type, k))

        # Kallene på sync_group legger inn nye entries i
        # %AffiliatedGroups; ting blir mye greiere å holde rede på om vi
        # fjerner "våre" nøkler derfra så snart vi er ferdige.
        del AffiliatedGroups[kurs_id]
    logger.info(" ... done")

    # Oppdaterer gruppene på nivå 1.
    #
    # Alle grupper knyttet til en undervisningsenhet skal meldes inn i den
    # u2k-interne emnekode-gruppen.  Man benytter så emnekode-gruppen til
    # å definere eksport-egenskaper for alle grupper tilknyttet en
    # undervisningsenhet.
    logger.info("Oppdaterer emne-supergrupper:")
    for gname in AffiliatedGroups.keys():
        sync_group(fs_supergroup, gname,
                   "Ikke-eksporterbar gruppe.  Brukes for å samle kursene"+
                   " knyttet til %s." % gname,
                   co.entity_group, AffiliatedGroups[gname]);
    logger.info(" ... done")


    #
    # Alle emnekode-supergrupper skal meldes inn i en supergruppe
    # spesifikk for denne importmekanismen.
    #
    # På denne måten holdes det oversikt over hvilke grupper som er
    # automatisk opprettet på bakgrunn av import fra FS.  Uten en slik
    # oversikt vil man ikke kunne foreta automatisk sletting av grupper
    # tilhørende "utgåtte" undervisningsenheter og -aktiviteter.

    logger.info("Oppdaterer supergruppe for alle ekstra grupper")
    sync_group(None, auto_supergroup,
               "Ikke-eksporterbar gruppe.  Definerer hvilke andre "+
               "automatisk opprettede grupper som refererer til "+
               "grupper speilet fra FS.",
               co.entity_group,
               AffiliatedGroups[auto_supergroup])
    logger.info(" ... done")

    logger.info("Oppdaterer supergruppe for alle emnekode-supergrupper")
    sync_group(None, fs_supergroup,
               "Ikke-eksporterbar gruppe.  Definerer hvilke andre grupper "+
               "som er opprettet automatisk som følge av FS-import.",
               co.entity_group,
               AffiliatedGroups[fs_supergroup])
    logger.info(" ... done")



## send_mail("\n$warn_msg",
##        sender => 'ureg2000-core@usit.uio.no',
##        recips => [ split(m/\s+/, $warn_addr) ],
##        subject => 'Bygging av ureg2000-grupper fra FS-data',
##        dryrun => $dryrun,
##        dryrun_output => '>&STDOUT')
##   if $warn_msg;

## $u2k.commit() unless $dryrun;

def get_undervisningsenheter():
    # TODO: Dumpe alle unervisningsenheter til fil
    for enhet in fs.GetUndervEnhetAll()[1]:
        # Prefikser alle nøkler i %UndervEnhet som stammer fra
        # undervisningsenheter med "kurs:".
        enhet_id = "kurs:%s:%s:%s:%s:%s:%s" % (
            enhet['institusjonsnr'], enhet['emnekode'],
            enhet['versjonskode'], enhet['terminkode'],
            enhet['arstall'], enhet['terminnr'])
        if UndervEnhet.has_key(enhet_id):
            raise ValueError, "Duplikat undervisningsenhet: <%s>" % enhet_id
        UndervEnhet[enhet_id] = {'aktivitet': {}}
        multi_id = "%s.%s.%s.%s" % (enhet['institusjonsnr'], enhet['emnekode'],
                                    enhet['terminkode'], enhet['arstall'])
        # Finnes det flere enn en undervisningsenhet tilknyttet denne
        # emnekoden i inneværende semester?
        emne_versjon.setdefault(multi_id, {})[enhet['versjonskode']] = 1
        emne_termnr.setdefault(multi_id, {})[enhet['terminnr']] = 1

def get_undervisningsaktiviteter():
    for akt in fs.list_undervisningsaktiviteter():
        enhet_id = "kurs:%s:%s:%s:%s:%s:%s" % (
            akt['institusjonsnr'], akt['emnekode'],
            akt['versjonskode'], akt['terminkode'],
            akt['arstall'], akt['terminnr'])
        if not UndervEnhet.has_key(enhet_id):
            raise ValueError, "Ikke-eksisterende enhet <%s> har aktiviteter" %\
                  enhet_id
        if UndervEnhet[enhet_id]['aktivitet'].has_key(akt['aktivitetkode']):
            raise ValueError, "Duplikat undervisningsaktivitet <%s:%s>" % (
                enhet_id, akt['aktivitetkode'])
        UndervEnhet[enhet_id][
            'aktivitet'][akt['aktivitetkode']] = akt['aktivitetsnavn']

def get_evukurs_aktiviteter():
    for kurs in fs.GetEvuKurs()[1]:
        kurs_id = "evu:%s:%s" % (kurs['etterutdkurskode'],
                                 kurs['kurstidsangivelsekode'])
        UndervEnhet[kurs_id] = {}
        for aktivitet in fs.GetAktivitetEvuKurs(
            kurs['etterutdkurskode'], kurs['kurstidsangivelsekode'])[1]:
            UndervEnhet[kurs_id].setdefault('aktivitet', {})[
                aktivitet['aktivitetskode']] = aktivitet['aktivitetsnavn']
        tmp = {}
        for evuansv in fs.GetAnsvEvuKurs(kurs['etterutdkurskode'],
                                         kurs['kurstidsangivelsekode'])[1]:
            fnr = "%06d%05d" % (
                int(evuansv['fodselsdato']), int(evuansv['personnr']))
            if fnr2account_id.has_key(fnr):
                tmp[fnr2account_id[fnr][0]] = 1
        UndervEnhet[kurs_id]['fagansv'] = tmp.copy()
        tmp = {}
        for student in fs.GetStudEvuKurs(kurs['etterutdkurskode'],
                                         kurs['kurstidsangivelsekode'])[1]:
            fnr = "%06d%05d" % (
                int(student['fodselsdato']), int(student['personnr']))
            if fnr2account_id.has_key(fnr):
                tmp[fnr2account_id[fnr][0]] = 1
        UndervEnhet[kurs_id]['students'] = tmp.copy()

def get_evu_ansv(kurskode, tidsrom):
    kurs_id = "evu:%s:%s" % (kurskode, tidsrom)
    return UndervEnhet[kurs_id]['fagansv']

def get_evu_students(kurskode, tidsrom):
    kurs_id = "evu:%s:%s" % (kurskode, tidsrom)
    return UndervEnhet[kurs_id]['students']

def populate_enhet_groups(enhet_id):
    type_id = enhet_id.split(":")
    type = type_id.pop(0).lower()

    if type == 'kurs':
        Instnr, emnekode, versjon, termk, aar, termnr = type_id

        # Finnes det mer enn en undervisningsenhet knyttet til dette
        # emnet, kun forskjellig på versjonskode og/eller terminnr?  I
        # så fall bør gruppene få beskrivelser som gjør det mulig å
        # knytte dem til riktig undervisningsenhet.
        multi_enhet = []
        multi_id = "%s:%s:%s:%s" % (Instnr, emnekode, termk, aar)
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

        #
        # Ansvarlige for undervisningsenheten.
        logger.debug(" enhetsansvar")
        enhet_ansv = {}
        prim, sec = fnrs2account_ids(fs.GetAnsvUndervEnhet(Instnr, emnekode,
                                                           versjon, termk,
                                                           aar, termnr)[1],
                                     primary_only = False)
        for account_id in prim:
            enhet_ansv[account_id] = 1

        # TODO: generaliser ifi-hack seinare
        if (re.match(r"(dig|inf|med-inf|tool)", emnekode.lower())
            and termk == fs.get_curr_semester()
            and aar == str(fs.year)):
            logger.debug(" (ta med Ifi-spesifikke grupper)")
            ifi_hack = True
            netgr_emne = emnekode.lower().replace("-", "")
            alle_ansv = {}	# for gKURS: alle grl og kursledelse
            empty = {}
            if re.search(r'[0123]\d\d\d', emnekode):
                ifi_netgr_lkurs["g%s" % netgr_emne] = 1
        else:
            ifi_hack = False

        # Finnes kurs som går over mer enn et semester, samtidig som
        # at kurset/emnet starter hvert semester.  Utvider strukturen
        # til å ta høyde for at det til enhver tid kan finnes flere
        # kurs av samme type til enhver tid.
        kurs_id = FronterUtils.UE2KursID('kurs', Instnr, emnekode,
                                         versjon, termk, aar, termnr)

        # Også supergruppene til undervisningsenhet - og
        # -aktivitets-avledede grupper skal ha "kurs:"-prefiks.
        sync_group(kurs_id, "%s:enhetsansvar" % enhet_id,
                   "Ansvarlige %s %s %s%s" % (emnekode, termk,
                                              aar, enhet_suffix),
                   co.entity_account, enhet_ansv);
        
        # Ifi vil ha at alle konti til en gruppelærer skal listes opp
        # på lik linje.  Alle ikke-primære konti blir derfor lagt inn i
        # en egen interngruppe, og de to interngruppene blir medlemmer
        # i Ifis nettgruppe.
        if ifi_hack:
            enhet_ansv = {}
            for account_id in sec:
                enhet_ansv[account_id] = 1
            sync_group(kurs_id, "%s:enhetsansvar-sek" % enhet_id,
                       ("Ansvarlige %s %s %s%s (sekundærkonti)" %
                        (emnekode, termk, aar, enhet_suffix)),
                       co.entity_account, enhet_ansv);
            gname = mkgname("%s:enhetsansvar" % enhet_id,
                            prefix = 'uio.no:fs:')
            gmem = { gname: 1,
                     "%s-sek" % gname: 1 }
            netgr_navn = "g%s-0" % netgr_emne
            sync_group(auto_supergroup, netgr_navn,
                       "Ansvarlige %s %s %s%s" % (emnekode, termk, aar,
                                                  enhet_suffix),
                       co.entity_group, gmem, visible=True);
            add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
            alle_ansv[netgr_navn] = 1
        #
        # Alle nåværende undervisningsmeldte samt nåværende+fremtidige
        # eksamensmeldte studenter.
        logger.debug(" student")
        alle_stud = {}
        prim, sec = fnrs2account_ids(fs.GetStudUndervEnhet(Instnr, emnekode,
                                                           versjon, termk,
                                                           aar, termnr)[1],
                                     primary_only=False)
        for account_id in prim:
            alle_stud[account_id] = 1

        sync_group(kurs_id, "%s:student" % enhet_id,
                   "Studenter %s %s %s%s" % (emnekode, termk,
                                             aar, enhet_suffix),
                   co.entity_account, alle_stud);
        if ifi_hack:
            alle_stud_sek = {}
            alle_aktkoder = {}
            for account_id in sec:
                alle_stud_sek[int(account_id)] = 1
            gname = mkgname("%s:student-sek" % enhet_id, prefix = 'uio.no:fs:')
            sync_group(kurs_id, gname,
                       ("Studenter %s %s %s%s (sekundærkonti)" %
                        (emnekode, termk, aar, enhet_suffix)),
                       co.entity_account, alle_stud_sek);
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

        for aktkode in UndervEnhet[enhet_id].get('aktivitet', {}).keys():
            #
            # Ansvarlige for denne undervisningsaktiviteten.
            logger.debug(" aktivitetsansvar:%s" % aktkode)
            akt_ansv = {}
            prim, sec = fnrs2account_ids(
                fs.GetAnsvUndAktivitet(Instnr, emnekode, versjon, termk,
                                       aar, termnr, aktkode)[1],
                primary_only=False)
            
            for account_id in prim:
                akt_ansv[account_id] = 1

            gname = mkgname("%s:aktivitetsansvar" % enhet_id,
                            prefix = 'uio.no:fs:')
            sync_group(kurs_id, "%s:%s" % (gname, aktkode),
                       "Ansvarlige %s %s %s%s %s" % (
                emnekode, termk, aar, enhet_suffix,
                UndervEnhet[enhet_id]['aktivitet'][aktkode]),
                       co.entity_account, akt_ansv);

            if ifi_hack:
                akt_ansv = {}
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

                aktnavn = UndervEnhet[enhet_id]['aktivitet'][aktkode].lower()
                m = re.match(r'\S+ (\d+)$', aktnavn)
                if m:
                    aktnavn = m.group(1)
                else:
                    aktnavn = aktnavn.replace(" ", "-")
                logger.debug("Aktivitetsnavn '%s' -> '%s'" %
                             (UndervEnhet[enhet_id]['aktivitet'][aktkode],
                              aktnavn))
                sync_group(kurs_id, "%s-sek:%s" % (gname, aktkode),
                           ("Ansvarlige %s %s %s%s %s (sekundærkonti)" %
                            (emnekode, termk, aar, enhet_suffix, aktnavn)),
                           co.entity_account, akt_ansv)
                gmem = { "%s:%s" % (gname, aktkode) : 1,
                         "%s-sek:%s" % (gname, aktkode): 1 }
                netgr_navn = "g%s-%s" % (netgr_emne, aktnavn)
                sync_group(auto_supergroup, netgr_navn,
                           "Ansvarlige %s-%s %s %s%s" % (emnekode, aktnavn,
                                                         termk, aar,
                                                         enhet_suffix),
                           co.entity_group, gmem, visible=True)
                # midlertidig
                sync_group(auto_supergroup, netgr_navn,
                           "Ansvarlige %s-%s %s %s%s" % (emnekode, aktnavn,
                                                         termk, aar,
                                                         enhet_suffix),
                           co.entity_account, empty, visible=True)
                add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
                alle_ansv[netgr_navn] = 1
                ifi_netgr_g[netgr_navn] = 1

            # Studenter meldt på denne undervisningsaktiviteten.
            logger.debug(" student:%s" % aktkode)
            akt_stud = {}
            for account_id in fnrs2account_ids(
                fs.GetStudUndAktivitet(Instnr, emnekode, versjon, termk,
                                       aar, termnr, aktkode)[1]):
                if not alle_stud.has_key(account_id):
                    logger.warn("OBS: Bruker <%s> (fnr <%s>) er med i"
                                " undaktivitet <%s>, men ikke i"
                                " undervisningsenhet <%s>.\n" % (
                        account_id, account_id2fnr[account_id],
                        "%s:%s" % (enhet_id, aktkode), enhet_id))
                akt_stud[account_id] = 1

            student_med_akt.update(akt_stud)

            sync_group(kurs_id, "%s:student:%s" % (enhet_id, aktkode),
                       "Studenter %s %s %s%s %s" % (
                emnekode, termk, aar, enhet_suffix,
                UndervEnhet[enhet_id]['aktivitet'][aktkode]),
                       co.entity_account, akt_stud)
            if ifi_hack:
                gname = mkgname("%s:student:%s" % (enhet_id, aktkode),
                                prefix = 'uio.no:fs:')
                gmem = { gname: 1 }
                netgr_navn = "s%s-%s" % (netgr_emne, aktnavn)
                sync_group(auto_supergroup, netgr_navn,
                           "Studenter %s-%s %s %s%s" % (emnekode, aktnavn,
                                                        termk, aar,
                                                        enhet_suffix),
                           co.entity_group, gmem, visible=True);
                # midlertidig
                sync_group(auto_supergroup, netgr_navn,
                           "Studenter %s-%s %s %s%s" % (emnekode, aktnavn,
                                                        termk, aar,
                                                        enhet_suffix),
                           co.entity_account, empty, visible=True);
                add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
                alle_aktkoder[netgr_navn] = 1

        # ferdig med alle aktiviteter, bare noen få hack igjen ...
        for account_id in student_med_akt.iterkeys():
            if alle_stud.has_key(account_id):
                # Ved å fjerne alle som er meldt til minst en
                # aktivitet, ender vi opp med en liste over de som
                # kun er meldt til eksamene.
                del alle_stud[account_id]
        if ifi_hack:
            gname = mkgname("%s:student:%s" % (enhet_id, "kuneksamen"),
                            prefix = 'uio.no:fs:')
            sync_group(kurs_id, gname,
                       ("Studenter %s %s %s%s %s" %
                        (emnekode, termk, aar, enhet_suffix, "kun eksamen")),
                       co.entity_account, alle_stud)
            gmem = { gname: 1 }
            netgr_navn = "s%s-e" % netgr_emne
            sync_group(auto_supergroup, netgr_navn,
                       "Studenter %s-e %s %s%s" % (emnekode, termk, aar,
                                                   enhet_suffix),
                       co.entity_group, gmem, visible=True);
            # midlertidig
            sync_group(auto_supergroup, netgr_navn,
                       "Studenter %s-e %s %s%s" % (emnekode, termk, aar,
                                                   enhet_suffix),
                       co.entity_account, empty, visible=True);
            add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
            alle_aktkoder[netgr_navn] = 1
            # alle studenter på kurset
            netgr_navn = "s%s" % netgr_emne
            sync_group(auto_supergroup, netgr_navn,
                       "Studenter %s %s %s%s" % (emnekode, termk, aar,
                                                 enhet_suffix),
                       co.entity_group, alle_aktkoder, visible=True);
            # midlertidig
            sync_group(auto_supergroup, netgr_navn,
                       "Studenter %s %s %s%s" % (emnekode, termk, aar,
                                                 enhet_suffix),
                       co.entity_account, empty, visible=True);
            add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)
            # alle gruppelærere og kursledelsen
            netgr_navn = "g%s" % netgr_emne
            sync_group(auto_supergroup, netgr_navn,
                       "Ansvarlige %s %s %s%s" % (emnekode, termk, aar,
                                                  enhet_suffix),
                       co.entity_group, alle_ansv, visible=True);
            # midlertidig
            sync_group(auto_supergroup, netgr_navn,
                       "Ansvarlige %s %s %s%s" % (emnekode, termk, aar,
                                                  enhet_suffix),
                       co.entity_account, empty, visible=True);
            add_spread_to_group(netgr_navn, co.spread_ifi_nis_ng)

    elif type == 'evu':
        kurskode, tidsrom = type_id
        kurs_id = FronterUtils.UE2KursID("evu", kurskode, tidsrom)
        logger.debug("Oppdaterer grupper for %s: " % enhet_id)
        #
        # Ansvarlige for EVU-kurset
        logger.debug(" evuAnsvar")
        evuans = get_evu_ansv(kurskode, tidsrom)
        sync_group(kurs_id, "%s:enhetsansvar" % enhet_id,
                   "Ansvarlige EVU-kurs %s, %s" % (kurskode, tidsrom),
                   co.entity_account, evuans)
        #
        # Alle påmeldte studenter
        logger.debug(" evuStudenter")
        evustud = get_evu_students(kurskode, tidsrom)
        sync_group(kurs_id, "%s:student" % enhet_id,
                   "Studenter EVU-kurs %s, %s" % (kurskode, tidsrom),
                   co.entity_account, evustud)

        for aktkode in UndervEnhet[enhet_id].get('aktivitet', {}).keys():
            #
            # Ansvarlige for kursaktivitet
            logger.debug(" aktivitetsansvar:%s" % aktkode)
            evu_akt_ansv = {}
            for account_id in fnrs2account_ids(
                fs.GetAnsvEvuAktivitet(kurskode, tidsrom, aktkode)[1]):
                evu_akt_ansv[account_id] = 1

            sync_group(kurs_id, "%s:aktivitetsansvar:%s" % (enhet_id, aktkode),
                       "Ansvarlige EVU-kurs %s, %s: %s" % (
                kurskode, tidsrom,
                UndervEnhet[enhet_id]['aktivitet'][aktkode]),
                       co.entity_account, evu_akt_ansv)

            # Studenter til denne kursaktiviteten
            logger.debug(" student:%s" % aktkode)
            evu_akt_stud = {}
            for account_id in fnrs2account_ids(
                fs.GetStudEvuAktivitet(kurskode, tidsrom, aktkode)[1]):
                if not evustud.has_key(account_id):
                    logger.warn("""OBS: Bruker <%s> (fnr <%s>) er med i aktivitet <%s>, men ikke i kurset <%s>.""" % (
                        account_id, account_id2fnr[account_id],
                        "%s:%s" % (enhet_id, aktkode), enhet_id))
                evu_akt_stud[account_id] = 1
            sync_group(kurs_id, "%s:student:%s" % (enhet_id, aktkode),
                       "Studenter EVU-kurs %s, %s: %s" % (
                kurskode, tidsrom,
                UndervEnhet[enhet_id]['aktivitet'][aktkode]),
                       co.entity_account, evu_akt_stud)
    logger.debug(" done")

def populate_ifi_groups():
    sync_group(auto_supergroup, "ifi-g", "Alle gruppelærere for Ifi-kurs",
               co.entity_group, ifi_netgr_g, visible=True)
    add_spread_to_group("ifi-g", co.spread_ifi_nis_ng)
    sync_group(auto_supergroup, "lkurs", "Alle laveregradskurs ved Ifi",
               co.entity_group, ifi_netgr_lkurs, visible=True)
    add_spread_to_group("lkurs", co.spread_ifi_nis_ng)

def sync_group(affil, gname, descr, mtype, memb, visible=False):
    logger.debug("sync_group(%s; %s; %s; %s; %s" % (affil, gname, descr, mtype, memb))
    if mtype == co.entity_group:   # memb has group_name as keys
        members = {}
        for tmp_gname in memb.keys():
            grp = get_group(tmp_gname)
            members[int(grp.entity_id)] = 1
    else:                          # memb has account_id as keys
        members = memb.copy()
    if visible:
        # visibility implies that the group name should be used as is.
        correct_visib = co.group_visibility_all
        if not affil == auto_supergroup:
            raise ValueError, ("All visible groups must be members of the "
                               "supergroup for automatic groups")
    else:
        gname = mkgname(gname, 'uio.no:fs:')
        correct_visib = co.group_visibility_none
        if (affil is None or               # Nivå 0; $gname er supergruppen
            affil == fs_supergroup or         # $gname er på nivå 1
            re.search(r'^(evu|kurs):[^:]+$', affil, re.I)): # $gname er på nivå 2
            # Grupper så langt oppe i strukturen skal være rent interne;
            # de brukes kun til kontroll av hierarki og eksport.
            gname = mkgname(gname)
            correct_visib = co.group_visibility_internal
    if affil is not None:
        AffiliatedGroups.setdefault(affil, {})[gname] = 1
    known_FS_groups[gname] = 1

    # Gjør objektet $Group klar til å modifisere gruppen med navn
    # $gname.
    try:
        group = get_group(gname)
    except Errors.NotFoundError:
        group = Factory.get('Group')(db)
        group.clear()
        group.populate(group_creator, correct_visib, gname, description=descr)
        group.write_db()
    else:
        # Dersom gruppen $gname fantes, er $gr nå en peker til samme
        # objekt som $Group; i motsatt fall er $gr false.
        if group.visibility != correct_visib:
            logger.fatal("Group <%s> has wrong visibility." % gname)

        if group.description != descr:
            group.description = descr
            group.write_db()

        u, i, d = group.list_members(member_type=mtype)
        for member in u:
            member = int(member[1]) # member_id has index=1 (poor API design?)
            if members.has_key(member):
                del members[member]
            else:
                logger.debug("sync_group(): Deleting member %d" % member)
                group.remove_member(member, co.group_memberop_union)
                #
                # Supergroups will only contain groups that have been
                # automatically created by this script, hence it is
                # safe to automatically destroy groups that are no
                # longer member of their supergroup.
                if (mtype == co.entity_group and
                    correct_visib == co.group_visibility_internal and
                    (not known_FS_groups.has_key(member))):
                    destroy_group(member, 2)

    for member in members.keys():
        group.add_member(member, mtype, co.group_memberop_union)

def destroy_group(gname, max_recurse):
    gr = get_group(gname)
    if True:
        # 2004-07-01: Deletion of groups has been disabled until we've
        # managed to come up with a deletion process that can be
        # committed at multiple checkpoints, rather than having to
        # wait with commit until we're completely done.
        logger.debug("destroy_group(%s/%d, %d) [DISABLED]"
                     % (gr.group_name, gr.entity_id, max_recurse))
        return
    logger.debug("destroy_group(%s/%d, %d) [After get_group]"
                 % (gr.group_name, gr.entity_id, max_recurse))
    if max_recurse < 0:
        logger.fatal("destroy_group(%s): Recursion too deep" % gr.group_name)
        sys.exit(3)
        
    # If this group is a member of other groups, remove those
    # memberships.
    for r in gr.list_groups_with_entity(gr.entity_id):
        parent = get_group(r['group_id'])
        logger.info("removing %s from group %s" % (gr.group_name,
                                                   parent.group_name))
        parent.remove_member(gr.entity_id, r['operation'])

    # If a e-mail target is of type multi and has this group as its
    # destination, delete the e-mail target and any associated
    # addresses.  There can only be one target per group.
    et = Email.EmailTarget(db)
    try:
        et.find_by_email_target_attrs(target_type = co.email_target_multi,
                                      entity_id = gr.entity_id)
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
    u, i, d = gr.list_members(member_type=co.entity_group)
    logger.debug("destroy_group() subgroups: %r" % (u,))
    # Remove any spreads the group has
    for row in gr.get_spread():
        gr.delete_spread(row['spread'])
    # Delete the parent group (which implicitly removes all membership
    # entries representing direct members of the parent group)
    gr.delete()
    # Destroy any subgroups (down to level max_recurse).  This needs
    # to be done after the parent group has been deleted, in order for
    # the subgroups not to be members of the parent anymore.
    for subg in u:
        destroy_group(subg[1], max_recurse - 1)


def add_spread_to_group(group, spread):
    gr = get_group(group)
    if not gr.has_spread(spread):
        gr.add_spread(spread)
        logger.debug("Adding spread %s to %s\n" % (spread, group))

def get_group(id):
    gr = Factory.get('Group')(db)
    if isinstance(id, str):
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

def usage(exitcode=0):
    print """Usage: [options]
    --db-user name: connect with given database username
    --db-service name: connect to given database"""
    sys.exit(exitcode)

def main():
    global fs, db, co, logger, emne_versjon, emne_termnr, \
           account_id2fnr, fnr2account_id, AffiliatedGroups, \
           known_FS_groups, fs_supergroup, auto_supergroup, \
           group_creator, UndervEnhet, \
           ifi_netgr_g, ifi_netgr_lkurs

    logger = Factory.get_logger("cronjob")
    
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    try:
        opts, args = getopt.getopt(sys.argv[1:], "",
                                   ["db-user=", "db-service="])
    except getopt.GetoptError:
        usage(2)
    db_user = None         # TBD: cereconf value?
    db_service = None      # TBD: cereconf value?
    for o, val in opts:
        if o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val
    fs = FS(user = db_user, database = db_service)

    db = Factory.get('Database')()
    db.cl_init(change_program='CF_gen_groups')
    co = Factory.get('Constants')(db)
    emne_versjon = {}
    emne_termnr = {}
    account_id2fnr = {}
    fnr2account_id = {}
    AffiliatedGroups = {}
    known_FS_groups = {}
    UndervEnhet = {}
    # these keep state across calls to populate_enhet_groups()
    ifi_netgr_g = {}
    ifi_netgr_lkurs = {}

    # Inneholder tre av FS-grupper.
    fs_supergroup = "{supergroup}"
    # Inneholder gruppene som refererer til FS-gruppene over.  Flat
    # struktur.
    auto_supergroup = "{autogroup}"
    group_creator = get_account(cereconf.INITIAL_ACCOUNTNAME).entity_id
    process_kursdata()
    logger.debug("commit...")
    db.commit()
    logger.info("All done")

if __name__ == '__main__':
    main()
