#!/usr/bin/env python
# coding: latin1
# -*- coding: iso-8859-1 -*-
# vim: set fileencoding=latin1 :
# Copyright 2013 University of Oslo, Norway
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

"""
This script generates an export of exams and exam participants for digital
examinations. @and-more
"""

import getopt
import sys
#import string
from os.path import basename

import cereconf

from mx import DateTime
from Cerebrum.Utils import Factory, argument_to_sql
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.bofhd.auth import BofhdAuthOpSet, BofhdAuthOpTarget, BofhdAuthRole

logger = Factory.get_logger('console')


# TODO: Add actual cereconf-var
cereconf.DIGEKS_EXAMS = ('JUS3211', 'JUS4111', 'JUS4122', 'JUS4211')


def usage(exitcode=0):
    print """Usage: %(name)s [options]

    @tbd-Generates an export of exams and participants as CSV-file(s?)

    Options: 
      -c, --candidates           Output CSV-file with the candidates
      -e, --exams                Output CSV-file with the exam data
      -h, --help                 Show this help text.
    """ % {'name': basename(sys.argv[0])}

    sys.exit(exitcode)


def get_candidate_data(db, subject, year, version=None, vurdkomb=None, vurdtid=None):
    """ Fetches exam data from FS. 

    @type db: Cerebrum.Database
    @param db: The database connection of an FS-object.

    @type subject: string
    @param subject: The subjects to fetch exam data for

    @type year: int or string
    @param year: Filter results by year

    @type semester: string
    @param semester: Either 'HØST' or 'VÅR'. Filters results by semester

    @rtype: Cerebrum.extlib.db_row.row
    @return: Database rows with the FS results (exams).
             Fields: 
               brukernavn (str), emnekode (str), vurdtidkode (str),
               kandidatlopenr (int), kommislopenr (int), institusjonsnr (int),
               versjonskode (str), vurdkombkode (str), dato (str), tid (str),
    """
    subject = str(subject).upper()

    # Build query
    # TODO: Multiple subjects? Or should we use multiple queries?

    additional_clauses = ""
    if vurdtid:
        additional_clauses += "AND vm.vurdtidkode=:vurdtid "
    if vurdkomb:
        additional_clauses += "AND vm.vurdkombkode=:vurdkomb "
    if vurdtid:
        additional_clauses += "AND vm.versjonskode=:version "

    query = """SELECT DISTINCT p.brukernavn, vm.emnekode, vm.vurdtidkode, 
    vm.kandidatlopenr, vm.kommislopenr, ve.institusjonsnr, ve.versjonskode,
    ve.vurdkombkode, 
    to_char(nvl(ve.dato_eksamen,v2.dato_eksamen),'yyyy-mm-dd') AS dato,
    to_char(nvl(ve.klokkeslett_fremmote_tid,v2.klokkeslett_fremmote_tid),'hh24:mi') AS tid
    FROM fs.vurdkombmelding vm
    JOIN fs.person p ON (
            p.fodselsdato = vm.fodselsdato
        AND p.personnr = vm.personnr
        AND p.brukernavn IS NOT NULL)
    JOIN fs.vurdkombenhet ve ON (
            ve.emnekode = vm.emnekode
        AND ve.versjonskode = vm.versjonskode
        AND ve.vurdtidkode = vm.vurdtidkode
        AND ve.arstall = vm.arstall)
    JOIN fs.vurderingskombinasjon v ON (
            v.emnekode = ve.emnekode
        AND v.versjonskode = ve.versjonskode
        AND v.vurdkombkode = ve.vurdkombkode
        AND v.status_vurdering='J')   
    LEFT OUTER JOIN fs.vurdkombenhet v2 CROSS JOIN fs.eksavviklingperson e ON (
            v2.emnekode = vm.emnekode
        AND v2.versjonskode = vm.versjonskode
        AND v2.vurdtidkode = vm.vurdtidkode
        AND v2.arstall = vm.arstall
        AND e.fodselsdato = vm.fodselsdato
        AND e.personnr = vm.personnr
        AND e.emnekode = v2.emnekode
        AND e.vurdkombkode = v2.vurdkombkode
        AND e.vurdtidkode = v2.vurdtidkode
        AND e.arstall = v2.arstall)
    WHERE NOT nvl(ve.dato_eksamen,v2.dato_eksamen) IS NULL
        AND vm.status_er_kandidat = 'J'
        AND vm.emnekode like UPPER(:subject)
        AND vm.arstall = :year
        %(clauses)s
    ORDER BY 4;""" % {'clauses': additional_clauses}
    return db.query(query, {'subject': subject, 
                            'year': year, 
                            'vurdtid': vurdtid,
                            'vurdkomb': vurdkomb,
                            'version': version})


