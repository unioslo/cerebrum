#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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


#
# Generic imports
#
import getopt
import sys

#
# cerebrum imports
#
from Cerebrum import Errors
from Cerebrum.Utils import Factory

#
# Global variables
#
db = Factory.get('Database')()
logger = Factory.get_logger("cronjob")
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)
const = Factory.get('Constants')(db)
Cgroup = Factory.get('Group')(db)
ou = Factory.get('OU')(db)

group = []
current_group = None
progname = __file__.split("/")[-1]
db.cl_init(change_program=progname)
#
# doc string
#
__doc__ = """ This program adds accounts to groups. The program can
either read users and their groups from a text file, or from user input

usage:: %s [options] 

options:
       -h | --help       : this text
       -f | --file       : file containing groups and member username
       -i | --input      : read group names and usernames from user input
""" % (progname)


def process_file(file):
    fh = open(file, 'r')
    for line in fh:
        line = line.strip()
        process_line(line)
    fh.close()


def process_line(line):
    global current_group
    global group
    if ((line[0:3].isalpha()) and (line[3:5].isdigit()) and (len(line) == 6)):
        #        print "\t adding username: %s" % line
        add_user(line)
    elif (len(line) > 0):
        current_group = line.strip()
        add_group(line)
        # group.append(line)


#        print "adding group: %s" % line


def add_group(group_name):
    global group
    group_info = {'group_name': group_name, 'member': ''}
    group.append(group_info)


def add_user(user):
    global current_group
    global group
    for group_info in group:
        if group_info['group_name'] == current_group:
            group_info['member'] = "%s,%s" % (group_info['member'], user)


def print_all():
    global group
    for item in group:
        print "group: %s has members:%s" % (item['group_name'], item['member'])


#
# Parse group list. foreach group, add all members.
#
def add_user_to_group():
    global group
    member_list = []
    for item in group:
        Cgroup.clear()
        print "group is:%s" % item['group_name'].decode('utf-8')
        # foo = "%s" % item['group_name'].decode('utf-8')
        # bar = u"%s" % foo
        Cgroup.find_by_name(item['group_name'].decode('utf-8'))

        member_list = item['member'].split(',')
        for member in member_list:
            if (len(member) > 0):
                try:
                    logger.info("processing account name:%s" % member)
                    account.clear()
                    account.find_by_name(member)
                    logger.info("\t account found")
                except:
                    logger.error("Account %s not found" % (member,))
                    continue
                try:
                    person.clear()
                    person.find(account.owner_id)
                    logger.info("\t found person_id:%s" % person.entity_id)
                    if (person.has_spread(const.spread_uit_ldap_person) == 0):
                        person.add_spread(const.spread_uit_ldap_person)
                except Errors.NotFoundError:
                    logger.error(
                        "\r unable to set person spread LDAP_person for person:%s" % (
                            account.owner_id))
                    continue
                try:
                    retval = Cgroup.has_member(account.entity_id)
                    print "retval:%s" % retval
                    if retval == False:
                        Cgroup.add_member(account.entity_id)
                        logger.info("adding account_id:%s to group id:%s" % (
                            account.entity_id, Cgroup.entity_id))
                    else:
                        logger.info(
                            "account_id:%s is already a member of  group id:%s" % (
                                account.entity_id, Cgroup.entity_id))
                except:
                    # print dir(Cgroup)
                    logger.error(
                        "unable to add account_id:%s to group_id:%s" % (
                            account.entity_id, Cgroup.entity_id))
                    logger.error("is account already a member of this group?")
                    db.rollback()
                    continue


def main():
    input_file = None
    input == False
    dryrun = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'f:ihd',
                                   ['file=', 'input', 'help', 'dryrun'])
    except getopt.GetoptError, m:
        usage(1, m)

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        if opt in ('-f', '--file'):
            input_file = val
        if opt in ('-i', '--input'):
            input == True
        if opt in ('-d', '--dryrun'):
            logger.info("Dryrun. no changes to database")
            dryrun = True

    if (input == True):
        input()
    elif (input_file != None):
        process_file(input_file)
        print_all()
        add_user_to_group()
    else:
        msg = "You must spesify either -f or -i to add/remove accounts to groups"
        usage(msg)

    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Comitting changes to database")


def usage(exitcode=0, msg=None):
    if msg: print msg
    print __doc__
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
