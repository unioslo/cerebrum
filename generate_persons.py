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
# This file reads slp4 dump file and creates a person xml file.
#
#

import getopt
import sys
import os
import time
import string
import locale

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.Utils import Factory, AtomicFileWriter
from Cerebrum.extlib import xmlprinter

from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError

db = Factory.get('Database')()
logger = Factory.get_logger("cronjob")


# Define default file locations
date = time.localtime()
dumpdir_employees = os.path.join(cereconf.DUMPDIR, "employees")
dumpdir_slp4 = os.path.join(cereconf.DUMPDIR, "slp4")
default_employee_file = 'uit_persons_%02d%02d%02d.xml' % (date[0], date[1], date[2])
default_slp4_file = 'slp4_personer_%02d%02d%02d.txt' % (date[0], date[1], date[2])


class create_person_xml:

    def __init__(self,out_file,type,slp4_file):
        person_dict = []
	person_dict_no_uname =[] 
        if (type =="AD"):
	    if slp4_file != 0:
	    	person_info_slp4 = self.parse_person_file(slp4_file,out_file)
                
	    self.create_employee_person_xml(person_info_slp4,out_file)


    # This function reads a SLP4 person file with information about persons 
    # to create person data for import to cerebrum
    def parse_person_file(self,person_file,out_file):
        ou_obj = Factory.get('OU')(db)

        
        person_info = []
        person_info_no_uname = []
        # first lets create a hash table with faculty, institute and group number currently in cerebrum
        query = "select fakultet, institutt, avdeling from stedkode"
        stedkode_row = db.query(query)

        # now lets parse the person_info file and collect all relevant information        
	person_handle = open(person_file,"r")
        lineno = 0
        for person in person_handle:
            lineno += 1
            if(person[0] != "#"):
                try:
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
                except ValueError:
                    logger.error("Person info with wrong format in person file: %s", person);
                    continue

		#print "###person name of this person is %s " % (personnavn)
                if(personnavn =='' or fodt_dato =='' or fodselsnr =='' or kjonn =='' or ansvarssted ==''
                   or fakultet =='' or stillingskode =='' or stillingsbetegnelse =='' or begynt ==''):
                    logger.error("Missing vital data from slp4 source. line nr: %d" % (lineno))
                    continue

                # now lets format the information to suit our system. remove surplus "" etc.
                personnavn = personnavn.lstrip("\"").rstrip("\"")
                #print "personnavn = %s" % personnavn

                fodselsnr = fodselsnr.lstrip("\"").rstrip("\"")
                if(len(fodselsnr) == 4):
                    logger.warning("person '%s','%s' is missing parts of fodselsnr, add leading 0's" % (fodt_dato,fodselsnr))
                    # add leading zero where fodselsnr length == 4
                    fodselsnr = "0%s" % fodselsnr
                    
                fodt_dato = fodt_dato.lstrip("\"").rstrip("\"")
                fodtdag,fodtmnd,fodtar = fodt_dato.split(".",3)
                
                ansvarssted = ansvarssted.lstrip("\"").rstrip("\"")
                #print "stedkode = %s" % ansvarssted
                fakultetnr = ansvarssted[0:2]
                instituttnr = ansvarssted[2:4]
                gruppenr = ansvarssted[4:6]

                last_name_length=1
                if personnavn.startswith("VAN ") or \
                   personnavn.startswith("VON ") or \
                   personnavn.startswith("DES ") or \
                   personnavn.startswith("DE ")  or \
                   personnavn.startswith("DO ")  or \
                   personnavn.startswith("DA ") or \
                   personnavn.startswith("ESKONSIPO NYSTAD "):
                    last_name_length=2
                if personnavn.startswith("VAN DER "):
                    last_name_length=3

		try:
                    name_split= personnavn.decode('iso8859-1').title().encode('iso8859-1').split(" ",last_name_length)
                    etternavn=" ".join(name_split[:last_name_length])
                    fornavn=" ".join(name_split[last_name_length:])
		except ValueError,m:
		    logger.error("Person %s %s is missing part of name (%s), ignoring" % (fodt_dato, fodselsnr, personnavn))
		    continue

                try:
                    # some people have a ' in their name. f.eks: d'acoz
                    # this name needs a Capital A and a not D. like: d'Acoz
                    etternavn_part1,etternavn_part2 = etternavn.split("'",1)
                    temp = etternavn_part1[-1]
                    temp = temp.lower()
                    etternavn_part1 = "%s%s" % (etternavn_part1[:-1],temp)
                    etternavn = "%s'%s" % (etternavn_part1,etternavn_part2.capitalize())
                except:
                    pass

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
                    
                # lets create a new personnavn with the new fornavn and etternavn
                personnavn = "%s %s" % (fornavn,etternavn)
                begynt = begynt.rstrip("\n")

                # lets create a SSN on the right format for storage in cerebrum
                SSN = "%s%s" % (fodt_dato.replace(".",'',3),fodselsnr)

                ##########################
                # collect right stedkode #
                ##########################
                # lets check if the ou referenced as affiliation exists in cerebrum
                query = "select new_ou_id from ou_history where old_ou_id='%s'" % ansvarssted
                #print "query = %s" % query
                new_ou_id = db.query(query)
                if(len(new_ou_id) != 0):
                    logger.warn("new_ou_id %s for person %s %s will be used instead of %s" % (new_ou_id[0][0],fodt_dato,fodselsnr,ansvarssted))
                    ansvarssted = "%s" % new_ou_id[0][0]
                    fakultetnr = ansvarssted[0:2]
                    instituttnr = ansvarssted[2:4]
                    gruppenr = ansvarssted[4:6]

                match = 0
                if(ansvarssted == ''):
                    logger.error("person %s does not have a stedkode, person not included in person.xml" % (SSN))
                    continue

                for stedkode in stedkode_row:
                    temp_stedkode = "%02d%02d%02d"% (stedkode[0],stedkode[1],stedkode[2])
                    if(ansvarssted.isdigit()):
                        if(int(temp_stedkode) == int(ansvarssted)):
                            match = temp_stedkode
                            break

                if(match == 0):
                    # this person has a stedkode that does not exist in cerebrum. return error message
                    if (ansvarssted != 'None'):
                        # None comes from SLP4 on persons that are "kontraktloennet"
                        logger.error("stedkode %s for person %s does not exists in cerebrum." % (ansvarssted,SSN))
                    continue

                ou_obj.clear();
                try:
                    ou_obj.find_stedkode(int(fakultetnr), int(instituttnr), int(gruppenr), cereconf.DEFAULT_INSTITUSJONSNR)
                except EntityExpiredError:
                    logger.error("Stedkode %s%s%s for person %s is expired. Person not included in person.xml" % (fakultetnr, instituttnr, gruppenr, SSN))
                    continue
                
                

                ###########################
                # collect ou_address data #
                ###########################

                # temporary solution : we hardcode the following variables
                # adresselinje1,poststednr and poststednavn
                adresselinje1 = "Universitetet i Troms�"
                poststednr = "9037"
                poststednavn = "Troms�"
                
                ##########################################
                # all data collected, lets create a dict #
                ##########################################
                stillingskode = stillingskode.lstrip("\"").rstrip("\"")
                stillingsbetegnelse = stillingsbetegnelse.lstrip("\"").rstrip("\"")
                if((match != 0) and (stillingskode != 'None') and (stillingsbetegnelse != 'None') and(instituttnr !='None')):
                    # This means that we have all the info we need to store a new person in cerebrum
                    # lets format the input data.

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
                                   'Fradato' : begynt.lstrip("\"").rstrip("\"").strip("\n")}
                
		    # Now...we must check if this person is already inserted into our person_info array
                    # if that is the case, do not enter new data
                    person_check = 0
                    for person in person_info:
                        if(person['fodtdag']== person_dict['fodtdag'] and
                           person['fodtmnd'] == person_dict['fodtmnd'] and
                           person['personnr'] == person_dict['personnr']):
                            person_check = 1
                            logger.info("%s %s already exists in the person list. NOT inserted" % (person['fornavn'],person['etternavn']))
                    if person_check == 0:
                        person_info.append(person_dict)



        # all person data collected, lets send the array of dicts to
        # the function that creates the xml file
        return person_info #,person_info_no_uname




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
        hovedkat['F�RSTEAMANUENSIS'] = "VIT" # ok
        hovedkat['AMANUENSIS'] = "VIT"    # ok
        hovedkat['FORSKER'] = "VIT"       # OK
        hovedkat['VITENSKAPELIG ASS'] = "VIT" # OK
        hovedkat['F�RSTEAMANUENSIS II'] = "VIT" # OK
        hovedkat['AVDELINGSINGENI�R'] = "�VR"
        hovedkat['OVERINGENI�R'] = "�VR"
        hovedkat['SENIORINGENI�R'] = "�VR"
        hovedkat['AVD.BIBLIOTEKAR'] = "�VR"
        hovedkat['AVDELINGSBIBLIOTEKAR'] = "�VR"
        hovedkat['BIBLIOTEKAR'] = "�VR"
        hovedkat['L�RLING (REFORM  94)'] = "�VR"
        hovedkat['BIBLIOTEKFULLMEKTIG'] = "�VR"
        hovedkat['RENHOLDSLEDER'] = "�VR"
        hovedkat['UNIVERSITETSLEKTOR'] = "�VR"
        hovedkat['KONSULENT'] = "�VR"
        hovedkat['F�RSTELEKTOR'] = "�VR"
        hovedkat['F�RSTEBETJENT'] = "�VR"
        hovedkat['UNIVERSITETSDIREKT�R'] = "�VR"
        hovedkat['LABORANT'] = "�VR"
        hovedkat['TEKNIKER'] = "�VR"
        hovedkat['FORSKNINGSTEKNIKER'] = "�VR"
        hovedkat['PROSJEKTLEDER'] = "�VR"
        hovedkat['AVDELINGSLEDER'] = "�VR"
        hovedkat['R�DGIVER'] = "�VR"
        hovedkat['SEKRET�R'] = "�VR"
        hovedkat['SEKSJONSSJEF'] = "�VR"
        hovedkat['F�RSTEKONSULENT'] = "�VR"
        hovedkat['AVDELINGS BIBLIOTEKAR'] = "�VR"
        hovedkat['KONTORSJEF'] = "�VR"
        hovedkat['AVDELINGSDIREKT�R'] = "�VR"
        hovedkat['UNIVERSI.BIBLIOTEKAR'] = "�VR"
        hovedkat['F�RSTESEKRET�R'] = "�VR"

        stream = AtomicFileWriter(out_file, "w")
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level = 2,
                                       data_mode = True,
                                       input_encoding = "latin1")
        writer.startDocument(encoding = "iso8859-1")
        writer.startElement("data")

        for person_dict in person_hash:
            temp_bilag = []
            temp_tils = []            
            tittel = person_dict['tittel'].decode('iso8859-1').capitalize().encode('iso8859-1')
            # figgure out the stillingstype each person has
            query = "select stillingstype from person_stillingskoder where stillingskode = %s" % (person_dict['stillingskode'])
            db_row = db.query(query)
            if(len(db_row) == 0):
                logger.error("person %s %s has a stillingskode '%s' not recognized by cerebrum" % (person_dict['fornavn'],person_dict['etternavn'],person_dict['stillingskode']))
                continue
            else:
                if(db_row[0][0] == 'VITENSKAPELIG'):
                    stillingstype = "VIT"
                else:
                    stillingstype = "�VR"

            tils_value = {'hovedkat' : stillingstype,
                          'stillingkodenr_beregnet_sist' : person_dict['stillingskode'],
                          'tittel' : tittel,
                          'prosent_tilsetting' : '100',
                          'fakultetnr_utgift' : person_dict['fakultet'],
                          'instituttnr_utgift' : person_dict['institutt'],
                          'gruppenr_utgift' : person_dict['gruppe'],
                          'dato_fra' : person_dict['Fradato'],
                          'dato_til' : ''}
            stedkode_value = {'stedkode' : person_dict['stedkode']}
            temp_bilag.append({'name' : 'bilag','child' : 'None', 'attr' : stedkode_value})
            temp_tils.append({'name' : 'tils','child' : 'None','attr' : tils_value})
            del person_dict['stedkode']
            person_dict['tittel'] = person_dict['tittel'].decode('iso8859-1').capitalize().encode('iso8859-1')
            writer.startElement("person",person_dict)
            writer.emptyElement("tils",tils_value)
            writer.endElement("person")
        writer.endElement("data")
        writer.endDocument()
        stream.close()


