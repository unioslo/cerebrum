#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
# This script reads data exported from our HR system PAGA.
# It is a simple CSV file.
#
from __future__ import unicode_literals

import getopt
import sys
import os
import mx.DateTime
import datetime
import time

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.extlib import xmlprinter

from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError

progname = __file__.split("/")[-1]
__doc__="""Usage: %s [options]
    Parse datafile from PAGA. 

    options:
    -o | --out_file   : alternative xml file to store data in
    -p | --paga-file  : file to read from
    -s | --show       : give fnr,and person info is shown
    -h | --help       : show this
    --logger-name     : name of logger to use
    --logger-level    : loglevel to use
    
    """ % progname




#Define defaults
TODAY=mx.DateTime.today().strftime("%Y-%m-%d")
CHARSEP=';'
dumpdir_employees = os.path.join(cereconf.DUMPDIR, "employees")
dumpdir_paga = os.path.join(cereconf.DUMPDIR, "paga")
default_employee_file = 'paga_persons_%s.xml' % (TODAY,)
default_paga_file = 'uit_paga_last.csv'

# some common vars
db = Factory.get('Database')()
logger = Factory.get_logger("cronjob")

# define field positions in PAGA csv-data
# First line in PAGA csv file contains field names. Use them.
KEY_AKSJONKODE='A.kode'.encode('ISO-8859-1')
KEY_AKSJONDATO='A.dato'.encode('ISO-8859-1')
KEY_ANSATTNR='Ansattnr'.encode('ISO-8859-1')
KEY_HJEMSTED_ADRESSE='Adresse'.encode('ISO-8859-1')
KEY_HJEMSTED_POSTSTED='Poststed'.encode('ISO-8859-1')
KEY_HJEMSTED_POSTNR='Postnr'.encode('ISO-8859-1')
KEY_AV='Av'.encode('ISO-8859-1')
KEY_BRUKERNAVN= 'Brukernavn'.encode('ISO-8859-1')
KEY_DBHKAT='DBH stillingskategori'.encode('ISO-8859-1')
KEY_DATOFRA='F.lønnsdag'.encode('ISO-8859-1')
KEY_DATOTIL='S.lønnsdag'.encode('ISO-8859-1')
KEY_EPOST='E-postadresse'.encode('ISO-8859-1')
KEY_ETTERNAVN='Etternavn'.encode('ISO-8859-1')
KEY_FNR='Fødselsnummer'.encode('ISO-8859-1')
KEY_FORNAVN= 'Fornavn'.encode('ISO-8859-1')
KEY_HOVEDARBFORH='HovedAF'.encode('ISO-8859-1')
KEY_KOSTNADSTED='K.sted'.encode('ISO-8859-1')
KEY_NR='Nr'.encode('ISO-8859-1')
KEY_ORGSTED='Org.nr.'.encode('ISO-8859-1')
KEY_PERMISJONKODE='P.kode'.encode('ISO-8859-1')
KEY_STANDEL='St.andel'.encode('ISO-8859-1')
KEY_STILLKODE='St. kode'.encode('ISO-8859-1')
KEY_TITTEL='St.bet'.encode('ISO-8859-1')
KEY_TJFORH='Tj.forh.'.encode('ISO-8859-1')
KEY_UNIKAT='Univkat'.encode('ISO-8859-1')
KEY_UITKAT='UITkat'.encode('ISO-8859-1')
KEY_KJONN='Kjønn'.encode("iso-8859-1")
KEY_FODSELSDATO='Fødselsdato'.encode('ISO-8859-1')
KEY_LOKASJON='Lokasjon'.encode('ISO-8859-1')

