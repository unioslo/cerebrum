#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import os
import ldap
import cyruslib

import cerebrum_path
import cereconf

from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import Account
from Cerebrum import Disk
from Cerebrum import Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.extlib import logging

db = Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
dryrun = True
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
        ldapconn.simple_bind_s("","")
    res = ldapconn.search_s("ou=mail,dc=uio,dc=no",
                            ldap.SCOPE_SUBTREE,
                            "(&(target=%s)(mailPause=true))" % user)
    return len(res) == 1

def get_email_target_id(user_id):
    t = Email.EmailTarget(db)
    t.find_by_entity(user_id)
    return t.email_target_id

def get_primary_email_address(user_id):
    t = Email.EmailPrimaryAddressTarget(db)
    t.find_by_entity(user_id)
    a = Email.EmailAddress(db)
    a.find(t.get_address_id())
    d = Email.EmailDomain(db)
    d.find(a.get_domain_id())
    return "%s@%s" % (a.get_localpart(), d.get_domain_name())

def get_email_hardquota(user_id):
    eq = Email.EmailQuota(db)
    try:
        eq.find_by_entity(user_id)
    except Errors.NotFoundError:
        return 0	# unlimited/no quota
    return eq.email_quota_hard

# get_imaphost
# input:  entity ID of account
# output: hostname of IMAP server, or None if user's mail is stored in
#         a different system

def get_imaphost(user_id):
    em = Email.EmailServerTarget(db)
    em.find(get_email_target_id(user_id))
    server = Email.EmailServer(db)
    server.find(em.get_server_id())
    if server.email_server_type == const.email_server_type_cyrus:
        return server.name
    return None

