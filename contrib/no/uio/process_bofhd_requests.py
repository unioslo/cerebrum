#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003-2006 University of Oslo, Norway
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

import getopt
import sys
import time
import os
import re
import mx
import imaplib

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import Constants
from Cerebrum.Utils import Factory, read_password
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio.AutoStud.Util import AutostudError
from Cerebrum.extlib import logging

db = Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")

max_requests = 999999
ou_perspective = None

# Hosts to connect to, set to None in a production environment:
debug_hostlist = None
SUDO_CMD = "/usr/bin/sudo"
ldapconns = None

EXIT_SUCCESS = 0

# TODO: now that we support multiple homedirs, we need to which one an
# operation is valid for.  This information should be stored in
# state_data, but for e-mail commands this column is already used for
# something else.  The proper solution is to change the databasetable
# and/or letting state_data be pickled.
default_spread = const.spread_uio_nis_user

class CyrusConnectError(Exception):
    pass

def email_delivery_stopped(user):
    global ldapconns
    # Delayed import so the script can run on machines without ldap
    # module
    import ldap, ldap.filter, ldap.ldapobject
    if ldapconns is None:
        ldapconns = [ldap.ldapobject.ReconnectLDAPObject("ldap://%s/" % server)
                     for server in cereconf.LDAP_SERVERS]
    userfilter = ("(&(target=%s)(mailPause=TRUE))" %
                  ldap.filter.escape_filter_chars(user))
    for conn in ldapconns:
        try:
            # FIXME: cereconf.LDAP_MAIL['dn'] has a bogus value, so we
            # must hardcode the DN.
            res = conn.search_s("cn=targets,cn=mail,dc=uio,dc=no",
                                ldap.SCOPE_ONELEVEL, userfilter, ["1.1"])
            if len(res) != 1:
                return False
        except ldap.LDAPError, e:
            logger.error("LDAP search failed: %s", e)
            return False
    return True

def get_email_hardquota(user_id):
    eq = Email.EmailQuota(db)
    try:
        eq.find_by_entity(user_id)
    except Errors.NotFoundError:
        return 0	# unlimited/no quota
    return eq.email_quota_hard


def get_email_server(account_id):
    """Return Host object for account's mail server."""
    et = Email.EmailTarget(db)
    et.find_by_entity(account_id)
    est = Email.EmailServerTarget(db)
    est.find(et.email_target_id)
    server = Email.EmailServer(db)
    server.find(est.email_server_id)
    return server

def get_home(acc, spread=None):
    if not spread:
        spread = default_spread
    try:
        tmp = acc.get_home(spread)
    except Errors.NotFoundError:
        # Unable to find a proper home directory for this user, as it
        # isn't a PosixUser.
        return None
    if tmp['home']:
        return tmp['home']
    elif tmp['disk_id'] is not None:
        disk = Factory.get('Disk')(db)
        disk.find(tmp['disk_id'])
        return "%s/%s" % (disk.path, acc.account_name)
    else:
        return None

def add_forward(user_id, addr):
    ef = Email.EmailForward(db)
    ef.find_by_entity(user_id)
    # clean up input a little
    if addr.startswith('\\'):
        addr = addr[1:]
    addr = addr.strip()

    if addr.startswith('|') or addr.startswith('"|'):
        logger.warn("forward to pipe ignored: %s", addr)
        return
    elif not addr.count('@'):
        try:
            acc = get_account(name=addr)
        except Errors.NotFoundError:
            logger.warn("forward to unknown username: %s", addr)
            return
        addr = acc.get_primary_mailaddress()
    for r in ef.get_forward():
        if r['forward_to'] == addr:
            return
    ef.add_forward(addr)
    ef.write_db()

def connect_cyrus(host=None, username=None, as_admin=True):
    """Connect to user's Cyrus and return IMAP object.  Authentication
    is always as CYRUS_ADMIN, but if as_admin is True (default),
    authorise as admin user, not username.

    It is assumed the Cyrus server accepts SASL PLAIN and SSL.
    """
    def auth_plain_cb(response):
        cyrus_pw = read_password(cereconf.CYRUS_ADMIN, cereconf.CYRUS_HOST)
        return "%s\0%s\0%s" % (username or cereconf.CYRUS_ADMIN,
                               cereconf.CYRUS_ADMIN, cyrus_pw)

    if host is None:
        assert username is not None
        try:
            acc = get_account(name=username)
            host = get_email_server(acc.entity_id).name
        except Errors.NotFoundError:
            raise CyrusConnectError("connect_cyrus: unknown user " + username)
    if as_admin:
        username = cereconf.CYRUS_ADMIN
    imapconn = imaplib.IMAP4_SSL(host=host)
    try:
        imapconn.authenticate('PLAIN', auth_plain_cb)
    except imapconn.error, e:
        raise CyrusConnectError("%s@%s: %s" % (username, host, e))
    return imapconn

