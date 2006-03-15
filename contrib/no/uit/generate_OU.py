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

import getopt
import sys
import string

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

#sys.path = ['/home/cerebrum/CVS/cerebrum_H05/cerebrum/contrib/no/uit/create_import_data/lib'] + sys.path
#import fstalk
from Cerebrum.modules.no.uit.uit_txt2xml_lib import FSImport


# Default stedkode data.
fakultetnr="0"                          # FAKNR in fs 
instituttnr="0"                         # INSTITUTTNR in fs
gruppenr="0"                            # GRUPPENR in fs
forkstednavn= ""                      
stednavn=""                           # STEDNAVN_BOKMAL in fs
akronym=""                            # STEDAKRONYM in fs
stedkortnavn_bokmal=""                # STEDKORTNAVN in fs
stedkortnavn_nynorsk=""              
stedkortnavn_engelsk=""
stedlangnavn_bokmal=""
stedlangnavn_nynorsk=""
stedlangnavn_engelsk=""
fakultetnr_for_org_sted="0"             # FAKNR_ORG_UNDER in fs
instituttnr_for_org_std="0"            # INSTITUTTNR_ORG_UNDER in fs
gruppenr_for_org_sted="0"               # GRUPPENR_ORG_UNDER in fs
opprettetmerke_for_oppf_i_kat="X"
telefonnr="77644000"                    # TELEFONNR in fs
innvalgnr="0"
linjenr="0"
stedpostboks="0"

adrtypekode_besok_adr="INT"
adresselinje1_besok_adr="Universitetet i Tromsø" # ADRLIN1 in fs
adresselinje2_besok_adr="Tromsø"       # ADRLIN2 in fs
poststednr_besok_adr="9037"             # POSTNR in fs
poststednavn_besok_adr="Uit"            
landnavn_besok_adr="NORGE"              # ADRESSELAND in fs

adrtypekode_intern_adr="INT"
adresselinje1_intern_adr=""
adresselinje2_intern_adr=""
poststednr_intern_adr="0"
poststednavn_intern_adr="0"
landnavn_intern_adr=""

adrtypekode_alternativ_adr="INT"
adresselinje1_alternativ_adr=""       # ADRLIN1_BESOK in fs
adresselinje2_alternativ_adr=""       # ADRLIN2_BESOK in fs
poststednr_alternativ_adr="0"           # POSTNR_BESOK in fs
poststednavn_alternativ_adr=""
landnavn_alternativ_adr=""            # ADRESSELAND_BESOK in fs

fs_data = []


# default ou xml file
default_xml = "cerebrum_ou.xml"
db = Factory.get('Database')()
logger = Factory.get_logger('cronjob')

class fs_list:
    def __init__(self):
        self.fs_data = []

    def add(self,fs_data):
        self.fs_data.append(fs_data)

    #def debug(self):
        #for item in self.fs_data:
            #print "item = %s " % item['stednavn']

            #print "###%s %s" % (fs_data[item]['temp_inst_nr'],fs_data[item]['stednavn']) 
            #print ""


