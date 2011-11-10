#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2010-2011 University of Oslo, Norway
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
Perform full notes group sync

Fetch groups from Notes and groups with notes spread from Cerebrum and
compare. This script will create new notes groups, perform memgership
updates and delete notes groups depending on the differences.
"""


import getopt
import sys
import cerebrum_path
from Cerebrum.modules import NotesUtils
from Cerebrum.Utils import Factory

db = Factory.get('Database')()
db.cl_init(change_program="notes_group")
co = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")
dryrun = False


def fetch_cerebrum_data(group_spread, account_spread):
    """
    Fetch relevant data for all groups that has spread to Notes.

    @param spread: notes spread
    @type  spread: str
    @rtype: list
    @return: TODO
    """
    logger.debug('Fetching groups from Cerebrum')
    # TBD: list instead of dict?
    groups = {}
    group = Factory.get('Group')(db)
    for row in group.search(spread=group_spread):
        gid = int(row['group_id'])
        tmp = groups.setdefault(gid, {'group_id': gid,
                                      'members': []})
        tmp['name'] = row['name']
        tmp['description'] = row['description']
        
    logger.debug('Fetching group members from Cerebrum')
    # We only want members of notes groups. Furthermore only account
    # members with notes spread are relevent
    for row in group.search_members(group_id=groups.keys(), 
                                    member_spread=account_spread):
        gid = int(row['group_id'])
        mid = int(row['member_id'])
        if mid not in groups[gid]['members']:
            groups[gid]['members'].append(mid)

    logger.debug('Fetch from Cerebrum done')
    return groups


def read_from_notes():
    """
    Fetch data about Notes groups

    @rtype: dict
    @return: group name -> ?
    """
    sock = NotesUtils.SocketCom()
    groupdict = {}
    logger.debug("Reading groups from notes...")
    # TBD: How to list groups?

    return groupdict


def compare_groups(notesdata, cerebrumdata):
    """
    Compare groups from Notes and Cerebrum

    @param notesdata: gname -> ?
    @type  notesdata: dict 
    @param cerebrumdata: 
    @type  cerebrumdata: list of dicts with keys: group_id, name, description, members 
    @rtype: None
    """
    
    sock = NotesUtils.SocketCom()
    for group in cerebrumdata:
        if group['name'] not in notesdata:
            # The user exists only in Cerebrum.
            logger.info("New group: " + group['name'])
            create_notes_group(sock, group)
        else:
            # TODO: compare description, members, etc.
            pass
        
    # The remaining entries in notesdata should not exist in Notes
    # delete_notes_groups(sock, notesdata)
    sock.close()


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


def delete_notes_group(sock, groupnames):
    """
    Delete the given notes groups.
    
    @param sock: Connection to Notes server
    @type  sock: NotesUtils.SocketCom instance
    @param groupnames: list of group names which should be deleted.
    @type  groupnames: list
    """
    cmd = ['DELGRP',
           'GroupName', None]
    for group in groupnames:
        logger.info('Deleting group: ' + group)
        cmd[2] = group
        notes_cmd(sock, cmd, dryrun=dryrun)


def create_notes_group(sock, group):
    """
    Create the given group.

    @param sock: Connection to Notes server
    @type  sock: NotesUtils.SocketCom instance
    @param group: dict with the keys: group_id, name, description, members 
    @type  group: dict
    """
    cmd = ["CREATEGRP", "GroupName", group['name'],
           "GroupType", None, 'GroupDescr', group['description']]
    notes_cmd(sock, cmd, dryrun=dryrun)


def full_sync():
    """
    Run full Cerebrum -> Notes sync.
    """
    notesdata = read_from_notes()
    logger.info("Fetched %i groups from notes" % len(notesdata))
    # FIXME: Notes group spread doesn't exists yet
    cerebrumdata = fetch_cerebrum_data("Notes_group")
    logger.info("Fetched %i groups from cerebrum" % len(cerebrumdata))
    compare_groups(notesdata, cerebrumdata)


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
