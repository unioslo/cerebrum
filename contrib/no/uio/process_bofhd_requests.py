#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2016 University of Oslo, Norway
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

from __future__ import unicode_literals

import errno
import fcntl
import getopt
import mx
import os
import pickle
import re
import sys
import time
import socket
import ssl
import subprocess
from select import select
from contextlib import closing

import cereconf

from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules import PosixGroup

from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio.AutoStud.Util import AutostudError

logger = Utils.Factory.get_logger("bofhd_req")
db = Utils.Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
cl_const = Utils.Factory.get('CLConstants')(db)
const = Utils.Factory.get('Constants')(db)

max_requests = 999999
ou_perspective = None

SSH_CMD = "/usr/bin/ssh"
SUDO_CMD = "sudo"
SSH_CEREBELLUM = [SSH_CMD, "cerebrum@cerebellum"]

ldapconns = None

DEBUG = False
EXIT_SUCCESS = 0

studconfig_file = studieprogs_file = emne_info_file = student_info_file = None
fnr2move_student = autostud = None

# TODO: now that we support multiple homedirs, we need to which one an
# operation is valid for.  This information should be stored in
# state_data, but for e-mail commands this column is already used for
# something else.  The proper solution is to change the databasetable
# and/or letting state_data be pickled.
default_spread = const.spread_uio_nis_user


class RequestLocked(Exception):
    pass


class RequestLockHandler(object):
    def __init__(self, lockdir=None):
        """lockdir should be a template holding exactly one %d."""
        if lockdir is None:
            lockdir = cereconf.BOFHD_REQUEST_LOCK_DIR
        self.lockdir = lockdir
        self.lockfd = None

    def grab(self, reqid):
        """Release the old lock if one is held, then grab the lock
        corresponding to reqid.  Returns False if it fails.

        """
        if self.lockfd is not None:
            self.close()

        self.reqid = reqid
        try:
            lockfile = file(self.lockdir % reqid, "wb")
        except IOError, e:
            logger.error("Checking lock for %d failed: %s", reqid, e)
            return False
        try:
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError, e:
            if e.errno == errno.EAGAIN:
                logger.debug("Skipping locked request %d", reqid)
            else:
                logger.error("Locking request %d failed: %s", reqid, e)
            return False
        self.lockfd = lockfile
        return True

    def close(self):
        """Release and clean up lock."""
        if self.lockfd is not None:
            fcntl.flock(self.lockfd, fcntl.LOCK_UN)
            # There's a potential race here (someone else can grab and
            # release this lock before the unlink), but users of this
            # class should remove the request from the todo list
            # before releasing the lock.
            os.unlink(self.lockdir % self.reqid)
            self.lockfd = None


class CyrusConnectError(Exception):
    pass


def email_delivery_stopped(user):
    global ldapconns
    import ldap
    import ldap.filter
    import ldap.ldapobject
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


def get_email_hardquota(user_id, local_db=db):
    eq = Email.EmailQuota(local_db)
    try:
        eq.find_by_target_entity(user_id)
    except Errors.NotFoundError:
        # unlimited/no quota
        return 0
    return eq.email_quota_hard


def get_email_server(account_id, local_db=db):
    """Return Host object for account's mail server."""
    et = Email.EmailTarget(local_db)
    et.find_by_target_entity(account_id)
    server = Email.EmailServer(local_db)
    server.find(et.email_server_id)
    return server


def get_home(acc, spread=None):
    if not spread:
        spread = default_spread
    try:
        return acc.get_homepath(spread)
    except Errors.NotFoundError:
        return None


