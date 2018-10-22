#!/usr/bin/env python
# -*- coding: utf-8 -*-

# kbj005 2015.02.10: copied from /home/cerebrum/cerebrum/contrib/no/uio

"""
Generere LDAP tre med uioEduSection (Undervisningsaktivitet - gruppe,
kollokvia...) eller uioEduOffering (Undervisningsenhet - emne) objekter.
Hver av disse vil ha en uioEduCourseOffering verdi som inneholder en
URN som unikt identifiserer dette studie-elementet.

ldap-person-dumpen vil generere eduCourseMember atributter med verdi
role@eduCourseOffering, der eduCourseOffering er URN-en over, og
role=Learner for studenter og Instructor for gruppe-l�rer/foreleser.

--aktivitetfile fname : xml fil med undervisningsaktiviteter
--enhetfile fname : xml fil med undervisningsenheter
--emnefile fname : xml fil med emner
--ldiffile fname.ldif : trigger generering av ldif fil med angitt navn
--picklefile fname : brukes av person-ldif exporten til � sette eduCourseMember
"""
from __future__ import unicode_literals
import getopt
import pickle
import os, sys
import cerebrum_path
import locale
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules.LDIFutils import *
from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
ac = Factory.get('Account')(db)
group = Factory.get('Group')(db)

locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))  # norsk "�".lower()

#
# IVR 2008-07-14 Vortex group wanted more detailed information about FS roles
# assigned to people. Specifically, they wanted to know about roles previously
# captured by 'enhetsansvarlig'. Nowadays, that concept is more fine-grained,
# and people get an extra entitlement per role per undenh/undakt in
# LDAP. Vortex can lookup these roles in LDAP.
interesting_fs_roles = (('student', 'Learner'),
                        ('admin', 'Administrator'),
                        ('dlo', 'DLO'),
                        ('fagansvar', 'Fagansvarlig'),
                        ('foreleser', 'Foreleser'),
                        ('gjestefore', 'Gjesteforeleser'),
                        ('gruppel�re', 'Gruppelaerer'),
                        ('hovedl�re', 'Hovedlaerer'),
                        ('it-ansvarl', 'IT-ansvarlig'),
                        ('l�rer', 'Laerer'),
                        ('sensor', 'Sensor'),
                        ('studiekons', 'Studiekonsulent'),)

class CerebrumGroupInfo(object):
    ## Fra generate_fronter_full.py:214
    ##             id_seq = (self.EMNE_PREFIX, enhet['institusjonsnr'],
    ##                       enhet['emnekode'], enhet['versjonskode'],
    ##                       enhet['terminkode'], enhet['arstall'],
    ##                       enhet['terminnr'])
    ##             enhet_id = ":".join([str(x) for x in id_seq]).lower()

    ## 1144:       enhstud = "uio.no:fs:%s:student" % enhet_id.lower()
    ## 982:        aktstud = "uio.no:fs:%s:student:%s" % (enhet_id.lower(), aktkode.lower())

    ##     752523 |           15 | uio.no:fs:kurs:185:inf-mat2351:1:v�r:2007:1:aktivitetsansvar:2-2
    ##     752521 |           15 | uio.no:fs:kurs:185:inf-mat2351:1:v�r:2007:1:enhetsansvar
    ##     752522 |           15 | uio.no:fs:kurs:185:inf-mat2351:1:v�r:2007:1:student
    ##     752526 |           15 | uio.no:fs:kurs:185:inf-mat2351:1:v�r:2007:1:student:2-1
    PREFIX = "uit.no:fs:kurs:"
    id_key_seq = ('institusjonsnr', 'emnekode', 'versjonskode',
                  'terminkode', 'arstall', 'terminnr')

    def __init__(self):
        self._emne_key2dta = {}

        for row in group.search(name="%s%%" % CerebrumGroupInfo.PREFIX):
            name = row['name'][len(CerebrumGroupInfo.PREFIX):]
            emne_key = name.split(":")[:len(CerebrumGroupInfo.id_key_seq)]
            emne_val = name.split(":")[len(CerebrumGroupInfo.id_key_seq):]
            self._emne_key2dta.setdefault(tuple(emne_key), []).append(
                {'group_id': int(row['group_id']),
                 'emne_val': emne_val})
            # for k, v in self._emne_key2dta.items():
            #     logger.debug("Emne "+repr(k)+" -> "+repr(v))

    def find_group_by_undervisningsenhet(
        self, institusjonsnr, emnekode, versjonskode, terminkode,
        arstall, terminnr, persontype):
        """Returnerer entity-id for aktuell gruppe.
        persontype er en av ('enhetsansvar', 'student').  De �vrige
        verdiene tilsvarer kolonner i FS
        """
        rows = self._emne_key2dta.get(
            (institusjonsnr, emnekode, versjonskode, terminkode,
             arstall, terminnr), [])