def dependency_pending(dep_id):
    if not dep_id:
        return False
    br = BofhdRequests(db, const)
    for dr in br.get_requests(request_id=dep_id):
        logger.debug("waiting for request %d" % int(dep_id))
        return True
    return False

def process_email_requests():
    global start_time
    
    br = BofhdRequests(db, const)
    now = mx.DateTime.now()
    start_time = time.time()
    for r in br.get_requests(operation=const.bofh_email_create):
        logger.debug("Req: email_create %d at %s",
                     r['request_id'], r['run_at'])
        if keep_running() and r['run_at'] < now:
            hq = get_email_hardquota(r['entity_id'])
            servername = None
            if r['destination_id']:
                es = Email.EmailServer(db)
                es.find(r['destination_id'])
                servername = es.name
            if (cyrus_create(r['entity_id'], host=servername) and
                cyrus_set_quota(r['entity_id'], hq, host=servername)):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    start_time = time.time()
    for r in br.get_requests(operation=const.bofh_email_hquota):
        logger.debug("Req: email_hquota %s", r['run_at'])
        if keep_running() and r['run_at'] < now:
            hq = get_email_hardquota(r['entity_id'])
            if cyrus_set_quota(r['entity_id'], hq):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    start_time = time.time()
    for r in br.get_requests(operation=const.bofh_email_delete):
        if not is_valid_request(r['request_id']):
            continue
        logger.debug("Req: email_delete %s", r['run_at'])
        if keep_running() and r['run_at'] < now:
            try:
                uname = get_account(r['entity_id']).account_name
            except Errors.NotFoundError:
                logger.error("bofh_email_delete: %d: user not found",
                             r['entity_id'])
                br.delay_request(request_id=r['request_id'])
                db.commit()
                continue

            # The database contains the new host, so the id of the server
            # to remove from is passed in destination_id.
            server = Email.EmailServer(db)
            try:
                server.find(r['destination_id'])
            except Errors.NotFoundError:
                logger.error("bofh_email_delete: %d: target server not found",
                             r['destination_id'])
                br.delay_request(request_id=r['request_id'])
                db.commit()
                continue
            account = get_account(r['entity_id'])
            # If the account is deleted, we assume that delete_user
            # has already bumped the generation.  Othwerise, we bump
            # the generation ourself
            generation = account.get_trait(const.trait_account_generation)
            update_gen = False
            if generation:
                generation = generation['numval']
            else:
                generation = 0
            if not account.is_deleted():
                generation += 1
                update_gen = True
            if cyrus_delete(server.name, uname, generation):
                br.delete_request(request_id=r['request_id'])
                if update_gen:
                    account.populate_trait(const.trait_account_generation, numval=generation)
                    account.write_db()
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    start_time = time.time()
    for r in br.get_requests(operation=const.bofh_email_move):
        if not is_valid_request(r['request_id']):
            continue
        logger.debug("Req: email_move %s %d", r['run_at'], int(r['state_data']))
        if keep_running() and r['run_at'] < now:
            # state_data is a request-id which must complete first,
            # typically an email_create request.
            logger.debug("email_move %d, state is %r" % \
                         (r['entity_id'], r['state_data']))
            if dependency_pending(r['state_data']):
                br.delay_request(r['request_id'])
                continue 
            try:
                acc = get_account(r['entity_id'])
            except Errors.NotFoundError:
                logger.error("email_move: user %d not found", r['entity_id'])
                continue
            old_server = get_email_server(r['entity_id'])
            new_server = Email.EmailServer(db)
            new_server.find(r['destination_id'])
            if old_server.entity_id == new_server.entity_id:
                logger.error("trying to move %s from and to the same server!",
                             acc.account_name)
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue
            if not email_delivery_stopped(acc.account_name):
                logger.debug("E-mail delivery not stopped for %s",
                             acc.account_name)
                db.rollback()
                continue
            if move_email(acc, old_server, new_server):
                est = Email.EmailServerTarget(db)
                est.find_by_entity(acc.entity_id)
                est.populate(new_server.entity_id)
                est.write_db()
                br.delete_request(request_id=r['request_id'])
                br.add_request(r['requestee_id'], r['run_at'],
                               const.bofh_email_delete,
                               r['entity_id'], old_server.entity_id)
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()
        
