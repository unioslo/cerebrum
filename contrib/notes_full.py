#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import cerebrum_path
from Cerebrum.modules import notesutils
from Cerebrum import Errors
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
db.cl_init(change_program="notes_full")

co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")
dryrun = False

def fetch_cerebrum_data(spread):
    """For all accounts that has spread to Notes, returns a list of
    dicts with the keys: uname, fullname, account_id, ou_path, person_id

    """
    logger.debug('Fetching person names from Cerebrum')
    pid2name = {}
    person = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    for row in person.list_persons_name(source_system=co.system_cached,
                                        name_type=co.name_full):
        pid2name[int(row['person_id'])] = row['name']

    # Fetch account-info.  Unfortunately the API doesn't provide all
    # required info in one function, so we do this in steps.
    logger.debug('Fetching accounts from Cerebrum')
    aid2ainfo = {}
    for row in ac.search(spread=spread, owner_type=co.entity_person):
        aid2ainfo[int(row['account_id'])] = { 'uname': row['name'] }

    logger.debug('Fetching owners from Cerebrum')
    for row in ac.list():
        acc_id = int(row['account_id'])
        if acc_id not in aid2ainfo:
            continue
        aid2ainfo[acc_id]['owner_id'] = int(row['owner_id'])

    ou_path = {}
    logger.debug('Fetching ous from Cerebrum')
    done_person = {}
    for row in ac.list_accounts_by_type():
        person_id = int(row['person_id'])
        account_id = int(row['account_id'])
        if account_id not in aid2ainfo:
            # not a Notes user
            continue
        if 'ou_path' in aid2ainfo[account_id]:
            # already did this account, this row is a secondary
            # affiliation
            continue
        if person_id in done_person:
            logger.warn("User %s has more than one Notes user",
                        aid2ainfo[account_id]['uname'])
        ou_id = int(row['ou_id'])
        if ou_id not in ou_path:
            path = notesutils.get_cerebrum_ou_path(ou_id)
            if not path:
                # can be None or empty list
                ou_path[ou_id] = 'ANDRE'
            else:
                ou_path[ou_id] = "/".join(path)
        aid2ainfo[account_id]['ou_path'] = ou_path[ou_id]
        done_person[person_id] = True

    ret = []
    for ac_id, dta in aid2ainfo.items():
        tmp = { 'account_id': ac_id, 'uname': dta['uname'] }

        if dta['owner_id'] not in pid2name:
            logger.warn("%i is very new?" % dta['owner_id'])
            continue
        if 'ou_path' not in dta:
            logger.warn("User %s has no affiliations?", dta['uname'])
            dta['ou_path'] = 'ANDRE'
        tmp['person_id'] = dta['owner_id']
        tmp['ou_path'] = dta['ou_path']
        tmp['fullname'] = pid2name[dta['owner_id']]
        ret.append(tmp)

    logger.debug('Fetch from Cerebrum done')
    return ret


def read_from_notes():
    sock = notesutils.SocketCom()
    userdict = {}

    resp, lines = notes_cmd(sock, 'LUSERS')
    for line in lines:
        userdata = line.split("&")
        user = userdata[1]
        fullname = userdata[3]
        try:
            if userdict[user] >= 0:
                logger.warn("User exists multiple times in domino: %r " % user)
        except KeyError:
            userdict[user] = fullname
    sock.close()
    return userdict


def compare_users(notesdata, cerebrumdata):
    sock = notesutils.SocketCom()

    for user in cerebrumdata:
        if user['uname'] not in notesdata:
            # The user exists only in Cerebrum.
            logger.info("New user: " + user['uname'])
            create_notes_user(sock, user['uname'])
        else:
            n_user = notesdata[user['uname']]
            c_notes_username = "%s/%s/UIO" % (user['fullname'],
                                              user['ou_path'].upper())
            if n_user != c_notes_username:
                logger.info("%s: new name '%s', current '%s'",
                            user['uname'], c_notes_username, n_user)
                rename_notes_user(sock, user)
            # Everything is OK or taken care of
            del notesdata[user['uname']]
    # The remaining entries in notesdata should not exist in Notes
    delete_notes_users(sock, notesdata)
    sock.close()


class NotesException(Exception):
    pass


def notes_cmd(sock, cmd, dryrun=False):
    """Sends cmd over socket and reads response.  If the response code
    is not 2xx, throw an exception.  The response is returned as a
    tuple consisting of the response code and an array of the lines.

    """

    if dryrun:
        logger.debug("Notes command: '%s'", cmd)
        return ("200", ["dryrun mode"])

    assert cmd == 'LUSERS'
    sock.send(cmd + "\n")
    line = sock.readline()
    resp_code = line[:3]
    lines = []
    while line[3] == '-':
        lines.append(line[4:].decode('cp850').encode('latin1'))
        line = sock.readline()
    if resp_code[0] != '2':
        raise NotesException("Notes cmd '%s' returned %s (%s)" %
                             (cmd, resp_code, lines[0]))
    return resp_code, lines


def delete_notes_users(sock, usernames):
    for user in usernames:
        logger.info('Deleting user: ' + user)
        notes_cmd(sock, "DELETEUSR&Shortname&" + user, dryrun=dryrun)


def create_notes_user(sock, username):
    notes_cmd(sock, "CREATEUSR&ShortName&" + username, dryrun=dryrun)


def rename_notes_user(sock, user):
    ous = user['ou_path'].split("/")
    ous.reverse()
    cmd = ['RENAMEUSR',
           'ShortName', user['uname'],
           'FullName', user['fullname']]
    i = 1
    for ou in ous:
        cmd.extend(("OU%d" % i, ou))
        i += 1
    notes_cmd(sock, "&".join(cmd), dryrun=dryrun)


def full_sync():
    notesdata = read_from_notes()
    cerebrumdata = fetch_cerebrum_data("Notes_user")
    logger.info("Fetched %i users" % len(cerebrumdata))
    compare_users(notesdata, cerebrumdata)


def main():
    global dryrun
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                   ['help', 'full', 'dryrun'])
    except getopt.GetoptError:
        usage()

    do_full = False
    for opt, val in opts:
        if opt in ('--help',):
            usage(0)
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--full',):
            do_full = True
    if not do_full:
        usage()
    full_sync()

def usage(exitcode=64):
    print """Usage: [options]
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