# This function reates an ou xml entry with data from FS and default values
def create_xml_fsd(fs_data,DISPLAY):

    xml_handle = open(default_xml,"w")
    
    if((fs_data['temp_inst_nr'] == "") or (fs_data['fakultetnr'] == "") or (fs_data['instituttnr'] == "") or(fs_data['gruppenr'] == "") or (fs_data['fakultetnr_for_org_sted'] =="") or (fs_data['instituttnr_for_org_sted'] =="") or (fs_data['gruppenr_for_org_sted'] == "")):
        print "Error in FS data, exiting"
        system.exit(0)
    else:
        if ((fs_data['gruppenr'] == '0') and(fs_data['instituttnr'] == '0')):
            # we have a fakulty, must reference the uit institution
            FAKNR_ORG_UNDER = '00'
            INSTITUTTNR_ORG_UNDER = '00'
            GRUPPENR_ORG_UNDER= '00'

        if((fs_data['gruppenr'] != '0') and (fs_data['instituttnr'] != '0')):
            # we have a group, must reference the institute
            FAKNR_ORG_UNDER = '%s' % fs_data['fakultetnr']
            INSTITUTTNR_ORG_UNDER = "%s" % fs_data['instituttnr']
            GRUPPENR_ORG_UNDER = '00'

        if(((fs_data['instituttnr'] == '0')and(fs_data['gruppenr'] != '0'))or((fs_data['instituttnr'] != '0')and(fs_data['gruppenr'] =='0'))):
            # we have either a institute or a group directly under a faculty. in either case
            # it should reference he faculty
            FAKNR_ORG_UNDER = '%s' % fs_data['fakultetnr']
            INSTITUTTNR_ORG_UNDER = '00'
            GRUPPENR_ORG_UNDER = '00'

        
        fs_data['display_name'] = DISPLAY
        fs_data['instituttnr_for_org_sted'] = INSTITUTTNR_ORG_UNDER
        fs_data['fakultetnr_for_org_sted'] = FAKNR_ORG_UNDER
        fs_data['gruppenr_for_org_sted'] = GRUPPENR_ORG_UNDER
        #print "OLD - %s%s%s references %s%s%s" % (fs_data['fakultetnr'],fs_data['instituttnr'],fs_data['gruppenr'],fs_data['fakultetnr_for_org_sted'],fs_data['instituttnr_for_org_sted'],fs_data['gruppenr_for_org_sted'])
        if(fs_data['stednavn'] == ""):
            fs_data['stednavn'] = stednavn
        if(fs_data['akronym'] == ""):
            fs_data['akronym'] = akronym
        if(fs_data['stedkortnavn_bokmal'] == ""):
            fs_data['stedkortnavn_bokmal'] = stedkortnavn_bokmal
        if(fs_data['telefonnr'] ==""):
            fs_data['telefonnr'] = telefonnr
        if(fs_data['adresselinje1_besok_adr'] ==""):
            fs_data['adresselinje1_besok_adr'] = adresselinje1_besok_adr
        if(fs_data['adresselinje2_besok_adr'] ==""):
            fs_data['adresselinje2_besok_adr'] = adresselinje2_besok_adr
        if((fs_data['poststednr_besok_adr'] == "") and (poststednr_besok_adr.isdigit())):
            fs_data['poststednr_besok_adr'] = poststednr_besok_adr    
        if(fs_data['landnavn_besok_adr'] ==""):
            fs_data['landnavn_besok_adr'] = landnavn_besok_adr
        if(fs_data['adresselinje1_alternativ_adr'] == ""):
            fs_data['adresselinje1_alternativ_adr'] = adresselinje1_alternativ_adr
        if(fs_data['adresselinje2_alternativ_adr'] == ""):
            fs_data['adresselinje2_alternativ_adr'] = adresselinje2_alternativ_adr
        if(fs_data['landnavn_alternativ_adr'] == ""):
            fs_data['landnavn_alternativ_adr'] = landnavn_alternativ_adr

    # create the xml entries
    # Tom, this is where your functions will do their thing
    fs_data2 = fs_data.copy()
    del fs_data2['temp_inst_nr']
    #data = fs_list()
    #data.add(fs_data2)
    #data.debug()
    #print "###%s %s" % (fs_data['fakultetnr'],fs_data['instituttnr']) 
    
    #man_ou_handle.writeXML.writeElem(fs_data)
    return fs_data2

