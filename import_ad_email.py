#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2005 University of Oslo, Norway
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

progname = __file__.split("/")[-1]
__doc__ = """
    
    Usage: %s -i path/to/import/file
    -i | --import_file : import file containing ad email addresses.
    -l | --logger_name : name of logger target
    -h | --help        : this text
    -d | --dryrun

    This program imports AD email addreses into cerebrum.
    the file must be on the form: account_name,email_address
""" % progname 

import sys
import string
import getopt
import os.path
from sets import Set

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors


logger = None
logger_name = cereconf.DEFAULT_LOGGER_TARGET


class ad_email_import:


    def __init__(self,file_path):
        if(0 == os.path.isfile(file_path)):
            logger.critical("file %s does not exist." % file_path)
            sys.exit(1)
        else:
            self.db = Factory.get('Database')()
            
        self.infile = {}
        self.indb = {}
        self.added=0
        self.deleted=0
        self.modified=0

    def loaddb(self):
        
        sql = """
        SELECT account_name, local_part, domain_part
        FROM [:table schema=cerebrum name=ad_email]
        """
        res = self.db.query(sql)
        for r in res:
            self.indb[r['account_name']] = [r['local_part'],r['domain_part']]


    def sync(self,file_path):
        self.parse(file_path)
        self.loaddb()
        
        acc_infile = Set(self.infile.keys())
        acc_indb = Set(self.indb.keys())
        
        to_delete = acc_indb.difference(acc_infile)
        to_add = acc_infile.difference(acc_indb)
        to_update = acc_infile.intersection(acc_indb)
        for item in to_add.union(to_update):
            self.insert(item)
            
        for item in to_delete:
            self.delete(item)
        
        


    def parse(self,file_path):
        file_handle = open(file_path,"r")
        for line in file_handle:
            if ((line[0] != '\n') or (line[0] != "#")):
                line = line.rstrip()
                uname,email_address = line.split(",")
                local_part,domain = email_address.split("@")
                self.infile[uname] = [local_part,domain]
                #self.insert(uname,local_part,domain)


    def delete(self,uname):
        
        sql = """
        DELETE from [:table schema=cerebrum name=ad_email]
        WHERE account_name=:account_name
        """
        binds = {'account_name': uname }
        self.db.execute(sql,binds)
        logger.info("Deleted %s from ad_email, no longer in inputfile" % (uname))
        self.deleted+=1

    # if an old one is found, update.
    def insert(self,uname):
      
        db_data = self.indb.get(uname) 
        file_data = self.infile.get(uname,[None,None])
        if db_data == file_data:
            logger.info("Address data for %s unchanged. (%s@%s)" % (uname,db_data[0],db_data[1]))
            return
        else: 
            logger.info("Address data for %s changed! old=%s, new=%s" % (uname,db_data,file_data))
        local_part = file_data[0]
        domain_part= file_data[1]

        ins_query = """
        INSERT INTO [:table schema=cerebrum name=ad_email]
        (account_name,local_part,domain_part,create_date,update_date)
        VALUES (:account_name,:local_part,:domain_part,[:now],[:now])
        """
        ins_binds = {'account_name':uname,
                     'local_part': local_part,
                     'domain_part': domain_part
                     }

        sel_query = """
        SELECT account_name,local_part,domain_part from [:table schema=cerebrum name=ad_email]
        WHERE account_name=:account_name
        """
        sel_binds = {'account_name': uname}

        upd_query = """
        UPDATE [:table schema=cerebrum name=ad_email]
        SET local_part=:local_part, domain_part=:domain_part,update_date=[:now]
        WHERE account_name=:account_name
        """
        upd_binds = { 'local_part' : local_part,
                      'domain_part' : domain_part,
                      'account_name': uname
                      }

        
        try:
            res = self.db.query_1(sel_query,sel_binds)
            res = self.db.execute(upd_query,upd_binds)
            logger.info("Updated %s to %s@%s" % (uname,local_part,domain_part))
            self.modified+=1
        except Errors.NotFoundError:
            res = self.db.execute(ins_query,ins_binds)
            logger.info("Inserted new: %s to %s@%s" % (uname,local_part,domain_part))
            self.added+=1



def main():
    global logger, logger_name
    try:
        opts,args = getopt.getopt(sys.argv[1:],'di:',['dryrun','import_file'])
    except getopt.GetoptError,m:
        print m
        usage()
        sys.exit(1)

    import_path = 0
    dryrun = False

    for opt,val in opts:
        if opt in('-i','--import_file'):
            import_path = val
        elif opt in ('-d','--dryrun'):
            dryrun = True
        elif opt in ('-l','--logger_name'):
            logger_name=val

    logger = Factory.get_logger(logger_name)


    if import_path != 0:
        ad = ad_email_import(import_path)
        ad.sync(import_path)
        logger.info("Added %d new, updated %d, deleted %d email entries in ad_email" % (ad.added,ad.modified,ad.deleted))
        if dryrun:
            ad.db.rollback()
            logger.debug("All changes rollback from database")
        else:
            ad.db.commit()
            logger.debug("All changes comittet to database")
    else:
        usage()


def usage():
    print __doc__


if __name__=='__main__':
    main()

# arch-tag: b4458ff6-b426-11da-83c0-a8a36dc8763a
