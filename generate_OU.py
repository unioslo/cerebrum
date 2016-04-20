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
import os
import time

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Database
from Cerebrum.modules.no.uit.access_FS import FS
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.extlib import xmlprinter

logger = Factory.get_logger("cronjob")

# Default file locations
t = time.localtime()
sourcedir = cereconf.CB_SOURCEDATA_PATH
default_input_files = [os.path.join(sourcedir, 'stedtre-gjeldende.csv'), os.path.join(sourcedir, 'stedtre-eksterne.csv')]

dumpdir = os.path.join(cereconf.DUMPDIR,"ou")
default_output_file = os.path.join(dumpdir,'uit_ou_%d%02d%02d.xml' % (t[0], t[1], t[2]))

class ou:

    def __init__(self,ou_files):
        for file in ou_files:
            if not(os.path.isfile(file)):
                logger.error("ou file:%s does not exist\n" % file)
                sys.exit(1)
        self.ou_files = ou_files
        # BAS
	logger.info("Connecting to BAS DB")
        self.db = Factory.get('Database')()

        # FS 
        user="fsbas"
        service="fsprod"
        logger.info("Connecting to FS db")
        self.fs_db = Database.connect(user=user,service=service,DB_driver='Oracle')
        self.fs = FS(self.fs_db)
        self.fs_data=dict()
	logger.info("Connections ok")

    # lets collect data about all active ou's from FS.
    def get_fs_ou(self):
        logger.info("Reading OU's from FS")
        #ouer = self.fs.ou.GetAlleOUer(institusjonsnr=186)
        ouer = self.fs.ou.GetAktiveOUer(institusjonsnr=186)
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

            if not i['telefonlandnr'] : i['telefonlandnr']="0"
            if not i['telefonretnnr'] : i['telefonretnnr']="0"
            if not i['telefonnr'] : i['telefonnr']="0"
            if not i['adrlin1'] : i['adrlin1'] = 'Universitetet i Tromsø'
            if not i['adrlin2'] : i['adrlin2'] = i['stednavn_bokmal'] 
            if not i['postnr'] : i['postnr'] = '9037'
            if not i['adrlin3'] : i['adrlin3'] = 'Tromsø'

            self.fs_data[temp_inst_nr] = {
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
                }    
        return self.fs_data
    
    def get_authoritative_ou(self):
        authoritative_ou=dict()
        # positions in file
        FAKNR=0
        FAKNAME=1
        INSTNR=2
        INSTNAME=3
        GRPNR=4
        GRPNAME=5
        PORTAL=8
        #NODE_FOR_PERSON=7
        SHORTNAME=6        
        #STED_ORGCARD_NAME=9
        STED_AKRONYM=7
        #LEVEL=11
        #LEVEL_SPES=12
        SORT_KEY=9
        num_fields=11        
        import codecs

        # BEGIN
        for file in self.ou_files:
        
            logger.info("Reading authoritative OU file %s" % file)
            fileObj = codecs.open(file, "r", "iso-8859-1" )
            for line in fileObj:
                line = line.encode('iso-8859-1')
                if line and not line.startswith("#"):
                    items=line.rstrip().split(";")
                    if len(items)!=num_fields:
                        logger.critical("Wrong length: got %d, ekspected %d\nLine=%s" % \
                                        (len(items),num_fields,line.rstrip()))
                        sys.exit(1)
                        
                    faknr=items[FAKNR].strip("\"").strip()
#                    faknr=items[FAKNR].strip()
                    fakultet=items[FAKNAME].strip("\"").strip()
#                    fakultet=items[FAKNAME].strip()
                    instnr=items[INSTNR].strip("\"").strip()
#                    instnr=items[INSTNR].strip()
                    avdnr=items[GRPNR].strip("\"").strip()
#                    avdnr=items[GRPNR].strip()
                    avdeling=items[GRPNAME].strip("\"").strip()
#                    avdeling=items[GRPNAME].strip()
                    shortname=items[SHORTNAME].strip("\"").strip()
#                    shortname=items[SHORTNAME].strip()
                    portal=items[PORTAL].strip("\"").strip()
#                    portal=items[PORTAL].strip()
                    akronym=items[STED_AKRONYM].strip("\"").strip()
#                    akronym=items[STED_AKRONYM].strip()
                    sort_key=items[SORT_KEY].strip("\"").strip()
