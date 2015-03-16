#!/bin/env python

import datetime
import getopt
import sys


import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum import Errors


logger_name = 'console'
logger = None

class Changer:
    global logger


    def __init__(self):
        self.db=Factory.get('Database')()
        self.co=Factory.get('Constants')(self.db)
        self.account=Factory.get('Account')(self.db)
        self.person=Factory.get('Person')(self.db)
        self.logger=Factory.get_logger(logger_name)
        self.db.cl_init(change_program ='fix_homedir')
        self.count=0


    def fix_homedir(self,account_name=None):

        if account_name:            
            self.updateOneAccount(account_name)
        else:
            self.account.clear()
            a_list = self.account.list(filter_expired=False)
            for ac in a_list:
                #self.logger.debug("account: %s, keys=%s" % (ac,ac.keys()))
                self.updateOneAccount(ac['account_id'])
            


    def updateOneAccount(self,acc):
        self.account.clear()

        try:
            if isinstance(acc,str):
                self.account.find_by_name(acc)
            else:
                #assuming int
                self.account.find(acc)
        except Errors.NotFoundError:
            self.logger.error("Account %s not found!" % acc)
            return None
        
        self.logger.info("Working on account %s(ID=%d)" % (self.account.account_name,self.account.entity_id ))
        
        spreads = self.account.get_spread()
        for sprd in spreads:   # for hvert spread vi skal sette
            s = sprd['spread']
            do_write=False
            try:
                home = self.account.get_home(s)
            except Errors.NotFoundError:
                self.logger.warn("Account %s has spread %s, but no home for that spread, create" % (self.account.account_name,s))
                self.account.set_home_dir(s)
                do_write=True 
            else:
                if not home['home']:
                    self.logger.debug("home for spread %d: home=%s, update needed" % (s,home['home']))
                    self.account.set_home_dir(s)                    
                    do_write=True
            if do_write:
                self.count+=1
                try:
                    self.account.write_db()
                except Exception,m:
                    self.logger.error("Failed updating DB: %s",m)
                
            
                

    def commit(self):
        self.db.commit()
        self.logger.info("Commited all changes to database")
        self.logger.info("Updated %d entries" % (self.count))

    def rollback(self):
        self.db.rollback()
        self.logger.info("DRYRUN: Rolled back all changes")
        self.logger.info("Would update %d entries" % (self.count))

   
def usage(exitcode=0):
    print """Usage: extend_account.py -a name [-h] [-d] [-l loggername] 
    -h | --help : show this message
    -d | --dryrun : do not commit changes to database
    -a | --account <name> : work only on this account
    -l | --logger_name <name> : logger target to use

    This program fixes inconsistensies in how homedir should be set for accounts.
    We want all our account to have homedir on this form:
    username=bto001 => homeDirectory: /its/home/b/bt/bto001

    """
    sys.exit(exitcode)



def main():
    global logger_name

    
    dryrun = False
    account_name = None
    today = datetime.date.today()
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hda:l:',
                                   ['help','dryrun','account=','logger_name='])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ['-h', '--help']:
            usage(0)
        elif opt in ['-d', '--dryrun']:
            dryrun=True
        elif opt in ['-a', '--account']:
            account_name=val
        elif opt in [ '-l', '--logger_name']:
            logger_name = val

    worker=Changer()
    worker.fix_homedir(account_name)

    if dryrun:
        worker.rollback()
    else:
        worker.commit()
       
if __name__ == '__main__':
    main()



