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

import getopt
import sys
import os
import re
import ldap
import cyruslib

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

db = Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)
logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")
# for debug:
# logger = logging.getLogger("console")
# Hosts to connect to, set to None in a production environment:
debug_hostlist = None
SUDO_CMD = "/usr/bin/sudo"
ldapconn = None
imapconn = None
imaphost = None

def email_delivery_stopped(user):
    global ldapconn
    if ldapconn is None:
        ldapconn = ldap.open("ldap.uio.no")
        ldapconn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        try:
            ldapconn.simple_bind_s("","")
        except ldap.LDAPError, e:
            logger.error("Connect to LDAP failed: %s", e)
            return False
    try:
        res = ldapconn.search_s("ou=mail,dc=uio,dc=no",
                                ldap.SCOPE_SUBTREE,
                                "(&(target=%s)(mailPause=TRUE))" % user)
    except ldap.LDAPError, e:
        logger.error("LDAP search failed: %s", e)
        return False

    return len(res) == 1

def get_email_target_id(user_id):
    t = Email.EmailTarget(db)
    t.find_by_entity(user_id)
    return t.email_target_id

def get_email_hardquota(user_id):
    eq = Email.EmailQuota(db)
    try:
        eq.find_by_entity(user_id)
    except Errors.NotFoundError:
        return 0	# unlimited/no quota
    return eq.email_quota_hard


def get_imaphost(user_id):
    """
    user_id is entity id of account to look up. Return hostname of
    IMAP server, or None if user's mail is stored in a different
    system.
    """
    em = Email.EmailServerTarget(db)
    em.find(get_email_target_id(user_id))
    server = Email.EmailServer(db)
    server.find(em.get_server_id())
    if server.email_server_type == const.email_server_type_cyrus:
        return server.name
    return None

def get_home(acc):
    if acc.home:
        return acc.home
    elif acc.disk_id is not None:
        disk = Factory.get('Disk')(db)
        disk.find(acc.disk_id)
        return "%s/%s" % (disk.path, acc.account_name)
    else:
        return None

def add_forward(user_id, addr):
    ef = Email.EmailForward(db)
    ef.find_by_entity(user_id)
    # clean up input a little
    if addr.startswith('\\'):
        addr = addr[1:]
    if addr.endswith('\r'):
        addr = addr[:-1]
        
    if addr.startswith('|') or addr.startswith('"|'):
        logger.warn("forward to pipe ignored: %s", addr)
        return
    elif not addr.count('@'):
        acc = Factory.get('Account')(db)
        try:
            acc.find_by_name(addr)
        except Errors.NotFoundError:
            logger.warn("forward to unknown username: %s", addr)
            return
        addr = acc.get_primary_mailaddress()
    for r in ef.get_forward():
        if r['forward_to'] == addr:
            return
    ef.add_forward(addr)
    ef.write_db()

def connect_cyrus(host=None, user_id=None):
    global imapconn, imaphost
    if host is None:
        assert user_id is not None
        try:
            host = get_imaphost(user_id)
            if host is None:
                raise CerebrumError("connect_cyrus: not an IMAP user " +
                                    "(user id = %d)" % user_id)
        except:
            raise CerebrumError("connect_cyrus: unknown user " +
                                "(user id = %d)" % user_id)
    if imapconn is not None:
        if not imaphost == host:
            imapconn.logout()
            imapconn = None
    if imapconn is None:
        imapconn = cyruslib.CYRUS(host = host)
        # TODO: _read_password should moved into Utils or something
        pw = db._read_password(cereconf.CYRUS_HOST, cereconf.CYRUS_ADMIN)
        if imapconn.login(cereconf.CYRUS_ADMIN, pw) is None:
            raise CerebrumError("Connection to IMAP server %s failed" % host)
        imaphost = host
    return imapconn

