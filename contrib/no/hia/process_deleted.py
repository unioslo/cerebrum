#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2005-2017 University of Oslo, Norway
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
This is a HiA-spesific cerebrum related script that processes
account-deletion requests registered in Cerebrum.
When an account is deleted a delete request is registered in
'bofhd_requests'. The following is done by this script:




nis  : write "deleted" file
       <uname>:<crypt>:<uid>:<gid>:<gecos>:<home>:<shell>
       for both nis and nisans, account@nis/nisans removed
ad   : account@ad spread removed
email: write file (<uname>:<email_server>), account@imap spread removed
other spreads: removed

TODO: this script must be more robust and pretty (but first we make it work)
"""


import time
import os
import mx
import string

from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import BofhdRequests


logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)
max_requests = None
start_time = None


def process_delete_requests():
    br = BofhdRequests(db, const)
    now = mx.DateTime.now()
    del_file = []
    group = Factory.get('Group')(db)
    account = Factory.get('Account')(db)
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
        logger.info("Trying to delete account %s", account.account_name)

        blockers = account.get_delete_blockers(ignore_group_memberships=True)
        if blockers:
            logger.error('Manual cleaning required: '
                         'Deleting account %s is blocked by: %s',
                         account.account_name, ', '.join(blockers))
            continue
        set_operator(r['requestee_id'])
        # Set expire_date (do not export data about this account)
        account.expire_date = br.now
        logger.debug("expire_date for %s registered as %s",
                     account.account_name, br.now)
        account.write_db()
        # check for posix attrs
        posix_user = Factory.get('PosixUser')(db)
        posix_user.clear()
        try:
            posix_user.find(r['entity_id'])
        except Errors.NotFoundError:
            posix_user = None

        # Deal with all the systems that account data is exported to
        spreads = account.get_spread()
        logger.debug("Fetched all spreads for %s, %s",
                     account.account_name, spreads)
        for row in spreads:
            # Account is valid in AD, remove account@ad spread
            if row['spread'] == const.spread_hia_ad_account:
                try:
                    home = account.get_home(row['spread'])
                    account.set_homedir(current_id=home['homedir_id'],
                                        status=const.home_status_archived)
                    account.clear_home(row['spread'])
                except Errors.NotFoundError:
                    logger.debug("No home in AD for %s, will remove spread to "
                                 "AD only.", account.account_name)
                account.delete_spread(row['spread'])
                logger.debug("Deleted account@ad spread for %s",
                             account.account_name)
            # student-accounts usually have account@ldap, remove this
            elif row['spread'] == const.spread_ldap_account:
                account.delete_spread(row['spread'])
                logger.debug("Deleted account@ldap spread for %s",
                             account.account_name)
            # An email account exists, remove account@imap spread,
            # register email account delete
            elif row['spread'] == const.spread_hia_email:
                et = Email.EmailTarget(db)
                try:
                    et.find_by_target_entity(account.entity_id)
                except Errors.NotFoundError:
                    logger.warn('No email target for %s, removing imap spread '
                                'only.', account.account_name)
                logger.debug("Found e-mail target for %s",
                             account.account_name)
                if et:
                    es = Email.EmailServer(db)
                    es.find(et.email_server_id)
                    del_file.append('EMAIL:' + account.account_name + ':' +
                                    es.name)
                    et.email_target_type = const.email_target_deleted
                    et.write_db()
                account.delete_spread(row['spread'])
            elif row['spread'] in (const.spread_exchange_account,
                                   const.spread_exchange_acc_old):
                et = Email.EmailTarget(db)
                try:
                    et.find_by_target_entity(account.entity_id)
                except Errors.NotFoundError:
                    logger.warn('No email target for %s, will remove exchange '
                                'spread.', account.account_name)
                if et:
                    et.email_target_type = const.email_target_deleted
                    et.write_db()
                    logger.info("Deleted e-mail target for %s",
                                account.account_name)
                account.delete_spread(row['spread'])
            # Account is valid in nis@hia, remove account@nis spread,
            # register nis-home delete
            elif row['spread'] == const.spread_nis_user:
                if not isinstance(posix_user, Factory.get('PosixUser')):
                    logger.error("Manual intervention required, no posix "
                                 "account is found for account %s",
                                 account.account_name)
                    continue
                posix_home = posix_user.get_posix_home(row['spread'])
                uid = posix_user.posix_uid
                gid = posix_user.gid_id
                shell = posix_user.shell
                line = string.join([account.account_name, pwd, str(uid),
                                    str(gid), gecos, posix_home,
                                    str(shell)], ':')
                line = 'NIS:' + line
                del_file.append(line)
                try:
                    home = account.get_home(row['spread'])
                except Errors.NotFoundError:
                    continue
                account.set_homedir(current_id=home['homedir_id'],
                                    status=const.home_status_archived)
                logger.debug("Set home to archived %s (%s)",
                             home['homedir_id'], row['spread'])
                account.clear_home(row['spread'])
                logger.debug("clear_home in %s", row['spread'])
                account.delete_spread(row['spread'])
            else:
                account.delete_spread(row['spread'])
        if posix_user:
            posix_user.delete_posixuser()

        # Remove account from all groups
        for g in group.search(member_id=account.entity_id,
                              indirect_members=False):
            group.clear()
            group.find(g['group_id'])
            group.remove_member(account.entity_id)
        # All done, remove request, commit results
        account.write_db()
        if posix_user:
            posix_user.write_db()
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
    outfile_dir = '/cerebrum/var/cache/Delete/'
    outfile = outfile_dir + str(date) + '-' + str(os.getpid()) + '-slettes.dat'
    max_requests = 999999
    start_time = time.time()

    del_list = process_delete_requests()

    if del_list:
        stream = open(outfile, 'w')
        for i in del_list:
            stream.write(i)
            stream.write('\n')
        stream.close()

if __name__ == '__main__':
    main()