def get_exam_data(db, subjects, year, semester=None):
    """ Fetches exam data from FS. 

    @type db: Cerebrum.Database
    @param db: The database connection of an FS-object.

    @type subject: string
    @param subject: The subjects to fetch exam data for

    @rtype: Cerebrum.extlib.db_row.row
    @return: Database rows with the FS results (exams).
             Fields:
               emnekode (str), versjonskode (str), vurdkombkode (str), 
               vurdtidkode (str), arstall (int), institusjon (int),
               fakultet (int), institutt (int), gruppe (int), dato (str),
               tid (str),
    """
    binds = {'year': year, 'semester': semester}

    subjects_clause = argument_to_sql(subjects, 've.emnekode', binds, str)

    semester_clause = ""
    if semester:
        semester_clause = "AND vm.vurdtidkode = :semester "
        binds['semester'] = semester

    query = """SELECT ve.emnekode, ve.versjonskode, ve.vurdkombkode,
    ve.vurdtidkode, ve.arstall, ve.institusjonsnr AS institusjon, e.faknr_kontroll AS fakultet,
    e.instituttnr_kontroll AS institutt, e.gruppenr_kontroll AS gruppe,
    to_char(nvl(ve.dato_eksamen,v2.dato_eksamen),'yyyy-mm-dd') AS dato,
    to_char(nvl(ve.klokkeslett_fremmote_tid,v2.klokkeslett_fremmote_tid),'hh24:mi') AS tid
    FROM fs.vurdkombenhet ve
    JOIN fs.vurderingskombinasjon v ON (
            v.emnekode = ve.emnekode
        AND v.versjonskode = ve.versjonskode
        AND v.vurdkombkode = ve.vurdkombkode
        AND v.status_vurdering = 'J')
    JOIN fs.emne e ON (
            e.emnekode = ve.emnekode 
        AND e.institusjonsnr = ve.institusjonsnr
        AND e.versjonskode = ve.versjonskode)
    LEFT OUTER JOIN fs.vurdkombenhet v2 ON (
            v2.emnekode = ve.emnekode
        AND v2.versjonskode = ve.versjonskode
        AND v2.vurdtidkode = ve.vurdtidkode
        AND v2.arstall = ve.arstall)
    WHERE NOT nvl(ve.dato_eksamen,v2.dato_eksamen) IS NULL
        %(semester)s
        AND %(subjects)s
        AND ve.arstall = :year
    ORDER BY 1;""" % {'subjects': subjects_clause,
                      'semester': semester_clause, }
    return db.query(query, binds)


def escape_chars(string, special='', escape='\\'):
    """ Adds escape characters to a string, L{fields}. Replaces a single
    L{escape} character, with two escape characters, and a single L{special}
    character with an escape character and the special character.

    @type string: str
    @param string: The string to format (add escape chars to)

    @type special: iterable
    @param string: String or other iterable containing characters that needs to
                   be escaped.

    @type string: str
    @param string: The string to format (add escape chars to)

    @rtype: str
    @return: A string with escape charactes added for the characters mentioned.
    """
    # Backslash is our escape character, so it needs to be replaced first.
    assert escape not in special
    special = set(special)
    tmp = string.replace(escape, escape+escape)
    for char in special:
        tmp = tmp.replace(char, escape+char)
    return tmp


