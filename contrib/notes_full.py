#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009-2011 University of Oslo, Norway
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
Perform full notes sync

Fetch accounts from Notes and accounts with notes spread from cerebrum
and compare. This script will create new notes accounts, perform name
or OU changes or delete notes accounts depending on the differences.
"""

import getopt
import sys
import cerebrum_path
import cereconf
from Cerebrum.modules import NotesUtils
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
db.cl_init(change_program="notes_full")
co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")
dryrun = False


def fetch_cerebrum_data(spread):
    """
    Fetch relevant data for all accounts that has spread to Notes.

    @param spread: notes spread
    @type  spread: str
    @rtype: list
    @return: list of dicts with keys: uname, fullname, account_id,
             ou_path, person_id
    """
    logger.debug('Fetching person names from Cerebrum')
    pid2name = {}
    person = Factory.get('Person')(db)
    ac = Factory.get('Account')(db)
    for row in person.search_person_names(source_system=co.system_cached,
                                          name_variant=co.name_full):
        pid2name[int(row['person_id'])] = row['name']

    # Fetch all accounts with Notes spread
    logger.debug('Fetching accounts from Cerebrum')
    aid2ainfo = {}
    for row in ac.search(spread=spread, owner_type=co.entity_person):
        aid2ainfo[int(row['account_id'])] = {'uname': row['name'],
                                             'owner_id': int(row['owner_id'])}
    # Fetch OU information for accounts, that is the OU for the
    # primary affiliation.  

    # TODO: we should use person affiliation and person affiliation
    # status to determine primary affiliation, not account types (much
    # as we do in generate_org_ldif for UiO). there is however no time
    # to do this now and as notes will be disused fairly soon (as of
    # 2013-01-03) this change does not have a high priority

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
            # Already did this account, this row is a secondary
            # affiliation (Result from ac.list_accounts_by_type is
            # ordered by affiliations priority.)
            continue
        if person_id in done_person:
            logger.warn("User %s has more than one Notes user",
                        aid2ainfo[account_id]['uname'])
        ou_id = int(row['ou_id'])
        if ou_id not in ou_path:
            path = NotesUtils.get_cerebrum_ou_path(ou_id)
            if not path:
                # can be None or empty list
                logger.debug("Didn't find a ou_path for user %s" %
                             aid2ainfo[account_id]['uname'])
                ou_path[ou_id] = 'ANDRE'
            elif '' in [x.strip() for x in path]:
                # If path contains empty strings then some part of ou
                # hierarchy lacks an acronym. Then something's
                # probably wrong and we should investigate.
                logger.warn("Empty element in ou path for user %s: %s" %
                            (aid2ainfo[account_id]['uname'], path) +
                            "Setting ou path to: ANDRE")
                ou_path[ou_id] = 'ANDRE'
            else:
                # If '&' is a part of ou path, then we must escape it
                ou_path[ou_id] = "/".join(path).replace('&', '%26')
                
        aid2ainfo[account_id]['ou_path'] = ou_path[ou_id]
        done_person[person_id] = True

    ret = []
    for ac_id, dta in aid2ainfo.items():
        tmp = { 'account_id': ac_id, 'uname': dta['uname'] }

        if dta['owner_id'] not in pid2name:
            logger.warn("%i is very new?" % dta['owner_id'])
            continue
        if 'ou_path' not in dta:
            logger.info("User %s has no affiliations?", dta['uname'])
            dta['ou_path'] = 'ANDRE'
        tmp['person_id'] = dta['owner_id']
        tmp['ou_path'] = dta['ou_path']
        tmp['fullname'] = pid2name[dta['owner_id']]
        ret.append(tmp)

    logger.debug('Fetch from Cerebrum done')
    return ret


def read_from_notes():
    """
    Fetch data about Notes accounts

    @rtype: dict
    @return: uname -> '<Full name>/<OU path>' 
    """
    sock = NotesUtils.SocketCom()
    userdict = {}
    logger.debug("Reading users from notes...")
    resp, lines = notes_cmd(sock, 'LUSERS')
    for line in lines:
        userdata = line.split("&")
        user = userdata[1]
        fullname = userdata[3]
        if user in userdict:
            logger.warn("User exists multiple times in domino: %r " % user)
        else:
            userdict[user] = fullname.strip()
    sock.close()
    logger.info("Got %d users from notes" % len(userdict))
    return userdict


def compare_users(notesdata, cerebrumdata):
    """
    Compare accounts from Notes and Cerebrum

    @param notesdata: uname -> name and OU info 
    @type  notesdata: dict 
    @param cerebrumdata: 
    @type  cerebrumdata: list of dicts with keys: uname, fullname,
             account_id, ou_path, person_id
    @rtype: None
    """
    
    sock = NotesUtils.SocketCom()
    for user in cerebrumdata:
        if user['uname'] not in notesdata:
            # The user exists only in Cerebrum.
            logger.info("New user: " + user['uname'])
            create_notes_user(sock, user)
        else:
            notes_name, notes_ou_path = notesdata[user['uname']].split('/', 1)
            # Compare name
            if notes_name != user['fullname']:
                logger.info("%s: new name '%s', current '%s'",
                            user['uname'], user['fullname'], notes_name)
                rename_notes_user(sock, user)
            # Compare OU
            cere_ou_path = user['ou_path'].rstrip('/')
            notes_ou_path = ou_clean(notes_ou_path)
            if not cere_ou_path == notes_ou_path:
                # If only case differs don't move user
                if cere_ou_path.upper() == notes_ou_path.upper():
                    logger.debug("Only case differs. Not moving user. " +
                                 "Cerebrum OU: %s, Notes OU: %s" %
                                 (cere_ou_path, notes_ou_path))
                else:
                    logger.info("%s: new OU path '%s', current '%s'",
                                user['uname'], cere_ou_path, notes_ou_path)
                    move_notes_user(sock, user)
            # Everything is OK or taken care of
            del notesdata[user['uname']]
    # The remaining entries in notesdata should not exist in Notes
    ##
    ## TODO: Notes-dift vil ikke slette brukere inntil ting er testet
    ## bedre. Kommenterer ut inntil videre.
    ##
    delete_notes_users(sock, notesdata)
    sock.close()


def ou_clean(ou_path):
    # Strip away trailing /
    ou_path = ou_path.rstrip('/')
    # Strip away any leading CN=
    ou_path = ou_path.split("CN=")[-1]
    # Strip ou suffix from notes_path
    for ou_suffix in cereconf.NOTES_OU_SUFFIX:
        ou_path = ou_path.rstrip('/')
        if ou_path.endswith(ou_suffix):
            ou_path = ou_path[:-len(ou_suffix)-1]
            break
    return ou_path


class NotesException(Exception):
    pass


def notes_cmd(sock, cmd, dryrun=False):
    """Sends cmd over socket and reads response. If the response code
    is not 2xx, throw an exception. Just print command and return
    success if dryrun mode.

    @param sock: Connection to Notes server
    @type  sock: NotesUtils.SocketCom instance
    @param cmd: Command to send to Notes server
    @type  cmd: str, tuple or list
    @rtype: tuple
    @return: The response is returned as a tuple consisting of the
    response code and an array of the lines.
    """
    ## TODO: We send text encoded as utf-8, recieves cp850 and encode
    ## that to latin-1. This needs to be sorted out.
    if dryrun:
        logger.debug("Notes command: '%s'", cmd)
        return ("200", ["dryrun mode"])
    
    if isinstance(cmd, (list, tuple)):
        cmd = "&".join(cmd)
    sock.send(cmd + "\n")
    line = sock.readline()
    resp_code = line[:3]
    lines = []
    while line[3] == '-':
        lines.append(line[4:].decode('cp850').encode('latin1'))
        line = sock.readline()
    if resp_code[0] != '2':
        raise NotesException("Notes cmd '%s' returned %s (%s)" %
                             (cmd, resp_code, line))
    logger.debug("Response from Notes server: " + str(line))
    return resp_code, lines


def delete_notes_users(sock, usernames, status='delete'):
    """
    Delete the given notes users.  must be one of the
    alternatives defined in the communication protocol.
    
    @param sock: Connection to Notes server
    @type  sock: NotesUtils.SocketCom instance
    @param usernames: list of usernames which should be deleted.
    @type  usernames: list
    @param status: must be one of the alternatives defined in the
    communication protocol
    @type  : str
    """
    cmd = ['DELUNDELUSR',
           'ShortName', None,
           'Status', status]
    for user in usernames:
        logger.info('Deleting user: ' + user)
        cmd[2] = user
        notes_cmd(sock, cmd, dryrun=dryrun)


def create_notes_user(sock, user):
    """
    Try to create the given account.

    @param sock: Connection to Notes server
    @type  sock: NotesUtils.SocketCom instance
    @param user: account dict with the keys: uname, fullname,
             account_id, ou_path, person_id
    @type  user: dict
    """
    fname, lname = split_name(user['fullname'])
    cmd = ["CREATEUSR", "ShortName", user['uname'],
           "FirstName", fname, "LastName", lname]
    # map ou_path to Notes format
    ous = user['ou_path'].split("/")
    ous.reverse()
    i = 1
    for ou in ous:
        cmd.extend(["OU%d" % i, ou])
        i += 1
    notes_cmd(sock, cmd, dryrun=dryrun)


def split_name(name):
    # str.rsplit would be convenient, but didn't appear until Python 2.4
    names = name.split(' ')
    return " ".join(names[:-1]), names[-1]


def rename_notes_user(sock, user):
    """
    Try to change name for the given account.

    @param sock: Connection to Notes server
    @type  sock: NotesUtils.SocketCom instance
    @param user: account dict with the keys: uname, fullname,
             account_id, ou_path, person_id
    @type  user: dict
    """
    fname, lname = split_name(user['fullname'])
    cmd = ['RENAMEUSR',
           'ShortName', user['uname'],
           'FirstName', fname,
           'LastName', lname]
    notes_cmd(sock, cmd, dryrun=dryrun)


def move_notes_user(sock, user):
    """
    Try to alter OU for the given account.

    @param sock: Connection to Notes server
    @type  sock: NotesUtils.SocketCom instance
    @param user: account dict with the keys: uname, fullname,
             account_id, ou_path, person_id
    @type  user: dict
    """
    ous = user['ou_path'].split("/")
    ous.reverse()
    cmd = ['MOVEUSR',
           'ShortName', user['uname']]
    i = 1
    for ou in ous:
        cmd.extend(["OU%d" % i, ou])
        i += 1
    notes_cmd(sock, cmd, dryrun=dryrun)


def full_sync():
    """
    Run full Cerebrum -> Notes sync.
    """
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
    --dryrun        Don't do anything
    --full          Perform full sync (required argument)
    --logger-name   Which logger to use ("console" or "cronjob")
    --logger-level  Which debug level to use
    """
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
