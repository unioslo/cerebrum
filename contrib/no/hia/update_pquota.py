#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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
This file is a HiA-specific extension of Cerebrum. The purpose of this
script is to keep track of printer quota updates for students at HiA.
The actual accounting is done in eDir.
"""

import cerebrum_path
import cereconf

import getopt
import sys

from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum.modules.no.hia.printerquotas import PQuota
from Cerebrum.modules.no.hia import EdirUtils
from Cerebrum.modules.no.hia import EdirLDAP
from Cerebrum.modules.no.access_FS import FS
from Cerebrum import Errors

def _er_ansatt(person):
    affs = {}
    for row in person.get_affiliations():
        affs[row['affiliation']] = row['status']
    if (int(const.affiliation_ansatt) in affs.keys() \
        or int(const.affiliation_tilknyttet in affs.keys()) \
        or (int(const.affiliation_manuell) in affs.keys() \
            and affs[int(const.affiliation_manuell)] <> \
            int(const.affiliation_status_manuell_gjest_student))):
        return True
    return False

def check_paid_semfee():
    paid_semfee = []
    fs_db = Database.connect(user='cerebrum', service='FSHIA.uio.no',
                             DB_driver='Oracle')

    fs = FS(fs_db)
    temp = fs.student.list_betalt_semesteravgift()
    for row in temp:
        fnr = '%06d%05d' % (row['fodselsdato'], row['personnr'])
        person.clear()
        ansatt = False
        try:
            person.find_by_external_id(const.externalid_fodselsnr, fnr,
                                       source_system=const.system_fs)
        except Errors.NotFoundError:
            logger.error('No such person (%s)' % fnr)
            continue
#        ansatt = _er_ansatt(person)
#        if not ansatt:
        paid_semfee.append(int(person.entity_id))
    return paid_semfee

def update_quota(update, ldap_handle, pq, edir_ut, noup):
    total = 0
    for k, v in update.iteritems():
        try:
            pq.find(int(k))
        except Errors.NotFoundError:
            pq.insert_new_quota(int(k))
        logger.debug('Setting new quota (%s)' % update[k])

        pq.update_free_quota(int(k))
        logger.debug('Updating free quota for %s' % update[k])        
        pq_bal = edir_ut.get_pq_balance(update[k])
        if pq_bal:
            total = int(pq_bal[0]) + int(cereconf.NW_FREEQUOTA)
            logger.info('Updating total quota for %s, new total %d (old total = %d)' % (update[k],
                                                                                        total,
                                                                                        int(pq_bal[0])))
            pq.update_total(int(k), total)
        if noup:
            logger.debug('Should update edir with new total %d for %s.' % (total,
                                                                           update[k]))
        else:
            edir_ut.set_pq_balance(update[k])

def need_to_update(paid_sem, updated):
    logger.debug("In need-to-update")
    account = Factory.get('Account')(db)
    update = {}
    for i in paid_sem:
        if not i in updated:
            try:
                person.clear()
                person.find(i)
            except Errors.NotFoundError:
                logger.error('No such person (%s)!' % i)
                # if there is no person, there is definitely no account.
                continue

            acc_id = person.get_primary_account()
            if acc_id is None: 
                logger.error('Could not find primary account for %s!' % i)
                continue
            else:
                logger.debug("Account found %s" % acc_id)

            try:
                account.clear()
                account.find(acc_id)
            except Errors.NotFoundError:
                logger.error('Could not find account with account_id == %s!' % acc_id)
                continue
            update[i] = account.account_name
    logger.debug("Done with need-to-update")
    return update

def make_info_log(edir_util):
    return edir_util.get_all_pq_info()
 
def usage():
    print """Usage: update_pquota.py
             -d, --dryrun  : do not update eDir or Cerebrum
             -o, --outfile : create a log file with all information
                             about current printer quotas registered
                             in eDir   
          """
    sys.exit(0)
   
def main():
    global db, logger, const, person

    temp = {}
    updated = []
    db = Factory.get('Database')()
    db.cl_init(change_program='update_pquota')
    
    logger = Factory.get_logger('cronjob')
    const = Factory.get('Constants')(db)
    person = Factory.get('Person')(db)
    
    passwd = db._read_password(cereconf.NW_LDAPHOST,
                               cereconf.NW_ADMINUSER.split(',')[:1][0])
    ldap_handle = EdirLDAP.LDAPConnection(db, cereconf.NW_LDAPHOST,
                                          cereconf.NW_LDAPPORT,
                                          binddn=cereconf.NW_ADMINUSER,
                                          password=passwd, scope='sub')
    edir_util = EdirUtils.EdirUtils(db, ldap_handle)
    pq = PQuota.PQuota(db)

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'o:d',
                                   ['outfile=',
                                    'dryrun'])
    except getopt.GetoptError:
        usage()

    dryrun = False
    outfile = ""
    for opt, val in opts:
        if opt in ('-d', '--dryrun'):
            dryrun = True
        elif opt in ('-o', '--outfile'):
            outfile = val

    if outfile:
        logger.info('Getting information about printer quotas in eDir.')
        temp = make_info_log(edir_util)
        stream = open(outfile, 'w')
        for i in temp:
            stream.write(i)
            stream.write('\n')
        stream.close()
        sys.exit(0)
    
    logger.info('Checking for paid semester fee.')
    paid = check_paid_semfee()
    
    logger.info('Checking for update quota.')
    for i in pq.list_updated():
        updated.append(int(i['person_id']))
    logger.info('Making need-to-update dict.')
    temp = need_to_update(paid, updated)

    if len(temp.keys()) <> 0:
        logger.info('Starting quota updates.')    
        update_quota(temp, ldap_handle, pq, edir_util, dryrun)
    else:
        logger.info('Nothing to do, disconnecting from eDir')
    ldap_handle.close_connection()
    
    if not dryrun:
        db.commit()
        logger.info('Pquota-processing done, commiting all changes.')
    else:
        db.rollback()
        logger.info('Pquota-processing done, rolling back all changes.')

if __name__ == '__main__':
    main()
    
# arch-tag: b19d3b32-6309-11da-8bdf-07d796d0d800