def process_exams(db, subjects, year, semester=None):
    # Document, this is a bit messy. Used to gather, sanitize and organize
    # results.

    exams = dict()
    candidates = dict()
    db_exams = get_exam_data(db, subjects, year, semester=None)

    for row in db_exams:
        try:
            # The key is used to identify an exam.
            key = ';'.join([
                str(row['institusjon']),
                escape_chars(row['emnekode'], special=';'),
                escape_chars(row['versjonskode'], special=';'),
                escape_chars(row['vurdkombkode'], special=';'),
                escape_chars(row['vurdtidkode'], special=';'),
                ])

            if not exams.has_key(key):
                # TODO: Sanitize datetime
                exams[key] = {'datetime': '%s %s' % (row['dato'], row['tid']),
                              'sko': '%02d0000' % row['fakultet'],
                              'access': ''}
            else:
                # There's no guarantee that the exam actually is unique from
                # FS. We warn about duplicate exams. If there are duplicates,
                # only the first exam will be exported to the exam file, but
                # all candidates from all exams with the same key will be
                # 'added' to that exam. 
                logger.warn("Unable to process exam, duplicate exam with key '%s'!" % key)
                continue

            db_candidates = get_candidate_data(
                    db, 
                    row['emnekode'], 
                    year,
                    version=row['versjonskode'], 
                    vurdkomb=row['vurdkombkode'],
                    vurdtid=row['vurdtidkode'])
        
        except KeyError, e:
            logger.warn('Unable to process exam, no such column in FS result: ' % str(e))
            continue

        for row in db_candidates:
            try:
                key = ';'.join([
                    str(row['institusjonsnr']),
                    escape_chars(row['emnekode'], special=';'),
                    escape_chars(row['versjonskode'], special=';'),
                    escape_chars(row['vurdkombkode'], special=';'),
                    escape_chars(row['vurdtidkode'], special=';'),
                    ])
                
                if not candidates.has_key(key):
                    candidates[key] = list()

                candidates[key].append({
                    'account_name': row['brukernavn'],
                    'candidate_no': row['kandidatlopenr'],
                    'commission_no': row['kommislopenr'],
                    })

            except KeyError, e:
                logger.warn('Unable to process candidate, no such column in FS result: ' % str(e))
                continue

    return (exams, candidates)


def _find_or_create_group(db, group_name):
    """ This method will find and return the group object corresponding to
    L{group_name}. If no group exists with that name, the group will be
    created and returned.

    @type db: Cerebrum.Database.Database
    @param db: A Cerebrum database object.
    
    @type group_name: str
    @param group_name: Name of the group to find or create

    @rtype: Cerebrum.Group.Group
    @return: A Cerebrum group object, with the specified group selected.
    """
    #gr = Factory.get('Group')(db)
    
    # FIXME: This is ugly, as we bypass the test for NIS-memberships in the UIO
    # mixin. The group *could* get promoted to PosixGroup and get NIS-spreads.
    # However, the test that we bypass causes add_member() to take approx.
    # 100 ms. Adding 100 candidates to an exam group will then take ~10
    # seconds, and *that* doesn't scale very well.
    from Cerebrum.Group import Group
    gr = Group(db)

    try:
        gr.find_by_name(group_name)
        return gr
    except NotFoundError:
        pass

    logger.info("Group '%s' didn't exist, will be created" % group_name)
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    creator = ac.search(name='bootstrap_account')[0]['account_id']
    gr.populate(creator_id = creator, name = group_name,
            visibility = co.group_visibility_all,
            description = "Digital exams group '%s'" % group_name)
    gr.write_db()

    # It will be up to the caller to commit/rollback
    return gr


def _set_group_owner(db, owner_id, group_id):
    """ This method will simply set up the Entity L{owner_id} as a
    C{Group-owner} of group L{group_id}.
    
    @type db: Cerebrum.Database.Database
    @param db: A Cerebrum database object.
    
    @type owner_id: int
    @param owner_id: The entity_id of the owner object.

    @type group_id: int
    @param group_id: The entity_id of a group object.
    """
    co = Factory.get('Constants')(db)
    ar = BofhdAuthRole(db)
    aos = BofhdAuthOpSet(db)
    aot = BofhdAuthOpTarget(db)

    # TODO: control that the entity_id's exists, and that group_id actually
    # exists as a group object.
    
    # Find or create group operation target
    try:
        aot.find(aot.list(entity_id=group_id, 
                          target_type=co.auth_target_type_group
                         )[0]['op_target_id'])
    except IndexError:
        aot.populate(group_id, co.auth_target_type_group)
        aot.write_db()
    
    # Find the 'Group-owner' OpSet to get its entity_id
    aos.find_by_name('Group-owner')

    if not len(ar.list(owner_id, aos.op_set_id, aot.op_target_id)):
        ar.grant_auth(owner_id, aos.op_set_id, aot.op_target_id)
        return True

    return False


def get_exam_group(db, sko):
    """ This method will find or create the group for exam candidates. It will
    also find or create an owner group, and set up the group-owner
    relation.

    @type sko: str
    @param sko: The faculty sko for the exam

    @rtype:  Group
    @return: The Group object that was found/created.
    """

    owner_name = _gen_group_name(sko, True)
    owner = _find_or_create_group(db, owner_name)

    group_name = _gen_group_name(sko, False)
    group = _find_or_create_group(db, group_name)

    if _set_group_owner(db, owner.entity_id, group.entity_id):
        logger.info("Group-owner relation created, %s -> %s" % 
                (owner.group_name, group.group_name))

    return group