def add_forward(user_id, addr):
    ef = Email.EmailForward(db)
    ef.find_by_target_entity(user_id)
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
        cyrus_pw = Utils.read_password(cereconf.CYRUS_ADMIN,
                                       cereconf.CYRUS_HOST)
        return "%s\0%s\0%s" % (username or cereconf.CYRUS_ADMIN,
                               cereconf.CYRUS_ADMIN, cyrus_pw)

    if as_admin:
        username = cereconf.CYRUS_ADMIN
    try:
        imapconn = Utils.CerebrumIMAP4_SSL(
            host=host.name,
            ssl_version=ssl.PROTOCOL_TLSv1)
    except socket.gaierror as e:
        raise CyrusConnectError("%s@%s: %s" % (username, host.name, e))
    try:
        imapconn.authenticate('PLAIN', auth_plain_cb)
    except (imapconn.error, socket.error) as e:
        raise CyrusConnectError("%s@%s: %s" % (username, host.name, e))
    return imapconn


def dependency_pending(dep_id, local_db=db, local_co=const):
    if not dep_id:
        return False
    br = BofhdRequests(local_db, local_co)
    for dr in br.get_requests(request_id=dep_id):
        logger.debug("waiting for request %d" % int(dep_id))
        return True
    return False


def process_requests(types):
    global max_requests

    operations = {
        'quarantine':
        [(const.bofh_quarantine_refresh, proc_quarantine_refresh, 0)],
        'delete':
        [(const.bofh_archive_user, proc_archive_user, 2*60),
         (const.bofh_delete_user, proc_delete_user, 2*60)],
        'move':
        [(const.bofh_move_user_now, proc_move_user, 24*60),
         (const.bofh_move_user, proc_move_user, 24*60)],
        'email':
        [(const.bofh_email_create, proc_email_create, 0),
         (const.bofh_email_hquota, proc_email_hquota, 0),
         (const.bofh_email_delete, proc_email_delete, 4*60),
         ],
        'sympa':
        [(const.bofh_sympa_create, proc_sympa_create, 2*60),
         (const.bofh_sympa_remove, proc_sympa_remove, 2*60)],
        }
    """Each type (or category) of requests consists of a list of which
    requests to process.  The tuples are operation, processing function,
    and how long to delay the request (in minutes) if the function returns
    False.

    """

    # TODO: There is no variable containing the default log directory
    # in cereconf

    with closing(RequestLockHandler()) as reqlock:
        br = BofhdRequests(db, const)
        for t in types:
            if t == 'move' and is_ok_batch_time(time.strftime("%H:%M")):
                # convert move_student into move_user requests
                process_move_student_requests()
            if t == 'email':
                process_email_move_requests()
            for op, process, delay in operations[t]:
                set_operator()
                start_time = time.time()
                for r in br.get_requests(operation=op, only_runnable=True):
                    reqid = r['request_id']
                    logger.debug("Req: %s %d at %s, state %r",
                                 op, reqid, r['run_at'], r['state_data'])
                    if time.time() - start_time > 30 * 60:
                        break
                    if r['run_at'] > mx.DateTime.now():
                        continue
                    if not is_valid_request(reqid):
                        continue
                    if reqlock.grab(reqid):
                        if max_requests <= 0:
                            break
                        max_requests -= 1
                        if process(r):
                            br.delete_request(request_id=reqid)
                            db.commit()
                        else:
                            db.rollback()
                            if delay:
                                br.delay_request(reqid, minutes=delay)
                                db.commit()


def proc_email_create(r):
    hq = get_email_hardquota(r['entity_id'])
    es = None
    if r['destination_id']:
        es = Email.EmailServer(db)
        es.find(r['destination_id'])
    return (cyrus_create(r['entity_id'], host=es) and
            cyrus_set_quota(r['entity_id'], hq, host=es))


def proc_email_hquota(r):
    hq = get_email_hardquota(r['entity_id'])
    return cyrus_set_quota(r['entity_id'], hq)


