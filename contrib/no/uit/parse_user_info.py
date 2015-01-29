#! /usr/bin/env python
#-*- coding: iso-8859-1 -*-
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
# This file reads ou data from a text file. Compares the stedkode
# code with what already exists in a ou data file form FS and inserts
# right ou information from that file. For stedkoder who doesnt
# exist in the FS file, default data is inserted
#

""" This file is part of cerebrum """

import string
import sys
import getopt
import os.path
import exceptions
import time

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory




class process_student:
    def __init__(self,student_file):
        if(0 !=os.path.isfile(student_file)):
            return self.parse(student_file)
        else:
            print "file %s does not exists" % student_file

    def parse(self,student_file):
        # This function parses the student-it file and stores all usernames in the legacy table in the database
        db = Factory.get('Database')()
        file_handle = open(student_file,'r')
        for person in file_handle:
            #number = person.count(":")
            #print "num : = %s" % number
            if ((person[0] != '#') and (person[0] != '\n')):
                
                fodselsdato,personnr,brukernavn,fornavn,mellomnavn,etternavn,hjemmekatalog,hjemmekatalog2,passord= person.split(":",8)
                #ssn1 = temp_ssn[0:5]
                #ssn2 = temp_ssn[5:11]
                ssn ='%s%s' % (fodselsdato,personnr)
                #month,day,year = fodselsdato.split("-",3)
                #new_fodselsdato = day+month+year[-2:]
                #ssn = "%s%s" % (new_fodselsdato,personnr)
                #print "OLD = %s" % temp_ssn
                #print "NEW = %s" % ssn
                # We will only store users names on the form: XXXYYY where XXX = arbitrary letters and YYY= counter
                # lets check for this now
                #rest = 0
                #letters = brukernavn[0:3]

                #rest = brukernavn[6:]
                #print "letters = %s AND counter = %s and rest = %s" % (letters,counter,rest)
                #if(len(ssn)==11):
                # if the username is on the form XXXYYY (described above, then lets insert it into the legacy usertable)
                #print "username <%s> is allowed" % username
                query = "insert into legacy_users (user_name,ssn,source,type) values('%s','%s','SUT','P')" % (brukernavn,ssn)
                #print "query = %s" % query
                try:
                    db_row = db.query(query)
                    db.commit()
                except:
                    print "person <%s> has already been registred with an account" % ssn
                #else:
                    # username is on a form not recognized by cerebrum. return error message
                    #print "username <%s> is NOT allowed" % username


class process:

    def __init__(self,static_file):
        self.db = Factory.get('Database')()
        #self.logger = Factory.get_logger('console')
        self.logger = Factory.get_logger('cronjob')
        #self.logger.info("Processing static_user file=%s" % static_file)            
     
        self.cache_static = {}
        self.cache_legacy_db = {}
            
        self.cache_from_db()
#        import pprint
#        pp = pprint.PrettyPrinter(indent=2)
#        pp.pprint(self.cache_legacy_db)
        
        self.cache_static_data(static_file)
#        pp.pprint(self.cache_static)
        
        
        self.update_legacy_db()
        self.db.commit()
        
        # Do the updates
        #if(os.path.isfile(static_file)):
        #    temp = self.file(static_file)
        #else:
        #    self.logger.error("file %s does not exists" % static_file)
        #sys.exit(1)


            
    def cache_from_db(self):
        

        rows = self.db.query("""SELECT user_name,ssn,name,comment FROM [:table schema=cerebrum name=legacy_users] l""")
