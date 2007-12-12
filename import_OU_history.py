#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003, 2003 University of Tromsoe, Norway
#
# 


import string
import getopt
import sys
import string


import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory


db = Factory.get('Database')()
logger=Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)

# This function inserts or updates ou history information
class ou_history:
    def __init__(self,file):
        splitchar = ';'
        fh = open(file,'r')
        lines = fh.readlines()
        fh.close()
        self.ou_hist = []
        linenr = 0
        for i in lines:
            linenr += 1
            i=i.rstrip()
            if ( i == '' or i.startswith('#')):
                continue
            try:
                (new_ou_id,name,old_ou_id) = i.split(splitchar)
                self.ou_hist.append({'new_ou_id':new_ou_id,'name':name,'old_ou_id':old_ou_id})
            except ValueError:
                logger.error("Invalid data in line %i: '%s'" % (linenr, i))

    # This function inserts or updates ou history
    # information
    def execute_ou_info(self):

        for foo in self.ou_hist:
            query = """
            SELECT name FROM [:table schema=cerebrum name=ou_history]
            WHERE old_ou_id=:old_ou_id AND new_ou_id=:new_ou_id
            """
            params= {'old_ou_id': foo['old_ou_id'],
                     'new_ou_id': foo['new_ou_id']}
            db_row = db.query(query,params)
            if(len(db_row)>0):
                # info on this ou mapping already exists, do nothing
                logger.info("%s (new=%s,old=%s) already exists in ou_history" % 
                            (foo['name'],foo['new_ou_id'],foo['old_ou_id']))                            
            else:
                db.execute("""INSERT INTO [:table schema=cerebrum name=ou_history]
                  (new_ou_id,name,old_ou_id)
                  VALUES
                  (:l_new_ou_id, :l_name, :l_old_ou_id)""",
                {'l_new_ou_id': int(foo['new_ou_id']),
                 'l_name': foo['name'],
                 'l_old_ou_id': foo['old_ou_id']})
                logger.info("Inserted new_id=%s, old_ou_id=%s, name=%s" %
                            (foo['new_ou_id'],foo['old_ou_id'],foo['name']))


        # Now we will delete all entries in ou_history which is not in the ou_history.txt file
        # this will ensure that the database is in sync with the import data.
        query="""
        SELECT new_ou_id, name,old_ou_id
        FROM [:table schema=cerebrum name=ou_history]
        """
        db_row=db.query(query)

        for row in db_row:
            check=False
            for single_ou in self.ou_hist:
                if(row['old_ou_id']==single_ou['old_ou_id'] and
                   row['new_ou_id']==int(single_ou['new_ou_id']) and
                   row['name']==single_ou['name']):
                    check=True
            if check ==False:
                query="""
                DELETE FROM [:table schema=cerebrum name=ou_history]
                WHERE new_ou_id=:new_ou_id AND
                name=:name and old_ou_id=:old_ou_id
                """
                params = { 'new_ou_id': row['new_ou_id'],
                           'name': row['name'],
                           'old_ou_id': row['old_ou_id']
                           }
                db.query(query,params)
                logger.info("Deleted %s" % params)

        return 0



def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'o:dh?',
                                  ['ou_history=','dryrun'])
    except getopt.GetoptError,m:
        usage(1,m)

    ou_file = ''
    dryrun=False
    for opt,val in opts:
        if opt in ('-h','-?'):
            usage()
        if opt in ('-o','--ou_history'):
            ou_file =  val
        if opt in ('-d','--dryrun'):
            dryrun=True

    if (ou_file==''):
        print "No ou file"
        usage(1)

    my_ou = ou_history(ou_file)
    my_ou.execute_ou_info()
    logger.info("done storing old ou\'s")

    if dryrun:
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committed all changes to database")
        
    sys.exit(0)
    
def usage(exit_code=0,msg=None):
    if msg:
        print msg
        
    print """

    Usage: import_OU_history -o ou_file -h -d|--dryrun

    ou_file needs to be of the following format:
    <new_ou_id>;<name>;<old_ou_id>.

    new_ou_id and old_ou_id is a 6 digit stedkode

    -h | -?              : show help
    -d | --dryrun        : do not change DB
    --logger-name name   : use this logger
    --logger-level level : use this loglevel
    """
    sys.exit(exit_code)
    
if __name__ == '__main__':
    main()

    
