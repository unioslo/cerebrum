#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
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
# This file reads 
#
#
#

import getopt
import sys
import time
import string
import locale

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
#from contrib.no.uit.create_import_data.lib import fstalk
#sys.path = ['/home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/lib'] + sys.path
#import fstalk
from Cerebrum.modules.no.uit.uit_txt2xml_lib import FSImport
db = Factory.get('Database')()
logger = Factory.get_logger('cronjob')
locale.setlocale(locale.LC_ALL,"en_US.ISO-8859-1")


class create_person_xml:


    #def __init__(self,out_file,person_file,type,uname_file,slp4_file):
    def __init__(self,out_file,type,slp4_file):
        person_dict = []
	person_dict_no_uname =[] 
        if (type =="AD"):
	    if slp4_file != 0:
	    	person_info_slp4 = self.parse_person_file(slp4_file,out_file)
                
	    self.create_employee_person_xml(person_info_slp4,out_file)


    # This function uses a person file with information about persons from the NIFU file
    # along with a user_name file which contains a mapping between ssn and AD usernames
    # to create person data for import to cerebrum
    def parse_person_file(self,person_file,out_file):
        person_info = []
        person_info_no_uname = []
        # first lets create a hash table with faculty, institute and group number currently in cerebrum
        query = "select fakultet, institutt, avdeling from stedkode"
        stedkode_row = db.query(query)

        # now lets parse the person_info file and collect all relevant information
        
	person_handle = open(person_file,"r")
        for person in person_handle:
            #print person
            if(person[0] != "#"):
                (personnavn,
                 fodt_dato,
                 fodselsnr,
                 kjonn,
                 ansvarssted,
                 fakultet,
                 institutt,
                 stillingskode,
                 stillingsbetegnelse,
                 begynt) = person.split(",")

		#print "###person name of this person is %s " % (personnavn)
                # TODO: kenneth. husk på at data om personer som ikke finnes i NIFU fila kan finnes i SLP4 dompen
                if(personnavn =='' or fodt_dato =='' or fodselsnr =='' or kjonn =='' or ansvarssted =='' or fakultet =='' or stillingskode =='' or stillingsbetegnelse =='' or begynt ==''):
                    #print "person %s is missing vital data and will not be included in person.xml" % personnavn
                    #print "------------"
                    #print "'%s','%s','%s','%s','%s','%s','%s','%s','%s','%s'" % (personnavn,fodt_dato,fodselsnr,kjonn,ansvarssted,fakultet,institutt,stillingskode,stillingsbetegnelse,begynt)
                    #print "from %s" % person_file
                    #print "------------"
                    continue

                # now lets format the information to suit our system. remove surplus "" etc.
                personnavn = personnavn.lstrip("\"").rstrip("\"")
                #print "personnavn = %s" % personnavn
                fodt_dato = fodt_dato.lstrip("\"").rstrip("\"")
                ansvarssted = ansvarssted.lstrip("\"").rstrip("\"")
                fodselsnr = fodselsnr.lstrip("\"").rstrip("\"")
                if(len(fodselsnr) == 4):
                    #print "PERSON FILE = %s" % person_file
                    logger.warning("WARNING. person '%s','%s' is missing parts of ssn" % (fodt_dato,fodselsnr))
                    # TODO: terrible hack follows. For some reason leading
                    # zeroes in fodselsnr are not stored in the NIFU file.
                    # add leading zero where fodselsnr length == 4
                    fodselsnr = "0%s" % fodselsnr
                    
                fodt_dato = fodt_dato.lstrip("\"").rstrip("\"")
                fodtdag,fodtmnd,fodtar = fodt_dato.split(".",3)
                fakultetnr = ansvarssted[0:2]
                instituttnr = ansvarssted[2:4]
                gruppenr = ansvarssted[4:6]
		try:
                    etternavn,fornavn = personnavn.capitalize().split(" ",1)
		except ValueError,m:
		    logger.warning("Error: Person missing part of name, ignoring person %s%s" % (fodt_dato, fodselsnr))
		    continue
		    
                fornavn = fornavn.capitalize()
                try:
                    # For people with middle names we need to capitalize the
                    # first letter in the middle name
                    fornavn_part1,fornavn_part2 = fornavn.split(" ",1)
                    fornavn = "%s %s" % (fornavn_part1.capitalize(),fornavn_part2.capitalize())
                    
                except:
                    pass
                    #sys.stdout.write(".")
                    #print "No middle name stored in fornavn"

                try:
                    etternavn_part1,etternavn_part2 = etternavn.split(" ",1)
                    etternavn = "%s %s" % (etternavn_part1.capitalize(),etternavn_part2.capitalize())
                except:
                    #sys.stdout.write(".")
                    #print "No middle name stored in etternavn"
                    pass
                try:
                    # Some people have '-' in their names. Need to capitalize the first
                    # letter after the '-'
                    fornavn_part1,fornavn_part2 = fornavn.split("-",1)
                    fornavn = "%s-%s" % (fornavn_part1.capitalize(),fornavn_part2.capitalize())

                except:
                    pass
                    #sys.stdout.write(".")
                    #print "no '-' in this persons name fornavn"
                try:
                    etternavn_part1,etternavn_part2 = etternavn.split("-",1)
                    #print "etternavn_part2 = '%s'" % etternavn_part2.capitalize()
                    etternavn = "%s-%s" % (etternavn_part1.capitalize(),etternavn_part2.capitalize())
                except:
                    pass
                    #sys.stdout.write(".")
                    #print "no '-' in this persons name etternavn"

                try:
                    # some people have a ' in their name. f.eks: d'acoz
                    # this name needs a Capital A and a not D. like: d'Acoz
                    fornavn_part1,fornavn_part2 = fornavn.split("'",1)
                    temp = fornavn_part1[-1]
                    temp = temp.lower()
                    fornavn_part1 = "%s%s" %(fornavn_part1[:-1],temp)
                    fornavn = "%s'%s" % (fornavn_part1,fornavn_part2.capitalize())
                except:
                    pass
                    #sys.stdout.write(".")
                    #print "No ' in this persons fornavn "   

                try:
                    # some people have a ' in their name. f.eks: d'acoz
                    # this name needs a Capital A and a not D. like: d'Acoz
                    etternavn_part1,etternavn_part2 = etternavn.split("'",1)
                    temp = etternavn_part1[-1]
                    temp = temp.lower()
                    etternavn_part1 = "%s%s" % (etternavn_part1[:-1],temp)
                    etternavn = "%s'%s" % (etternavn_part1,etternavn_part2.capitalize())
                    #print "etternavn = %s" % etternavn
                except:
                    pass
                    #sys.stdout.write(".")
                    #print "No ' in this persons etternavn "   
                
                #sys.stdout.write("\n")


                    
                #print "etternavn = %s" % etternavn    
                #etternavn = etternavn.capitalize()
                # lets create a new personnavn with the new fornavn and etternavn
                personnavn = "%s %s" % (fornavn,etternavn)
                begynt = begynt.rstrip("\n")
                #print "begynt = '%s'" % begynt
                # lets create a SSN on the right format for storage in cerebrum
                SSN = "%s%s" % (fodt_dato.replace(".",'',3),fodselsnr)
                #print "SSN = %s" % SSN
                #print "stedkode = %s" % ansvarssted
                ##########################
                # collect right username #
                ##########################
                
                # lets see if we can get the AD username for this person
               	#if(uname_file !=0):
                #    uname = ""
                #    uname = self.get_uname(uname_file,SSN)
                #    if uname == "":
                #        logger.error("username for person %s not found in legacy. Not inserted!." % SSN)
                                                 
                


                ##########################
                # collect right stedkode #
                ##########################
                
                # lets check if the ou referenced as affiliation exists in cerebrum
                query = "select new_ou_id from ou_history where old_ou_id='%s'" % ansvarssted
                #print "query = %s" % query
                new_ou_id = db.query(query)
                if(len(new_ou_id) != 0):
                    #print "new_ou_id %s for person %s%s will be used instead of %s" % (new_ou_id[0][0],fodt_dato,fodselsnr,ansvarssted)
                    ansvarssted = "%s" % new_ou_id[0][0]
                    fakultetnr = ansvarssted[0:2]
                    instituttnr = ansvarssted[2:4]
                    gruppenr = ansvarssted[4:6]

                match = 0
                if(ansvarssted == ''):
                    #print "person %s does not have a stedkode, person not included in person.xml" % SSN
                    continue
                for stedkode in stedkode_row:
                    temp_stedkode = "%02d%02d%02d"% (stedkode[0],stedkode[1],stedkode[2])
                    if(ansvarssted.isdigit()):
                        if(int(temp_stedkode) == int(ansvarssted)):
                            match = temp_stedkode
                            break
                            #institutt = temp_stedkode
                if(match == 0):
                    # this person has a stedkode that does not exist in cerebrum. return error message
                    #print "stedkode %s does not exists in cerebrum." % (ansvarssted)
                    continue
                    #sys.exit(0)

                ###########################
                # collect ou_address data #
                ###########################

                # temporary solution : we hardcode the following variables
                # adresselinje1,poststednr and poststednavn
                adresselinje1 = "Universitetet i Tromsø"
                poststednr = "9037"
                poststednavn = "Tromsø"
                
                ##########################################
                # all data collected, lets create a dict #
                ##########################################
                stillingskode = stillingskode.lstrip("\"").rstrip("\"")
                stillingsbetegnelse = stillingsbetegnelse.lstrip("\"").rstrip("\"")
                #print "uname =%s AND match = %s AND uname_file = %s AND stillingskode = '%s'" % (len(uname),match,uname_file,stillingskode)
                if((match != 0) and (stillingskode != 'None') and (stillingsbetegnelse != 'None') and(instituttnr !='None')):
                    # This means that we have all the info we need to store a new person in cerebrum
                    # lets format the input data.
                    #print "with uname = %s" % personnavn
                    #print "uname = %s" % uname
                    #print "###name of person to be inserted is %s" % fornavn

                    #if (fodselsnr == "38052"):
                        #print "stedkode = %s" % ansvarssted
                        #print "etternavn = %s" % etternavn
		    ansvarssted = ansvarssted.lstrip("\"").rstrip("\"")
                    begynt = begynt.replace(".","/")
                    person_dict = {'navn' : personnavn, #.capitalize(),
                                   'etternavn' : etternavn, #.capitalize(),
                                   'fornavn' : fornavn,
                                   'fodtdag' : fodtdag,
                                   'fodtmnd' : fodtmnd,
                                   'fodtar' : fodtar,
                                   'personnr' : fodselsnr,
                                   'kjonn' : kjonn.lstrip("\"").rstrip("\""),
                                   'stedkode' : ansvarssted,
                                   'fakultet' : fakultetnr,
                                   'institutt' : instituttnr,
                                   'gruppe': gruppenr,
                                   'adresselinje1' : adresselinje1,
                                   'poststednr' : poststednr,
                                   'poststednavn' : poststednavn,
                                  
                                   'stillingskode' : stillingskode.lstrip("\"").rstrip("\""),
                                   'tittel' : stillingsbetegnelse.lstrip("\"").rstrip("\""),
				   #'uname' : uname,	
                                   'Fradato' : begynt.lstrip("\"").rstrip("\"").strip("\n")}
                
                    #print "%s" % person_dict.items()
		    # Now...we must check if this person is already inserted into our person_info array
                    # if that is the case, do not enter new data
                    person_check = 0
                    for person in person_info:
                        if(person['fodtdag']== person_dict['fodtdag'] and person['fodtmnd'] == person_dict['fodtmnd'] and person['personnr'] == person_dict['personnr']):
                            person_check = 1
                            #print "%s %s already exists in the person list. NOT inserted" % (person['fornavn'],person['etternavn'])
                    if person_check == 0:
                        #print "APPEND %s" % person_dict.items()
                        person_info.append(person_dict)