# This function creates an ou xml entry with data from default values only
# (ou does not exist in FS)
def create_xml_nd(INST_NR,STEDNAVN,DISPLAY):
    data = {}
    #print "INST NR = %s" % INST_NR

    # create xml entries from default values
    
    #We must generate fakultetnr_for_org_sted,institutt_for_org_sted and gruppenr_for_org_sted
    # As these cannot have bogus values.
    if(1 ==1):
    #if((int(INST_NR[4]) != 0) and (int(INST_NR[5]) != 0)):
        #temp_str = INST_NR.replace(INST_NR[4:6],"00")
        faknr = INST_NR[0:2]
        instnr = INST_NR[2:4]
        gruppenr = INST_NR[4:6]
        #print "instnr = %s" % instnr
        # now to check if there exists an ou which this group adheres to

        if ((gruppenr == '00') and(instnr == '00')):
            # we have a fakulty, must reference the uit institution
            FAKNR_ORG_UNDER = '00'
            INSTITUTTNR_ORG_UNDER = '00'
            GRUPPENR_ORG_UNDER= '00'

        if((gruppenr != '00') and (instnr != '00')):
            # we have a group, must reference the institute
            FAKNR_ORG_UNDER = '%s' % faknr
            INSTITUTTNR_ORG_UNDER = "%s" % instnr
            GRUPPENR_ORG_UNDER = '00'

        if(((instnr == '00')and(gruppenr != '00'))or((instnr != '00')and(gruppenr =='00'))):
            # we have either a institute or a group directly under a faculty. in either case
            # it should reference he faculty
            FAKNR_ORG_UNDER = '%s' % faknr
            INSTITUTTNR_ORG_UNDER = '00'
            GRUPPENR_ORG_UNDER = '00'


        # TODO: COMPLETE THE VALUES BELOW
        #print "NEW - %s%s%s references %s%s%s" % (faknr,instnr,gruppenr,FAKNR_ORG_UNDER,INSTITUTTNR_ORG_UNDER,GRUPPENR_ORG_UNDER)
        data['display_name'] = DISPLAY
        data['forkstednavn'] = 'UITØ'
        data['fakultetnr'] = faknr
        data['instituttnr'] = instnr
        data['gruppenr'] = gruppenr
        data['stednavn'] = STEDNAVN.capitalize()
        data['akronym'] = akronym
        data['stedkortnavn_bokmal'] = stedkortnavn_bokmal
        data['stedkortnavn_nynorsk'] = stedkortnavn_nynorsk
        data['stedkortnavn_engelsk'] = stedkortnavn_engelsk
        data['stedlangnavn_bokmal'] = stedlangnavn_bokmal
        data['stedlangnavn_nynorsk'] = stedlangnavn_nynorsk
        data['stedlangnavn_engelsk'] = stedlangnavn_engelsk
        data['fakultetnr_for_org_sted'] = FAKNR_ORG_UNDER
        data['instituttnr_for_org_sted'] = INSTITUTTNR_ORG_UNDER
        data['gruppenr_for_org_sted'] = GRUPPENR_ORG_UNDER
        data['opprettetmerke_for_oppf_i_kat'] = opprettetmerke_for_oppf_i_kat
        data['telefonnr'] = telefonnr
        data['innvalgnr'] = innvalgnr
        data['linjenr'] = linjenr
        data['stedpostboks'] = stedpostboks

        data['adrtypekode_besok_adr'] = adrtypekode_besok_adr
        data['adresselinje1_besok_adr'] = adresselinje1_besok_adr
        data['adresselinje2_besok_adr'] = adresselinje2_besok_adr
        data['poststednr_besok_adr'] = poststednr_besok_adr
        data['poststednavn_besok_adr'] = poststednavn_besok_adr
        data['landnavn_besok_adr'] = landnavn_besok_adr

        data['landnavn_intern_adr'] = landnavn_intern_adr
        data['adrtypekode_intern_adr'] = adrtypekode_intern_adr
        data['adresselinje1_intern_adr'] = adresselinje1_intern_adr
        data['adresselinje2_intern_adr'] = adresselinje2_intern_adr
        data['poststednr_inter_adr'] = poststednr_intern_adr
        data['poststednavn_intern_adr'] = poststednavn_intern_adr
        data['landnavn_intern_adr'] = landnavn_intern_adr
        
        data['adrtypekode_alternativ_adr'] = adrtypekode_alternativ_adr
        data['landnavn_alternativ_adr'] = landnavn_alternativ_adr
        data['adresselinje1_alternativ_adr'] = adresselinje1_alternativ_adr
        data['adresselinje2_alternativ_adr'] = adresselinje2_alternativ_adr
        data['poststednr_alternativ_adr'] = poststednr_alternativ_adr
        data['poststednavn_alternativ_adr'] = poststednavn_alternativ_adr
        data['landnavn_alternativ_adr'] = landnavn_alternativ_adr

    
    
    return data