def cyrus_create(user_id, host=None):
    try:
        uname = get_account(user_id).account_name
    except Errors.NotFoundError:
        logger.error("cyrus_create: %d not found", user_id)
        return False
    try:
        cyradm = connect_cyrus(host=host, username=uname)
        cyr = connect_cyrus(host=host, username=uname, as_admin=False)
    except CyrusConnectError, e:
        logger.error("cyrus_create: %s", e)
        return False
    status = True
    for sub in ("", ".spam", ".Sent", ".Drafts", ".Trash", ".Templates"):
        res, folders = cyradm.list('user.', pattern=uname+sub)
        if res == 'OK' and folders[0]:
            continue
        mbox = 'user.%s%s' % (uname, sub)
        res, msg = cyradm.create(mbox)
        if res != 'OK':
            logger.error("IMAP create %s failed: %s", mbox, msg)
            status = False
            break
        res, msg = cyr.subscribe(mbox)
        if res != 'OK':
            # We don't consider this fatal, but we want to know about
            # problems.
            logger.warn("IMAP subscribe %s failed: %s", mbox, msg)
    else:
        logger.debug("cyrus_create: %s successful", uname)
    cyradm.logout()
    cyr.logout()
    
    return status

def cyrus_delete(host, uname, generation):
    logger.debug("will delete %s from %s", uname, host)
    # Backup Cyrus data before deleting it.
    if not archive_cyrus_data(uname, host, generation):
        logger.error("bofh_email_delete: Archival of Cyrus data failed.")
        return False
    try:
        cyradm = connect_cyrus(host=host)
    except CyrusConnectError, e:
        logger.error("bofh_email_delete: %s: %s" % (host, e))
        return False
    res, listresp = cyradm.list("user.", pattern=uname)
    if res <> 'OK' or listresp[0] == None:
        logger.error("bofh_email_delete: %s: no mailboxes", uname)
        cyradm.logout()
        return True
    folders = ["user.%s" % uname]
    res, listresp = cyradm.list("user.%s." % uname)
    if res == 'OK' and listresp[0]:
        for line in listresp:
            m = re.match(r'^\(.*?\) ".*?" "(.*)"$', line)
            folders += [ m.group(1) ]
    # Make sure the subfolders are deleted first by reversing the
    # sorted list.
    folders.sort()
    folders.reverse()
    for folder in folders:
        logger.debug("deleting %s ... ", folder)
        cyradm.setacl(folder, cereconf.CYRUS_ADMIN, 'c')
        res = cyradm.delete(folder)
        if res[0] <> 'OK':
            logger.error("IMAP delete %s failed: %s", folder, res[1])
            cyradm.logout()
            return False
    cyradm.logout()
    return True

def cyrus_set_quota(user_id, hq, host=None):
    try:
        uname = get_account(user_id).account_name
    except Errors.NotFoundError:
        logger.error("cyrus_set_quota: %d: user not found", user_id)
        return False
    try:
        cyradm = connect_cyrus(username=uname, host=host)
    except CyrusConnectError, e:
        logger.error("cyrus_set_quota(%s, %d): %s" % (uname, hq, e))
        return False
    res, msg = cyradm.setquota("user.%s" % uname, '(STORAGE %d)' % (hq * 1024))
    logger.debug("cyrus_set_quota(%s, %d): %s" % (uname, hq, repr(res)))
    return res == 'OK'

def archive_cyrus_data(uname, mail_server, generation):
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'archivemail',
           mail_server, uname, generation]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    errnum = EXIT_SUCCESS
    if debug_hostlist is None or mail_server in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    if errnum == EXIT_SUCCESS:
        return True
    logger.error("%s returned %i", cmd, errnum)
    return False