def proc_email_delete(r):
    try:
        uname = get_account(r['entity_id']).account_name
    except Errors.NotFoundError:
        logger.error("bofh_email_delete: %d: user not found",
                     r['entity_id'])
        return False

    # The database contains the new host, so the id of the server
    # to remove from is passed in destination_id.
    server = Email.EmailServer(db)
    try:
        server.find(r['destination_id'])
    except Errors.NotFoundError:
        logger.error("bofh_email_delete: %d: target server not found",
                     r['destination_id'])
        return False
    account = get_account(r['entity_id'])
    # If the account is deleted, we assume that delete_user has
    # already bumped the generation.  Otherwise, we bump the
    # generation ourselves
    generation = account.get_trait(const.trait_account_generation)
    update_gen = False
    if generation:
        generation = generation['numval']
    else:
        generation = 0
    if not account.is_deleted():
        generation += 1
        update_gen = True
    if cyrus_delete(server, uname, generation):
        if update_gen:
            account.populate_trait(const.trait_account_generation,
                                   numval=generation)
            account.write_db()
        return True
    else:
        return False

pwfile = os.path.join(cereconf.DB_AUTH_DIR,
                      'passwd-%s@%s' % (cereconf.CYRUS_ADMIN,
                                        cereconf.CYRUS_HOST))