def process_email_requests():
    acc = Factory.get('Account')(db)
    br = BofhdRequests(db, const)
    for r in br.get_requests(operation=const.bofh_email_create):
        logger.debug("Req: email_create %d at %s",
                     r['request_id'], r['run_at'])
        if r['run_at'] < br.now:
            hq = get_email_hardquota(r['entity_id'])
            if (cyrus_create(r['entity_id']) and
                cyrus_set_quota(r['entity_id'], hq)):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_hquota):
        logger.debug("Req: email_hquota %s", r['run_at'])
	if r['run_at'] < br.now:
            hq = get_email_hardquota(r['entity_id'])
            if cyrus_set_quota(r['entity_id'], hq):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_delete):
        logger.debug("Req: email_delete %s", r['run_at'])
	if r['run_at'] < br.now:
	    try:
                acc.clear()
                acc.find(r['entity_id'])
                uname = acc.account_name
            except Errors.NotFoundError:
                logger.error("bofh_email_delete: %d: user not found",
                             r['entity_id'])
                br.delay_request(request_id=r['request_id'])
                db.commit()
                continue
            
            # The database contains the new host, so the id of the server
            # to remove from is passed in state_data.
            server = Email.EmailServer(db)
            try:
                server.find(r['state_data'])
            except Errors.NotFoundError:
                logger.error("bofh_email_delete: %d: target server not found",
                             r['state_data'])
                br.delay_request(request_id=r['request_id'])
                db.commit()
                continue
            if cyrus_delete(server.name, uname):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_move):
        logger.debug("Req: email_move %s %d", r['run_at'], int(r['state_data']))
	if r['run_at'] < br.now:
            # state_data is a request-id which must complete first,
            # typically an email_create request.
            # TBD: make it a general feature in BofhdRequests?
            if r['state_data']:
                found_dep = False
                for dr in br.get_requests(request_id=r['state_data']):
                    found_dep = True
                if found_dep:
                    br.delay_request(r['request_id'])
                    logger.debug("waiting for request %d", int(r['state_data']))
                    continue
	    try:
                acc.clear()
                acc.find(r['entity_id'])
            except Errors.NotFoundError:
                logger.error("%d not found", r['entity_id'])
                continue
            est = Email.EmailServerTarget(db)
            est.find(get_email_target_id(r['entity_id']))
            old_server = r['destination_id']
            new_server = est.get_server_id()
            if old_server == new_server:
                logger.error("trying to move %s from and to the same server!",
                             acc.account_name)
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue
            if not email_delivery_stopped(acc.account_name):
                logger.debug("E-mail delivery not stopped for %s",
                             acc.account_name)
                db.rollback()
                br.delay_request(r['request_id'])
                db.commit()
                continue
            if move_email(r['entity_id'], r['requestee_id'],
                          old_server, new_server):
                br.delete_request(request_id=r['request_id'])
                es = Email.EmailServer(db)
                es.find(old_server)
                if es.email_server_type == const.email_server_type_nfsmbox:
                    br.add_request(r['requestee_id'], r['run_at'],
                                   const.bofh_email_convert,
                                   r['entity_id'], old_server)
                elif es.email_server_type == const.email_server_type_cyrus:
                    br.add_request(r['requestee_id'], r['run_at'],
                                   const.bofh_email_delete,
                                   r['entity_id'], None,
                                   state_data=old_server)
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_convert):
        logger.debug("Req: email_convert %s", r['run_at'])
	if r['run_at'] < br.now:
            user_id = r['entity_id']
            try:
                acc.clear()
                acc.find(user_id)
            except Errors.NotFoundErrors:
                logger.error("bofh_email_convert: %d not found" % user_id)
                continue
            try:
                posix = PosixUser.PosixUser(db)
                posix.find(user_id)
            except Errors.NotFoundErrors:
                logger.debug("bofh_email_convert: %s: " % acc.account_name +
                             "not a PosixUser, skipping e-mail conversion")
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue

            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'convertmail',
                   acc.account_name, get_home(acc),
                   posix.posix_uid, posix.gid_id]
            cmd = ["%s" % x for x in cmd]
            unsafe = False
            for word in cmd:
                if not re.match("^[A-Za-z0-9./_-]*$", word):
                    unsafe = True
            if unsafe:
                logger.error("possible unsafe invocation to popen: %s", cmd)
                continue

            try:
                fd = os.popen(" ".join(cmd))
            except:
                logger.error("bofh_email_convert: %s: " % acc.account_name +
                             "running %s failed" % cmd)
                continue
            success = True
            try:
                subsep = '\034'
                for line in fd.readlines():
                    if line.endswith('\n'):
                        line = line[:-1]
                    logger.debug("email_convert: %s", repr(line))
                    if line.startswith("forward: "):
                        for addr in [t.split(subsep)
                                     for t in line.split(": ")][1]:
                            add_forward(user_id, addr)
                    elif line.startswith("forward+local: "):
                        add_forward(user_id, acc.get_primary_mailaddress())
                        for addr in [t.split(subsep)
                                     for t in line.split(": ")][1]:
                            add_forward(user_id, addr)
                    elif line.startswith("tripnote: "):
                        msg = "\n".join([t.split(subsep)
                                         for t in line.split(": ")][1])
                        vac = Email.EmailVacation(db)
                        vac.find_by_entity(user_id)
                        # if there's a message imported from ~/tripnote
                        # already, get rid of it -- this message will
                        # be the same or fresher.
                        start = db.Date(1970, 1, 1)
                        for v in vac.get_vacation():
                            if v['start_date'] == start:
                                vac.delete_vacation(start)
                        vac.add_vacation(start, msg, enable='T')
                    else:
                        logger.error("convertmail reported: %s\n" % line)
            except Exception, e:
                    db.rollback()
                    # TODO better diagnostics
                    success = False
                    logger.error("convertmail failed: %s (%s)", repr(e), e)
            if success:
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()
        