def move_email(acc, src, dest):
    """Copy e-mail for Account acc from EmailServer src to EmailServer
    dest.  The servers must support IMAP.
    
    """
    if (dest.email_server_type != const.email_server_type_cyrus or
        src.email_server_type != const.email_server_type_cyrus):
        logger.error("move_email: unsupported server type (%s or %s)",
                     src.name, dest.name)
        return False

    pwfile = os.path.join(cereconf.DB_AUTH_DIR,
                          'passwd-%s@%s' % (cereconf.CYRUS_ADMIN,
                                            cereconf.CYRUS_HOST))
    cmd = [cereconf.IMAPSYNC_SCRIPT,
           '--user1', acc.account_name, '--host1', src.name,
           '--user2', acc.account_name, '--host2', dest.name,
           '--authusing', cereconf.CYRUS_ADMIN,
           '--passfile1', pwfile,
           '--useheader', 'Message-ID',
           '--regexmess', 's/\\0/ /g',
           '--ssl', '--subscribe', '--nofoldersizes']
    logger.debug("doing %s" % cmd)
    errnum = EXIT_SUCCESS
    if debug_hostlist is None or (src.name in debug_hostlist and
                                  dest.name in debug_hostlist):
        errnum = spawn_and_log_output(cmd)
    if errnum == EXIT_SUCCESS:
        logger.info('%s: imapsync completed successfully',
                    acc.account_name)
    else:
        logger.error('move mail failed, returned %d' % errnum)
        return False
    cmd = [cereconf.MANAGESIEVE_SCRIPT,
           '-v', '-a', cereconf.CYRUS_ADMIN, '-p', pwfile,
           acc.account_name, src.name, dest.name]
    logger.debug("doing %s" % cmd)
    errnum = EXIT_SUCCESS
    if debug_hostlist is None or (src.name in debug_hostlist and
                                  dest.name in debug_hostlist):
        errnum = spawn_and_log_output(cmd)
    if errnum == EXIT_SUCCESS:
        logger.info('%s: managesieve_sync completed successfully',
                    acc.account_name)
    else:
        logger.error('move sieve failed, returned %d' % errnum)
        return False
    return True


def process_mailman_requests():
    br = BofhdRequests(db, const)
    now = mx.DateTime.now()
    for r in br.get_requests(operation=const.bofh_mailman_create):
        if not is_valid_request(r['request_id']):
            continue
        logger.debug("Req: mailman_create %d at %s",
                     r['request_id'], r['run_at'])
        if keep_running() and r['run_at'] < now:
            try:
                listname = get_address(r['entity_id'])
            except Errors.NotFoundError:
                logger.warn("List address %s deleted!  It probably wasn't "+
                            "needed anyway.", listname)
                br.delete_request(request_id=r['request_id'])
                continue
            try:
                admin = get_address(r['destination_id'])
            except Errors.NotFoundError:
                logger.error("Admin address deleted for %s!  Ask postmaster "+
                             "to create list manually.", listname)
                br.delete_request(request_id=r['request_id'])
                continue
            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c',
                   'mailman', 'newlist', listname, admin ];
            logger.debug(repr(cmd))
            errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
            logger.debug("returned %d", errnum)
            if errnum == EXIT_SUCCESS:
                logger.debug("delete %d", r['request_id'])
                br.delete_request(request_id=r['request_id'])
                db.commit()
            else:
                logger.error("bofh_mailman_create: %s: returned %d" %
                             (listname, errnum))
                br.delay_request(r['request_id'])
    for r in br.get_requests(operation=const.bofh_mailman_add_admin):
        if not is_valid_request(r['request_id']):
            continue
        logger.debug("Req: mailman_add_admin %d at %s",
                     r['request_id'], r['run_at'])
        if keep_running() and r['run_at'] < now:
            if dependency_pending(r['state_data']):
                br.delay_request(r['request_id'])
                continue 
            listname = get_address(r['entity_id'])
            admin = get_address(r['destination_id'])
            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c',
                   'mailman', 'add_admin', listname, admin ];
            errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
            if errnum == EXIT_SUCCESS:
                br.delete_request(request_id=r['request_id'])
                db.commit()
            else:
                logger.error("bofh_mailman_admin_add: %s: returned %d" %
                             (listname, errnum))
                br.delay_request(r['request_id'])
    for r in br.get_requests(operation=const.bofh_mailman_remove):
        if not is_valid_request(r['request_id']):
            continue
        logger.debug("Req: mailman_remove %d at %s",
                     r['request_id'], r['run_at'])
        if keep_running() and r['run_at'] < now:
            listname = r['state_data']
            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c',
                   'mailman', 'rmlist', listname, "dummy" ];
            errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
            if errnum == EXIT_SUCCESS:
                br.delete_request(request_id=r['request_id'])
                db.commit()
            else:
                logger.error("bofh_mailman_remove: %s: returned %d" %
                             (listname, errnum))
                br.delay_request(r['request_id'])