#                        WHERE l.type=:type AND l.source=:source""", {'source':'AD', 'type':'P'})
        for row in rows:
            dict = {'personnr':row['ssn'],'name':row['name'],'comment':row['comment']}
            self.cache_legacy_db[row['user_name']] = dict
        
    
    
    def cache_static_data(self, file_name):
        f_handle = open(file_name,"r")
        lines = f_handle.readlines()
        f_handle.close()

        tech = "default"
        i = 0
        for person in lines:
            i += 1
            person = person.rstrip()    # remove \n 
            comment = username = name = ssn = ""
            
            if(person == '# MARTIN'):
                tech = "MARTIN"
            if((person != '') and (person[0] != "#")):
                if(tech == "MARTIN"):
                    try: 
                        username,ssn,name,comment = person.split(",",3)
                    except Exception,msg:
                        self.logger.error("STATIC_USER: Critical error on line %d in %s\nError was: %s" % (i,file_name,msg))
                        sys.exit(1)
                    # remove whitespace, is this neccesary?
                    username = username.strip()
                    ssn = ssn.strip()
                    name=name.strip()
                    comment = comment.strip()
                elif(tech =="default"):
                    self.logger.error("ERROR in parsing static_user_info. Technique not set before line %d!. EXITING" % i)
                    sys.exit(1)


                # data in lower part of file takes priority as new data from ASP is appended to static file.
                #if (self.cache_static.has_key(username)):
                    #self.logger.warn("DUPLICATE USERNAME '%s' on line %d" % (username,i))
                #self.logger.info("caching UNAME %s: ['%s','%s','%s']" % (username,ssn,name,comment))
                self.cache_static[username] = {'personnr':ssn, 'name':name,'comment':comment}


        # end cache_static_data

        
    def update_legacy_db(self):
        
        from sets import Set
        
        db_unames = Set(self.cache_legacy_db.keys())
        static_unames = Set(self.cache_static.keys())
        
        new_keys = static_unames.difference(db_unames)
        update_keys = db_unames.intersection(static_unames)
        
        type ="P"
        source = "AD"            
        # new keys
        for k in new_keys:
            username = k
            ssn = self.cache_static[username]['personnr']
            name = self.cache_static[username]['name']
            comment = self.cache_static[username]['comment']
            #self.logger.debug("Insert needed, %s not in db" % username)
            #debug_str = "Calling INSERT: '%s','%s','%s','%s','%s','%s'" % (username,ssn,name,comment,source,type)
            #print debug_str
            
            try:
                db_row = self.db.execute("""INSERT INTO [:table schema=cerebrum name=legacy_users]
                                           (user_name,ssn,name,comment,source,type) 
                                           VALUES (:l_user_name, :l_ssn, :l_name, :l_comment, :l_source, :l_type)""",
                                           {'l_user_name' : username, 'l_ssn' : ssn, 'l_name': name, 'l_comment': comment,
                                           'l_source' : source, 'l_type' : type})
            except Exception:
                self.logger.error("WHHOOOA: Insert failed on %s!" % username)
                
    

        for k in update_keys:
            username = k
            
            in_db = self.cache_legacy_db[username]
            in_static = self.cache_static[username]
            
            if (in_db != in_static):  ## data different in static data vs db data
                ssn = self.cache_static[username]['personnr']
                name = self.cache_static[username]['name']
                comment = self.cache_static[username]['comment']
                #debug_str = "Calling UPDATE: '%s','%s','%s','%s','%s','%s'" % (username,ssn,name,comment,source,type)
                #print debug_str
                #self.logger.debug("Update needed, db data not equal to static data:\nIn_dB: %s\nIN_Static:%s" % (in_db,in_static))
                try:        
                    db_row = self.db.execute("""UPDATE [:table schema=cerebrum name=legacy_users]
                                             set ssn=:new_ssn, name=:name, comment=:comment, type=:type, source=:source 
                                             where user_name=:username
                                             """,{'new_ssn':ssn, 'name':name, 'comment':comment, 'username':username, 
                                             'type':type  ,'source':source})
                except Exception:
                    self.logger.errror("WHHOOOA: UPDATE failed on %s!" % username)
            else:
                pass
                #self.logger.debug("No update needed, db data equal to static data:\nIn_dB: %s\nIN_Static:%s" % (in_db,in_static))
        
        
# functions below made obsolete 2006-01-24 by bto001
# use new methods for updating legacy_users table in cerebrum