def cyrus_create(user_id):
    try:
        uname = get_account(user_id)[1]
    except Errors.NotFoundError:
        logger.error("cyrus_create: %d not found", user_id)
        return False
    assert uname is not None
    try:
        cyradm = connect_cyrus(user_id = user_id)
    except CerebrumError, e:
        logger.error("cyrus_create: " + str(e))
        return False
    for sub in ("", ".spam", ".Sent", ".Drafts", ".Trash"):
        res, list = cyradm.m.list ('user.', pattern='%s%s' % (uname, sub))
        if res == 'OK' and list[0]:
            continue
        res = cyradm.m.create('user.%s%s' % (uname, sub))
        if res[0] <> 'OK':
            logger.error("IMAP create user.%s%s failed: %s",
                         uname, sub, res[1])
            return False
    # restrict access to INBOX.spam.  the user can change the
    # ACL to override this, though.
    cyradm.m.setacl("user.%s.spam" % uname, uname, "lrswipd")
    # we don't care to check if the next command runs OK.
    # almost all IMAP clients ignore the file, anyway ...
    cyrus_subscribe(uname, imaphost)
    return True

def cyrus_delete(host, uname):
    logger.debug("will delete %s from %s", uname, host)
    try:
        cyradm = connect_cyrus(host=host)
    except CerebrumError, e:
        logger.error("bofh_email_delete: %s: %s" % (host, e))
        return False
    res, list = cyradm.m.list("user.", pattern=uname)
    if res <> 'OK' or list[0] == None:
        # TBD: is this an error we need to keep around?
        db.rollback()
        logger.error("bofh_email_delete: %s: no mailboxes", uname)
        return False
    folders = ["user.%s" % uname]
    res, list = cyradm.m.list("user.%s." % uname)
    if res == 'OK' and list[0]:
        for line in list:
            folder = line.split(' ')[2]
            folders += [ folder[1:-1] ]
    # Make sure the subfolders are deleted first by reversing
    # the sorted list.
    folders.sort()
    folders.reverse()
    allok = True
    for folder in folders:
        logger.debug("deleting %s ... ", folder)
        cyradm.m.setacl(folder, cereconf.CYRUS_ADMIN, 'c')
        res = cyradm.m.delete(folder)
        if res[0] <> 'OK':
            logger.error("IMAP delete %s failed: %s", folder, res[1])
            return False
    cyrus_subscribe(uname, host, action="delete")
    return True

def cyrus_set_quota(user_id, hq):
    try:
        uname = get_account(user_id)[1]
    except Errors.NotFoundError:
        logger.error("cyrus_set_quota: %d: user not found", user_id)
        return False
    try:
        cyradm = connect_cyrus(user_id = user_id)
    except CerebrumError, e:
        logger.error("cyrus_set_quota: " + str(e))
        return False
    res, msg = cyradm.m.setquota("user.%s" % uname, 'STORAGE', hq * 1024)
    logger.debug("return %s", repr(res))
    return res == 'OK'

def cyrus_subscribe(uname, server, action="create"):
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'subscribeimap',
           action, server, uname];
    cmd = ["%s" % x for x in cmd]
    if debug_hostlist is None or old_host in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    else:
        errnum = 0
    if not errnum:
        return True
    logger.error("%s returned %i", cmd, errnum)
    return False

def move_email(user_id, mailto_id, from_host, to_host):
    acc = Factory.get("Account")(db)
    # bofh_move_email requests that are "magically" added by giving a
    # user spread 'spread_uio_imap' will have mailto_id == None.
    mailto = ""
    if mailto_id is not None:
        try:
            acc.find(mailto_id)
        except Errors.NotFoundError:
            logger.error("move_email: operator %d not found" % mailto_id)
            return False
        try:
            mailto = acc.get_primary_mailaddress()
        except Errors.NotFoundError:
            mailto = ""
    try:
        acc.clear()
        acc.find(user_id)
    except Errors.NotFoundError:
        logger.error("move_email: %d not found" % user_id)
        return False

    es_to = Email.EmailServer(db)
    es_to.find(to_host)
    type_to = int(es_to.email_server_type)
    
    es_fr = Email.EmailServer(db)
    es_fr.find(from_host)
    type_fr = int(es_fr.email_server_type)

    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'mvmail',
           acc.account_name, get_home(acc),
           mailto, get_email_hardquota(user_id),
           es_fr.name, str(Email._EmailServerTypeCode(type_fr)),
           es_to.name, str(Email._EmailServerTypeCode(type_to))]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    EXIT_SUCCESS = 0
    EXIT_LOCKED = 101
    EXIT_NOTIMPL = 102
    EXIT_QUOTAEXCEEDED = 103
    EXIT_FAILED = 104
    errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    if errnum == EXIT_QUOTAEXCEEDED:
        # TODO: bump quota, or something else
        pass
    elif errnum == EXIT_SUCCESS:
        pass
    else:
        logger.error('mvmail failed, returned %d' % errnum)
        return False
    if es_fr.email_server_type == const.email_server_type_cyrus:
        return cyrus_delete(es_fr.name, acc.account_name)
    return True

