#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2014 University of Oslo, Norway
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

# kbj005 2015.02.25: Copied from Leetah.

#
# Generic imports.
#
import getopt
import os
import time
import mx.DateTime
import copy
import sys
from pprint import pprint
import string
from lxml import etree
import time
import datetime



#
# Cerebrum imports.
#
import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum import Group
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum import Errors
db = Factory.get('Database')()
group = Factory.get('Group')(db)
person = Factory.get('Person')(db)
const = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
ou = Factory.get('OU')(db)
sko = Stedkode(db)
#
# Global variables
#
progname = __file__.split(os.sep)[-1]
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)
dumpdir = cereconf.DUMPDIR
db.cl_init(change_program=progname)
#person_list = []
__doc__="""

This script generates an xml file with information about
temporary employed scientific persons at UiT.

usage:: %s <-p person_file> [-t <employee_type>] <-o outfile.xml> [-h] 

options:
   [--logger-name]          - Where to log
   [-p | --person_file]     - Source file containing person info (from paga)
   [-a | --aff_status]      - one or more of (vitenskapelig,drgrad,gjest,etc).
                              This is a comma separated list. default value is: vitenskapelig 
   [-o | --out]             - Destination xml file
   [-h | --help]            - This text

""" % (progname)

#
# Class containgin all relevant information for each entry/person in the xml file.
#
class temp_vit_person(object):


    account_name = None
    external_id = None
    emp_type = None
    stedkode = None
    email = None
    faculty_name = None
    
    def __init__(self,external_id,account_name,faculty_name,email,stedkode):

        self.account_name = account_name
        self.external_id = external_id
        self.emp_type = None
        self.stedkode = stedkode
        self.email = email
        self.faculty_name = faculty_name



#
# Foreach person in person_list, set tj_forhold:
#
# Only prosess persons which :
# - has fnr in paga file and BAS
# - has stedkode in paga file that matches stedkode from BAS
# - has stillingsprosent > 49%
# - has employment type != F

def set_tj_forhold(person_list,paga_data):
    qualified_list = []
    for person in person_list:
        found = False
        for paga_person in paga_data:
            if person.external_id == paga_person['fnr']:
                # fnr from BAS also exists in paga file
                found = True
                if person.stedkode == paga_person['stedkode']:
                    # correct stedkode
                    my_prosent = str(paga_person['prosent']).split(',',1)
                    if int(my_prosent[0]) > 49:
                        # prosent:%s is larger than 50 %
                        person.emp_type = paga_person['ansatt_type']
                        if person.emp_type != 'F':
                            qualified_person = copy.deepcopy(person)
                            qualified_list.append(qualified_person)                        
                            logger.debug("setting employment type:%s for person:%s" % (paga_person['ansatt_type'],person.external_id))
                            
                        else:
                            logger.debug("person:%s has permanent job. NOT inserting" % (person.external_id))
                    else:
                        logger.warn("WARNING: person:%s has prosent:%s. which is less than 50. NOT inserting" % (person.external_id,my_prosent[0]))
                else:
                    # no match on stedkode
                    logger.debug("match on fnr:%s, but stedkode:%s from BAS does not match stedkode:%s from PAGA" % (person.external_id,person.stedkode,paga_person['stedkode']))
        if found == False:
            logger.debug("Unable to find fnr:%s in paga file" % (person.external_id))
    return qualified_list

