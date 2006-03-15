#!/usr/bin/env python2.2
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
from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory


# This function inserts or updates ou history information
class Ou_History:
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
            if ( i == '' or i[0] == '#'):
                #print "dropping line nr %i:'%s'" % (linenr,i) 
                continue
            try:
                (new_ou_id,name,old_ou_id) = i.split(splitchar)
                self.ou_hist.append({'new_ou_id':new_ou_id,'name':name,'old_ou_id':old_ou_id})
            except ValueError:
                print "Invalid data in line %i: '%s'" % (linenr, i)
        #print self.ou_hist


    # This function inserts or updates ou history
    # information
    def execute_ou_info(self):
        db = Factory.get('Database')()
        for foo in self.ou_hist:
            query = "select name from ou_history where old_ou_id='%s' and new_ou_id='%s'" % (foo['old_ou_id'],foo['new_ou_id'])
            db_row = db.query(query)
            
            if(len(db_row)>0):
                # info on this ou mapping already exists, do nothing
                print"%s already exists in ou_history" % foo['name']
            else:
                db.execute("""INSERT INTO [:table schema=cerebrum name=ou_history]
                  (new_ou_id,name,old_ou_id)
                  VALUES
                  (:l_new_ou_id, :l_name, :l_old_ou_id)""",
                {'l_new_ou_id': int(foo['new_ou_id']),
                 'l_name': foo['name'],
                 'l_old_ou_id': foo['old_ou_id']})
                #self._db.log_change(self.entity_id, self.const.person_create, None)
        db.commit()
        return 1
        


def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'o:',['ou_history='])
    except getopt.GetoptError:
        print "Parameter error"
        usage()
 
    ou_done = 0
    ou_file = ''
    print "Parsing vars... opts=%s args=%s" % (opts,args)
    
    for opt,val in opts:
        print "check"
        if opt in ('-o','--ou_history'):
            print "OU file=%s" % ou_file
            ou_file =  val
            print "OU file=%s" % ou_file

            
    if (ou_file==''):
        print "No ou file"
        usage()
        sys.exit(1)

    my_ou = Ou_History(ou_file)
#    ou_values = my_ou.populate_ou_list()
    my_ou.execute_ou_info()
    print "done storing old ou\'s"
    sys.exit(1)
    
def usage():
    print """Usage: import_OU_history -o ou_file 

    Note: The bofhd daemon needs to run in order to create users.
    """
    
if __name__ == '__main__':
    main()

    