# this function creates a dummy faculty for uit
def create_dummy(file_name):

    file_handle = open(file_name,'w')
    dummy = {}
    dummy['fakultetnr'] = "42"
    dummy['instituttnr'] = "00"
    dummy['gruppenr'] = "00"
    dummy['stednavn'] = 'Universitetet i Tromsø'
    dummy['forkstednavn'] = 'UITØ'
    dummy['akronym'] = 'UIT'
    dummy['stedkortnavn_bokmal'] = 'Tromsø'
    dummy['stedkortnavn_nynorsk'] = stedkortnavn_nynorsk
    dummy['stedkortnavn_engelsk'] = stedkortnavn_engelsk
    dummy['stedlangnavn_bokmal'] = stedlangnavn_bokmal
    dummy['stedlangnavn_nynorsk'] = stedlangnavn_nynorsk
    dummy['stedlangnavn_engelsk'] = stedlangnavn_engelsk
    dummy['fakultetnr_for_org_sted'] = "0"
    dummy['instituttnr_for_org_sted'] = "0"
    dummy['gruppenr_for_org_sted'] = "0"
    dummy['opprettetmerke_for_oppf_i_kat'] = opprettetmerke_for_oppf_i_kat
    dummy['telefonnr'] = '77644000'
    dummy['innvalgnr'] = innvalgnr
    dummy['linjenr'] = linjenr
    dummy['stedpostboks'] = stedpostboks
    
    dummy['adrtypekode_besok_adr'] = adrtypekode_besok_adr
    dummy['adresselinje1_besok_adr'] = 'dummy'
    dummy['adresselinje2_besok_adr'] = 'dummy'
    dummy['poststednr_besok_adr'] = '9037'
    dummy['poststednavn_besok_adr'] = poststednavn_besok_adr
    dummy['landnavn_besok_adr'] = 'norge'
    
    dummy['adrtypekode_intern_adr'] = adrtypekode_intern_adr
    dummy['adresselinje1_intern_adr'] = adresselinje1_intern_adr
    dummy['adresselinje2_intern_adr'] = adresselinje2_intern_adr
    dummy['poststednr_inter_adr'] = poststednr_intern_adr
    dummy['poststednavn_intern_adr'] = poststednavn_intern_adr
    dummy['landnavn_intern_adr'] = 'norge'
    
    dummy['adrtypekode_alternativ_adr'] = adrtypekode_alternativ_adr
    dummy['adresselinje1_alternativ_adr'] = 'dummy'
    dummy['adresselinje2_alternativ_adr'] = 'dummy'
    dummy['poststednr_alternativ_adr'] = '9037'
    dummy['poststednavn_alternativ_adr'] = poststednavn_alternativ_adr
    dummy['landnavn_alternativ_adr'] = 'norge'

    #dummy_data.append(create_xml_fsd(dummy))
    man_ou_handle = FSImport()
    man_ou_handle.readConfig("config.xml")
    bar = {'name' : 'data', 'attr' : 'None'}
    foo = []
    #for sted_dict in global_dummy:
    foo.append({'name': 'sted', 'child': 'None', 'attr' : dummy})

    bar['child'] = foo
    
    man_ou_handle.writeXML("kenny", bar,default_xml)