def _gen_group_name(sko, is_admin=False):
    return "digeks-%s%s" % (('', 'adm-')[int(is_admin)], sko)


def main():

    from datetime import datetime

    db = Factory.get('Database')()
    db.cl_init(change_program='proc-digeks')
    ac = Factory.get('Account')(db)
    co = Factory.get('Constants')(db)
    pe = Factory.get('Person')(db)

    fs = Factory.get('FS')()

    examfile = sys.stdout
    candidatefile = sys.stdout

    #subjects = None
    year = 2013
    semester = None

    opts, args = getopt.getopt(sys.argv[1:], 'hd')
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage(0)
        elif opt in ('-d',):
            print 'opt', opt, 'val', val
            raise NotImplementedError('na')
        elif opt in ('-v'):
            semester = 'v'
        elif opt in ('-h'):
            semester = 'h'
        else:
            logger.error("Invalid argument: '%s'" % val)
            usage(1)

    logger.debug('Getting FS data')
    exams, candidates = process_exams(fs.db, cereconf.DIGEKS_EXAMS, year)

    # As this script will process an increasing number of students, we will
    # have to cache students up front to reduce DB lookups.
    pta = datetime.now()

    logger.debug('Caching candidate data')
    all_accounts = ac.search(owner_type=co.entity_person)

    # Create a set of all candidate account names, regardless of exam
    all_candidates = set([c['account_name'] for exam in candidates.values() for
        c in exam])

    # Filter all_accounts by all_candidates, create a dict mapping:
    # account_name -> (account_id, owner_id)
    account_names = filter(lambda a: a['name'] in all_candidates, all_accounts)
    cand_accounts = dict((a['name'], {
        'account_id': a['account_id'],
        'owner_id':a['owner_id']}) for a in account_names)
    
    # Lookup the mobile number of all candidates, and create a dict mapping:
    # person_id -> mobile number
    owners = set([a['owner_id'] for a in cand_accounts.values()])
    cand_mobiles = dict((mob['entity_id'], mob['contact_value']) for mob in
            pe.list_contact_info(source_system=co.system_fs,
                                 contact_type=co.contact_mobile_phone,
                                 entity_type=co.entity_person, 
                                 entity_id=owners))

    def uname2account(account_name):
        account = cand_accounts.get(account_name, None)
        if not account:
            return None
        return account['account_id']

    def uname2mobile(account_name):
        account = cand_accounts.get(account_name, None)
        if not account:
            return ''
        return cand_mobiles.get(account['owner_id'], '')

    ptb = datetime.now()

    logger.debug('Processing results')
    for key, exam in exams.items():
        logger.debug('Exam %s at %s, %d candidates' % (key,
            exam.get('datetime'), len(candidates.get(key, []))))

        exam_group = get_exam_group(db, exam.get('sko', '000000'))

        # Process candidates
        for candidate in candidates.get(key, []):

            account_id = uname2account(candidate['account_name'])
            if not account_id:
                logger.warn("Couldn't find account %s, omitted" % 
                        candidate['account_name'])
                continue

            mobile = uname2mobile(candidate['account_name'])
            if not mobile:
                logger.debug("No mobile number for '%s'" % 
                        candidate['account_name'])

            if not exam_group.has_member(account_id):
                exam_group.add_member(account_id)
            else:
                logger.debug('User %s already in group %s' % 
                        (candidate['account_name'], exam_group.group_name))

            line = '%(uname)s;%(key)s;%(kand)s;%(komm)s;%(mob)s\n' % {
                'uname': escape_chars(candidate['account_name'], special=';'),
                'key': key,
                'kand': str(candidate['candidate_no']),
                'komm': str(candidate['commission_no']),
                'mob': escape_chars(mobile, special=';'),}

            #candidatefile.write(line.decode('latin1').encode('utf8'))
        
        exam_group.write_db()

        line = '%(key)s;%(datetime)s;%(sko)s;%(access)s\n' % {
            'key': key,
            'datetime': escape_chars(exam['datetime'], special=';'),
            'sko': escape_chars(exam['sko'], special=';'),
            'access': escape_chars(exam['access'], special=';'),}
        #examfile.write(line.decode('latin1').encode('utf8'))

    db.rollback()

    ptc = datetime.now()

    print "Caching: %s, Processing: %s" % ((ptb-pta), (ptc-ptb))

    if not examfile is sys.stdout:
        examfile.close()
    if not candidatefile is sys.stdout:
        candidatefile.close()


if __name__ == '__main__':
    main()
