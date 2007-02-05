#! /usr/bin/env python
#-*- coding: iso-8859-1 -*-
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


import getopt
import sys
import string
import os
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum.modules.no import Stedkode


class validate:

    def __init__(self,file,logger):
        if not(os.path.isfile(file)):
            self.logger.error("ou file:%s does not exist\n" % file)
            sys.exit(1)
        self.db = Factory.get('Database')()
        self.person = Factory.get('Person')(self.db)
        self.stedkode = Stedkode.Stedkode(self.db)
        self.constants = Factory.get('Constants')(self.db)
        self.logger = Factory.get_logger(logger)
        self.file_handle = open(file,"r")

    def parse(self):
        ou=[]
       
        for line in self.file_handle:
            fakultet,institutt,kode,navn = line.split(",")
            fakultet =fakultet.strip("\"")
            institutt= institutt.strip("\"")
            kode = kode.strip("\"")
            navn = navn.strip("\"")
            sted = None
            if(kode.isdigit()):
                if(len(kode)==6):
                    sted = self.stedkode.get_stedkoder(fakultet=kode[0:2],institutt=kode[2:4],avdeling=kode[4:6],institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
                    if(len(sted)>0):
                        ou.append(sted[0]['ou_id'])
                    else:
                        self.logger.warn("%s does not exist in BAS" % kode)
                        
        return ou
            
    def get_person_aff(self,ou_id_list,student,employee,active,tilknyttet,manual):
        ansatt_person_list=[]
        student_person_list=[]
        tilknyttet_person_list=[]
        manual_person_list=[]
        
        if(employee):
            ansatt_person_list = self.person.list_affiliations(affiliation=self.constants.affiliation_ansatt,include_deleted=active)
        if(student):
            student_person_list = self.person.list_affiliations(affiliation=self.constants.affiliation_student,include_deleted=active)
        if(tilknyttet):
            tilknyttet_person_list = self.person.list_affiliations(affiliation=self.constants.affiliation_tilknyttet,include_deleted=active)
        if(manual):
            manual_person_list = self.person.list_affiliations(affiliation=self.constants.affiliation_manuell,include_deleted=active)
        employee_counter = 0
        student_counter = 0
        manual_counter= 0
        tilknyttet_counter=0
        
        for ansatt in ansatt_person_list:
            if (ansatt['ou_id'] not in ou_id_list):
                print "person:%s has an affiliation %s on a suspicious ou:%s" % (ansatt['person_id'],ansatt['affiliation'],ansatt['ou_id'])
                employee_counter = employee_counter + 1
        for student in student_person_list:
            if(student['ou_id'] not in ou_id_list):
                print "person:%s has an affiliation %s on a suspicious ou:%s" % (student['person_id'],student['affiliation'],student['ou_id'])
                student_counter = student_counter+1
        for tilknyttet in tilknyttet_person_list:
            if(tilknyttet['ou_id'] not in ou_id_list):
                print "person:%s has an affiliation %s on a suspicious ou:%s" % (tilknyttet['person_id'],tilknyttet['affiliation'],tilknyttet['ou_id'])
                tilknyttet_counter = tilknyttet_counter+1
        for manual in manual_person_list:
            if(manual['ou_id'] not in ou_id_list):
                print "person:%s has an affiliation %s on a suspicious ou:%s" % (manual['person_id'],manual['affiliation'],manual['ou_id'])
                manual_counter = manual_counter+1
        

        print "total number of employees:%s" % employee_counter
        print "total number of students:%s" % student_counter
        print "total number of tilknyttet:%s" % tilknyttet_counter
        print "total number of manual:%s" % manual_counter
def main():
    try:
        opts,args = getopt.getopt(sys.argv[1:],'seaf:ltm',['student','employee','active','file=','logger','tilknyttet','manuell'])
    except getopt.GetoptError:
        usage()
    student = False
    employee = False
    active = True
    file = False
    manual = False
    tilknyttet = False
    logger_name = cereconf.DEFAULT_LOGGER_TARGET
    
    for opt,val in opts:
        if opt in('-s','--student'):
            student = True
        if opt in('-e','--emploee'):
            employee = True
        if opt in('-a','--active'):
            active = False
        if opt in('-f','--file'):
            file = val
        if opt in('-l','--logger'):
            logger_name = val
        if opt in('-m','--manuell'):
            manual = True
        if opt in('-t','--tilknyttet'):
            tilknyttet = True
            
    if ((student or employee or tilknyttet or manual)!= False and file !=False ):
        my_val = validate(file,logger_name)
        ou_list = my_val.parse()
        my_val.get_person_aff(ou_list,student,employee,active,tilknyttet,manual)
    else:
        usage()
        sys.exit(0)
        
        
def usage():
    print """
    This script collects person affiliations from BAS and validates them against the file given with the -f option
    Usage: python validate_person_affiliation.py | -s | -e | -a | -f 
    -s | --student  -  validate students
    -e | --employees  -  validate employees
    -t | --tilknyttet  -  affiliate persons. from sys-x
    -m | --manuall  -  Manually added persons
    -a | --active  -  validate against active affiliations only
    -f | --file  -  validate the affiliations against this file
    """


if __name__=='__main__':
    main()