##         logger.debug("nokkel: %s" % repr((institusjonsnr, emnekode, versjonskode, terminkode,
##              arstall, terminnr)))
##         logger.debug("Leter i %s" % repr(rows))
        for dta in rows:
            if(len(dta['emne_val']) == 1):
                if persontype == dta['emne_val'][0]:
                    return dta['group_id']
        return None

    def find_group_by_undervisningsaktivitet(
        self, institusjonsnr, emnekode, versjonskode, terminkode,
        arstall, terminnr, aktkode, persontype):
        """Returnerer entity-id for aktuell gruppe.
        persontype er en av ('aktivitetsansvar', 'student').  De
        �vrige verdiene tilsvarer kolonner i FS
        """

        rows = self._emne_key2dta.get(
            (institusjonsnr, emnekode, versjonskode, terminkode,
             arstall, terminnr), [])

        # logger.debug("nokkel: %s -- aktkode=%s" % (repr((institusjonsnr, emnekode, versjonskode, terminkode,
        #                                                  arstall, terminnr)), aktkode))
        # logger.debug("Leter i %s" % repr(rows))

        for dta in rows:
            if(len(dta['emne_val']) == 2):
                if (persontype, aktkode) == tuple(dta['emne_val']):
                    return dta['group_id']
        return None

##  1. Lage et "Offerings & sections" tre med informasjon om de
##  undervisningsenheter og undervisningsaktiviteter som er definert
##  ved UiO.

class StudinfoParsers(object):
    def __init__(self, emne_file, aktivitet_file, enhet_file):
        self.emnekode2info = self._parse_emner(emne_file)
        self.undervisningsaktiviteter = self._parse_undervisningsaktivitet(aktivitet_file)
        self.undervisningsenheter = self._parse_undervisningenheter(enhet_file)
        # The current emne query does not fetch emnenavn_bokmal.  If it did,
        # we could avoid this pre-parsing and use generators instead
        for entry in self.undervisningsenheter:
            tmp =  self.emnekode2info.get(entry['emnekode'])
            if not tmp:
                logger.info("Enhet for ukjent emne: %s" % entry)
            else:
                tmp['emnenavn_bokmal'] = entry['emnenavn_bokmal']
    
    def _parse_emner(self, fname):
        logger.debug("Parsing %s" % fname)
        emnekode2info = {}
        def got_emne(dta, elem_stack):
            entry = elem_stack[-1][-1]
            sko = "%02i%02i%02i" % (int(entry['faknr_reglement']),
                                    int(entry['instituttnr_reglement']),
                                    int(entry['gruppenr_reglement']))
            emnekode2info[entry['emnekode']] = {
                'sko': sko,
                'studienivakode': entry['studienivakode'],
                'institusjonsnr': entry['institusjonsnr'],
                'versjonskode': entry['versjonskode']
                }

        cfg = [(['data', 'emne'], got_emne)]
        GeneralXMLParser(cfg, fname)
        return emnekode2info

    def _parse_undervisningsaktivitet(self, fname):
        logger.debug("Parsing %s" % fname)
        ret = []
        def got_aktivitet(dta, elem_stack):
            entry = elem_stack[-1][-1]
            ret.append(entry)

        cfg = [(['data', 'aktivitet'], got_aktivitet)]
        GeneralXMLParser(cfg, fname)
        return ret

    def _parse_undervisningenheter(self, fname):
        logger.debug("Parsing %s" % fname)
        ret = []
        def got_enhet(dta, elem_stack):
            entry = elem_stack[-1][-1]
            ret.append(entry)

        cfg = [(['data', 'enhet'], got_enhet)]
        GeneralXMLParser(cfg, fname)
        return ret