#    def file(self,file_val):
#        # now comes the tricky part.
#        # the file consists of 3 parts. hildes data, martins data
#        # and stigs data. each of these 3 require different parsing
#        # techniques. The parts each has its own header to signal
#        # that a new parsing technique must be used.
#        # once the file has been parsed and the right data collected
#        # the data needs to be stored in the cerebrum database.
#        # the table used is the user_legacy table
#
#        file_handle = open(file_val,'r')
#        technique = "default"
#        for person in file_handle:
#            if(person[0:7] =='# HILDE'):
#                technique = "HILDE"
#            if(person[0:6] == "# STIG"):
#                technique = "STIG"
#            if(person[0:8] == "# MARTIN"):
#                technique = "MARTIN"
#
#            # only process person information if its not a blank line
#            # and not a # as the first letter.
#            if((person[0] != '\n') and (person[0] != '#')):
#                self.parse(person,technique)
#        
#        file_handle.close()
#        db.commit()
#
#
#    def parse(self,person,technique):
#        if(technique == "MARTIN"):
#            # lets set som default variables
#            type ="P"
#            source = "AD"
#            print "PROCESS LINE: %s" %  person
#            
#            username,ssn,name,comment = person.split(",",3) # Only split on first 3 commas. Rest is part of comment
#            new_ssn = ssn.strip()
#            username = username.strip()
#            name = name.strip()
#            comment = comment.rstrip() # remove trailing whitespace (\n also)
#            print "'%s','%s','%s','%s','%s','%s'" % (username,new_ssn,name,comment,source,type)
#
#            try:
#                db_row = self.db.execute("""INSERT INTO [:table schema=cerebrum name=legacy_users]
#                (user_name,ssn,name,comment,source,type) VALUES (:l_user_name, :l_ssn, :l_name, :l_comment, :l_source, :l_type)""",
#                                    {'l_user_name' : username, 'l_ssn' : new_ssn, 'l_name': name, 'l_comment': comment,
#                                     'l_source' : source, 'l_type' : type})
#                
#
#            except Exception:
#                # Due to possible inconsistencies in the data we have collected, we will let the
#                # data from MARTIN take priority. Any conflics in usernames will adhere to what
#                # MARTINs data sez. hench, if the above insert does not work(meaning that the data
#                # has already been inserted from another source), an update on ssn will be tried instead
#                print "Entry for user_name='%s' already exists, UPDATING WITH NEWEST INFO" % username
#                try:
#                    self.db.execute("""UPDATE [:table schema=cerebrum name=legacy_users]
#                                   set ssn=:new_ssn, name=:name, comment=:comment where user_name=:username
#                                   """,{'new_ssn' : new_ssn, 'name':name, 'comment':comment, 'username' : username})
#                except Exception,msg:
#                    print "Failed to update username '%s' with new data: ssn='%s', name='%s', comment='%s'" % (username,new_ssn,name,comment)
#                    print "Error was: %s" % msg
#                    sys.exit(1)
#        else:
#            print "I do not know how to handle this data : %s. No technique is defined. EXITING" % person
#            sys.exit(1)

def main():

    # lets set default user_info file
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    file_path = cereconf.CB_PREFIX + '/var/source'
    file_name = '%s/static_user_info.txt' % (file_path)
    file_val = file_name 
    

    try:
        opts,args = getopt.getopt(sys.argv[1:],'esf:h',['employee','student','file=','help'])
    except getopt.GetoptError:
        usage()
        sys.exit(0)


    emp = 0
    stud = 0
    student = 0
    for opt,val in opts:
        if opt in('-e','--employee'):
            emp = 1
        if opt in ('-s','--student'):
            stud = 1
        if opt in('-f','file'):
            file_val = val
        if opt in ('-h','--help'):
            usage()
            sys.exit(0)

    if((emp == 1) and (stud == 0)):
        go = process(file_val)
    elif((stud != 0 )and (emp ==0)):
        go = process_student(file_val)
    else:
        usage()
        sys.exit(0)
    #if(file_val ==0 and student == 0):
    #    usage()
            
def usage():
    print """This program gets user information from a text file generated
    by data from stig,martin and hilde and inserts usernames,SSN,source and type into the legacy_users table. If -e is used an optional -f can be used. If -s is used -f must also be used.

    Usage: parse_user_info <-e [-f] | -s -f>
    -e | --employee: indicating employee data
    -s | --student : indicating student information. typically from SUT
    -f | --file: file with user information
    -h | --help: this text

    """
    
if __name__ == '__main__':
    main()

