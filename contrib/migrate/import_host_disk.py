#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2006, 2014 University of Oslo, Norway
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

""" Register hosts, disks or e-mail servers in Cerebrum from input file. """

import getopt
import sys
import string
import re

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

def usage(exitcode=0):
    print """Usage: import_host_disk.py -h hostname -d diskpath
                    import_host_disk.py -f filename

    Register hosts, disks or e-mail servers in Cerebrum from input file.

    -h, --host HOSTNAME Register a host in Cerebrum with the given hostname.
    -d, --disk PATH     Register a disk in Cerebrum with the given path.
    -e, --email-server  Register email servers in Cerebrum. The servers need to
                        be given through the --file argument.
    -f, --file FILE     Parse file and register hosts/disks/servers in Cerebrum.
                        Available line formats::

                            HOSTNAME:DISK_PATH:DESCRIPTION

                            HOSTNAME:DISK_PATH

                            HOSTNAME

                        For email servers the line format is a bit different::

                           SERVER_TYPE:NAME:DESCRIPTION

                        where SERVER_TYPE must exist in Cerebrum, e.g.
                        'exchange'.

                        Comments could be added with #.

    --dryrun            Do not commit the changes
    --help              Show this and quit
    """
    sys.exit(exitcode)

def register_host(hname, description="A host"):
    host = Factory.get('Host')(db)
    try:
        host.find_by_name(hname)
        if host.description != description:
            host.description=description
    except Errors.NotFoundError:
        host.populate(hname, description)
    try:
        host.write_db()
        logger.info("Host %s registered\n", hname)
    except Errors.DatabaseException:
        logger.error("Could not write to the Cerebrum-database")
        sys.exit(2)
    db.commit()

def register_email_server(email_srv_type, email_srv_name, description):
    email_server = Email.EmailServer(db)

    try:
        email_srv_type = const.EmailServerType(email_srv_type)
        int(email_srv_type)
    except Errors.NotFoundError:
        logger.error("Unknown email server type: %s. Entry skipped",
                     email_srv_type)
        return

    try:
        email_server.find_by_name(email_srv_name)
        email_server.email_server_type=email_srv_type
        email_server.description=description
    except Errors.NotFoundError:
        try:
            host = Factory.get('Host')(db)
            host.find_by_name(email_srv_name)
            email_server.populate(email_srv_type, parent=host.entity_id)
        except Errors.NotFoundError:
            email_server.populate(email_srv_type, name=email_srv_name, description=description)
    try:
        email_server.write_db()
        logger.debug("Registered email server %s", email_srv_name)
    except Errors.DatabaseException:
        logger.error("Could not write to the Cerebrum-database")
        sys.exit(3)

def register_disk(host_name, disk_path, description="A disk"):
    disk = Factory.get('Disk')(db)
    host = Factory.get('Host')(db)
    try:
        host.find_by_name(host_name)
    except Errors.NotFoundError:
        logger.error("No such host %s", host_name)
        sys.exit(3)
    try:
        disk.find_by_path(disk_path)
        if disk.description != description:
            disk.description = description
        if disk.host_id != host.entity_id:
            disk.host_id = host.entity_id
    except Errors.NotFoundError:
        disk.populate(host.entity_id, disk_path, description)
    try:
        disk.write_db()
        logger.info("Disk %s registered\n", disk_path)
    except Errors.DatabaseException:
        logger.error("Could not write to the Cerebrum-database")
        sys.exit(2)

def process_line(infile, emailsvr):
    """Parse given file and

    :param str infile: The input file that should contain the hosts.

    :param bool emailsvr:
        If the hosts from file should be registered as email servers. The input
        format is a bit different.

    """
    stream = open(infile, 'r')
    disk = None
    if emailsvr:
        for l in stream:
            l = l.split("#",1)[0]
            l = l.strip()
            if not l:
                continue
            logger.debug("Next is <%s>", l)
            server_type, name, description = l.split(":")
            register_email_server(server_type, name, description)
        return
    for l in stream:
        l=l.split("#",1)[0].strip()
        if l=="":
            continue
        args = l.split(":")
        if len(args)==3:
            hostname, disk, description = args
            if (disk==""):
                register_host(hostname, description)
            else:
                register_disk(hostname, disk, description)
            continue
        elif len(args)==2:
            hostname, disk = args
        elif len(args)==1:
            hostname = args[0]
        else:
            logger.warn("syntax error")
        if hostname:
            register_host(hostname)
        if disk:
            register_disk(hostname, disk)

def main():
    global db, logger, const, emailsrv

    logger = Factory.get_logger("console")
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    db.cl_init(change_program="email_dom")
    creator = Factory.get("Account")(db)
    creator.clear()
    creator.find_by_name('bootstrap_account')
    infile = None
    emailsrv = False
    disk_in = host_in = False

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'f:h:d:e',
                                   ['file=',
                                    'disk=',
                                    'host=',
                                    'email-server',
                                    'help',
                                    'dryrun'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    dryrun = False
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host_in = True
            host_name = val
        elif opt in ('-d', '--disk'):
            if not host_in:
                logger.error('You need to use -h option as well.')
                sys.exit(1)
            disk_in = True
            disk_path = val
        elif opt in ('-f', '--file'):
            infile = val
        elif opt in ('-e', '--email-server'):
            emailsrv = True
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--help',):
            usage()

    if not (host_in or disk_in) and infile == None:
        print "Missing input file and/or -d or -h"
        usage(1)

    if infile and (host_in or disk_in):
        logger.error('Cannot use both -h and -f options.')
        sys.exit(1)

    if emailsrv and infile == None:
        logger.error('You may only register email servers from file')
        usage(1)

    if infile:
        process_line(infile, emailsrv)

    if host_in:
        register_host(host_name)

    if disk_in:	
        register_disk(host_name, disk_path)

    if dryrun:
        db.rollback()
        logger.info("Rolled back all changes")
    else:
        db.commit()
        logger.info("Commiting all...")

if __name__ == '__main__':
    main()