def gen_undervisningsaktivitet(cgi, sip, out):
    # uioEduSection - Undervisningsaktivitet (instansiering av gruppe,
    #                 kollokvia, lab, skrivekurs, forelesning)
    # access_FS.py:Undervisning.list_aktiviteter
    #
    # uioEduCourseCode - FS.emne.emnekode
    # uioEduCourseAdministrator - (FS.emne.*_reglement (6 siffer)).
    # uioEduCourseLevel - (FS.emne.studienivakode)
    # uioEduCourseName - (FS.emne.emnenavn_bokmal)
    # uioEduCourseSectionName - (FS.undaktivitet.aktivitetsnavn)
    # uioEduCourseOffering - urn:mace:uit.no:section:<noe>
    n = 0
    ret = {}
    top_dn = ldapconf('KURS', 'dn')
    for entry in sip.undervisningsaktiviteter:
        try:
            emne = sip.emnekode2info[entry['emnekode']]
        except KeyError:
            logger.warn("Undervisningsaktivitet %s er ikke knyttet til gyldig emne",
                        entry['emnekode'])
            continue
        if not emne.has_key('emnenavn_bokmal'):
            logger.warn("Undervisningsaktivitet %s uten enhet?" % repr(entry))
            continue
        aktivitet_id = {}
        for persontype, role in interesting_fs_roles:
            args = [entry[x] for x in CerebrumGroupInfo.id_key_seq]
            args.extend((entry['aktivitetkode'], persontype))
            args = [x.lower() for x in args]
            entity_id = cgi.find_group_by_undervisningsaktivitet(*args)
            if entity_id is not None:
                aktivitet_id["%i" % entity_id] = role
#        if len(aktivitet_id) != 2:
#            continue
        keys = aktivitet_id.keys()
        keys.sort()
        urn = 'urn:mace:uit.no:section:aktivitet-%s' % "_".join(keys)

        out.write(entry_string("cn=ua-%i,%s" % (n, top_dn), {
            'objectClass':               ("top", "uioEduSection"),
            'uioEduCourseCode':          (entry['emnekode'],),
            'uioEduCourseAdministrator': (emne['sko'],),
            'uioEduCourseLevel':         (emne['studienivakode'],),
            'uioEduCourseName':          (emne['emnenavn_bokmal'],),
            'uioEduCourseSectionName':   (entry['aktivitetsnavn'],),
            'uioEduCourseInstitution':   (emne['institusjonsnr'],),
            'uioEduCourseVersion':       (emne['versjonskode'],),
            'uioEduCourseSectionCode':   (entry['aktivitetkode'],),
            'uioEduOfferingTermCode':    (entry['terminkode'],),
            'uioEduOfferingYear':        (entry['arstall'],),
            'uioEduOfferingTermNumber':  (entry['terminnr'],),
            'uioEduCourseOffering':      (urn,)}))
        n += 1
        ret[urn] = aktivitet_id
    return ret