def get_address(address_id):
    ea = Email.EmailAddress(db)
    ea.find(address_id)
    ed = Email.EmailDomain(db)
    ed.find(ea.email_addr_domain_id)
    return "%s@%s" % (ea.email_addr_local_part,
                      ed.rewrite_special_domains(ed.email_domain_name))

def is_ok_batch_time(now):
    times = cereconf.LEGAL_BATCH_MOVE_TIMES.split('-')
    if times[0] > times[1]:   #  Like '20:00-08:00'
        if now > times[0] or now < times[1]:
            return True
    else:                     #  Like '08:00-20:00'
        if now > times[0] and now < times[1]:
            return True
    return False

def log_output(fileobj, logfunc):
    """Read lines from fileobj without buffering, strip trailing
    whitespace, and call func on each line.

    """
    # We use file.readline since file.__iter__ buffers input
    while True:
        line = fileobj.readline()
        if line == '':
            break
        logfunc(line.rstrip())

def spawn_and_log_output(cmd):
    """Run command and copy stdout to logger.info and stderr to
    logger.error.  cmd may be a sequence.

    """
    # Popen3 only works on Unix.  Now you know.
    from popen2 import Popen3
    proc = Popen3(cmd, capturestderr=True, bufsize=10240)
    proc.tochild.close()
    # FIXME: The process will block if it outputs more than 10 KiB on
    # stderr.
    log_output(proc.fromchild, logger.debug)
    log_output(proc.childerr, logger.error)
    return proc.wait() >> 8

def process_move_requests():
    br = BofhdRequests(db, const)
    now = mx.DateTime.now()
    requests = br.get_requests(operation=const.bofh_move_user_now)
    if is_ok_batch_time(time.strftime("%H:%M")):
        process_move_student_requests() # generates bofh_move_user requests
        requests.extend(br.get_requests(operation=const.bofh_move_user))    
    for r in requests:
        if not is_valid_request(r['request_id']):
            continue
        if keep_running() and r['run_at'] < now:
            logger.debug("Req %d: bofh_move_user %d",
                         r['request_id'], r['entity_id'])
            try:
                account, uname, old_host, old_disk = get_account_and_home(
                    r['entity_id'], type='PosixUser', spread=r['state_data'])
                new_host, new_disk  = get_disk(r['destination_id'])
            except Errors.NotFoundError:
                logger.error("move_request: user %i not found" % r['entity_id'])
                continue
            if account.is_expired():
                logger.warn("Account %s is expired, cancelling request" %
                            account.account_name)
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue
            set_operator(r['requestee_id'])
            try:
                operator = get_account(r['requestee_id']).account_name
            except Errors.NotFoundError:
                # The mvuser script requires a valid address here.  We
                # may want to change this later.
                operator = "cerebrum"
            group = get_group(account.gid_id, grtype='PosixGroup')

            spread = ",".join(["%s" % Constants._SpreadCode(int(a['spread']))
                               for a in account.get_spread()]),
            if move_user(uname, int(account.posix_uid), int(group.posix_gid),
                         old_host, old_disk, new_host, new_disk, spread,
                         operator):
                logger.debug('user %s moved from %s to %s' %
                             (uname,old_disk,new_disk))
                ah = account.get_home(default_spread)
                account.set_homedir(current_id=ah['homedir_id'],
                                    disk_id=r['destination_id'])
                account.write_db()
                br.delete_request(request_id=r['request_id'])
            else:
                if new_disk == old_disk:
                    br.delete_request(request_id=r['request_id'])
                else:
                    br.delay_request(r['request_id'], minutes=24*60)
            db.commit()