# this function compares two files and extracts ou information for
# all ou's that has this information. For those ou's that does
# not have any information, default values are used
def create_ou(ou_file,fs_file,root,default_xml):
    global_data = []
    global_data2 = []
    fs_handle = open(fs_file,"r")
    ou_handle = open(ou_file,"r")
    i = 0
    
    for temp in fs_handle:
        if (temp[0] != "#"):
            INSTITUSJONSNR,FAKNR,INSTITUTTNR,GRUPPENR,STEDAKRONYM,STEDNAVN_BOKMAL,ORGNIVAKODE,INSTITUSJONSNR_ORG_UNDER,FAKNR_ORG_UNDER,INSTITUTTNR_ORG_UNDER,GRUPPENR_ORG_UNDER,ADRLIN1,ADRLIN2,POSTNR,ADRLIN3,ADRESSELAND,STEDKORTNAVN,STEDNAVN_NYNORSK,STEDNAVN_ENGELSK,TELEFONLANDNR,TELEFONRETNNR,TELEFONNR,FAXNR,INSTITUSJONSNR_ERSTATTES_AV,FAKNR_ERSTATTES_AV,INSTITUTTNR_ERSTATTES_AV,GRUPPENR_ERSTATTES_AV,DATO_AKTIV_FRA,DATO_AKTIV_TIL,NSD_AVDKODE,EIERTYPEKODE,ADRLIN1_BESOK,ADRLIN2_BESOK,POSTNR_BESOK,ADRLIN3_BESOK,ADRESSELAND_BESOK,EMAILADRESSE,KODEVERDITYPE,NSDINSTKODE,INSTTYPEKODE,UTRSTEDKODE,LANDNR,TELEFONLANDNR_FAX,TELEFONRETNNR_FAX,TELEFONNR_FAX,INSTITUSJONSNR_GEOGR,FAKNR_GEOGR,INSTITUTTNR_GEOGR,GRUPPENR_GEOGR,BIBSYSBESTSTEDKODE,ORGNR,URL,TELEFONLANDNR_2,TELEFONRETNNR_2,TELEFONNR_2,MERKNADTEKST = temp.split(",",55)
            temp_inst_nr = "%02d%02d%02d" % (int(FAKNR),int(INSTITUTTNR),int(GRUPPENR))
            
            fs_data.append({})
            fs_data[i]['temp_inst_nr'] = temp_inst_nr
            fs_data[i]['fakultetnr'] = FAKNR
            fs_data[i]['instituttnr'] = INSTITUTTNR
            fs_data[i]['gruppenr'] = GRUPPENR
            fs_data[i]['stednavn'] = STEDNAVN_BOKMAL
            fs_data[i]['forkstednavn'] = forkstednavn
            fs_data[i]['akronym'] = STEDAKRONYM
            fs_data[i]['stedkortnavn_bokmal'] = STEDKORTNAVN
            fs_data[i]['stedkortnavn_nynorsk'] = stedkortnavn_nynorsk
            fs_data[i]['stedkortnavn_engelsk'] = stedkortnavn_engelsk
            fs_data[i]['stedlangnavn_bokmal'] = stedlangnavn_bokmal
            fs_data[i]['stedlangnavn_nynorsk'] = stedlangnavn_nynorsk
            fs_data[i]['stedlangnavn_engelsk'] = stedlangnavn_engelsk
            fs_data[i]['fakultetnr_for_org_sted'] = FAKNR_ORG_UNDER
            fs_data[i]['instituttnr_for_org_sted'] = INSTITUTTNR_ORG_UNDER
            fs_data[i]['gruppenr_for_org_sted'] = GRUPPENR_ORG_UNDER
            fs_data[i]['opprettetmerke_for_oppf_i_kat'] = opprettetmerke_for_oppf_i_kat
            fs_data[i]['telefonnr'] = TELEFONNR
            fs_data[i]['innvalgnr'] = innvalgnr
            fs_data[i]['linjenr'] = linjenr
            fs_data[i]['stedpostboks'] = stedpostboks

            fs_data[i]['adrtypekode_besok_adr'] = adrtypekode_besok_adr
            fs_data[i]['adresselinje1_besok_adr'] = ADRLIN1
            fs_data[i]['adresselinje2_besok_adr'] = ADRLIN2
            if(POSTNR.isdigit()):
                fs_data[i]['poststednr_besok_adr'] = POSTNR
            else:
                fs_data[i]['poststednr_besok_adr'] = poststednr_besok_adr
            fs_data[i]['poststednavn_besok_adr'] = poststednavn_besok_adr
            fs_data[i]['landnavn_besok_adr'] = ADRESSELAND
            
            fs_data[i]['adrtypekode_intern_adr'] = adrtypekode_intern_adr
            fs_data[i]['adresselinje1_intern_adr'] = adresselinje1_intern_adr
            fs_data[i]['adresselinje2_intern_adr'] = adresselinje2_intern_adr
            fs_data[i]['poststednr_inter_adr'] = poststednr_intern_adr
            fs_data[i]['poststednavn_intern_adr'] = poststednavn_intern_adr
            fs_data[i]['landnavn_intern_adr'] = ADRESSELAND

            fs_data[i]['adrtypekode_alternativ_adr'] = adrtypekode_alternativ_adr
            fs_data[i]['adresselinje1_alternativ_adr'] = ADRLIN1_BESOK
            fs_data[i]['adresselinje2_alternativ_adr'] = ADRLIN2_BESOK
            if(POSTNR_BESOK.isdigit()):
                fs_data[i]['poststednr_alternativ_adr'] = POSTNR_BESOK
            else:
                fs_data[i]['poststednr_alternativ_adr'] = poststednr_alternativ_adr
            fs_data[i]['poststednavn_alternativ_adr'] = poststednavn_alternativ_adr
            fs_data[i]['landnavn_alternativ_adr'] = ADRESSELAND_BESOK
            #print "### %s = %s" % (i,fs_data[i]['temp_inst_nr'])
            # special case for including the uit institution
            if(root ==1):
                if(int (fs_data[i]['temp_inst_nr']) == 000000):
                    #print "INSERT ROOT OU"
                    fs_data[i]['display_name'] = 'Universitetet i tromsø'
                    global_data2 = fs_data[i].copy()
                    del global_data2['temp_inst_nr']
                    global_data.append(global_data2)
                    
                    #create_xml_fsd(fs_data[i])
            i+=1
            
    num_elements = i-1

    #i+=1
    # now we must read the authoritative uo file. IF ou exists in fs file
    # then use stored info, if not, use default info.

    test_value_1 = 0
    test_value_2 = 0
    for temp in ou_handle:
        if((temp[0] !='\n') and (temp[0] != '#')):
            INST_NR,SOURCE,STEDNAVN,GRUPPE,DISPLAY = temp.split(",") # TODO. MUST SEND EITHER SOURCE,STEDNAVN OR GRUPPE BASED ON OU TYPE
            DISPLAY = DISPLAY.rstrip("\n").capitalize()
            DISPLAY= DISPLAY.rstrip("\t")
            #print "Processing line = %s %s %s '%s'" % (INST_NR,SOURCE,STEDNAVN,DISPLAY)
            # lets fix the display string. Remove trailing newline and set the right character capitalization

            if(1 == remove_surp_ou(INST_NR)):
                match = 0
                i=0
                while(i<=num_elements):
                    #print "%s = %s" % (fs_data[i]['temp_inst_nr'],INST_NR) 
                    if(int(fs_data[i]['temp_inst_nr']) == int(INST_NR)):
                        #print "MATCH on %s" % INST_NR
                        match = 1
                        test_value_1 += 1
                        # For all ou in both files, use stored ou info
                        #fs_data2 = fs_data
                        global_data.append(create_xml_fsd(fs_data[i],DISPLAY))
                                
                    i+=1

                if(match == 0):
                    #print "DEBUG: match=0, ou does not exist in FS."
                    # this ou does not exist in fs. must generate ou info based on default values
                    test_value_2 +=1
                    # lets find the right ou name to use in the xml file
                    ou_description = get_ou_name(INST_NR,STEDNAVN,SOURCE,GRUPPE)
                    global_data.append(create_xml_nd(INST_NR,ou_description,DISPLAY))
                match = 0
    #print "number of old OU's = %s AND number of new OU's = %s" % (test_value_1,test_value_2)
                
    #print "GD = %s" % global_data
    man_ou_handle = FSImport()
    #man_ou_handle.readConfig("/cerebrum/lib/python2.3/site-packages/Cerebrum/modules/no/uit/uit_txt2xml_config.xml")
    bar = {'name' : 'data', 'attr' : 'None'}
    foo = []
    for sted_dict in global_data:
        #print "forkstednavn = %s " %sted_dict['forkstednavn']
        foo.append({'name': 'sted', 'child': 'None', 'attr' : sted_dict})

    bar['child'] = foo
    
    man_ou_handle.writeXML("kenny", bar,default_xml)