def main():
    
    # lets set default out_file file
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    
    out_file = os.path.join(dumpdir_employees, default_employee_file)
    slp4_file = os.path.join(dumpdir_slp4, default_slp4_file)
    #uname_file = cereconf.CB_PREFIX + '/var/source/static_user_info.txt'
    #print "Reading %s" % slp4_file
    #print "Reading %s" % uname_file
    #print "Writing to %s" % (out_file)
    #print "reading %s" % person_file
    try:
        opts,args = getopt.getopt(sys.argv[1:],'p:o:t:u:s:',['person_file=','out_file=','type=','uname_file=','slp4_file='])

    except getopt.GetoptError:
        usage()

    for opt,val in opts:
        if opt in ('-o','--out_file'):
            out_file = val
        if opt in ('-t','--type'):
            type = val
        if opt in ('-s','--slp4_file'):
            slp4_file = val
    
    person_handle = create_person_xml(out_file, type, slp4_file)

def usage():
    print """Usage: python generate_person.py 
    As of now parse_Type only accepts the value \"frida\" and \"AD\"
    User_name_file must be a text file on the following format: FORNAVN ETTERNAVN, PERSONNUMMER, BRUKERNAVN, FAKULTET
    The script can be run with the -t option only. the default values for gathering data will then be used.
    

    options:
    -o | --out_file   : alternative xml file to store data in
    -t | --type       : type of data. AD or FRIDA.. use AD for now
    -s | --slp4_file  : file with slp4 data
    --logger-name     : name of logger to use
    --logger-level    : loglevel to use
    
    """
    sys.exit(0)

if __name__ == '__main__':
    main()

# arch-tag: b19ddc7c-b426-11da-8dfb-f6448add1a85