def process_move_student_requests():
    global fnr2move_student, autostud
    br = BofhdRequests(db, const)
    rows = br.get_requests(operation=const.bofh_move_student)
    if not rows:
        return
    logger.debug("Preparing autostud framework")
    autostud = AutoStud.AutoStud(db, logger, debug=False,
                                 cfg_file=studconfig_file,
                                 studieprogs_file=studieprogs_file,
                                 emne_info_file=emne_info_file,
                                 ou_perspective=ou_perspective)

    # Hent ut personens fødselsnummer + account_id
    fnr2move_student = {}
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)
    for r in rows:
        if not is_valid_request(r['request_id']):
            continue
        account.clear()
        account.find(r['entity_id'])
        person.clear()
        person.find(account.owner_id)
        fnr = person.get_external_id(id_type=const.externalid_fodselsnr,
                                     source_system=const.system_fs)
        if not fnr:
            logger.warn("Not student fnr for: %i" % account.entity_id)
            br.delete_request(request_id=r['request_id'])
            db.commit()
            continue
        fnr = fnr[0]['external_id']
        if not fnr2move_student.has_key(fnr):
            fnr2move_student[fnr] = []
        fnr2move_student[fnr].append((
            int(account.entity_id), int(r['request_id']),
            int(r['requestee_id'])))
    logger.debug("Starting callbacks to find: %s" % fnr2move_student)
    autostud.start_student_callbacks(
        student_info_file, move_student_callback)

    # Move remaining users to pending disk
    disk = Factory.get('Disk')(db)
    disk.find_by_path(cereconf.AUTOSTUD_PENDING_DISK)
    logger.debug(str(fnr2move_student.values()))
    for tmp_stud in fnr2move_student.values():
        for account_id, request_id, requestee_id in tmp_stud:
            logger.debug("Sending %s to pending disk" % repr(account_id))
            br.delete_request(request_id=request_id)
            br.add_request(requestee_id, br.batch_time,
                           const.bofh_move_user,
                           account_id, disk.entity_id,
                           state_data=int(default_spread))
            db.commit()

class NextAccount(Exception):
    pass

def move_student_callback(person_info):
    """We will only move the student if it has a valid fnr from FS,
    and it is not currently on a student disk.

    If the new homedir cannot be determined, user will be moved to a
    pending disk.  process_students moves users from this disk as soon
    as a proper disk can be determined.

    Currently we only operate on the disk whose spread is
    default_spread"""

    fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                              int(person_info['personnr'])))
    if not fnr2move_student.has_key(fnr):
        return
    logger.debug("Callback for %s" % fnr)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    br = BofhdRequests(db, const)
    for account_id, request_id, requestee_id in fnr2move_student.get(fnr, []):
        account.clear()
        account.find(account_id)
        groups = []
        for r in group.list_groups_with_entity(account_id):
            groups.append(int(r['group_id']))
        try:
            profile = autostud.get_profile(person_info, member_groups=groups)
            logger.debug(profile.matcher.debug_dump())
        except AutostudError, msg:
            logger.debug("Error getting profile, using pending: %s" % msg)
            continue

        # Determine disk
        disks = []
        spreads = [int(s) for s in profile.get_spreads()]
        try:
            for d_spread in profile.get_disk_spreads():
                if d_spread != default_spread:
                    # TBD:  How can all spreads be taken into account?
                    continue
                if d_spread in spreads:
                    try:
                        ah = account.get_home(d_spread)
                        homedir_id = ah['homedir_id']
                        current_disk_id = ah['disk_id']
                    except Errors.NotFoundError:
                        homedir_id, current_disk_id = None, None
                    if autostud.disk_tool.get_diskdef_by_diskid(int(current_disk_id)):
                        logger.debug("Already on a student disk")
                        br.delete_request(request_id=request_id)
                        db.commit()
                        # actually, we remove a bit too much data from
                        # the below dict, but remaining data will be
                        # rebuilt on next run.
                        
                        del(fnr2move_student[fnr])
                        raise NextAccount
                    try:
                        new_disk = profile.get_disk(d_spread, current_disk_id,
                                                    do_check_move_ok=False)
                        if new_disk == current_disk_id:
                            continue
                        disks.append((new_disk, d_spread))
                        if (autostud.disk_tool.using_disk_kvote and
                            homedir_id is not None):
                            # Delay import as non-uio people may use this script
                            from Cerebrum.modules.no.uio import DiskQuota
                            
                            disk_quota_obj = DiskQuota.DiskQuota(db)
                            try:
                                cur_quota = disk_quota_obj.get_quota(homedir_id)
                            except Errors.NotFoundError:
                                cur_quota = None
                            quota = profile.get_disk_kvote(new_disk)
                            if cur_quota is None or cur_quota['quota'] != int(quota):
                                disk_quota_obj.set_quota(homedir_id, quota=int(quota))
                    except AutostudError, msg:
                        # Will end up on pending (since we only use one spread)
                        logger.debug("Error getting disk: %s" % msg)
                        break
        except NextAccount:
            pass   # Stupid python don't have labeled breaks
        logger.debug(str((fnr, account_id, disks)))
        if disks:
            logger.debug("Destination %s" % repr(disks))
            del(fnr2move_student[fnr])
            for disk, spread in disks:
                br.delete_request(request_id=request_id)
                br.add_request(requestee_id, br.batch_time,
                               const.bofh_move_user,
                               account_id, disk, state_data=spread)
                db.commit()

