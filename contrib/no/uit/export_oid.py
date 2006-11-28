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

# This script exports OID data for all users in BAS, on the following format:
# first_name;last_name;uid;primary_email;[affiliation-student,ou];[affiliation-employee,ou],[affiliation-affiliate,ou],MD5-crypt

import cerebrum_path
import cereconf
import getopt
import sys
import string
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode, _SpreadCode

class data:

    def __init__(self,file):
        self.db = Factory.get('Database')()
        self.account = Factory.get('Account')(self.db)
        self.person = Factory.get('Person')(self.db)
        self.constants = Factory.get('Constants')(self.db)
        self.stedkode = Stedkode(self.db)
        self.logger_name=cereconf.DEFAULT_LOGGER_TARGET
        self.logger = Factory.get_logger('cronjob')
        self.num2const = {}
        self.file_handle = open(file,"w")

        # Merk: ANSATT vil bli oversatt til enten VIT eller OVR. Disse 2 bestemmer hvilken EduPersonAffiliation personen vil få.
        self.affiliate_dict={'STUDENT' : ['STUDENT','MEMBER'],
                             'VIT':['FACULTY','EMPLOYEE','MEMBER'],
                             'OVR':['STAFF','EMPLOYEE','MEMBER'],
                             }
        self.affiliation_status_dict={211 : 'VIT',
                                      210 : 'OVR',
                                      465 : 'OVR'}
        

        # storing all person names in a list
        self.person_names = self.person.getdict_persons_names(self.constants.system_cached,self.constants.name_full)
    # {A person never has more than 1 account}
    def get_data(self):
        person_list=[]
        for c in dir(self.constants):
            tmp = getattr(self.constants, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp

        self.logger.warn("før account.list_account_home")
        all_accounts = self.account.list(filter_expired=True)
        #all_accounts=[2155]


        for accounts in all_accounts:
            self.account.clear()
            #self.account.find(2155)
            self.account.find(accounts.account_id)
            #print "account:id=%s" % self.account.entity_id
            try:
                quarantine=self.account.get_entity_quarantine(only_active=True)
                if (len(quarantine)!=0):
                    # This account has a quarantine, lets skip to the next account.
                    self.logger.warn("account_id:%s has active quarantine" % self.account.entity_id)
                    continue
                
                account_type_data=self.account.get_account_types(filter_expired=True)
                if(len(account_type_data)==0):
                    # this account has no active affiliations, lets skip to the next account.
                    self.logger.warn("person:%s has no active affiliation" % self.account.owner_id)
                    continue

                account_spread=''
                if(self.account.has_spread(self.constants.spread_uit_ldap_account)==False):
                   self.logger.warn("account:%s does not have ldap spread" % self.account.entity_id)
                   continue
                #account is not expired, has no quarantine, and has ldap spread. person also has active affiliation, lets continue.
                name = self.person_names[self.account.owner_id]
                (first_name,last_name) = string.split(name[162],' ',1)
                uid = self.account.get_account_name()
                email = self.account.get_primary_mailaddress()
                crypt = self.account.get_account_authentication(self.constants.auth_type_md5_b64)
                self.person.clear()
                self.person.find(self.account.owner_id)
                person_affiliations= self.person.get_affiliations()
                pers_aff={}
                my_status=[]
                for aff in person_affiliations:
                     self.stedkode.clear()
                     self.stedkode.find(aff.ou_id)
                     my_stedkode='%02d%02d%02d' % (self.stedkode.fakultet,self.stedkode.institutt,self.stedkode.avdeling)

                     if(aff.affiliation == self.constants.affiliation_ansatt):
                         #print "key:%s" % self.affiliation_status_dict[aff.status]
                         #print "%s" % (self.affiliate_dict[self.affiliation_status_dict[aff.status]])
                         my_status=(self.affiliate_dict[self.affiliation_status_dict[aff.status]])
                         pers_aff[my_stedkode]= my_status
                     elif(aff.affiliation==self.constants.affiliation_student):
                         #my_status=(self.affiliate_dict[self.affiliation_status_dict[aff.status]])
                         #my_status= str(self.num2const[int(aff.affiliation)])
                         my_status=self.affiliate_dict[str(self.num2const[int(aff.affiliation)])]
                         pers_aff[my_stedkode]= my_status

                #print "pers_aff=%s" % pers_aff
                if (len(pers_aff)>0):
                    #All data for 1 object collected. store in dict20
                    person_list.append({'first_name': first_name,'last_name' : last_name,'uid' : uid,'primary_email' : email,'affiliations' : pers_aff,'crypt' : crypt})
                
            except Errors.NotFoundError,m:
                self.logger.info("Error collecting account data for person id:%s. %s. Account probably expired" % (self.account.owner_id,m))


        for l_person in person_list:
            self.file_handle.writelines("%s;%s;%s;%s;" % (l_person['first_name'],l_person['last_name'],l_person['uid'],l_person['primary_email']))
            #print "writing:%s - %s" % (l_person['affiliations'],l_person['uid'])

            for lfp in l_person['affiliations'].keys():
                #ou_counter=0
                for aff_status in l_person['affiliations'][lfp]:
                    self.file_handle.writelines("%s," % aff_status)
                    self.file_handle.writelines("%s:" % lfp)
                    #ou_counter = ou_counter+1
                    #if(ou_counter<(len(l_person['affiliations'][lfp]))):
                    #    self.file_handle.writelines(":")

            #self.file_handle.writelines("%s;" %)    
            self.file_handle.seek(-1,1) # setting the file_handler to point to the last element in the file and overwrite the ":" with the ";" below
            self.file_handle.writelines(";%s\n" % l_person['crypt'])
        self.file_handle.close()
        self.logger.warn("etter account.list_account_home")                
                                        
                                        
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'f:h',
                                   ['file=','help'])
    except getopt.GetoptError:
        usage()
        sys.exit(1)

    storage_file=None

    for opt,val in opts:
        if opt in('-f','--file'):
            storage_file=val
        if opt in('-h','--help'):
            usage()
            sys.exit(1)

    if storage_file is not None:
        oid_export = data(storage_file)
        oid_export.get_data()
    else:
        usage()
        sys.exit(1)
    

    

def usage():
    print """
usage: export_uid.py -f <filename>

   -f | --file : Filename to store the uid data in
   -h | --help : This text

This script exports OID data for all users in BAS, on the following format:
first_name;last_name;uid;primary_email;[affiliation-student,ou];[affiliation-employee,ou],[affiliation-affiliate,ou],MD5-crypt
"""


if __name__ == '__main__':
    main()
