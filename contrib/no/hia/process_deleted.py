#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
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

# This is a HiA-spesific cerebrum related script that processes
# account-deletion requests registered in Cerebrum.
# When an account is deleted a delete request is registered in
# 'bofhd_requests'. The following is done by this script:
#
#
#
#
# eDir : user object is deleted, account@edir spread removed
# nis  : write "deleted" file
#        <uname>:<crypt>:<uid>:<gid>:<gecos>:<home>:<shell>
#        for both nis and nisans, account@nis/nisans removed
# ad   : account@ad spread removed
# email: write file (<uname>:<email_server>), account@imap spread removed
#
# TODO: this script must be more robust and pretty (but first we make it work) :-)


import getopt
import sys
import time
import os
import mx
import string

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.extlib import logging
from Cerebrum.modules.no.hia import EdirLDAP

db = Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")

def process_delete_requests():
    br = BofhdRequests(db, const)
    now = mx.DateTime.now()
    del_file = []
    group = Factory.get('Group')(db)
    account = Factory.get('Account')(db)
    operator = Factory.get('Account')(db)
    spreads = []
    posix_home = ''
    pwd = '*'
    uid = ''
    gid = ''
    gecos = 'gecos'
    shell = ''
    line = ''

    for r in br.get_requests(operation=const.bofh_delete_user):
        if not is_valid_request(r['request_id']):
            continue
        if not keep_running():
            break
        if r['run_at'] > now:
            continue
        try:
            account.clear()
            account.find(r['entity_id'])
        except Errors.NotFoundError:
            logger.error('Could not find account %s' % r['entity_id'])
            continue
        if account.is_deleted():
            logger.warn("%s is already deleted" % account.account_name)
            br.delete_request(request_id=r['request_id'])
            db.commit()
            continue

        posix_user = PosixUser.PosixUser(db)
        set_operator(r['requestee_id'])

        # check for posix attrs
        posix_user.clear()
        try:
            posix_user.find(r['entity_id'])
        except Errors.NotFoundError:
            posix_user = None

        ## Deal with all the systems that account data is exported to 
        spreads = account.get_spread()

        for row in spreads:

            ## Account is valid in AD, remove account@ad spread
            if row['spread'] == const.spread_hia_ad_account:
                account.delete_spread(row['spread'])
            ## student-accounts usually have account@ldap, remove this
            elif row['spread'] = const.spread_ldap_account:
                account.delete_spread(row['spread'])
            ## An email account exists, remove account@imap spread, register email account delete
            elif row['spread'] == const.spread_hia_email:
                est = Email.EmailServerTarget(db)
                try:
                    est.find_by_entity(account.entity_id)
                except Errors.NotFoundError:
                    logger.warn('No email server assigned to %s, removing imap spread only.' % account.account_name)
                if est:
                    es = Email.EmailServer(db)
                    es.find(est.email_server_id)
                    del_file.append('EMAIL:' + account.account_name + ':' + es.name)
                account.delete_spread(row['spread'])

            ## Account is valid in nis@hia, remove account@nis spread, register nis-home delete
            elif row['spread'] == const.spread_nis_user:
                posix_home = posix_user.get_posix_home(row['spread'])
                uid = posix_user.posix_uid
                gid = posix_user.gid_id
                shell = posix_user.shell
                line = string.join([account.account_name, pwd, str(uid), str(gid), gecos, posix_home, str(shell)], ':')
                line = 'NIS:' + line
                del_file.append(line)
                account.delete_spread(row['spread'])
                try:
                    home = account.get_home(row['spread'])
                except Errors.NotFoundError:
                    continue
                account.set_homedir(current_id=home['homedir_id'],
                                    status=const.home_status_archived)

            ## Account is valid in nisans@hia, remove account@nisans spread, register nisans-home delete
            elif row['spread'] == const.spread_ans_nis_user:
                posix_home = posix_user.get_posix_home(row['spread'])
                uid = posix_user.posix_uid
                gid = posix_user.gid_id
                shell = posix_user.shell
                line = string.join([account.account_name, pwd, str(uid), str(gid), gecos, posix_home, str(shell)], ':')
                line = 'NISANS:' + line
                del_file.append(line)
                account.delete_spread(row['spread'])
                try:
                    home = account.get_home(row['spread'])
                except Errors.NotFoundError:
                    continue
                account.set_homedir(current_id=home['homedir_id'],
                                    status=const.home_status_archived)

            ## Account is valid in eDir, remove account@edir spread, delete user-object in eDir
            elif row['spread'] == const.spread_hia_novell_user:
                passwd = db._read_password(cereconf.NW_LDAPHOST,
                                           cereconf.NW_ADMINUSER.split(',')[:1][0])
                ldap_handle = EdirLDAP.LDAPConnection(db, cereconf.NW_LDAPHOST,
                                                      cereconf.NW_LDAPPORT,
                                                      binddn=cereconf.NW_ADMINUSER,
                                                      password=passwd, scope='sub')
                search_str = '(&(cn=%s)(%s))' % (account.account_name, 'objectClass=inetOrgPerson')
                ldap_objects = ldap_handle.ldap_get_objects(cereconf.NW_LDAP_ROOT, search_str)
                if ldap_objects:
                    (ldap_object_dn, ldap_attrs) = ldap_objects[0]
                    ldap_handle.ldap_delete_object(ldap_object_dn)
                    ldap_handle.close_connection()
                account.delete_spread(row['spread'])
                try:
                    home = account.get_home(row['spread'])
                except Errors.NotFoundError:
                    continue
                account.set_homedir(current_id=home['homedir_id'],
                                    status=const.home_status_archived)
            if posix_user:
                posix_user.delete_posixuser()
                
            ## Remove account from all groups (including eDir-server groups)
            for g in group.list_groups_with_entity(account.entity_id):
                group.clear()
                group.find(g['group_id'])
                group.remove_member(account.entity_id, g['operation'])
                
            ## Set expire_date (do not export data about this account)
            account.expire_date = br.now
            account.write_db()

    ## All done, remove request, commit results
        br.delete_request(request_id=r['request_id'])
        db.commit()
    return del_file
    
def keep_running():
    # If we've run for more than half an hour, it's time to go on to
    # the next task.  This check is necessary since job_runner is
    # single-threaded, and so this job will block LDAP updates
    # etc. while it is running.
    global max_requests
    max_requests -= 1
    if max_requests < 0:
        return False
    return time.time() - start_time < 15 * 60

def is_valid_request(req_id):
    # The request may have been canceled very recently
    br = BofhdRequests(db, const)
    for r in br.get_requests(request_id=req_id):
        return True
    return False

def set_operator(entity_id=None):
    if entity_id:
        db.cl_init(change_by=entity_id)
    else:
        db.cl_init(change_program='process_bofhd_r')

def main():
    global start_time, max_requests

    del_list = []
    date = "%d-%d-%d" % time.localtime()[:3]
    outfile_dir = '/cerebrum/dumps/Delete/'
    outfile = outfile_dir + str(date) + '-' + str(os.getpid()) + '-slettes.dat'
    max_requests = 999999
    start_time = time.time()

    del_list =  process_delete_requests()

    if del_list:
        stream = open(outfile, 'w')
        for i in del_list:
            stream.write(i)
            stream.write('\n')
        stream.close()

if __name__ == '__main__':
    main()


# arch-tag: 7ea2ced0-7291-11da-98b7-cafae64c692b