def gen_undervisningsenhet(cgi, sip, out):
    # uioEduOffering - Undervisningsenhet (instansiering av et emne)
    # access_FS.py:Undervisning.list_undervisningenheter
    #
    # uioEduCourseCode, uioEduCourseAdministrator, uioEduCourseLevel,
    # uioEduCourseName - som for Undervisningsaktivitet
    # uioEduCourseOffering - urn:mace:uit.no:offering:<noe>
    n = 0
    ret = {}
    top_dn = ldapconf('KURS', 'dn')
    for entry in sip.undervisningsenheter:
        emne = sip.emnekode2info.get(entry['emnekode'])
        if not emne:
            continue # warned erlier
        aktivitet_id = {}
        for persontype, role in interesting_fs_roles:
            args = [entry[x] for x in CerebrumGroupInfo.id_key_seq]
            args.append(persontype)
            args = [x.lower() for x in args]
            entity_id = cgi.find_group_by_undervisningsenhet(*args)
            if entity_id is not None:
                aktivitet_id["%i" % entity_id] = role
#        if len(aktivitet_id) != 2:
#            continue
        keys = aktivitet_id.keys()
        keys.sort()
        urn = 'urn:mace:uit.no:offering:enhet-%s' % "_".join(keys)
        out.write(entry_string("cn=ue-%i,%s" % (n, top_dn), {
            'objectClass':               ("top", "uioEduOffering"),
            'uioEduCourseCode':          (entry['emnekode'],),
            'uioEduCourseAdministrator': (emne['sko'],),
            'uioEduCourseLevel':         (emne['studienivakode'],),
            'uioEduCourseName':          (emne['emnenavn_bokmal'],),
            'uioEduCourseInstitution':   (emne['institusjonsnr'],),
            'uioEduCourseVersion':       (emne['versjonskode'],),
            'uioEduOfferingTermCode':    (entry['terminkode'],),
            'uioEduOfferingYear':        (entry['arstall'],),
            'uioEduOfferingTermNumber':  (entry['terminnr'],),
            'uioEduCourseOffering':      (urn,)}))
        n += 1
        ret[urn] = aktivitet_id
    return ret

def dump_pickle_file(fname, urn_dict1, urn_dict2):
    urn_dict1.update(urn_dict2)

    owner_id2urn = {}
    member_id2owner_id = {}
    for row in ac.list():
        member_id2owner_id[int(row['account_id'])] = int(row['owner_id'])
    for urn, members in urn_dict1.items():
        for entity_id, role in members.items():
            entity_id = int(entity_id)
            group.clear()
            group.find(entity_id)
            for row in group.search_members(group_id=group.entity_id):
                member_id = int(row["member_id"])
                owner_id = member_id2owner_id.get(member_id)
                if owner_id:
                    owner_id2urn.setdefault(owner_id, []).append("%s@%s" %
                                                                 (role, urn))
    tmpfname = fname + ".tmp"
    pickle.dump(owner_id2urn, open(tmpfname, "w"))
    os.rename(tmpfname, fname)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', [
            'help', 'aktivitetfile=', 'enhetfile=', 'emnefile=', 'ldiffile=',
            'picklefile='])
    except getopt.GetoptError:
        usage(1)

    aktivitetfile, enhetfile, emnefile, picklefile, ldiffile = map(
        cereconf.LDAP_KURS.get,
        ('aktivitetfile', 'enhetfile', 'emnefile', 'picklefile', 'file'))
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('--aktivitetfile',):
            aktivitetfile = val
        elif opt in ('--enhetfile',):
            enhetfile = val
        elif opt in ('--emnefile',):
            emnefile = val
        elif opt in ('--picklefile',):
            picklefile = val
        elif opt in ('--ldiffile',):
            ldiffile = val
    if not (aktivitetfile and enhetfile and
            emnefile and picklefile and ldiffile) or args:
        usage(1)

    destfile = ldif_outfile('KURS', ldiffile)
    destfile.write(container_entry_string('KURS'))
    cgi = CerebrumGroupInfo()
    sip = StudinfoParsers(emnefile, aktivitetfile, enhetfile)
    dump_pickle_file(picklefile,
                     gen_undervisningsaktivitet(cgi, sip, destfile),
                     gen_undervisningsenhet(cgi, sip, destfile))
    end_ldif_outfile('KURS', destfile)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