#                    sort_key=items[SORT_KEY].strip()

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

                    if (((instnr[2:4] == '00')and(avdnr[4:6] != '00')) or
                        ((instnr[2:4] != '00')and(avdnr[4:6] =='00'))):
                        # we have either a institute or a group directly under a 
                        # faculty. in either case it should reference he faculty
                        faknr_org_under = faknr
                        instituttnr_org_under = '00'
                        gruppenr_org_under = '00'


                    katalog_merke='F'
                    if portal.find('JA')>=0:
                        katalog_merke='T'

                    authoritative_ou[avdnr]  = {
                        'fakultetnr' : faknr,
                        'instituttnr' : instnr[2:4],
                        'gruppenr' : avdnr[4:6],
                        'stednavn' : avdeling,
                        'display_name' : avdeling,
                        'forkstednavn' : shortname,
                        'stedlangnavn_bokmal': avdeling,
                        'fakultetnr_for_org_sted' : faknr_org_under,
                        'instituttnr_for_org_sted': instituttnr_org_under,
                        'gruppenr_for_org_sted' : gruppenr_org_under,
                        'adresselinje1_intern_adr' : 'Universitetet i Tromsø',
                        'adresselinje2_intern_adr': avdeling,
                        'poststednr_intern_adr': '9037',
                        'poststednavn_intern_adr': 'Tromsø',
                        'opprettetmerke_for_oppf_i_kat' : katalog_merke,
                        'telefonnr' : "77644000",
                        'sort_key': sort_key
                        }
                    if akronym:
                        authoritative_ou[avdnr]['akronym']=akronym

            fileObj.close()
        # END
        
        return authoritative_ou

        
    def generate_ou(self,fs_ou,auth_ou):
        result_ou=dict()
        for a_ou,a_ou_data in auth_ou.items():            
            f_ou = fs_ou.get(a_ou,None)
            if f_ou:
                # fill in OU data elemnts from FS where we have no
                # eqivalent data in authoritative ou file
                for k,v in f_ou.items():
                    if not a_ou_data.has_key(k):
                        #logger.debug("no reinert data for %s: use '%s' from FS" % (k,v))
                        a_ou_data[k]=v
                del fs_ou[a_ou]
            else:
                logger.warn("OU %s not in FS, only using steddata from Reinert" % a_ou)

            result_ou[a_ou]= a_ou_data

        # log remaining FS ou's as errors
        for f_ou,f_ou_data in fs_ou.items():            
            logger.error("OU in FS not in Reinert file: %s-%s" % (f_ou, f_ou_data['stednavn']))
        return result_ou


    def print_ou(self,final_ou,out_file):
        logger.info("Wrinting OU file %s" % out_file)
        stream = AtomicFileWriter(out_file, "w")
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level = 2,
                                       data_mode = True,
                                       input_encoding = "latin1")
        writer.startDocument(encoding = "iso-8859-1")
        writer.startElement("data")
        for ou,ou_data in final_ou.items():
            writer.emptyElement("sted",ou_data)
        writer.endElement("data")
        writer.endDocument()
        stream.close()

        
def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'o:O:h',['ou_source=','Out_file=','help'])
    except getopt.GetoptError,m:
        usage(1,m)
        
    ou_files = default_input_files
    out_file = default_output_file
    for opt,val in opts:
        if opt in ('-o','--ou_source'):
            ou_files = val.split(',')
        if opt in ('-O','-Out_file'):
            out_file = val
        if opt in ('-h','--help'):
            usage()

            
    # initiate the ou instance
    my_ou = ou(ou_files)
    # get ou from FS.
    fs_ou = my_ou.get_fs_ou()
    # get OU from the authoritative file
    auth_ou = my_ou.get_authoritative_ou()
    # generate the final ou list based on the authoritative ou list and data from FS
    final_ou = my_ou.generate_ou(fs_ou,auth_ou)
    # print the ou xml file
    my_ou.print_ou(final_ou,out_file)


def usage(exit_code=0,msg=None):
    if msg:
        print msg

    print """

    Usage: python new_generate_OU.py -o ou_files -O out_file.xml | -l
    
    -o | --ou_source - ou data source files separated by , (comma)
    -O | --Out_file - indicates file to write result xml"""
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