def process_quarantine_refresh_requests():
    """process_changes.py has added bofh_quarantine_refresh for the
    start/disable/end dates for the quarantines.  Register a
    quarantine_refresh change-log event so that changelog-based
    quicksync script can revalidate the quarantines."""

    br = BofhdRequests(db, const)
    now = mx.DateTime.now()
    for r in br.get_requests(operation=const.bofh_quarantine_refresh):
        if r['run_at'] > now:
            continue
        set_operator(r['requestee_id'])
        db.log_change(r['entity_id'], const.quarantine_refresh, None)
        br.delete_request(request_id=r['request_id'])
        db.commit()

def process_delete_requests():
    br = BofhdRequests(db, const)
    now = mx.DateTime.now()
    group = Factory.get('Group')(db)
    spread = default_spread # TODO: check spread in r['state_data']

    for r in br.get_requests(operation=const.bofh_archive_user):
        if not is_valid_request(r['request_id']):
            continue
        if not keep_running():
            break
        if r['run_at'] > now:
            continue
        account, uname, old_host, old_disk = \
                 get_account_and_home(r['entity_id'], spread=spread)
        operator = get_account(r['requestee_id']).account_name
        if delete_user(uname, old_host, '%s/%s' % (old_disk, uname),
                       operator, ''):
            try:
                home = account.get_home(spread)
            except Errors.NotFoundError:
                pass
            else:
                account.set_homedir(current_id=home['homedir_id'],
                                    status=const.home_status_archived)
            br.delete_request(request_id=r['request_id'])
            db.commit()
        else:
            db.rollback()
            br.delay_request(r['request_id'], minutes=120)
            db.commit()
        
    for r in br.get_requests(operation=const.bofh_delete_user):
        if not is_valid_request(r['request_id']):
            continue
        if not keep_running():
            break
        if r['run_at'] > now:
            continue
        is_posix = False
        try:
            account, uname, old_host, old_disk = get_account_and_home(
                r['entity_id'], spread=spread, type='PosixUser')
            is_posix = True
        except Errors.NotFoundError:
            account, uname, old_host, old_disk = get_account_and_home(
                r['entity_id'], spread=spread)
        if account.is_deleted():
            logger.warn("%s is already deleted" % uname)
            br.delete_request(request_id=r['request_id'])
            db.commit()
            continue
        set_operator(r['requestee_id'])
        operator = get_account(r['requestee_id']).account_name
        est = Email.EmailServerTarget(db)
        try:
            est.find_by_entity(account.entity_id)
        except Errors.NotFoundError:
            mail_server = ''
        else:
            es = Email.EmailServer(db)
            es.find(est.email_server_id)
            mail_server = es.name

        if delete_user(uname, old_host, '%s/%s' % (old_disk, uname), operator,
                       mail_server):
            if is_posix:
                # demote the user first to avoid problems with
                # PosixUsers with names illegal for PosixUsers
                account.delete_posixuser()
                account_id = account.entity_id
                account = Factory.get('Account')(db)
                account.find(account_id)
            account.expire_date = br.now
            account.write_db()
            try:
                home = account.get_home(spread)
            except Errors.NotFoundError:
                pass
            else:
                account.set_homedir(current_id=home['homedir_id'],
                                    status=const.home_status_archived)
            # Remove references in other tables
            # Note that we preserve the quarantines for deleted users
            # TBD: Should we have an API function for this?
            for s in account.get_spread():
                account.delete_spread(s['spread'])
            for g in group.list_groups_with_entity(account.entity_id):
                group.clear()
                group.find(g['group_id'])
                group.remove_member(account.entity_id, g['operation'])
            br.delete_request(request_id=r['request_id'])
            db.log_change(r['entity_id'], const.account_delete, None)
            db.commit()
        else:
            db.rollback()
            br.delay_request(r['request_id'], minutes=120)
            db.commit()