# THIS function returns the correct name for the ou given.
# A faculty will use the STEDNAVN name
# A institute will ise the SOURCE name
# A group will use the GRUPPE name
def get_ou_name(INST_NR,STEDNAVN,SOURCE,GRUPPE):
    fakultet = INST_NR[0:2]
    institutt = INST_NR[2:4]
    gruppe = INST_NR[4:6]

    if((fakultet != '00') and (institutt == '00') and (gruppe =='00')):
        # We have a faculty. return STEDNAVN name
        #print "returning faculty name %s" % SOURCE
        return SOURCE
    if((fakultet != '00') and (gruppe != '00')):
        # we have a group, return GRUPPE name
        #print "returning group name %s" % GRUPPE
        return GRUPPE
    if((fakultet != '00') and (institutt != '00') and (gruppe == '00')):
        # we have a institute return SOURCE name
        #print "returning institute name %s" % STEDNAVN
        return STEDNAVN
        

# sertain ou's, are not to be stored in cerebrum. all references to these ou's
# need to be redirected to its parent ou. This function checks a mapping table in cerebrum
# and generates the correct mapping for ou's and persons
def remove_surp_ou(INST_NR):

    query = "select old_ou_id from ou_history where old_ou_id='%s'" % INST_NR
    db_row = db.query(query)
    if(len(db_row) > 0):
        logger.debug("%s IS NOT TO BE REGISTRED IN CEREBRUM" % INST_NR)
        # indication that all references to this ou is to be replaced with another one.
        # i.e, this ou is not to be inserted
        return 0
    return 1

        
