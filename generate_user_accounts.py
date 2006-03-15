#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-
 
# Copyright 2002, 2003 University of Tromsø, Norway
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


import cerebrum_path
import cereconf
import string
import getopt
import sys
import server.bofhd

#from server.bofhd import StandardBofhdServer
from server.bofhd import BofhdServer
from server.bofhd import BofhdSession
from server.bofhd import BofhdRequestHandler
from Cerebrum.extlib import logging
from Cerebrum.modules.no.uit.bofhd_uit_cmds import BofhdExtension
from Cerebrum.Utils import Factory
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.no.uit.Email import email_address

email_list = {}

class create_users:

    def __init__(self,faculty_id,institute_id,person_file,password_file,email_file):
        #global email_list
        #print "creating list over all email addresses.."
        #email_list = self.build_email_list()
        #print "list created.."
        db = Factory.get('Database')()
        conffile = '/cerebrum/etc/cerebrum/config.dat'
        port = 8001
        #server = StandardBofhdServer(db, conffile,("0.0.0.0", port), BofhdRequestHandler)
        server = BofhdServer(("0.0.0.0",port), BofhdRequestHandler,db,conffile)

        #(db, conffile,("0.0.0.0", port), BofhdRequestHandler)

        if(person_file != 0):
            # This means that we will create posix users for people in the
            # indicated file only.
            query ="not implemented yet"
        else:
            # This means that we will make posix users for those people having affiliation to
            # the faculty and institute given.
            #query = "select user_name,ssn from legacy_users where ssn in (select external_id from person_external_id where person_id in (select person_id from person_affiliation where ou_id in (select ou_id from stedkode"# where fakultet=%s" % (faculty_id)


            query = "select l.user_name,l.ssn from legacy_users l, entity_external_id e, person_affiliation pa, stedkode st where l.ssn = e.external_id and e.entity_id = pa.person_id and pa.ou_id = st.ou_id"

            
            if (faculty_id != "0"):
                query = "%s and st.fakultet=%s" % (query,faculty_id)
            if(institute_id != "0"):
                query_part2 = " and st.institutt = %s and l.source='AD'" % institute_id
            else:
                query_part2 = " and l.source='AD'"
            query = "%s%s" % (query,query_part2)
            #print "query = %s" % query
            db_row = db.query(query)

            # for each person do....
            if(len(db_row) > 0):
                #we have person info
                for row in db_row:
                    new = False
                    uname = row[0]
                    ssn = row[1]

                    # must get name of user
                    query = "select distinct p.name from person_name p,entity_external_id e where p.person_id = e.entity_id and e.external_id='%s' and p.name_variant=162" % ssn
                    #query = "select name from person_name where person_id in (select person_id from person_external_id where external_id='%s') and name_variant=162" % ssn;
                    #print "query = %s" % query
                    db_row = db.query(query)
                    name = db_row[0][0]
                    #print "name = %s AND uname = %s AND ssn = %s" % (name,uname,ssn)
                    self.create_posix(uname,ssn,server,name,password_file,email_file,db,new)
            #else:
                # no persons are affiliated to the spesified stedkode, return appropriate error message. TODO
                

    def create_posix(self,uname,fnr,server,navn,password_file,email_file,db,new=False):
        #db = Factory.get('Database')()
        co = Factory.get('Constants')(db)

        ou = Factory.get('OU')(db)
        logger = Factory.get_logger("cronjob")
        #logger = Factory.get_logger("console")
        const = Factory.get('Constants')(db)
        dk = Factory.get('Disk')(db)
        group = Factory.get('Group')(db)
        db.cl_init(change_program='uit_functions')
        ac = Factory.get('Account')(db)
        operator = BofhdSession(db)
        my_bofh_extension = BofhdExtension(server)
        #print "password = %s" % password_file
        password_handle = open(password_file,"w")
         
        #if(new == True):
        #    inits = my_bofh_extension.get_uit_inits(navn)
        #    uname = my_bofh_extension.get_serial(inits)
        #    print "NEW USER NAME = %s" % uname

        fodselsdato ="%s%s-%s-%s" % (19,fnr[5:7],fnr[3:5],fnr[1:3])
        disk = '/fakeserver/nodisk'
        shell = 'bash'
        filegroup = 'posixgruppe'
        
        # now lets get affiliation and person_id
        query = "select distinct pa.affiliation, pa.person_id,pa.ou_id from person_affiliation pa, entity_external_id e where pa.person_id = e.entity_id and e.external_id='%s' and pa.affiliation=188" % fnr
        #query = "select affiliation,person_id,ou_id from person_affiliation where person_id in (select person_id from person_external_id where external_id='%s' and affiliation=188)" %(fnr)
        #print "%s" % query
        db_row = db.query(query)
        if(len(db_row) < 1):
            #this person does not exist in cerebrum
            print "ERROR person with fnr = %s has no ANSATT affiliation in person_affiliation. ANSATT account not created" % fnr
        else:
            # person has an affiliation, lets check if the person already has an account.
            affiliation = db_row[0]['affiliation']
            person_id = db_row[0]['person_id']
            person_ou_id = db_row[0]['ou_id']
            
            # get username
            query = "select entity_id,entity_name from entity_name where entity_name = '%s'" % (uname)
            #print "%s" % query
            db_row = db.query(query)

            if(len(db_row) > 0):
                # user already exists in cerebrum, generate error message
                logger.debug("User %s already exists. person %s not inserted" % (db_row[0][1],fnr))
                # lets check if we need to do an update on the account
                ac.find(db_row[0]['entity_id'])
                foo = ac.get_account_types()
                for i in foo:
                    if(i['affiliation'] ==213): # 188 = ANSATT
                        # TODO: Bruke const.aff_ansatt
                        
                        #This user has an ANSATT account_type
                        #now we must check wether any of the info needs to be updated
                        if(i['ou_id']!= person_ou_id):
                            print "user %s: has an account ou_id %s which is different from person ou_id %s" % (i['account_id'],i['ou_id'],person_ou_id)
                        
                return

            else:
            #if(1):
                # User is not registred in cerebrum, create user
                print "person %s has no account in cerebrum. creating account..." % fnr
                posix_user = PosixUser.PosixUser(db)
                posix_user = PosixUser.PosixUser(db)
                uid = posix_user.get_free_uid()
                shell = my_bofh_extension._get_shell(shell)
                disk_id, not_used,home = my_bofh_extension._get_disk(disk)
                if home is not None:
                    if home[0] == ':':
                        home = home[1:]
                    else:
                        raise CerebrumError, "Invalid disk"
                
                posix_user.clear()
                gecos = None
                expire_date = None
                owner_type = my_bofh_extension.const.entity_person
                owner_id = my_bofh_extension._get_person("entity_id", person_id).entity_id
                np_type = None
                print "home = %s " % home

                #lets populate the posix_user.
                posix_user.populate(name = uname,
                                    owner_type = co.entity_person,
                                    owner_id = person_id,
                                    np_type = None,
                                    creator_id = 28,#TODO: 2 is hardcoded to bootstrap_account, must be changed later to -> default_creator_id,
                                    expire_date = None,
                                    posix_uid = uid, #posixuser.get_free_uid(),
                                    gid_id = 10173,#TODO: 204 is hardcoded, must be changed later to -> group.entity_id,
                                    gecos = gecos,
                                    shell = shell)#,#posix_user.const.shell_bash,
                                    #home = home)#"/full/path/til/hjemmeområde/for/brukeren")
                #lets set the users home. TODO this needs rewriting
                #disk_spread = 'AD_account'
                #disk_id = 1621 # for testing purposes
                #posix_user.set_home(disk_spread,disk_id,const.home_status_not_created)

                try:
                    posix_user.write_db()
                    
                    for spread in cereconf.BOFHD_NEW_USER_SPREADS:
                        print "default spread value = %s" % my_bofh_extension._get_constant(spread,"No such spread")
                        posix_user.add_spread(my_bofh_extension._get_constant(spread,"No such spread"))
                        
                    # must set the right groups for the user
                    ad_group = group.find_by_name("AD_group")
                    print "posix_user_id = %s" % posix_user.entity_id
                    type = 3 # 3 = account
                    op = 90
                    group.add_member(posix_user.entity_id,type,op)


                        
                    # For correct ordering of ChangeLog events, new users
                    # should be signalled as "exported to" a certain system
                    # before the new user's password is set.
                    passwd = fnr # TODO: edit this when fnr no longer will be password.#posix_user.make_passwd(uname)

                    password_handle.writelines("%s \t %s \t %s \t %s \n" % (navn,fnr,uname,passwd))
                    password_handle.writelines("\n")                    
                    posix_user.set_password(passwd)
                    #print "posix_user_password = '%s'" % passwd
                    #sys.exit(1)
                    # need to sett account_home
                    disk_spread = 'AD_account'
                    disk_spread_code = const.Spread('AD_account')
                    print "disk_spread_code = %s" % disk_spread_code
                    print "disk path used in find_by_path = '%s'" % disk
                    dk.find_by_path(disk)
                    disk_id = dk.entity_id
                    print "my_disk = %s" % disk_id
                    status = 93 # <- 93 = not created
                    home = None
                    homedir_id = posix_user.set_homedir(disk_id=disk_id,status=status)
                    posix_user.set_home(disk_spread_code,homedir_id)
                    print "set home done"
                    #sys.exit(1)
                    
                    
                    # And, to write the new password to the database, we have
                    # to .write_db() one more time...
                    posix_user.write_db()

                    my_bofh_extension._user_create_set_account_type(posix_user, owner_id, person_ou_id, affiliation)
                    
                    db.commit()
                except db.DatabaseError, m:
                    raise CerebrumError, "Database error: %s" % m
            
                # Need to create email address here.
                ##################################################
                # TODO. VERIFY THAT THIS ACTUALLY WORKS.         #
                # IF IT WORKS, COPY TO GENERATE_STUDENT_ACCOUNTS #
                # ################################################
                #posix_user.update_email_addresses()
                #my_account_id = posix_user.find_by_uid(uid)
                #account_list=[]
                #account_info={'account_id':my_account_id['account_id']}
                #account_list.append(account_info)
                #try:
                #    email=email_stuff(account_list,email_file,db,ac,ou,logger)
                #except:
                #    print "failed to set primary email address for posix uid %s.exiting" % uid
                #    sys.exit(1)
        