#                 elif((uname_file !=0) and (match != 0) and (len(uname) == 0) ):
# 		    # no uname found, lets create a dict withouth the uname field
#                     #print "NO uname = %s" % personnavn
#                     ansvarssted = ansvarssted.lstrip("\"").rstrip("\"")
#                     person_dict_no_uname = {'navn' : personnavn.capitalize(),
#                                    'etternavn' : etternavn,
#                                    'fornavn' : fornavn,
#                                    'fodtdag' : fodtdag,
#                                    'fodtmnd' : fodtmnd,
#                                    'fodtar' : fodtar,
#                                    'personnr' : fodselsnr,
#                                    'kjonn' : kjonn.lstrip("\"").rstrip("\""),
#                                    'stedkode' : ansvarssted,
#                                    'fakultet' : fakultetnr,
#                                    'institutt' : instituttnr,
#                                    'gruppe': gruppenr,
#                                    'adresselinje1' : adresselinje1,
#                                    'poststednr' : poststednr,
#                                    'poststednavn' : poststednavn,
#                                    'stillingskode' : stillingskode,
#                                    'tittel' : stillingsbetegnelse.lstrip("\"").rstrip("\""),
#                                    'Fradato' : begynt.lstrip("\"").rstrip("\"").strip("\n")}

                    # Now...we must check if this person is already inserted into our person_info array
                    # if that is the case, do not enter new data
