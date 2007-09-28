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
import os
import time
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum.modules.no.uit.access_FS import FS
from Cerebrum.Utils import Factory, AtomicFileWriter
from Cerebrum.extlib import xmlprinter

logger = Factory.get_logger("cronjob")

# Default file locations
t = time.localtime()
sourcedir = cereconf.CB_SOURCEDATA_PATH
default_input_file = os.path.join(sourcedir, 'stedtre-gjeldende.csv')

dumpdir = os.path.join(cereconf.DUMPDIR,"ou")
default_output_file = os.path.join(dumpdir,'uit_ou_%d%02d%02d.xml' % (t[0], t[1], t[2]))

class ou:

    def __init__(self,ou_file):
        if not(os.path.isfile(ou_file)):
            logger.error("ou file:%s does not exist\n" % ou_file)
            sys.exit(1)
        self.ou_file = ou_file
        # BAS
        self.db = Factory.get('Database')()

        # FS 
        user="fsbas"
        service="fsprod"
        self.fs_db = Database.connect(user=user,service=service,DB_driver='Oracle')
        self.fs = FS(self.fs_db)
        self.fs_data=[]


    # sertain ou's, are not to be stored in cerebrum. all references to these ou's
    # need to be redirected to its parent ou. This function checks a mapping table in cerebrum
    # and generates the correct mapping for ou's and persons
    def remove_surp_ou(self,INST_NR):

        query = "select old_ou_id from ou_history where old_ou_id='%s'" % INST_NR
        db_row = self.db.query(query)
        if(len(db_row) > 0):
            logger.error("%s IS NOT TO BE REGISTRED IN CEREBRUM" % INST_NR)
            # indication that all references to this ou is to be replaced with another one.
            # i.e, this ou is not to be inserted
            return 0
        return 1 



        
    # lets collect data about all active ou's from FS.
    def get_fs_ou(self):
        logger.info("Reading OU's from FS")
        ouer = self.fs.ou.GetAlleOUer(institusjonsnr=186)
        poststednr_besok_adr=''
        poststednr_alternativ_adr=''
        for i in ouer:
            temp_inst_nr = "%02d%02d%02d" % (i['faknr'],i['instituttnr'],i['gruppenr'])
            for key in i.keys():
                if i[key]==None:
                    i[key]=""
                else:
                    i[key]=str(i[key])
            postnr = "%s" % i['postnr']
            postnr_besok = "%s" % i['postnr_besok']
            
            if(postnr.isdigit()):
                poststednr_besok_adr = postnr

            if(postnr_besok.isdigit()):
                poststednr_alternativ_adr = postnr_besok
                #print i.keys()
            #print "telefonnr før = %s" % i['telefonnr']
            if not i['telefonlandnr'] : i['telefonlandnr']="0"
            if not i['telefonretnnr'] : i['telefonretnnr']="0"
            if not i['telefonnr'] : i['telefonnr']="0"
            if not i['adrlin1'] : i['adrlin1'] = 'Universitetet i Tromsø'
            if not i['adrlin2'] : i['adrlin2'] = i['stednavn_bokmal'] 
            if not i['postnr'] : i['postnr'] = '9037'
            if not i['adrlin3'] : i['adrlin3'] = 'Tromsø'
            
            self.fs_data.append({
                                 'temp_inst_nr' : temp_inst_nr,
                                 'fakultetnr' : "%02d" % int(i['faknr']),
                                 'instituttnr' : "%02d" % int(i['instituttnr']),
                                 'gruppenr' : "%02d" % int(i['gruppenr']),
                                 'stednavn' : i['stednavn_bokmal'],
                                 'forkstednavn' : i['stedkortnavn'],
                                 'akronym' : i['stedakronym'],
                                 'stedkortnavn_bokmal' : i['stedkortnavn'],
                                 'stedkortnavn_nynorsk' : i['stednavn_nynorsk'],
                                 'stedkortnavn_engelsk' : i['stednavn_engelsk'],
                                 'stedlangnavn_bokmal': i['stednavn_bokmal'],
                                 'stedlangnavn_nynorsk': i['stednavn_nynorsk'],
                                 'stedlangnavn_engelsk' : i['stednavn_engelsk'],
                                 'fakultetnr_for_org_sted' : "%02d" % int(i['faknr_org_under']),
                                 'instituttnr_for_org_sted': "%02d" % int(i['instituttnr_org_under']),
                                 'gruppenr_for_org_sted' : "%02d" % int(i['gruppenr_org_under']),
                                 'opprettetmerke_for_oppf_i_kat' : 'X', #i['opprettetmerke_for_oppf_i_kat'],
                                 'telefonnr' : i['telefonnr'],
                                 'innvalgnr' : '%s%s'%(i['telefonlandnr'],i['telefonretnnr']),
                                 'linjenr' : i['telefonnr'],
                                 'stedpostboks' : '',#i['stedpostboks'],
                                 'adrtypekode_besok_adr': 'INT',#i['adrtypekode_besok_adr'],
                                 'adresselinje1_besok_adr' :i['adrlin1'],
                                 'adresselinje2_besok_adr': i['adrlin2'],
                                 'poststednr_besok_adr' : poststednr_besok_adr,
                                 'poststednavn_besok_adr' : '%s %s %s' % (i['adrlin1_besok'],i['adrlin2_besok'],i['adrlin3_besok']),
                                 'landnavn_besok_adr' : i['adresseland_besok'],
                                 'adrtypekode_intern_adr': '',#i['adrtypekode_intern_adr'],
                                 'adresselinje1_intern_adr' : i['adrlin1'],
                                 'adresselinje2_intern_adr': i['adrlin2'],
                                 'poststednr_intern_adr': i['postnr'],
                                 'poststednavn_intern_adr': i['adrlin3'],
                                 'landnavn_intern_adr': i['adresseland'],
                                 'adrtypekode_alternativ_adr' : '',#i['adrtypekode_alternativ_adr'],
                                 'adresselinje1_alternativ_adr': '',#i['adrlin1_besok'],
                                 'adresselinje2_alternativ_adr': '',#i['adrlin2_besok'],
                                 'poststednr_alternativ_adr': '',#poststednr_alternativ_adr,
                                 'poststednavn_alternativ_adr' : '',#i['poststednavn_alternativ_adr'],
                                 'landnavn_alternativ_adr': '',#i['adresseland_besok']
                                 })
    
        return self.fs_data
    
    def get_authoritative_ou(self):
        authoritative_ou=[]
        
        import codecs
        logger.info("Reading authoritative OU file %s" % self.ou_file)
        fileObj = codecs.open( self.ou_file, "r", "utf-8" )
        for line in fileObj:
            line = line.encode('iso-8859-1')
            if line and not line.startswith("#"):
                faknr,fakultet,instnr,institutt,avdnr,avdeling=line.split(",")
                faknr=faknr.strip("\"")
                fakultet=fakultet.strip("\"")
                instnr=instnr.strip("\"")
                avdnr=avdnr.strip("\"")
                avdeling=avdeling.rstrip("\n").strip("\"")
                #print "avdeling=%s" % avdeling

                if ((avdnr[4:6] == '00') and(instnr[2:4] == '00')):
                    # we have a fakulty, must reference the uit institution
                    faknr_org_under = '00'
                    instituttnr_org_under = '00'
                    gruppenr_org_under= '00'
                    
                if((avdnr[4:6] != '00') and (instnr != '00')):
                    # we have a group, must reference the institute
                    faknr_org_under= faknr
                    instituttnr_org_under = instnr[2:4]
                    gruppenr_org_under='00'

                if(((instnr[2:4] == '00')and(avdnr[4:6] != '00'))or((instnr[2:4] != '00')and(avdnr[4:6] =='00'))):
                    # we have either a institute or a group directly under a faculty. in either case
                    # it should reference he faculty
                    faknr_org_under = faknr
                    instituttnr_org_under = '00'
                    gruppenr_org_under = '00'
                
                authoritative_ou.append({
                                 'temp_inst_nr' : avdnr,
                                 'fakultetnr' : faknr,
                                 'instituttnr' : instnr[2:4],
                                 'gruppenr' : avdnr[4:6],
                                 'stednavn' : avdeling,
                                 'forkstednavn' : '',#i['stedkortnavn'],
                                 'display_name' : avdeling,
                                 'akronym' : '',#i['stedakronym'],
                                 'stedkortnavn_bokmal' : '',#i['stedkortnavn'],
                                 'stedkortnavn_nynorsk' : '',#i['stednavn_nynorsk'],
                                 'stedkortnavn_engelsk' : '',#i['stednavn_engelsk'],
                                 'stedlangnavn_bokmal': avdeling,#i['stednavn_bokmal'],
                                 'stedlangnavn_nynorsk': '',#i['stednavn_nynorsk'],
                                 'stedlangnavn_engelsk' : '',#i['stednavn_engelsk'],
                                 'fakultetnr_for_org_sted' : faknr_org_under,
                                 'instituttnr_for_org_sted': instituttnr_org_under,
                                 'gruppenr_for_org_sted' : gruppenr_org_under,
                                 'opprettetmerke_for_oppf_i_kat' : 'X', #i['opprettetmerke_for_oppf_i_kat'],
                                 'telefonnr' :"77644000",
                                 'innvalgnr' : '0',#'%s%s'%(i['telefonlandnr'],i['telefonretnnr']),
                                 'linjenr' : '0',#i['telefonnr'],
                                 'stedpostboks' : '',#i['stedpostboks'],
                                 'adrtypekode_besok_adr': 'INT',#i['adrtypekode_besok_adr'],
                                 'adresselinje1_besok_adr' :'',#:i['adrlin1'],
                                 'adresselinje2_besok_adr': '',#i['adrlin2'],
                                 'poststednr_besok_adr' : '',#poststednr_besok_adr,
                                 'poststednavn_besok_adr' : '',#'%s %s %s' % (i['adrlin1_besok'],i['adrlin2_besok'],i['adrlin3_besok']),
                                 'landnavn_besok_adr' : '',#i['adresseland_besok'],
                                 'adrtypekode_intern_adr': '',#i['adrtypekode_intern_adr'],
                                 'adresselinje1_intern_adr' : 'Universitetet i Tromsø',
                                 'adresselinje2_intern_adr': avdeling,
                                 'poststednr_intern_adr': '9037',
                                 'poststednavn_intern_adr': 'Tromsø',
                                 'landnavn_intern_adr': '',#i['adresseland'],
                                 'adrtypekode_alternativ_adr' : '',#i['adrtypekode_alternativ_adr'],
                                 'adresselinje1_alternativ_adr': '',#i['adrlin1_besok'],
                                 'adresselinje2_alternativ_adr': '',#i['adrlin2_besok'],
                                 'poststednr_alternativ_adr': '',#poststednr_alternativ_adr,
                                 'poststednavn_alternativ_adr' : '',#i['poststednavn_alternativ_adr'],
                                 'landnavn_alternativ_adr': '',#i['adresseland_besok']
                                 })
        fileObj.close()
        return authoritative_ou

        
    def generate_ou(self,fs_ou,auth_ou):
        result_ou=[]
        for a_ou in auth_ou:
            a_ou_check=False
            for f_ou in fs_ou:
                if a_ou['temp_inst_nr']==f_ou['temp_inst_nr']:
                    # Match. generate result data
                    f_ou['stedlangnavn_bokmal'] = a_ou['stedlangnavn_bokmal']
                    f_ou['display_name'] = a_ou['display_name']
                    f_ou['adresselinje1_intern_adr'] = a_ou['adresselinje1_intern_adr']
                    f_ou['adresselinje2_intern_adr'] = a_ou['adresselinje2_intern_adr'] 
                    #print "%s in FS" % f_ou['temp_inst_nr']
                    result_ou.append(f_ou)
                    a_ou_check=True
                    break
            if a_ou_check==False:
                # The OU from the authoritative file does not exist in FS. Add the authoritative OU data to the list
                logger.warn("Not in FS: %s - %s" % (a_ou['temp_inst_nr'],a_ou['stedlangnavn_bokmal']))
                result_ou.append(a_ou)
        return result_ou


    def print_ou(self,final_ou,out_file):
        logger.info("Wrinting OU file %s" % out_file)
        stream = AtomicFileWriter(out_file, "w")
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level = 2,
                                       data_mode = True,
                                       input_encoding = "latin1")
        writer.startDocument(encoding = "iso8859-1")
        writer.startElement("data")
        for ou in final_ou:
            # lets check if this is an OU that is not to be presented in BAS
            if self.remove_surp_ou(ou['temp_inst_nr'])==1:
                del ou['temp_inst_nr']
                writer.emptyElement("sted",ou)
        writer.endElement("data")
        writer.endDocument()
        stream.close()

        
def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'o:O:',['ou_source=','Out_file='])
    except getopt.GetoptError:
        usage()
        
    ou_file = default_input_file
    out_file = default_output_file
    for opt,val in opts:
        if opt in ('-o','--ou_source'):
            ou_file = val
        if opt in ('-O','-Out_file'):
            out_file = val

            
    # initiate the ou instance
    my_ou = ou(ou_file)
    # get ou from FS.
    fs_ou = my_ou.get_fs_ou()
    # get OU from the authoritative file
    auth_ou = my_ou.get_authoritative_ou()
    # generate the final ou list based on the authoritative ou list and data from FS
    final_ou = my_ou.generate_ou(fs_ou,auth_ou)
    # print the ou xml file
    my_ou.print_ou(final_ou,out_file)


def usage():
    print """Usage: python new_generate_OU.py -o ou_file -O out_file.xml | -l
    
    -o | --ou_source - ou data source file
    -O | --Out_file - indicates file to write result xml"""
    sys.exit(0)

if __name__ == '__main__':
    main()