#
# Write persondata to xml file
#
def write_xml(qualified_list,out_file):
    #print "writing xml file..."
    root_members = []
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    #print st

    faculty_list = []
    # generate faculty name list for easier xml generation
    for qualified in qualified_list:
        #print "qualified.faculty_name:%s" % qualified.faculty_name
        if qualified.faculty_name not in faculty_list:
            faculty_list.append(qualified.faculty_name)



    # generate xml root node
    data  = etree.Element('data')

    # generate data node
    properties = etree.SubElement(data,'properties')

    # Generate properties node with timestamp
    tstamp = etree.SubElement(properties,'tstamp')
    tstamp.text = "%s" % st

    # generate global group which has all other groups as members
    global_group = etree.SubElement(data,'groups')

   
    
    # create 1 group foreach entry in faculty_list

    for faculty in faculty_list:
        member_list = []
        #print "faculty is:%s" % faculty
        group = etree.SubElement(global_group,'group')
        MailTip = etree.SubElement(group,'MailTip')
        MailTip.text = "%s Midlertidige vitenskapelige ansatte" % unicode(faculty,'iso-8859-1')
        
        displayname = etree.SubElement(group,'displayname')
        displayname.text = "%s Midlertidige vitenskapelige ansatte" % unicode(faculty,'iso-8859-1')
       
        account_names = ''
        for qualified in qualified_list:
            if qualified.emp_type:
                # sanity check...
                if qualified.emp_type != 'F':
                    if qualified.faculty_name == faculty:
                        #print "need to insert: %s" % qualified.account_name

                        #
                        # make sure usernames are unique (no duplicates) within each group
                        #
                        if qualified.account_name not in member_list:
                            member_list.append(qualified.account_name)
                            account_names ='%s,%s' % (account_names,qualified.account_name)
                            account_names = account_names.lstrip(',')
                        else:
                            logger.warn("member:%s not added to group:%s since the username already exists there" % (qualified.account_name,displayname.text))
            else:
                logger.warn("ERROR: person:%s does not have emp_type from Paga file. person did not qualify" % qualified.external_id)


                
        acc_name = etree.SubElement(group,'members')
        acc_name.text = "%s" % account_names
        name = etree.SubElement(group,'name')
        name.text = "%s Midlertidige vitenskapelige ansatte" % unicode(faculty,'iso-8859-1')
        samaccountname = etree.SubElement(group,'samaccountname')
        samaccountname.text ="uit.%s.midl.vit.ansatt" % unicode(faculty,'iso-8859-1')
        samaccountname.text = samaccountname.text.lower()
        root_members.append(samaccountname.text)

        mail = etree.SubElement(group,'mail')
        mail.text = "%s@auto.uit.no" % samaccountname.text
        mail.text = mail.text.lower()
        
        mail_nick= etree.SubElement(group,'alias')
        mail_nick.text="%s.midl.vit.ansatt" % unicode(faculty,'iso-8859-1')
        mail_nick.text = mail_nick.text.lower()



    #
    # generate root group
    #
    
    # generate system group containing list of all the other groups
    system_group = etree.SubElement(global_group,'group')

    MailTip = etree.SubElement(system_group,'MailTip')
    MailTip.text = "Midlertidige vitenskapelige ansatte UiT"

    displayname = etree.SubElement(system_group,'displayname')
    displayname.text = "Midlertidige vitenskapelige ansatte UiT"

    mail = etree.SubElement(system_group,'mail')
    mail.text = "uit.midl.vit.ansatt@auto.uit.no"

    alias = etree.SubElement(system_group,'alias')
    alias.text = "uit.midl.vit.ansatt"

    name = etree.SubElement(system_group,'name')
    name.text = "Midlertidig vitenskapelige ansatte UiT"

    # create list of all facultys
    all_facultys = ",".join(root_members)
    samaccountname = etree.SubElement(system_group,'samaccountname')
    samaccountname.text = "uit.midl.vit.ansatt"

    members = etree.SubElement(system_group,'members')
    members.text = "%s" % unicode(all_facultys,'iso-8859-1')




    fh = open(out_file,'w')
    fh.writelines(etree.tostring(data,pretty_print=True,encoding='iso-8859-1'))
    #fh.write(foo)
    fh.close()

    #pprint(faculty)

                

#
# Read (paga) person file
#
def read_paga(file):
    paga_person = []
    paga_dict = {}
    fh = open(file,'r')
    for line in fh:
        line_data = line.split(";")
        #print "line[0]=%s" % line_data[0]
        paga_dict = {'fnr' : line_data[0], 'ansatt_type' : line_data[39], 'prosent' : line_data[36],'stedkode' : line_data[15]}
        paga_person.append(paga_dict)
    return paga_person


#
# Generate list of all persons (in BAS DB) with the correct affiliation status
# each entry contains: account id, person id, external id and group membership
#
def get_persons(aff_status):

    person_list = []
    
    for aff in aff_status:
        if aff == 'vitenskapelig':
            #print "vitenskapelig"
            decoded_aff_status = int(const.affiliation_status_ansatt_vitenskapelig)
        # collect employee persons with affiliation = ansatt
        for row in person.list_affiliations(affiliation = const.affiliation_ansatt,status = decoded_aff_status):
            person.clear()
            data = (row['person_id'])
            person.find(data)
            #print "person_id:%s" % data

            external_id = person.get_external_id(id_type = const.externalid_fodselsnr)
            decoded_external_id = None

            # get external_id filtered by SYSTEM_LOOKUP
            for system in cereconf.SYSTEM_LOOKUP_ORDER:
                system_id = getattr(const,system)
                for id in external_id:
                    # get fnr with highest priority from SYSTEM_LOOKUP_ORDER
                    id_source = str(const.AuthoritativeSystem(id['source_system']))
                    if(str(system_id) == id_source):
                        decoded_external_id = id['external_id']
                        break
                if decoded_external_id != None:
                    break
            if decoded_external_id == None:
                print "no external id for person:%s. exiting" % data
                sys.exit(1)
                        
            # Get primary account for all of persons having employee affiliation
            acc_id = person.get_primary_account()
            if(acc_id != None):
                #pprint(acc_id)
                #print "####"
                account.clear()
                account.find(acc_id)
                acc_name = account.get_account_name()
                try:
                    email = account.get_primary_mailaddress()
                except Errors.NotFoundError:
                    logger.warning("Account %s (%s) has no primary email address", acc_id, acc_name)
                    email = None
                sko.clear()
                try:
                    sko.find(row['ou_id'])
                except:
                    logger.warning("unable to find ou_id:%s. Is it expired?"% row['ou_id'])
                    continue
                faculty_sko = sko.fakultet
                my_fakultet = sko.fakultet
                my_institutt = sko.institutt
                my_avdeling = sko.avdeling
                #print "sko fakultet:%s" % sko.fakultet

                if str(my_fakultet).__len__() == 1:
                    my_fakultet = "0%s" % my_fakultet
                if str(sko.institutt).__len__() == 1:
                    my_institutt = "0%s" % my_institutt
                if str(sko.avdeling).__len__() == 1:
                    my_avdeling = "0%s" % my_avdeling
                    
                my_stedkode = "%s%s%s" % (my_fakultet,my_institutt,my_avdeling)
                #print "calculated my_stedkode:%s" % my_stedkode
                sko_ou_id = sko.get_stedkoder(fakultet=faculty_sko,institutt=0, avdeling=0)
                my_ou_id = sko_ou_id[0]['ou_id']
                ou.clear()
                ou.find(my_ou_id)
                #faculty_name = ou.name
                faculty_name = ou.get_name_with_language(const.ou_name_acronym, const.language_nb, default='')
                logger.debug("collecting person from BAS: %s, %s, %s, %s, %s" % (decoded_external_id,acc_name,faculty_name,email,my_stedkode))
                person_node = temp_vit_person(decoded_external_id,acc_name,faculty_name,email,my_stedkode)
                person_list.append(person_node)

    return person_list