def process_move_requests():
    br = BofhdRequests(db, const)
    for r in br.get_requests(operation=const.bofh_move_user):
        if r['run_at'] < br.now:
            try:
                account, uname, old_host, old_disk = get_account(
                    r['entity_id'], type='PosixUser')
                new_host, new_disk  = get_disk(r['destination_id'])
            except Errors.NotFoundError:
                logger.error("%i not found" % r['entity_id'])
                continue
            operator = get_account(r['requestee_id'])[0].account_name
            group = get_group(account.gid_id, grtype='PosixGroup')

            spread = ",".join(["%s" % Constants._SpreadCode(int(a['spread']))
                               for a in account.get_spread()]),
            if get_imaphost(r['entity_id']) == None:
                spool = '1'
            else:
                spool = '0'
            if move_user(uname, int(account.posix_uid), int(group.posix_gid),
                         old_host, old_disk, new_host, new_disk, spread,
                         operator, spool):
                account.disk_id =  r['destination_id']
                account.write_db()
                br.delete_request(request_id=r['request_id'])
		db.log_change(r['entity_id'], cl_const.account_move , None, change_params={ 'old_host':old_host , 'new_host':new_host , 'old_disk':old_disk, 'new_disk':new_disk })
                db.commit()

    # Resten fungerer ikkje enno, so vi sluttar her.
    return

    for r in br.get_requests(operation=const.bofh_move_student):
        # TODO: Må også behandle const.bofh_move_student, men
        # student-auomatikken mangler foreløbig støtte for det.
        pass
    for r in br.get_requests(operation=const.bofh_delete_user):
        account, uname, old_host, old_disk = get_account(r['entity_id'])
        operator = get_account(r['requestee_id'])[0].account_name
        if delete_user(uname, old_host, '%s/%s' % (old_disk, uname), operator):
            account.expire_date = br.now
            account.write_db()
            br.delete_request(request_id=r['request_id'])
            db.commit()
def delete_user(uname, old_host, old_home, operator):
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'aruser', uname,
           operator, old_home]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    if debug_hostlist is None or old_host in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logger.error("%s returned %i" % (cmd, errnum))
    return 0

def move_user(uname, uid, gid, old_host, old_disk, new_host, new_disk, spread,
              operator, spool):
    mailto = operator
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'mvuser', uname, uid, gid,
           old_disk, new_disk, spread, mailto, spool]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    if debug_hostlist is None or (old_host in debug_hostlist and
                                  new_host in debug_hostlist):
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logger.error("%s returned %i" % (cmd, errnum))
    return 0

def get_disk(disk_id):
    disk = Factory.get('Disk')(db)
    disk.clear()
    disk.find(disk_id)
    host = Factory.get('Host')(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path

def get_account(account_id, type='Account'):
    if type == 'Account':
        account = Factory.get('Account')(db)
    elif type == 'PosixUser':
        account = PosixUser.PosixUser(db)        
    account.clear()
    account.find(account_id)
    home = account.home
    uname = account.account_name
    if home is None:
        if account.disk_id is None:
            return account, uname, None, None
        host, home = get_disk(account.disk_id)
    else:
        host = None  # TODO:  How should we handle this?
    return account, uname, host, home

def get_group(id, grtype="Group"):
    if grtype == "Group":
        group = Factory.get('Group')(db)
    elif grtype == "PosixGroup":
        group = PosixGroup.PosixGroup(db)
    group.clear()
    group.find(id)
    return group

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dp',
                                   ['debug', 'process'])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    global debug
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
        elif opt in ('-p', '--process'):
            process_move_requests()
            process_email_requests()
    
def usage(exitcode=0):
    print """Usage: process_bofhd_requests.py
    -d | --debug: turn on debugging
    -p | --process: perform the queued operations"""
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