def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:i:u:p:e:',['faculty=','institute=','user_info=','password_file=','email_file='])
 
    except getopt.GetoptError:
        usage()

    faculty_id = 0
    institute_id = 0
    user_info_file = 0
    password_file = 0
    
    for opt,val in opts:
        if opt in ('-f','--faculty'):
            faculty_id = val
        if opt in ('-i','--institute'):
            institute_id = val
        if opt in ('-u','--user_info'):
            user_info_file = val
        if opt in ('-p','--password_file'):
            password_file = val
        if(opt in ('-e','--email_file')):
            email_file=val
            
#    if(user_info_file ==0):
#        usage()
 #   else:
    create_users(faculty_id,institute_id,user_info_file,password_file,email_file)
        
def usage():
    print """Usage: python generate_user_accounts.py [-f <-i>] | [-p] 
    -f | --faculty - indicate which faculty to generate users for
    -i | --institute - indicate which institute to generate users for
    -p | --person_info - indicate file to write username/password of new users to.
    -e | --email_file: email conversion list.
    
    This program generate posix users from persons adhering to the given faculty and institute
    indicated. Faculty and institute must be identified with the \"stedkode\" id used in cerebrum.
    If no institute is given, users will be generated for the whole faculty. Thus the faculty must
    always be given. If the -p option is used instead, a file on the form: usernam,SSN must be
    referenced. All persons in this file will get a posix user account.
    """
    sys.exit(0)
    

if __name__ == '__main__':
    main()