#                    person_check = 0
#                    for person in person_info_no_uname:
#                        if(person['fodtdag']== person_dict_no_uname['fodtdag'] and person['fodtmnd'] == person_dict_no_uname['fodtmnd'] and person['personnr'] == person_dict_no_uname['personnr']):
#                            person_check = 1
                            #print "%s %s already exists in the person list. NOT inserted" % (person['fornavn'],person['etternavn'])
#                    if person_check == 0:
                        #print "appending person: %s %s" % (person_dict_no_uname['fornavn'],person_dict_no_uname['etternavn'])
#                        person_info_no_uname.append(person_dict_no_uname)

                    
                    #print "instnr = %s" % person_dict['institutt']
        # all person data collected, lets send the array of dicts to
        # the function that creates the xml file
        return person_info #,person_info_no_uname
        #ret = self.create_employee_person_xml(person_info,out_file)
                
                



    def get_uname2(self,SSN):
        query = "select user_name,source from legacy_users where ssn='%s'" % SSN
        person_uname = db.query(query)
        if(len(person_uname) != 0):
            for i in person_uname:
                if(i['source']=='AD'):
                    return i[0]
            #print "returning %s" % person_uname[0][0]
            return person_uname[0][0]
        else:
            return ""
    
    


    # This function gets any existing usernames for all users. If a user name exists in the
    # file given, a username is generated. The function reads a file on the format: name, SSN, uname,faculty