def email_move_child(host, r):
    local_db = Utils.Factory.get('Database')()
    local_co = Utils.Factory.get('Constants')(local_db)
    r_id = r['request_id']
    if not is_valid_request(r_id, local_db=local_db, local_co=local_co):
        return
    if dependency_pending(r['state_data'], local_db=local_db,
                          local_co=local_co):
        logger.debug("Request '%d' still has deps: '%s'.",  r_id,
                     r['state_data'])
        return
    try:
        acc = get_account(r['entity_id'], local_db=local_db)
    except Errors.NotFoundError:
        logger.error("email_move: user %d not found",
                     r['entity_id'])
        return
    old_server = get_email_server(r['entity_id'], local_db=local_db)
    new_server = Email.EmailServer(local_db)
    new_server.find(r['destination_id'])
    if old_server.entity_id == new_server.entity_id:
        logger.error("Trying to move %s from " % acc.account_name +
                     "and to the same server! Deleting request")
        br = BofhdRequests(local_db, local_co)
        br.delete_request(request_id=r_id)
        local_db.commit()
        return
    if not email_delivery_stopped(acc.account_name):
        logger.debug("E-mail delivery not stopped for %s",
                     acc.account_name)
        return
    logger.debug("User being moved: '%s'.",  acc.account_name)
    with closing(RequestLockHandler()) as reqlock:
        if not reqlock.grab(r_id):
            return
        # Disable quota while copying so the move doesn't fail
        cyrus_set_quota(acc.entity_id, 0, host=new_server, local_db=local_db)
        # Call the script
        cmd = [SSH_CMD, "cerebrum@%s" % host, cereconf.IMAPSYNC_SCRIPT,
               '--user1', acc.account_name, '--host1', old_server.name,
               '--user2', acc.account_name, '--host2', new_server.name,
               '--authusing', cereconf.CYRUS_ADMIN,
               '--passfile1', '/etc/cyrus.pw',
               '--useheader', 'Message-ID',
               '--regexmess', 's/\\0/ /g',
               '--ssl', '--subscribe', '--nofoldersizes']
        proc = subprocess.Popen(cmd, capturestderr=True, bufsize=10240,
                                close_fds=True, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pid = proc.pid
        logger.debug("Called cmd(%d): '%s'", pid, cmd)
        proc.stdin.close()
        # Stolen from Utils.py:spawn_and_log_output()
        descriptor = {proc.stdout: logger.debug,
                      proc.stderr: logger.info}
        while descriptor:
            # select() is called for _every_ line, since we can't inspect
            # the buffering in Python's file object.  This works OK since
            # select() will return "readable" for an unread EOF, and
            # Python won't read the EOF until the buffers are exhausted.
            ready, x, x = select(descriptor.keys(), [], [])
            for fd in ready:
                line = fd.readline()
                if line == '':
                    fd.close()
                    del descriptor[fd]
                else:
                    descriptor[fd]("[%d] %s" % (pid, line.rstrip()))
        status = proc.wait()
        if status == EXIT_SUCCESS:
            logger.debug("[%d] Completed successfully", pid)
        elif os.WIFSIGNALED(status):
            # The process was killed by a signal.
            sig = os.WTERMSIG(status)
            logger.warning('[%d] Command "%r" was killed by signal %d',
                           pid, cmd, sig)
            return
        else:
            # The process exited with an exit status
            sig = os.WSTOPSIG(status)
            logger.warning("[%d] Return value was %d from command %r",
                           pid, sig, cmd)
            return
        # Need move SIEVE filters as well
        cmd = [cereconf.MANAGESIEVE_SCRIPT,
               '-v', '-a', cereconf.CYRUS_ADMIN, '-p', pwfile,
               acc.account_name, old_server.name, new_server.name]
        if Utils.spawn_and_log_output(
                cmd,
                connect_to=[old_server.name, new_server.name]) != 0:
            logger.warning('%s: managesieve_sync failed!', acc.account_name)
            return
        logger.info('%s: managesieve_sync completed successfully',
                    acc.account_name)
        # The move was successful, update the user's server
        # Now set the correct quota.
        hq = get_email_hardquota(acc.entity_id, local_db=local_db)
        cyrus_set_quota(acc.entity_id, hq, host=new_server, local_db=local_db)
        et = Email.EmailTarget(local_db)
        et.find_by_target_entity(acc.entity_id)
        et.email_server_id = new_server.entity_id
        et.write_db()
        # We need to delete this request before adding the
        # delete to avoid triggering the conflicting request
        # test.
        br = BofhdRequests(local_db, local_co)
        br.delete_request(request_id=r_id)
        local_db.commit()
        br.add_request(r['requestee_id'], r['run_at'],
                       local_co.bofh_email_delete,
                       r['entity_id'], old_server.entity_id)
        local_db.commit()
        logger.info("%s: move_email success.", acc.account_name)


def process_email_move_requests():
    # Easy round robin to balance load on real mail servers
    round_robin = {}
    for i in cereconf.PROC_BOFH_REQ_MOVE_SERVERS:
        round_robin[i] = 0

    def get_srv():
        srv = ""
        low = -1
        for s in round_robin:
            if round_robin[s] < low or low == -1:
                srv = s
                low = round_robin[s]
        round_robin[srv] += 1
        return srv

    br = BofhdRequests(db, const)
    rows = [r for r in br.get_requests(operation=const.bofh_email_move,
                                       only_runnable=True)]
    if len(rows) == 0:
        return

    procs = []
    while len(rows) > 0 or len(procs) > 0:
        start = time.time()
        if len(procs) < 20 and len(rows) > 0:
            host = get_srv()
            r = rows.pop()
            pid = os.fork()
            if pid == 0:
                email_move_child(host, r)
                sys.exit(0)
            else:
                procs.append((pid, host))

        for pid, host in procs:
            status = os.waitpid(pid, os.WNOHANG)
            # (X, Y) = waitpid
            # X = 0   - still running
            # X = pid - finished
            # Y = exit value
            if status[0] != 0:
                # process finished
                if status[1] != 0:
                    logger.error("fork '%d' exited with code: %d",
                                 status[0], status[1])
                procs.remove((pid, host))
                round_robin[host] -= 1
        # Don't hog the CPU while throttling
        if time.time() <= start + 1:
            time.sleep(0.5)


def cyrus_create(user_id, host=None):
    try:
        uname = get_account(user_id).account_name
    except Errors.NotFoundError:
        logger.error("cyrus_create: %d not found", user_id)
        return False
    if host is None:
        host = get_email_server(user_id)
    if not (cereconf.DEBUG_HOSTLIST is None or
            host.name in cereconf.DEBUG_HOSTLIST):
        logger.info("cyrus_create(%s, %s): skipping", uname, host.name)
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
    if not (cereconf.DEBUG_HOSTLIST is None or
            host.name in cereconf.DEBUG_HOSTLIST):
        logger.info("cyrus_delete(%s, %s): skipping", uname, host.name)
        return False
    # Backup Cyrus data before deleting it.
    if not archive_cyrus_data(uname, host.name, generation):
        logger.error("bofh_email_delete: Archival of Cyrus data failed.")
        return False
    try:
        cyradm = connect_cyrus(host=host)
    except CyrusConnectError, e:
        logger.error("bofh_email_delete: %s: %s" % (host.name, e))
        return False
    res, listresp = cyradm.list("user.", pattern=uname)
    if res != 'OK' or listresp[0] is None:
        logger.error("bofh_email_delete: %s: no mailboxes", uname)
        cyradm.logout()
        return True
    folders = ["user.%s" % uname]
    res, listresp = cyradm.list("user.%s." % uname)
    if res == 'OK' and listresp[0]:
        for line in listresp:
            m = re.match(r'^\(.*?\) ".*?" "?([^"]+)"?$', line)
            if not m:
                logger.error("bofh_email_delete: invalid folder name: %s",
                             line)
            folders += [m.group(1), ]
    # Make sure the subfolders are deleted first by reversing the
    # sorted list.
    folders.sort()
    folders.reverse()
    for folder in folders:
        logger.debug("deleting %s ... ", folder)
        cyradm.setacl(folder, cereconf.CYRUS_ADMIN, 'c')
        res = cyradm.delete(folder)
        if res[0] != 'OK':
            logger.error("IMAP delete %s failed: %s", folder, res[1])
            cyradm.logout()
            return False
    cyradm.logout()
    return True


def cyrus_set_quota(user_id, hq, host=None, local_db=db):
    try:
        uname = get_account(user_id, local_db=local_db).account_name
    except Errors.NotFoundError:
        logger.error("cyrus_set_quota: %d: user not found", user_id)
        return False
    if host is None:
        host = get_email_server(user_id, local_db=local_db)
    if not (cereconf.DEBUG_HOSTLIST is None or
            host.name in cereconf.DEBUG_HOSTLIST):
        logger.info("cyrus_set_quota(%s, %d, %s): skipping",
                    uname, hq, host.name)
        return False
    try:
        cyradm = connect_cyrus(username=uname, host=host)
    except (CyrusConnectError, socket.error), e:
        logger.error("cyrus_set_quota(%s, %d): %s" % (uname, hq, e))
        return False
    quotalist = '(STORAGE %d)' % (hq * 1024)
    if hq == 0:
        quotalist = '()'
    res, msg = cyradm.setquota("user.%s" % uname, quotalist)
    logger.debug("cyrus_set_quota(%s, %d): %s" % (uname, hq, repr(res)))
    return res == 'OK'


def archive_cyrus_data(uname, mail_server, generation):
    args = [
        SUDO_CMD, cereconf.ARCHIVE_MAIL_SCRIPT,
        '--server', mail_server,
        '--user', uname,
        '--gen', str(generation)
    ]
    if DEBUG:
        args.append('--debug')
    cmd = SSH_CEREBELLUM + [" ".join(args), ]
    return (
        Utils.spawn_and_log_output(cmd, connect_to=[mail_server]) ==
        EXIT_SUCCESS)


def proc_sympa_create(request):
    """Execute the request for creating a sympa mailing list.

    @type request: ??
    @param request:
      An object describing the sympa list creation request.
    """

    try:
        listname = get_address(request["entity_id"])
    except Errors.NotFoundError:
        logger.warn("Sympa list address id:%s is deleted! No need to create",
                    request["entity_id"])
        return True

    try:
        state = pickle.loads(str(request["state_data"]))
    except:
        logger.exception("Corrupt request state for sympa list=%s: %s",
                         listname, request["state_data"])
        return True

    try:
        host = state["runhost"]
        profile = state["profile"]
        description = state["description"]
        admins = state["admins"]
        admins = ",".join(admins)
    except KeyError:
        logger.error("No host/profile/description specified for sympa list %s",
                     listname)
        return True

    # 2008-08-01 IVR FIXME: Safe quote everything fished out from state.
    cmd = [cereconf.SYMPA_SCRIPT, host, 'newlist',
           listname, admins, profile, description]
    return Utils.spawn_and_log_output(cmd) == EXIT_SUCCESS


def proc_sympa_remove(request):
    """Execute the request for removing a sympa mailing list.

    @type request: ??
    @param request:
      A dict-like object containing all the parameters for sympa list
      removal.
    """

    try:
        state = pickle.loads(str(request["state_data"]))
    except:
        logger.exception("Corrupt request state for sympa request %s: %s",
                         request["request_id"], request["state_data"])
        return True

    try:
        listname = state["listname"]
        host = state["run_host"]
    except KeyError:
        logger.error("No listname/runhost specified for request %s",
                     request["request_id"])
        return True

    cmd = [cereconf.SYMPA_SCRIPT, host, 'rmlist', listname]
    return Utils.spawn_and_log_output(cmd) == EXIT_SUCCESS


def get_address(address_id):
    ea = Email.EmailAddress(db)
    ea.find(address_id)
    ed = Email.EmailDomain(db)
    ed.find(ea.email_addr_domain_id)
    return "%s@%s" % (ea.email_addr_local_part,
                      ed.rewrite_special_domains(ed.email_domain_name))


def is_ok_batch_time(now):
    times = cereconf.LEGAL_BATCH_MOVE_TIMES.split('-')
    if times[0] > times[1]:  # Like '20:00-08:00'
        if now > times[0] or now < times[1]:
            return True
    else:  # Like '08:00-20:00'
        if now > times[0] and now < times[1]:
            return True
    return False


def proc_move_user(r):
    try:
        account, uname, old_host, old_disk = get_account_and_home(
            r['entity_id'], type='PosixUser',
            spread=r['state_data'])
        new_host, new_disk = get_disk(r['destination_id'])
    except Errors.NotFoundError:
        logger.error("move_request: user %i not found", r['entity_id'])
        return False
    if account.is_expired():
        logger.warn("Account %s is expired, cancelling request",
                    account.account_name)
        return False
    set_operator(r['requestee_id'])
    try:
        operator = get_account(r['requestee_id']).account_name
    except Errors.NotFoundError:
        # The mvuser script requires a valid address here.  We
        # may want to change this later.
        operator = "cerebrum"
    group = get_group(account.gid_id, grtype='PosixGroup')

    if move_user(uname, int(account.posix_uid), int(group.posix_gid),
                 old_host, old_disk, new_host, new_disk, operator):
        logger.debug('user %s moved from %s to %s',
                     uname, old_disk, new_disk)
        ah = account.get_home(default_spread)
        account.set_homedir(current_id=ah['homedir_id'],
                            disk_id=r['destination_id'])
        account.write_db()
        return True
    else:
        return new_disk == old_disk


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
    account = Utils.Factory.get('Account')(db)
    person = Utils.Factory.get('Person')(db)
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
        fnr2move_student.setdefault(fnr, []).append(
            (int(account.entity_id),
             int(r['request_id']),
             int(r['requestee_id'])))
    logger.debug("Starting callbacks to find: %s" % fnr2move_student)
    autostud.start_student_callbacks(student_info_file, move_student_callback)

    # Move remaining users to pending disk
    disk = Utils.Factory.get('Disk')(db)
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

    fnr = "%06d%05d" % (int(person_info['fodselsdato']),
                        int(person_info['personnr']))
    logger.debug("Callback for %s" % fnr)
    try:
        fodselsnr.personnr_ok(fnr)
    except Exception, e:
        logger.exception(e)
        return
    if fnr not in fnr2move_student:
        return
    account = Utils.Factory.get('Account')(db)
    group = Utils.Factory.get('Group')(db)
    br = BofhdRequests(db, const)
    for account_id, request_id, requestee_id in fnr2move_student.get(fnr, []):
        account.clear()
        account.find(account_id)
        groups = list(int(x["group_id"]) for x in
                      group.search(member_id=account_id,
                                   indirect_members=False))
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
                    if autostud.disk_tool.get_diskdef_by_diskid(
                            int(current_disk_id)):
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
                            from Cerebrum.modules.no.uio import DiskQuota
                            disk_quota_obj = DiskQuota.DiskQuota(db)
                            try:
                                cur_quota = disk_quota_obj.get_quota(
                                    homedir_id)
                            except Errors.NotFoundError:
                                cur_quota = None
                            quota = profile.get_disk_kvote(new_disk)
                            if (cur_quota is None or
                                    cur_quota['quota'] != int(quota)):
                                disk_quota_obj.set_quota(homedir_id,
                                                         quota=int(quota))
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


def proc_quarantine_refresh(r):
    """process_changes.py has added bofh_quarantine_refresh for the
    start/disable/end dates for the quarantines.  Register a
    quarantine_refresh change-log event so that changelog-based
    quicksync script can revalidate the quarantines.

    """
    set_operator(r['requestee_id'])
    db.log_change(r['entity_id'], const.quarantine_refresh, None)
    return True


def proc_archive_user(r):
    spread = default_spread  # TODO: check spread in r['state_data']
    account, uname, old_host, old_disk = get_account_and_home(r['entity_id'],
                                                              spread=spread)
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
        return True
    else:
        return False


def proc_delete_user(r):
    spread = default_spread  # TODO: check spread in r['state_data']
    #
    # IVR 2007-01-25 We do not care if it's a posix user or not.
    # TVL 2013-12-09 Except that if it's a POSIX user, it should retain a
    #                personal file group.
    account, uname, old_host, old_disk = get_account_and_home(r['entity_id'],
                                                              spread=spread)
    if account.is_deleted():
        logger.warn("%s is already deleted" % uname)
        return True
    set_operator(r['requestee_id'])
    operator = get_account(r['requestee_id']).account_name
    et = Email.EmailTarget(db)
    try:
        et.find_by_target_entity(account.entity_id)
        es = Email.EmailServer(db)
        es.find(et.email_server_id)
        mail_server = es.name
    except Errors.NotFoundError:
        mail_server = ''

    if not delete_user(uname, old_host, '%s/%s' % (old_disk, uname),
                       operator, mail_server):
        return False

    account.expire_date = mx.DateTime.now()
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

    # Make sure the user's default file group is a personal group
    group = Utils.Factory.get('Group')(db)
    default_group = _get_default_group(account.entity_id)
    pu = Utils.Factory.get('PosixUser')(db)

    try:
        pu.find(account.entity_id)
    except Errors.NotFoundError:
        pass
    else:
        # The account is a PosixUser, special care needs to be taken with
        # regards to its default file group (dfg)
        personal_fg = pu.find_personal_group()
        if personal_fg is None:
            # Create a new personal file group
            op = Utils.Factory.get('Account')(db)
            op.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            with pu._new_personal_group(op.entity_id) as new_group:
                personal_fg = new_group
                pu._set_owner_of_group(personal_fg)
                pu.map_user_spreads_to_pg()
            logger.debug("Created group: '%s'. Group ID = %d",
                         personal_fg.group_name, personal_fg.entity_id)

        pg = Utils.Factory.get('PosixUser')(db)
        # If user has a personal group, but it currently isn't a posix group.
        # This scenario should never really occur, but hey, this is Cerebrum.
        if not personal_fg.has_extension('PosixGroup'):
            pg.populate(parent=personal_fg)
            pg.write_db()
            personal_fg = pg
        # Set group to be dfg for the user.
        if personal_fg.entity_id != default_group:
            pu.gid_id = personal_fg.entity_id
            pu.write_db()
            default_group = _get_default_group(account.entity_id)

    # Remove the user from groups
    group.clear()
    for g in group.search(member_id=account.entity_id,
                          indirect_members=False):
        group.clear()
        group.find(g['group_id'])
        #
        # all posixuser-objects have to keep their membership
        # in their default group due to a FK-constraint from
        # posix_user to group_member
        if g['group_id'] == default_group:
            logger.debug("Skipping default group %s for user %s",
                         group.group_name, account.account_name)
            continue
        group.remove_member(account.entity_id)
    return True


def _get_default_group(account_id):
    try:
        # only posix_user-objects have a default group
        account = Utils.Factory.get('PosixUser')(db)
        account.clear()
        account.find(account_id)
    except Errors.NotFoundError:
        return None
    return account.gid_id


def delete_user(uname, old_host, old_home, operator, mail_server):
    account = get_account(name=uname)
    generation = account.get_trait(const.trait_account_generation)
    if generation:
        generation = generation['numval'] + 1
    else:
        generation = 1

    args = [
        SUDO_CMD, cereconf.RMUSER_SCRIPT,
        '--username', account.account_name,
        '--deleted-by', operator,
        '--homedir', old_home,
        '--generation', str(generation)
    ]
    if DEBUG:
        args.append('--debug')
    cmd = SSH_CEREBELLUM + [" ".join(args), ]

    if Utils.spawn_and_log_output(cmd, connect_to=[old_host]) == EXIT_SUCCESS:
        account.populate_trait(const.trait_account_generation,
                               numval=generation)
        account.write_db()
        return True
    return False


def move_user(uname, uid, gid, old_host, old_disk, new_host, new_disk,
              operator):
    args = [SUDO_CMD, cereconf.MVUSER_SCRIPT,
            '--user', uname,
            '--uid', str(uid),
            '--gid', str(gid),
            '--old-disk', old_disk,
            '--new-disk', new_disk,
            '--operator', operator]
    if DEBUG:
        args.append('--debug')
    cmd = SSH_CEREBELLUM + [" ".join(args), ]
    return (Utils.spawn_and_log_output(cmd, connect_to=[old_host, new_host]) ==
            EXIT_SUCCESS)


def set_operator(entity_id=None):
    if entity_id:
        db.cl_init(change_by=entity_id)
    else:
        db.cl_init(change_program='process_bofhd_r')


def get_disk(disk_id):
    disk = Utils.Factory.get('Disk')(db)
    disk.clear()
    disk.find(disk_id)
    host = Utils.Factory.get('Host')(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path


def get_account(account_id=None, name=None, local_db=db):
    assert account_id or name
    acc = Utils.Factory.get('Account')(local_db)
    if account_id:
        acc.find(account_id)
    elif name:
        acc.find_by_name(name)
    return acc


def get_account_and_home(account_id, type='Account', spread=None):
    if type == 'Account':
        account = Utils.Factory.get('Account')(db)
    elif type == 'PosixUser':
        account = Utils.Factory.get('PosixUser')(db)
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
        group = Utils.Factory.get('Group')(db)
    elif grtype == "PosixGroup":
        group = PosixGroup.PosixGroup(db)
    group.clear()
    group.find(id)
    return group


def is_valid_request(req_id, local_db=db, local_co=const):
    # The request may have been canceled very recently
    br = BofhdRequests(local_db, local_co)
    for r in br.get_requests(request_id=req_id):
        return True
    return False


def main():
    global max_requests, ou_perspective, DEBUG
    global emne_info_file, studconfig_file, studieprogs_file, student_info_file
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            'dpt:m:',
            ['debug',
             'process',
             'type=',
             'max=',
             'ou-perspective=',
             'emne-info-file=',
             'studconfig-file=',
             'studie-progs-file=',
             'student-info-file='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    types = []
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            DEBUG = True
        elif opt in ('-t', '--type',):
            types.append(val)
        elif opt in ('-m', '--max',):
            max_requests = int(val)
        elif opt in ('-p', '--process'):
            if not types:
                types = ['quarantine', 'delete', 'move',
                         'email', 'sympa', ]
            process_requests(types)
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
         repeated, and must precede -p
    -m | --max val: perform up to this number of requests

    Legal values for --type:
      email
      sympa
      move
      quarantine
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