def parse_paga_csv(pagafile):
    import csv
    persons=dict()
    tilsettinger=dict()
    permisjoner=dict()
    dupes=list()
    logger.info ("Reading %s",(pagafile,))
    print CHARSEP
    for detail in csv.DictReader(open(pagafile,'r'),delimiter=str(CHARSEP)):
        ssn=detail[KEY_FNR]     
        logger.debug("processing:%s" % ssn)
        # some checks
        if detail[KEY_TJFORH] == 'H':
            #these persons are 'honorar' persons. Skip them entirely
            logger.warn("skipping honorar: %s" % ssn)
            continue
            
        if detail[KEY_PERMISJONKODE] not in cereconf.PAGA_PERMKODER_ALLOWED:
            logger.warn("Dropping detail for %s, P.Kode=%s" % \
                (ssn,detail[KEY_PERMISJONKODE]))
            permisjoner[ssn]=detail[KEY_PERMISJONKODE]
            continue
        elif detail[KEY_AKSJONKODE]:
            logger.warn("Detail contains A.Kode for %s, A.Kode=%s" % \
                (ssn,detail[KEY_AKSJONKODE]))
        
        person_data={
            'ansattnr': detail[KEY_ANSATTNR],
            'fornavn': detail[KEY_FORNAVN],
            'etternavn': detail[KEY_ETTERNAVN],
            'brukernavn': detail[KEY_BRUKERNAVN],
            'epost': detail[KEY_EPOST],
            'brukernavn': detail[KEY_BRUKERNAVN], 
            'kjonn': detail[KEY_KJONN], 
            'fodselsdato': detail[KEY_FODSELSDATO],
            'adresse' : detail[KEY_HJEMSTED_ADRESSE],
            'poststed': detail[KEY_HJEMSTED_POSTSTED],
            'postnr' : detail[KEY_HJEMSTED_POSTNR],
            'lokasjon' : detail[KEY_LOKASJON]
        }
        tilskey="%s:%s"  % (detail[KEY_NR], detail[KEY_AV])
        tils_data={
            'stillingskode': detail[KEY_STILLKODE],
            'tittel':detail[KEY_TITTEL],
            'stillingsandel': detail[KEY_STANDEL],
            'kategori': detail[KEY_UITKAT],
            'hovedkategori': detail[KEY_UNIKAT],
            'tjenesteforhold': detail[KEY_TJFORH],            
            'dato_fra':detail[KEY_DATOFRA],
            'dato_til':detail[KEY_DATOTIL],
            'dbh_kat':detail[KEY_DBHKAT],
            'hovedarbeidsforhold':detail[KEY_HOVEDARBFORH],
            'forhold_nr':detail[KEY_NR],
            'forhold_av':detail[KEY_AV],
            'permisjonskode':detail[KEY_PERMISJONKODE]
        }
        stedkode=detail[KEY_ORGSTED]

        if persons.get(ssn,None):
            dupes.append(ssn)
            #logger.debug("ssn:%s already exists in dataset. check if new data has hovedarbeidsforhold == H" % ssn)
            #logger.debug("tilsdata:%s" % tils_data)hovedarbeidsforhold
            if tils_data['hovedarbeidsforhold'] == 'H': # and persons[ssn]['hovedarbeidsforhold'] != 'H':
                logger.debug("person %s already exists in dataset, but this instance has hovedarbeidsforhold == H. Update person data" % ssn)
                #logger.debug("old_data:%s" % persons[ssn])

                # DEBUG: how many changes do we get when updating person info to collect data from 'hovedarbeidsforhold' ? 
                #diffkeys = [k for k in person_data if person_data[k] != persons[ssn][k]]
                #for k in diffkeys:
                #    print k, '### :', person_data[k], '->', persons[ssn][k], ':ssn:', ssn


                persons[ssn]=person_data
                #logger.debug("new_data:%s" % persons[ssn])
        else:
            persons[ssn]=person_data

        #logger.debug('Person %s' % person_data)
        #tilsettinger we have seen before
        current=tilsettinger.get(ssn,dict())
        
        if not current:
            # sted not seen before, insert
            tilsettinger[ssn]={stedkode: tils_data}
            #logger.debug("ssn:%s has not been mapped to stedkode:%s before" %(ssn,stedkode))
        else:
            tmp=current.get(stedkode)
            if tmp:
                logger.warn("Several tilsettinger to same place for %s" % (ssn))
                #
                #several tilsettinger to same place. Decide which to keep.
                #
                # - Get affiliation where hovedarbeidsforhold == H and where dato_til is in the future
                #   - if the above line fails try the following:
                #     get affiliation where dato_fra is in the past and where dato_fra is later than dato_til in
                #     already registered affiliation and where dato_til is in the future
                #     - if the above test fails,try the following
                #          get affiliation where permisjonskode is being changed from somevalue to 0 (zero)
                #
                
                insert_person = False
                
                if tils_data['dato_til'] == '':
                    tils_dato_til_konverted = '20700101'
                else:
                    tils_dato_til_konverted = "%s%s%s" %(tils_data['dato_til'][0:4],tils_data['dato_til'][5:7],tils_data['dato_til'][8:11])

                    
                if tmp['dato_til'] == '':
                    tmp_dato_til_konverted = '20700101'
                else:
                    tmp_dato_til_konverted = "%s%s%s" % (tmp['dato_til'][0:4],tmp['dato_til'][5:7],tmp['dato_til'][8:11])


                    
                #konverted to a format easily tested on

                tils_dato_fra_konverted = "%s%s%s" %(tils_data['dato_fra'][0:4],tils_data['dato_fra'][5:7],tils_data['dato_fra'][8:11])
                tmp_dato_fra_konverted = "%s%s%s" % (tmp['dato_fra'][0:4],tmp['dato_fra'][5:7],tmp['dato_fra'][8:11])
                
                TODAY_konverted = "%s%s%s" % (TODAY[0:4],TODAY[5:7],TODAY[8:11])
                #print "tmp not converted:%s" % tmp['dato_til']
                #print "tmp_konverted =%s" % tmp_dato_til_konverted
                #print "dato_til etter kovertering:'%s'" % dato_til_konverted
                #print "TODAY etter kovertering:'%s'" % TODAY_konverted

                #print "hovedarbeidsforhold:%s, tils_data['dato_til']:%s, TODAY:%s" %(tils_data['hovedarbeidsforhold'],tils_data['dato_til'], TODAY)
                #print "KONVERTED: hovedarbeidsforhold:%s, tils_data['dato_til']:%s, TODAY:%s" %(tils_data['hovedarbeidsforhold'],tils_dato_til_konverted, TODAY_konverted)
                if((tils_data['hovedarbeidsforhold'] == 'H') and (int(tils_dato_til_konverted) > int(TODAY_konverted))):
                    logger.debug("on_hovedarbeidsforhold: inserting person:%s" % tils_data)
                    insert_person = True

                elif((tmp['hovedarbeidsforhold'] == 'H') and (int(tmp_dato_til_konverted) < int(TODAY_konverted))):
                    if((int(tils_dato_fra_konverted) < int(TODAY_konverted)) and (int(tils_dato_fra_konverted)) >= int(tmp_dato_til_konverted) and (int(tils_dato_til_konverted) > int(TODAY_konverted))):
                        logger.error("generating person object with ssn:%s ,based on dato_fra/dato_til. Verify this"% ssn)
                        insert_person = True

