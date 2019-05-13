#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generere LDAP tre med uioEduSection (Undervisningsaktivitet - gruppe,
kollokvia...) eller uioEduOffering (Undervisningsenhet - emne) objekter.
Hver av disse vil ha en uioEduCourseOffering verdi som inneholder en
URN som unikt identifiserer dette studie-elementet.

ldap-person-dumpen vil generere eduCourseMember atributter med verdi
role@eduCourseOffering, der eduCourseOffering er URN-en over, og
role=Learner for studenter og Instructor for gruppe-lærer/foreleser.

Note: Near-identical with uio/generate_kurs_ldif.py
"""
from __future__ import unicode_literals

import argparse
import logging
import os
import cPickle as pickle

from collections import defaultdict

import cereconf

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.Utils import make_timer
from Cerebrum.modules.LDIFutils import (
    ldapconf,
    entry_string,
    ldif_outfile,
    end_ldif_outfile,
    container_entry_string,
)
from Cerebrum.modules.xmlutils.GeneralXMLParser import GeneralXMLParser

logger = logging.getLogger(__name__)


interesting_fs_roles = (
    ('student', 'Learner'),
    ('admin', 'Administrator'),
    ('dlo', 'DLO'),
    ('fagansvar', 'Fagansvarlig'),
    ('foreleser', 'Foreleser'),
    ('gjestefore', 'Gjesteforeleser'),
    ('gruppelære', 'Gruppelaerer'),
    ('hovedlære', 'Hovedlaerer'),
    ('it-ansvarl', 'IT-ansvarlig'),
    ('lærer', 'Laerer'),
    ('sensor', 'Sensor'),
    ('studiekons', 'Studiekonsulent'),
)


class CerebrumGroupInfo(object):
    PREFIX = "uit.no:fs:kurs:"
    id_key_seq = ('institusjonsnr', 'emnekode', 'versjonskode',
                  'terminkode', 'arstall', 'terminnr')

    def __init__(self, db):
        timer = make_timer(logger, 'Initing CerebrumGroupInfo...')
        self._emne_key2dta = defaultdict(list)
        len_id_key_seq = len(CerebrumGroupInfo.id_key_seq)
        group = Factory.get('Group')(db)
        for row in group.search(name="%s%%" % CerebrumGroupInfo.PREFIX):
            name = row['name'][len(CerebrumGroupInfo.PREFIX):]
            emne_key = name.split(":")[:len_id_key_seq]
            emne_val = name.split(":")[len_id_key_seq:]
            self._emne_key2dta[tuple(emne_key)].append(
                {'group_id': int(row['group_id']),
                 'emne_val': emne_val})
        timer('... done initing CerebrumGroupInfo')

    def find_group_by_undervisningsenhet(
            self, institusjonsnr, emnekode, versjonskode, terminkode,
            arstall, terminnr, persontype):
        """Returnerer entity-id for aktuell gruppe.
        persontype er en av ('enhetsansvar', 'student').  De øvrige
        verdiene tilsvarer kolonner i FS
        """
        rows = self._emne_key2dta.get(
            (institusjonsnr, emnekode, versjonskode, terminkode,
             arstall, terminnr), [])
        for dta in rows:
            if len(dta['emne_val']) == 1:
                if persontype == dta['emne_val'][0]:
                    return dta['group_id']
        return None

    def find_group_by_undervisningsaktivitet(
            self, institusjonsnr, emnekode, versjonskode, terminkode,
            arstall, terminnr, aktkode, persontype):
        """Returnerer entity-id for aktuell gruppe.
        persontype er en av ('aktivitetsansvar', 'student').  De
        øvrige verdiene tilsvarer kolonner i FS
        """
        rows = self._emne_key2dta.get(
            (institusjonsnr, emnekode, versjonskode, terminkode,
             arstall, terminnr), [])
        for dta in rows:
            if len(dta['emne_val']) == 2:
                if (persontype, aktkode) == tuple(dta['emne_val']):
                    return dta['group_id']
        return None


class StudinfoParsers(object):
    def __init__(self, emne_file, aktivitet_file, enhet_file):
        timer = make_timer(logger, 'Initing StudinfoParsers...')
        self.emnekode2info = self._parse_emner(emne_file)
        self.undervisningsaktiviteter = self._parse_undervisningsaktivitet(
            aktivitet_file)
        self.undervisningsenheter = self._parse_undervisningenheter(enhet_file)
        # The current emne query does not fetch emnenavn_bokmal.  If it did,
        # we could avoid this pre-parsing and use generators instead
        for entry in self.undervisningsenheter:
            tmp = self.emnekode2info.get(entry['emnekode'])
            if not tmp:
                logger.info("Enhet for ukjent emne: %s", dict(entry))
            else:
                tmp['emnenavn_bokmal'] = entry['emnenavn_bokmal']
        timer('... done initing StudinfoParsers')

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
    timer = make_timer(logger, 'Starting gen_undervisningsaktivitet')
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
            logger.warn(
                "Undervisningsaktivitet %s er ikke knyttet til gyldig emne",
                entry['emnekode'])
            continue
        if 'emnenavn_bokmal' not in emne:
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
        keys = aktivitet_id.keys()
        keys.sort()
        urn = 'urn:mace:uit.no:section:aktivitet-%s' % "_".join(keys)
        out.write(entry_string("cn=ua-%i,%s" % (n, top_dn), {
            'objectClass': ("top", "uioEduSection"),
            'uioEduCourseCode': (entry['emnekode'],),
            'uioEduCourseAdministrator': (emne['sko'],),
            'uioEduCourseLevel': (emne['studienivakode'],),
            'uioEduCourseName': (emne['emnenavn_bokmal'],),
            'uioEduCourseSectionName': (entry['aktivitetsnavn'],),
            'uioEduCourseInstitution': (emne['institusjonsnr'],),
            'uioEduCourseVersion': (emne['versjonskode'],),
            'uioEduCourseSectionCode': (entry['aktivitetkode'],),
            'uioEduOfferingTermCode': (entry['terminkode'],),
            'uioEduOfferingYear': (entry['arstall'],),
            'uioEduOfferingTermNumber': (entry['terminnr'],),
            'uioEduCourseOffering': (urn,)}))
        n += 1
        ret[urn] = aktivitet_id
    timer('... done gen_undervisningsaktivitet')
    return ret


def gen_undervisningsenhet(cgi, sip, out):
    timer = make_timer(logger, 'Starting gen_undervisningsenhet')
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
            # warned earlier
            continue
        aktivitet_id = {}
        for persontype, role in interesting_fs_roles:
            args = [entry[x] for x in CerebrumGroupInfo.id_key_seq]
            args.append(persontype)
            args = [x.lower() for x in args]
            entity_id = cgi.find_group_by_undervisningsenhet(*args)
            if entity_id is not None:
                aktivitet_id["%i" % entity_id] = role
        keys = aktivitet_id.keys()
        keys.sort()
        urn = 'urn:mace:uit.no:offering:enhet-%s' % "_".join(keys)
        out.write(entry_string("cn=ue-%i,%s" % (n, top_dn), {
            'objectClass': ("top", "uioEduOffering"),
            'uioEduCourseCode': (entry['emnekode'],),
            'uioEduCourseAdministrator': (emne['sko'],),
            'uioEduCourseLevel': (emne['studienivakode'],),
            'uioEduCourseName': (emne['emnenavn_bokmal'],),
            'uioEduCourseInstitution': (emne['institusjonsnr'],),
            'uioEduCourseVersion': (emne['versjonskode'],),
            'uioEduOfferingTermCode': (entry['terminkode'],),
            'uioEduOfferingYear': (entry['arstall'],),
            'uioEduOfferingTermNumber': (entry['terminnr'],),
            'uioEduCourseOffering': (urn,)}))
        n += 1
        ret[urn] = aktivitet_id
    timer('... done gen_undervisningsenhet')
    return ret


def gen_owner_id2urn(db, urn_dict):
    timer = make_timer(logger, 'Starting gen_owner_id2urn...')
    ac = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    groups = []
    group_members = defaultdict(list)
    owner_id2urn = defaultdict(list)
    member_id2owner_id = {}
    for row in ac.list():
        member_id2owner_id[int(row['account_id'])] = int(row['owner_id'])
    for i in urn_dict.itervalues():
        groups.extend(map(int, i.keys()))
    for row in group.search_members(group_id=groups):
        group_members[row['group_id']].append(row['member_id'])
    for urn, members in urn_dict.iteritems():
        for group_id, role in members.items():
            for member_id in group_members[int(group_id)]:
                owner_id = member_id2owner_id.get(member_id)
                if owner_id:
                    owner_id2urn[owner_id].append('%s@%s' % (role, urn))
    timer('...done gen_owner_id2urn')
    return owner_id2urn


def dump_pickle_file(fname, urn_dict):
    timer = make_timer(logger, 'Starting dump_pickle_file...')
    tmpfname = fname + '.tmp'
    pickle.dump(urn_dict, open(tmpfname, 'wb'), pickle.HIGHEST_PROTOCOL)
    os.rename(tmpfname, fname)
    timer('...done dump_pickle_file')


def main(inargs=None):
    defaults = cereconf.LDAP_KURS
    parser = argparse.ArgumentParser(
        description="Generate course ldap tree",
    )
    parser.add_argument(
        '--aktivitetfile',
        default=defaults.get('aktivitetfile'),
        required=not defaults.get('aktivitetfile'),
        help='Use edu activities from %(metavar)s (%(default)s)',
        metavar='xml-file',
    )
    parser.add_argument(
        '--enhetfile',
        default=defaults.get('enhetfile'),
        required=not defaults.get('enhetfile'),
        help='Use edu units from %(metavar)s (%(default)s)',
        metavar='xml-file',
    )
    parser.add_argument(
        '--emnefile',
        default=defaults.get('emnefile'),
        required=not defaults.get('emnefile'),
        help='Use subjects from %(metavar)s (%(default)s)',
        metavar='xml-file',
    )
    parser.add_argument(
        '--picklefile',
        default=defaults.get('picklefile'),
        required=not defaults.get('picklefile'),
        help='Store course participation to %(metavar)s (%(default)s)',
        metavar='pickle-file',
    )
    parser.add_argument(
        '--ldiffile',
        default=defaults.get('file'),
        required=not defaults.get('file'),
        help='Write courses LDIF to %(metavar)s (%(default)s)',
        metavar='ldif-file',
    )
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()

    cgi = CerebrumGroupInfo(db)
    sip = StudinfoParsers(args.emnefile, args.aktivitetfile, args.enhetfile)
    destfile = ldif_outfile('KURS', args.ldiffile)
    destfile.write(container_entry_string('KURS'))
    urn_dict = gen_undervisningsaktivitet(cgi, sip, destfile)
    urn_dict.update(gen_undervisningsenhet(cgi, sip, destfile))
    end_ldif_outfile('KURS', destfile)
    owner_id2urn = gen_owner_id2urn(db, urn_dict)
    dump_pickle_file(args.picklefile, owner_id2urn)

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