#     def get_uname(self,uname_file,SSN):
#         name_check = 0
#         #print "uname file = %s" % uname_file
#         uname_handle = open(uname_file,'r')
#         for uname in uname_handle:
#             # Skal lage brukere til alle som:
#             # har brukernavn, personnummer
#             query = "select user_name,source from legacy_users where ssn='%s'" % SSN
#             person_uname = db.query(query)
#             if(len(person_uname) != 0):
#                 for i in person_uname:
#                     if(i['source']=='AD'):
#                         #print "returning %s" % i[0]
#                         return i[0]
#                 #print "returning %s" % person_uname[0][0]
#                 return person_uname[0][0]
            
#             else:
#                 #print "could not get username for person %s from legacy table, person not inserted into cerebrum" % SSN
#                 #sys.exit(0)
#                 return ""
#             #if ((uname[0] != '#') and (uname[0] != '\n')):
#             #    if(uname)
#             #    uname,perso = uname.split(",",2)
#             #    if(long(SSN) == long(personnr)):
#                     #print "***MATCH***"
#             #        return uname.lstrip()
                
#         # we only get here if no username was found
        


    # this function checks that a persons "personnr" is a valid number
    # This goes spesifically for foreign persons
    #def check_SSN(self,personnr):
    #    return personnr

    def create_employee_person_xml(self,person_hash,out_file):
        """ employees in cerebrum will be imported via an xml fil on the following format:
        <person tittel_personlig=""
        fornavn=""
        etternavn=""
        navn=""
        fodtdag=""
        personnr=""
        fodtmnd=""
        fodtar=""
        fakultetnr_for_lonnsslip=""
        instituttnr_for_lonnsslip=""
        gruppenr_for_lonnsslip=""
        #adresselinje1_privatadresse=""
        #poststednr_privatadresse=""
        #poststednavn_privatadresse=""
        #uname=""
        >
        <bilag stedkode=""/>
        </person>
        """

        hovedkat = {}
        #hovedkat.append({})
        hovedkat['PROFESSOR'] = "VIT"     # ok
        hovedkat['PROFESSOR II'] = "VIT"  # ok
        hovedkat['POST DOKTOR'] = "VIT"   # OK
        hovedkat['STIPENDIAT'] = "VIT"    # ok
        hovedkat['FØRSTEAMANUENSIS'] = "VIT" # ok
        hovedkat['AMANUENSIS'] = "VIT"    # ok
        hovedkat['FORSKER'] = "VIT"       # OK
        hovedkat['VITENSKAPELIG ASS'] = "VIT" # OK
        hovedkat['FØRSTEAMANUENSIS II'] = "VIT" # OK
        hovedkat['AVDELINGSINGENIØR'] = "ØVR"
        hovedkat['OVERINGENIØR'] = "ØVR"
        hovedkat['SENIORINGENIØR'] = "ØVR"
        hovedkat['AVD.BIBLIOTEKAR'] = "ØVR"
        hovedkat['AVDELINGSBIBLIOTEKAR'] = "ØVR"
        hovedkat['BIBLIOTEKAR'] = "ØVR"
        hovedkat['LÆRLING (REFORM  94)'] = "ØVR"
        hovedkat['BIBLIOTEKFULLMEKTIG'] = "ØVR"
        hovedkat['RENHOLDSLEDER'] = "ØVR"
        hovedkat['UNIVERSITETSLEKTOR'] = "ØVR"
        hovedkat['KONSULENT'] = "ØVR"
        hovedkat['FØRSTELEKTOR'] = "ØVR"
        hovedkat['FØRSTEBETJENT'] = "ØVR"
        hovedkat['UNIVERSITETSDIREKTØR'] = "ØVR"
        hovedkat['LABORANT'] = "ØVR"
        hovedkat['TEKNIKER'] = "ØVR"
        hovedkat['FORSKNINGSTEKNIKER'] = "ØVR"
        hovedkat['PROSJEKTLEDER'] = "ØVR"
        hovedkat['AVDELINGSLEDER'] = "ØVR"
        hovedkat['RÅDGIVER'] = "ØVR"
        hovedkat['SEKRETÆR'] = "ØVR"
        hovedkat['SEKSJONSSJEF'] = "ØVR"
        hovedkat['FØRSTEKONSULENT'] = "ØVR"
        hovedkat['AVDELINGS BIBLIOTEKAR'] = "ØVR"
        hovedkat['KONTORSJEF'] = "ØVR"
        hovedkat['AVDELINGSDIREKTØR'] = "ØVR"
        hovedkat['UNIVERSI.BIBLIOTEKAR'] = "ØVR"
        hovedkat['FØRSTESEKRETÆR'] = "ØVR"
        
        out_handle = open(out_file,"w")
        person_handle = FSImport()
        #person_handle.readConfig("config.xml")
        bar = {'name' : 'data', 'attr' : 'None'}
        foo = []

        for person_dict in person_hash:
            temp_bilag = []
            temp_tils = []
            tittel = person_dict['tittel'].capitalize()
            # figgure out the stillingstype each person has
            query = "select stillingstype from person_stillingskoder where stillingskode = %s" % (person_dict['stillingskode'])
            #print "person_data = %s" % person_dict.items()
            #print "query = %s" % query
            db_row = db.query(query)
            if(len(db_row) == 0):
                print "person %s %s has a stillingskode '%s' not recognized by cerebrum" % (person_dict['fornavn'],person_dict['etternavn'],person_dict['stillingskode'])
                continue
                #sys.exit(0)
            else:
                if(db_row[0][0] == 'VITENSKAPELIG'):
                    stillingstype = "VIT"
                else:
                    stillingstype = "ØVR"

            tils_value = {'hovedkat' : stillingstype, 'stillingkodenr_beregnet_sist' : person_dict['stillingskode'], 'tittel' : tittel, 'prosent_tilsetting' : '100', 'fakultetnr_utgift' : person_dict['fakultet'], 'instituttnr_utgift' : person_dict['institutt'], 'gruppenr_utgift' : person_dict['gruppe'], 'dato_fra' : person_dict['Fradato'], 'dato_til' : ''}
            stedkode_value = {'stedkode' : person_dict['stedkode']}
            temp_bilag.append({'name' : 'bilag','child' : 'None', 'attr' : stedkode_value})
            temp_tils.append({'name' : 'tils','child' : 'None','attr' : tils_value})
            del person_dict['stedkode']
            person_dict['tittel'] = person_dict['tittel'].capitalize()
            foo.append({'name': 'person', 'child': temp_bilag, 'child': temp_tils, 'attr' : person_dict})
        bar['child'] = foo
        person_handle.writeXML("kenny",bar,out_file)