#                 if((tils_data['hovedarbeidsforhold'] == 'H') and (til_data['dato_til'] > TODAY)):
#                     logger.debug("on_hovedarbeidsforhold: inserting person:%s" % tils_data)
#                     insert_person = True

#                 elif((tmp['hovedarbeidsforhold'] =='H') and (tmp['dato_til'] < TODAY)):
#                     if((tils_data['dato_fra'] < TODAY) and (tils_data['dato_fra'] >= tmp['dato_til']) and(tils_data['dato_til'] > TODAY)):
#                         logger.error("generating person object based on dato_fra/dato_til. Verify this")
#                         insert_person = True
                    
                elif(tmp['permisjonskode'] != '0') and (tils_data['permisjonskode'] == '0'):
                     logger.debug("on_permisjonskode: inserting person:%s" % tils_data)
                     insert_person = True
                   
                if(insert_person == True):
                    tilsettinger[ssn][stedkode]=tils_data
                    #logger.debug("INSERTING:%s" % tils_data)

                else:
                    logger.info("Skipped aff at same place for %s, data: %s" % (ssn,tils_data))
            else:
                logger.info("adding tilsetting for %s" % (ssn))
                tilsettinger[ssn][stedkode]=tils_data
                
    return persons,tilsettinger,permisjoner