def delete_user(uname, old_host, old_home, operator, mail_server):
    account = get_account(name=uname)
    generation = account.get_trait(const.trait_account_generation)
    if generation:
        generation = generation['numval'] + 1
    else:
        generation = 1
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'aruser', uname,
           operator, old_home, mail_server, generation]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    errnum = EXIT_SUCCESS
    if debug_hostlist is None or old_host in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    if errnum == EXIT_SUCCESS:
        account.populate_trait(
            const.trait_account_generation, numval=generation)
        account.write_db()
        return True
    logger.error("%s returned %i" % (cmd, errnum))
    return False

def move_user(uname, uid, gid, old_host, old_disk, new_host, new_disk, spread,
              operator):
    mailto = operator
    # Last argument is "on_mailspool?" and obsolete
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'mvuser', uname, uid, gid,
           old_disk, new_disk, spread, mailto, 0]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    errnum = EXIT_SUCCESS
    if debug_hostlist is None or (old_host in debug_hostlist and
                                  new_host in debug_hostlist):
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    if errnum == EXIT_SUCCESS:
        return True
    logger.error("%s returned %i" % (cmd, errnum))
    return False

def set_operator(entity_id=None):
    if entity_id:
        db.cl_init(change_by=entity_id)
    else:
        db.cl_init(change_program='process_bofhd_r')

def get_disk(disk_id):
    disk = Factory.get('Disk')(db)
    disk.clear()
    disk.find(disk_id)
    host = Factory.get('Host')(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path

def get_account(account_id=None, name=None):
    assert account_id or name
    acc = Factory.get('Account')(db)
    if account_id:
        acc.find(account_id)
    elif name:
        acc.find_by_name(name)
    return acc

def get_account_and_home(account_id, type='Account', spread=None):
    if type == 'Account':
        account = Factory.get('Account')(db)
    elif type == 'PosixUser':
        account = PosixUser.PosixUser(db)        
    account.clear()
    account.find(account_id)
    if spread is None:
        spread = default_spread
    uname = account.account_name
    try:
        home = account.get_home(spread)
    except Errors.NotFoundError:
        return account, uname, None, None
    if home['home'] is None:
        if home['disk_id'] is None:
            return account, uname, None, None
        host, home = get_disk(home['disk_id'])
    else:
        host = None  # TODO:  How should we handle this?
        home = home['home']
    return account, uname, host, home

def get_group(id, grtype="Group"):
    if grtype == "Group":
        group = Factory.get('Group')(db)
    elif grtype == "PosixGroup":
        group = PosixGroup.PosixGroup(db)
    group.clear()
    group.find(id)
    return group

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

def main():
    global start_time, max_requests
    global ou_perspective, emne_info_file, studconfig_file, \
           studieprogs_file, student_info_file
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dpt:m:',
                                   ['debug', 'process', 'type=', 'max=',
                                    'ou-perspective=',
                                    'emne-info-file=','studconfig-file=',
                                    'studie-progs-file=',
                                    'student-info-file='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    types = []
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            print "debug mode has not been implemented"
            sys.exit(1)
        elif opt in ('-t', '--type',):
            types.append(val)
        elif opt in ('-m', '--max',):
            max_requests = int(val)
        elif opt in ('-p', '--process'):
            if not types:
                types = ['delete', 'move', 'email', 'mailman']
            # We set start_time for each type of requests, so that a
            # lot of home directory moves won't stop e-mail requests
            # from being processed in a timely manner.
            for t in types:
                start_time = time.time()
                func = globals()["process_%s_requests" % t]
                set_operator()
                apply(func)
        elif opt in ('--ou-perspective',):
            ou_perspective = const.OUPerspective(val)
            int(ou_perspective)   # Assert that it is defined
        elif opt in ('--emne-info-file',):
            emne_info_file = val
        elif opt in ('--studconfig-file',):
            studconfig_file = val
        elif opt in ('--studie-progs-file',):
            studieprogs_file = val
        elif opt in ('--student-info-file',):
            student_info_file = val

def usage(exitcode=0):
    print """Usage: process_bofhd_requests.py
    -d | --debug: turn on debugging
    -p | --process: perform the queued operations
    -t | --type type: performe queued operations of this type.  May be
         repeated, and must be preceeded by -p
    -m | --max val: perform up to this number of requests

    Legal values for --type:
      email
      mailman
      move
      move_student
      quarantine_refresh
      delete

    Needed for move_student requests:
    --ou-perspective code_str: set ou_perspective (default: perspective_fs)
    --emne-info-file file:
    --studconfig-file file:
    --studie-progs-file file:
    --student-info-file file:
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 51f90579-3b28-439f-867f-34c14ac97b10