#
# Verify that file personfile exists. Exit if not
#
def verify_file(personfile):
    if(os.path.isfile(personfile) == False):
        logger.error("ERROR: File:%s does not exist. Exiting" % personfile)
        sys.exit(1)

#
# Main function
#
def main():
    today =mx.DateTime.today().strftime("%Y-%m-%d")
    person_file = None
    out_file = None
    out_path = None
    aff_status = 'vitenskapelig'
    out_mal ="temp_emp_%s.xml" % today
    out_file = os.path.join(dumpdir,out_mal)
    global person_list
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],'p:o:ha:',['person_file=','ou_file=','help','aff_status='])
    except getopt.GetoptError,m:
        usage(1,m)

    for opt,val in opts:
        if opt in('-p','--person_file'):
            person_file = val
        if opt in('-o','--out'):
            out_file = val
        if opt in('-a','--aff_status'):
            aff_status = val
        if opt in('-h','--help'):
            msg = 'display help information'
            usage(1,msg)

    if(out_file == None) or (person_file == None):
        msg ="you must spesify person file and out file"
        usage(1,msg)
    else:

        verify_file(person_file)

        # generate personlist from BAS
        #print "generating person list from BAS...",
        person_list = get_persons([aff_status])
        #print "done."
        # now set external_id and group membership foreach person in person_list
        #for person in person_list:
        #    print "account name:%s" % person.account_name
        #    print "stedkode:%s" % person.stedkode
        #    print "faculty name:%s" % person.faculty_name
        # read paga file
        print "read paga file"
        paga_data = read_paga(person_file)
        #pprint(paga_data)

        # Add tj.Forhold data for each person
        #print "set employment type"
        qualified_list = set_tj_forhold(person_list,paga_data)
        #pprint(qualified_list)

        # write xml file
        write_xml(qualified_list,out_file)
            

#
# Display usage and exit
#
def usage(exitcode=0,msg=None):
    if msg:
        print msg
    print __doc__
    sys.exit(exitcode)

#
# Start main function
#
if __name__ == '__main__':
    main()



# <?xml version="1.0" encoding="utf-8"?>

# <data>
#   <properties>
#     <tstamp>2014-04-29 02:40:54.00</tstamp>
#   </properties>
#   <groups>
# <group>
#       <MailTip>Midlertidige vitenskapelige ansatte uit.helsefak</MailTip>
#       <displayname>Midlertidige vitenskapelige ansatte uit.helsefak</displayname>
#       <mail>midlertidig.vitenskapelig.ansatt@helsefak.uit.no</mail>
      
#       <alias>helsefak.midlertidig.vitenskapelig.ansatt</alias>
#       <members>usernames,username.....</members>
#       <name>helsefak.midlertidig.vitenskapelig.ansatt</name>
#       <samaccountname>helsefak.midlertidig.vitenskapelig.ansatt</samaccountname>
#  </group>
#  <group>
#       <MailTip>Midlertidige vitenskapelige ansatte uit</MailTip>
#       <displayname>Midlertidige vitenskapelige ansatte uit</displayname>
#       <mail>uit.midlertidig.vitenskapelig.ansatt@uit.no</mail>
      
#       <alias>midlertidig.vitenskapelig.ansatt</alias>
#       <members>group_samaaccountname.....</members>
#       <name>uit.midlertidig.vitenskapelig.ansatt</name>
#       <samaccountname>uit.midlertidig.vitenskapelig.ansatt</samaccountname>
#  </group>
# </group>