def main():
    #print "syspath = %s" % sys.path
    try:
        opts,args = getopt.getopt(sys.argv[1:],'f:o:root:d:O:',['fs_source=','ou_source=','dummy=','Out_file='])

    except getopt.GetoptError:
        usage()
    fs_run = 0
    ou_run = 0
    dummy_run = 0
    root = 0
    for opt,val in opts:
        if opt in ('-f','--fs_source'):
            fs_run =1
            fs_file = val
        if opt in ('-o','--ou_source'):
            ou_run=1
            ou_file = val
        if opt in ('-r','-root'):
            root =1 # create the uit root uid
        if opt in('-d','-dummy'):
            dummy_run = 1
            dummy_val = val
        if opt in ('-O','-Out_file'):
            default_xml = val
    if(fs_run == 1 and ou_run == 1):
        create_ou(ou_file,fs_file,root,default_xml)
    elif(dummy_run ==1):
        create_dummy(dummy_val)
    else:
        usage()

def usage():
    print """Usage: python generate_OU.py -f fs_file | -o ou_source | -r
    -f | --fs_source - fs data source file
    -o | --ou_source - ou source file. list over all ou's to include in cerebrum
    -r | --root - indicates that we are to create the root node"""
    sys.exit(0)

if __name__ == '__main__':
    main()

# arch-tag: b0b0cfcc-b426-11da-8613-aa7e7937cdbc