def add_forward(user_id, addr):
    forw = Email.EmailForward(db)
    forw.find_by_entity(user_id, const.entity_account)
    forw.add_forward(addr)

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
    br = BofhdRequests(db, const)
    for r in br.get_requests(operation=const.bofh_email_create):
        logger.debug("Req: email_create %d at %d",
                     r['request_id'],r['run_at'])
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
        logger.debug("Req: email_hquota %d", r['run_at'])
	if r['run_at'] < br.now:
            hq = get_email_hardquota(r['entity_id'])
            if cyrus_set_quota(r['entity_id'], hq):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_delete):
        logger.debug("Req: email_delete %d", r['run_at'])
	if r['run_at'] < br.now:
	    try:
                uname = get_account(r['entity_id'])[1]
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
            host = server.name
            logger.debug("will delete %s from %s", uname, host)
            try:
                cyradm = connect_cyrus(host = host)
            except CerebrumError, e:
                logger.error("bofh_email_delete: %s: %s" % (host, str(e)))
                continue
            res, list = cyradm.m.list("user.%s" % uname)
            if res <> 'OK' or list[0] == None:
                # TBD: is this an error we need to keep around?
                db.rollback()
                logger.error("bofh_email_delete: %s: no mailboxes", uname)
                br.delay_request(r['request_id'])
                db.commit()
                continue
            folders = ["user.%s" % uname]
            res, list = cyradm.m.list("user.%s.*" % uname)
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
                    allok = False
            if allok:
                cyrus_subscribe(uname, host, action="delete")
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_will_move):
        logger.debug("Req: email_will_move %d", r['run_at'])
	if r['run_at'] < br.now:
	    try:
                uname = get_account(r['entity_id'])[1]
            except Errors.NotFoundError:
                logger.error("%i not found" % r['entity_id'])
                continue
            try:
                if not email_delivery_stopped(uname):
                    db.rollback()
                    br.delay_request(r['request_id'])
                    db.commit()
                    continue
            except _ldap.LDAPError:
                logger.error("connect to LDAP failed")

            # delivery is stopped, go to next phase
            br.delete_request(request_id=r['request_id'])
            br.add_request(r['requestee_id'], r['run_at'],
                           const.bofh_email_move,
                           r['entity_id'], r['destination_id'],
                           r['state_data'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_move):
        logger.debug("Req: email_move %d", r['run_at'])
	if r['run_at'] < br.now:
            # state_data is a request-id which must complete first,
            # typically a email_create request.
            # TBD: make it a general feature in BofhdRequests?
            if r['state_data']:
                try:
                    br.get_requests(request_id=r['state_data'])
                    br.delay_request(r['request_id'])
                    continue
                except Errors.NotFoundError:
                    pass
            em = Email.EmailServerTarget(db)
            em.find(get_email_target_id(r['entity_id']))
            if move_email(r['entity_id'], r['requestee_id'],
                          em.get_server_id(), r['destination_id']):
                br.delete_request(request_id=r['request_id'])
                br.add_request(r['requestee_id'], r['run_at'],
                               const.bofh_email_convert,
                               r['entity_id'], r['destination_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_convert):
        logger.debug("Req: email_convert %d", r['run_at'])
	if r['run_at'] < br.now:
            user_id = r['entity_id']
            try:
                # uname, home, uid, dfg
                acc = Factory.get('Account')(db)
                acc.find(user_id)
            except Errors.NotFoundErrors:
                logger.error("bofh_email_convert: %d not found" % user_id)
                continue
            try:
                posix = PosixUser.PosixUser(db)
                posix.find(user_id)
            except Errors.NotFoundErrors:
                logger.debug("bofh_email_convert: %s: " % acc.name +
                             "not a PosixUser, skipping e-mail conversion")
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue
                
            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'convertmail',
                   acc.name, acc.home, posix.posix_uid, posix.gid_id]
            try:
                fd = os.popen(cmd)
            except:
                logger.error("bofh_email_convert: %s: " % acc.name +
                             "running %s failed" % cmd)
                continue
            success = True
            try:
                subsep = '\037'
                for line in fs.readlines():
                    line = line[:-1]
                    if line.starts_with("forward: "):
                        for addr in [t.split(subsep)
                                     for t in line.split(": ")][1]:
                            add_forward(user_id, addr)
                    elif line.starts_with("forward+local: "):
                        add_forward(user_id, get_primary_email_address(user_id))
                        for addr in [t.split(subsep)
                                     for t in line.split(": ")][1]:
                            add_forward(user_id, addr)
                    elif line.starts_with("tripnote: "):
                        msg = "\n".join([t.split(subsep)
                                         for t in line.split(": ")][1])
                        vac = Email.EmailVacation(db)
                        vac.find(get_email_target_id(user_id))
                        vac.add_vacation(start = db.Date(1970, 1, 1),
                                         end = None, text=msg, enable=True)
                    else:
                        logger.error("convertmail reported: %s\n" % line)
            except:
                    db.rollback()
                    # TODO better diagnostics
                    success = False
                    logger.error("convertmail failed")
            if success:
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
    for folder in ["user.%s%s" % (uname, sub)
                   for sub in "", ".spam", ".Sent", ".Drafts", ".Trash"]:
        res, list = cyradm.m.list(folder)
        if res == 'OK' and list[0]:
            continue
        res = cyradm.m.create(folder)
        if res[0] <> 'OK':
            logger.error("IMAP create %s failed: %s", folder, res[1])
            return False

    # restrict access to INBOX.spam.  the user can change the
    # ACL to override this, though.
    res = cyradm.m.setacl("user.%s.spam" % uname, uname, "lrswipd")
            
    # we don't care to check if the next command runs OK.
    # almost all IMAP clients ignore the file, anyway ...
    cyrus_subscribe(uname, imaphost)
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
    try:
        uname = get_account(user_id)[1]
        mailto = get_primary_email_address(mailto_id)
    except Errors.NotFoundError:
        logger.error("%d or %d not found" % (user_id, mailto_id))
        return False

    es_to = Email.EmailServer(self._db)
    es_to.find(to_host)
    es_fr = Email.EmailServer(self._db)
    es_fr.find(from_host)
    hq = get_email_hardquota()

    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'mvmail',
           uname, mailto, hq,
           es_fr.name, str(es_fr.email_server_type),
           es_to.name, str(es_to.email_server_type)]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    EXIT_SUCCESS = 0
    EXIT_LOCKED = 1
    EXIT_NOTIMPL = 2
    EXIT_QUOTAEXCEEDED = 3
    EXIT_FAILED = 4
    errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    if errnum == EXIT_QUOTAEXCEEDED:
        # TODO: bump quota, or something else
        return True
    elif errnum == EXIT_SUCCESS:
        return True
    else:
        logger.error('mvmail failed, returned %d' % errnum)
        return False

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
    disk = Disk.Disk(db)
    disk.clear()
    disk.find(disk_id)
    host = Disk.Host(db)
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
        group = Group.Group(db)
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