class person_xml:

    def __init__(self,out_file):
        self.out_file=out_file


    def create(self,persons,affiliations,permisjoner):
        """ Build a xml that import_lt should process:
        <person tittel_personlig=""
        fornavn=""
        etternavn=""
        fnr=""
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

        #stream = AtomicFileWriter(self.out_file, "w")
        stream = open(self.out_file, "wb")
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level = 2,
                                       data_mode = True,
                                       input_encoding = "latin1")
        writer.startDocument(encoding = "iso8859-1")
        writer.startElement("data")

        for fnr, person_data in persons.iteritems():
            affs = affiliations.get(fnr)
            aff_keys=affs.keys()
            person_data['fnr']=fnr

            temp_tils=list()
            for sted in aff_keys:
                aff = affs.get(sted)
                ## use . instead of , as decimal char.
                st_andel=aff.get('stillingsandel','').replace(',','.')
                if st_andel=='':
                    logger.error("ST.andel for fnr %s er tom",fnr)
                tils_dict = {'hovedkategori' : aff['hovedkategori'],
                             'stillingskode' : aff['stillingskode'],
                             'tittel' : aff['tittel'],
                             'stillingsandel' : st_andel,
                             'fakultetnr_utgift' : sted[0:2],
                             'instituttnr_utgift' : sted[2:4],
                             'gruppenr_utgift' : sted[4:6],
                             'dato_fra' : aff['dato_fra'],
                             'dato_til' : aff['dato_til'],
                             'dbh_kat' : aff['dbh_kat'],
                             'hovedarbeidsforhold': aff['hovedarbeidsforhold'],
                             'tjenesteforhold': aff['tjenesteforhold'],
                          }
                temp_tils.append(tils_dict)
            writer.startElement("person",person_data)
            for tils in temp_tils:
                writer.emptyElement("tils",tils)
            writer.endElement("person")
        writer.endElement("data")
        writer.endDocument()
        stream.close()


def main():
       
    out_file = os.path.join(dumpdir_employees, default_employee_file)
    paga_file = os.path.join(dumpdir_paga, default_paga_file)
    show_person = None
    try:
        opts,args = getopt.getopt(sys.argv[1:],'hp:o:s:',
            ['paga-file=','out-file=','help','show='])
    except getopt.GetoptError,m:
        usage(1,m)

    for opt,val in opts:
        if opt in ('-o','--out-file'):
            out_file = val
        if opt in ('-p','--paga-file'):
            paga_file = val
        if opt in ('-s','--show'):
            show_person = val
        if opt in ('-h','--help'):
            usage()
    
    pers,tils,perms = parse_paga_csv(paga_file)
    logger.debug("File parsed. Got %d persons" % (len(pers),))

    if show_person is not None:
        if pers.has_key(show_person):
            print "*** Personinfo ***"
            print pers[show_person]
            print ""
        if tils.has_key(show_person):
            print "*** Tilsettingsinfo ***"
            print tils[show_person]
            print ""
        if perms.has_key(show_person):
            print "*** Permisjonsinfo ***"
            print perms[show_person]
            print ""
    else:
        xml=person_xml(out_file)
        xml.create(pers,tils,perms)
        sys.exit(0)
    
def usage(exit_code=0,msg=None):
    if msg: print msg
    print __doc__
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
