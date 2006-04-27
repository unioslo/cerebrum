#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import sys
import string
import getopt
import cerebrum_path
import cereconf
import os.path
import datetime

from Cerebrum.Utils import Factory
from Cerebrum import Errors

logger = Factory.get_logger("console")


class ad_email_import:


    def __init__(self,file_path):
        if(0 == os.path.isfile(file_path)):
            logger.critical("file %s does not exist." % file_path)
            sys.exit(1)
        else:
            self.db = Factory.get('Database')()

    def commit(self):
        self.db.commit()

    def parse(self,file_path):
        file_handle = open(file_path,"r")
        for line in file_handle:
            if ((line[0] != '\n') or (line[0] != "#")):
                line = line.rstrip()
                uname,email_address = line.split(",")
                local_part,domain = email_address.split("@")
                self.insert(uname,local_part,domain)


    # if an old one is found, it updates.
    def insert(self,uname,local_part,domain):
        #print "--%s,%s,%s" % (uname,local_part,domain)
        create_date = datetime.date.today()
        update_date = datetime.date.today()

        ins_query = """
        INSERT INTO [:table schema=cerebrum name=ad_email]
        (account_name,local_part,domain_part,create_date,update_date)
        VALUES (:account_name,:local_part,:domain_part,[:now],[:now])
        """
        ins_binds = {'account_name':uname,
                     'local_part': local_part,
                     'domain_part': domain
                     }

        sel_query = """
        SELECT account_name,local_part,domain_part from [:table schema=cerebrum name=ad_email]
        WHERE account_name=:account_name
        """
        sel_binds = {'account_name': uname}

        upd_query = """
        UPDATE [:table schema=cerebrum name=ad_email]
        SET local_part=:local_part, domain_part=:domain,update_date=[:now]
        WHERE account_name=:account_name
        """
        upd_binds = { 'local_part' : local_part,
                      'domain' : domain,
                      'account_name': uname
                      }

        
        try:
            res = self.db.query_1(sel_query,sel_binds)
            res = self.db.execute(upd_query,upd_binds)
            logger.info("Updated %s to %s@%s" % (uname,local_part,domain))
            
        except Errors.NotFoundError:
            res = self.db.execute(ins_query,ins_binds)
            logger.info("Insertet new %s to %s@%s" % (uname,local_part,domain))



def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'i:',['import_file'])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    import_path = 0

    for opt,val in opts:
        if opt in('-i','--import_file'):
            import_path = val

    if import_path != 0:
        ad = ad_email_import(import_path)
        ad.parse(import_path)
        ad.commit()
    else:
        usage()


def usage():
    print """ This program imports AD email addreses into cerebrum.
    the file must be on the form: account_name,email_address
    
    Usage: python import_ad_email.py -i path/to/import/file
    -i | --import_file : import file containing ad email addresses.
    -h | --help        : this text
    """


if __name__=='__main__':
    main()

# arch-tag: b4458ff6-b426-11da-83c0-a8a36dc8763a