def main():

     # lets set default out_file file
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    file_path = cereconf.CB_PREFIX + '/var/dumps/employees'
    out_file = '%s/uit_persons_%02d%02d%02d.xml' % (file_path,year,month,day)
    #person_file = 'source_data/NIFU.txt'
    slp4_file = cereconf.CB_PREFIX + '/var/dumps/slp4/slp4_personer_%02d%02d%02d.txt' % (year,month,day)
    #uname_file = cereconf.CB_PREFIX + '/var/source/static_user_info.txt'
    #print "Reading %s" % slp4_file
    #print "Reading %s" % uname_file
    #print "Writing to %s" % (out_file)
    #print "reading %s" % person_file
    try:
        opts,args = getopt.getopt(sys.argv[1:],'p:o:t:u:s:',['person_file=','out_file=','type=','uname_file=','slp4_file='])

    except getopt.GetoptError:
        usage()
    person_run = 0

    for opt,val in opts:
        if opt in ('-p','--person_file'):
            person_file = val
        if opt in ('-o','--out_file'):
            out_file = val
        if opt in ('-t','--type'):
            type = val
        if opt in ('-u','--uname_file'):
            uname_file = val
            
        if opt in ('-s','--slp4_file'):
            slp4_file = val

#    sys.exit(1)
    person_handle = create_person_xml(out_file,type,slp4_file)

def usage():
    print """Usage: python generate_person.py 
    As of now parse_Type only accepts the value \"frida\" and \"AD\"
    User_name_file must be a text file on the following format: FORNAVN ETTERNAVN, PERSONNUMMER, BRUKERNAVN, FAKULTET
    The script can be run with the -t option only. the default values for gathering data will then be used.
    

    options:
    -p | --person_file: NIFU file with person information
    -o | --out_file   : alternative xml file to store data in
    -t | --type       : type of data. AD or FRIDA.. use AD for now
    -u | --uname_file : user_info file
    -s | --slp4_file  : file with slp4 data
    
    """
    sys.exit(0)

if __name__ == '__main__':
    main()

# arch-tag: b19ddc7c-b426-11da-8dfb-f6448add1a85
