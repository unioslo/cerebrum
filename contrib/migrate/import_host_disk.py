#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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
import string
import re

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

def usage():
    print """Usage: import_host_disk.py -h hostname -d diskpath
                    import_host_disk.py -f filename
    -d, --disk         : register a disk in cerebrum
    -h, --host         : register a host in cerebrum
    -e, --email-server : register email servers in cerebrum  
    -f, --file         : parse file and register hosts/disks in cerebrum
                         [hostname:disk_path\n | hostname]
    """
    sys.exit(0)

def register_host(hname):
    host = Factory.get('Host')(db)
    try:
        host.find_by_name(hname)
    except Errors.NotFoundError:
        host.populate(hname, 'HiOF host')
    try:
        host.write_db()
        logger.info("Host %s registered\n", hname)
    except Errors.DatabaseException:
        logger.error("Could not write to the Cerebrum-database")
        sys.exit(2)
    db.commit()

def register_email_server(email_srv_type, email_srv_name, description):
    email_server = Email.EmailServer(db)
    if email_srv_type == 'nfs':
        email_srv_type = const.email_server_type_nfsmbox
    else:
        # feel free to implement support for other srv_types 
        logger.error("Unknow email server type")
    host = Factory.get('Host')(db)
    try:
        host.find_by_name(email_srv_name)
    except Errors.NotFoundError:        
        email_server.populate(email_srv_type, name=email_srv_name, description=description)
    try:
        email_server.write_db()
        logger.debug("Registered email server %s", email_srv_name)
    except Errors.DatabaseException:
        logger.error("Could not write to the Cerebrum-database")
        sys.exit(3)
        
def register_disk(host_name, disk_path):
    disk = Factory.get('Disk')(db)
    host = Factory.get('Host')(db)            
    try:
        host.find_by_name(host_name)
    except Errors.NotFoundError:
        logger.error("No such host %s", host_name)
        sys.exit(3)
    try:
        disk.find_by_path(disk_path)
    except Errors.NotFoundError:
        disk.populate(host.entity_id, disk_path, 'HiOF disk')
        try:
            disk.write_db()
            logger.info("Disk %s registered\n", disk_path)
        except Errors.DatabaseException:
            logger.error("Could not write to the Cerebrum-database")
            sys.exit(2)

def process_line(infile, emailsvr):
    stream = open(infile, 'r')        
    host = disk = None
    if emailsvr:
        for l in stream:
            type, name, description = string.split(l.strip(),":")
            register_email_server(type, name, description)
        return None
        stream.close()
    for l in stream:
	if ':' in l.strip():
           hostname, disk = string.split(l.strip(), ":")
        else:
           hostname = l.strip()
        if hostname:
            register_host(hostname)
        if disk:
            register_disk(hostname, disk)
    stream.close()

def main():
    global db, logger, const, emailsrv
    
    logger = Factory.get_logger("console")    
    db = Factory.get("Database")()
    account = Factory.get("Account")(db)
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
                                    'email-server'])
    except getopt.GetoptError:
        usage()

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
            
    if not (host_in or disk_in) and infile == None:
        usage()

    if infile and (host_in or disk_in):
        logger.error('Cannot use both -h and -f options.')
        sys.exit(1)

    if emailsrv and infile == None:
        logger.error('You may only register email servers from file')
        usage()
        
    if infile:
        process_line(infile, emailsrv)

    if host_in: 
        register_host(host_name)

    if disk_in:	
        register_disk(host_name, disk_path)

    db.commit()
    logger.info("Commiting all...")

if __name__ == '__main__':
    main()
