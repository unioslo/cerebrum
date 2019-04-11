#!/bin/env python
# -- coding: utf-8 --
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
# UiT specific extension to Cerebrum
# This script creates an xml file that our portal project reads.
#

# kbj005 2015.02.12: Copied from Leetah.

import getopt
import sys
import os
import mx.DateTime
import csv
import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.modules.no.uit.PagaDataParser import PagaDataParserClass
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError

db  = Factory.get('Database')()
ou = Factory.get('OU')(db)
p  = Factory.get('Person')(db)
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
logger = Factory.get_logger("console")

TODAY = mx.DateTime.today().strftime("%Y%m%d")   

# Stedkode CSV Defaults
default_mapping_file = os.path.join(cereconf.CB_PREFIX, "var", "source", "bas_portal_mapping.csv")
STEDKODE_FROM = 0
STEDKODE_TO = 1

# Person file
default_employees_file = os.path.join(cereconf.CB_PREFIX, "var", "dumps","employees", "paga_persons_%s.xml" % (mx.DateTime.today().strftime("%Y-%m-%d")))
aff_to_stilling_map = {}



def scan_person_affs(person):
    global aff_to_stilling_map


    fnr = person['fnr']
    
    for t in person.get('tils', ()):
        earliest = mx.DateTime.DateFrom(t.get("dato_fra")) - mx.DateTime.DateTimeDelta(cereconf.PAGA_EARLYDAYS)
        dato_fra = mx.DateTime.DateFrom(t.get("dato_fra"))
        dato_til = mx.DateTime.DateFrom(t.get("dato_til"))

        if (mx.DateTime.today() < earliest) or (dato_til and (mx.DateTime.today() > dato_til)):
            logger.warn("Not active, earliest: %s, dato_fra: %s, dato_til:%s" % (earliest, dato_fra,dato_til))
            continue

        stedkode = "%s%s%s" % (t['fakultetnr_utgift'].zfill(2),
                               t['instituttnr_utgift'].zfill(2),
                               t['gruppenr_utgift'].zfill(2))

        if t['hovedkategori'] == 'TEKN':
            tilknytning = co.affiliation_status_ansatt_tekadm
        elif t['hovedkategori'] == 'ADM':
            tilknytning = co.affiliation_status_ansatt_tekadm
        elif t['hovedkategori'] == 'VIT':
            tilknytning = co.affiliation_status_ansatt_vitenskapelig
        else:
            logger.warning("Unknown hovedkat: %s" % t['hovedkategori'])
            continue

        pros = "%2.2f" % float(t['stillingsandel'])


        # Looking up stillingstittel and dbh_kat from DB
        stillingskode = t['stillingskode']

        sql = "SELECT stillingstittel || ':::'  || stillingstype as db_info FROM [:table schema=cerebrum name=person_stillingskoder] WHERE stillingskode=:stillingskode"
        try:
            db_info = db.query_1(sql,{'stillingskode':stillingskode})
        except Errors.TooManyRowsError:
            logger.error("stillingskode %s repeated in person_stedkoder" % stillingskode)
        except Errors.NotFoundError:
            # Default to file info
            logger.error("Stillingskode not found in person_stillingskoder. Defaulting to person file info: %s" % (stillingskode))
            stillingstittel = t['tittel']
            dbh_kat = t['dbh_kat']
        else:
            # Use DB info
            stillingstittel, dbh_kat = db_info.split(':::')

        hovedarbeidsforhold = ''
        if t.has_key('hovedarbeidsforhold'):
            hovedarbeidsforhold = t['hovedarbeidsforhold']
        
        aux_key = (fnr, stedkode, str(tilknytning))
        aux_val = {'stillingskode': stillingskode, 'stillingstittel_paga': t['tittel'], 'stillingstittel': stillingstittel, 'prosent': pros, 'dbh_kat': dbh_kat, 'hovedarbeidsforhold':hovedarbeidsforhold}

        aff_to_stilling_map[aux_key] = aux_val





def load_cache():
    global account2name,owner2account,persons,uname2mail
    global num2const,name_cache_cached,auth_list
    global person2contact,person2campus,person2home_address,person2employeeNumber
    global bas_portal_mapping, ou_stedkode_mapping, pid_fnr_dict, aff_to_stilling_map


    logger.info("Generating mapping dict for ou_id based on stedkode mappings for the portal")

    # Caching stedkode -> ou
    stedkoder = ou.get_stedkoder()
    stedkode_ou_mapping = {}
    ou_stedkode_mapping = {}
    for stedkode in stedkoder:
        ou_stedkode_mapping[stedkode['ou_id']] = str(stedkode['fakultet']).zfill(2) + str(stedkode['institutt']).zfill(2) + str(stedkode['avdeling']).zfill(2)
        stedkode_ou_mapping[str(stedkode['fakultet']).zfill(2) + str(stedkode['institutt']).zfill(2) + str(stedkode['avdeling']).zfill(2)] = stedkode['ou_id']

    # Creating ou map
    mappings = csv.reader(open(default_mapping_file,'r'), delimiter=';')
    bas_portal_mapping = {}
    for mapping in mappings:
        stedkode_from = mapping[STEDKODE_FROM].strip()
        stedkode_to = mapping[STEDKODE_TO].strip()
        try:
            try:
                ou_from = stedkode_ou_mapping[stedkode_from]
            except KeyError:
                logger.error("Mapping FROM failed: %s %s" % (stedkode_from, stedkode_to))
                raise KeyError
            #
            #if stedkode_to == 'SKIP':
            #    ou_to = stedkode_to
            #else:
            #    try:
            #       ou_to = stedkode_ou_mapping[stedkode_to]
            #    except KeyError:
            #       logger.error("Mapping TO failed: %s %s" % (stedkode_from, stedkode_to))
            #       raise KeyError
            
            bas_portal_mapping[ou_from] = stedkode_to
            logger.info('Mapping OK: %s to %s' % (stedkode_from, stedkode_to))
        except KeyError:
            pass


    logger.info('Generating dict of PAGA persons affiliations and their stillingskoder, dbh_kat, etc')
    PagaDataParserClass(default_employees_file, scan_person_affs)

    logger.info('Getting pid -> fnr dict')
    pid_fnr_dict = p.getdict_fodselsnr()

    logger.info("Retrieving persons and their birth_dates")
    persons =dict()
    for pers in p.list_persons():
        persons[pers['person_id']]=pers['birth_date']

    logger.info("Retrieving person names")
    name_cache_cached = p.getdict_persons_names(source_system=co.system_cached,\
                                                name_types=(co.name_first, \
                                                            co.name_last))

    logger.info("Retrieving account names")
    account2name=dict()
    for a in ac.list_names(co.account_namespace):
        account2name[a['entity_id']]=a['entity_name']

    logger.info("Retrieving account emailaddrs")
    uname2mail=ac.getdict_uname2mailaddr()

    logger.info("Retrieving account owners")
    owner2account=dict()
    # filter out unwanted affiliations (only list those we want to export to oid)
    valid_affs = (co.affiliation_manuell,co.affiliation_ansatt,co.affiliation_tilknyttet,co.affiliation_student)
    for a in ac.list_accounts_by_type(affiliation=valid_affs,filter_expired=False, primary_only=True):
        owner2account[a['person_id']]=a['account_id']

    logger.info("Retrieving auth strings")
    auth_list=dict()
    auth_type=co.auth_type_md5_b64
    for auth in ac.list_account_authentication(auth_type=auth_type):
        auth_list[auth['account_id']]=auth['auth_data']

    logger.info("Retrieving contact info (phonenrs and such)")
    person2contact=dict()
    for c in p.list_contact_info(entity_type=co.entity_person, source_system=(co.system_tlf, co.system_fs)):
        person2contact.setdefault(c['entity_id'], list()).append(c)

    # get person campus location
    logger.info("Retreiving person campus location")
    person2campus=dict()

    for c in p.list_entity_addresses(entity_type=co.entity_person,source_system=co.system_paga,address_type=co.address_location):
        person2campus.setdefault(c['entity_id'], list()).append(c)

    # get person home address
    person2home_address = dict()
    for c in p.list_entity_addresses(entity_type=co.entity_person,source_system=co.system_paga,address_type=co.address_post_private):
        person2home_address.setdefault(c['entity_id'], list()).append(c)

    # get person employee number
    person2employeeNumber = dict()
    for c in p.list_external_ids(source_system=co.system_paga,id_type=co.externalid_paga_ansattnr,entity_type=co.entity_person):
        person2employeeNumber.setdefault(c['entity_id'],list()).append(c)

    logger.info("Start get constants")
    num2const=dict()
    for c in dir(co):
        tmp = getattr(co, c)
        if isinstance(tmp, _CerebrumCode):
            num2const[int(tmp)] = tmp

    ou_cache=dict()
    logger.info("Cache finished")

def load_cb_data():
    global export_attrs,person_affs
    logger.info("Listing affiliations")
    export_attrs=dict()
    person_affs=dict()
    ou_cache=dict()

    skip_source = []
    skip_source.append(co.system_lt)
    skip_source.append(co.system_flyt)
    #skip_source.append(co.system_hitos)

    #print aff_to_stilling_map
    
    for aff in p.list_affiliations():

        # simple filtering
        aff_status_filter=(co.affiliation_status_student_tilbud,co.affiliation_manuell_gjest,co.affiliation_manuell_gjest_u_konto,co.affiliation_status_ansatt_sito)
        if aff['status'] in aff_status_filter:
            continue

        if aff['source_system'] in skip_source:
            logger.warn('Skipped affiliation because it originated from unwanted source system %s' % aff)
            continue

        # Needs to keep original ou id in order to be able to look up persons BAS specific affiliation/stillingskode
        #original_ou_id = ou_id = aff['ou_id']
        #
        # Do mapping to "PORTAL specific" ou
        #try:
        #    ou_id_ = bas_portal_mapping[ou_id]
        #
        #    if ou_id_ == 'SKIP':
        #        logger.info('Skipped affiliation to ou=%s due to bas to portal mapping rule saying to do so' % (ou_id))
        #        continue
        #    
        #    logger.info('Mapped %s to %s' % (ou_id, ou_id_))
        #    ou_id = ou_id_
        #except KeyError:
        #    pass

        ou_id = aff['ou_id']
        
        last_date=aff['last_date'].strftime("%Y-%m-%d")
        
        if not ou_cache.get(ou_id,None):
            ou.clear()
            
            try:
                ou.find(ou_id)
            except EntityExpiredError:
                logger.warn('Expired ou (%s) for person: %s' % (aff['ou_id'], aff['person_id']))
                continue
            except Errors.NotFoundError:
                # ou withouth stedkode, it is not to be included in the oid export.
                logger.warn('ou: %s does not have stedkode. Removed from oid export' % ou_id)
                continue
            
            ou.clear()
            ou.find(ou_id)
            ou_name = ou.get_name_with_language(co.ou_name, co.language_nb, default='')

            ou.clear()
            ou.find(ou_id)
            sko_sted="%02d%02d%02d" % (ou.fakultet, ou.institutt,
                                       ou.avdeling)

            if bas_portal_mapping.has_key(ou_id):

                if bas_portal_mapping[ou_id] == 'SKIP':
                    logger.info('Skipped affiliation to ou=%s due to bas to portal mapping rule saying to do so' % (sko))
                    continue

                logger.info('Mapped %s to %s' % (ou,
                                                 bas_portal_mapping[ou_id]))
                sko_sted = bas_portal_mapping[ou_id]
                ou_name = "%s - MAPPED" % (ou_name)

            ou_cache[ou_id]=(ou_name,sko_sted)
            
        sko_name,sko_sted=ou_cache[ou_id]

        p_id = aff['person_id']
        aff_stat=num2const[aff['status']]
        
        # account
        acc_id=owner2account.get(p_id,None)
        acc_name=account2name.get(acc_id,None)
        if not acc_name:
            logger.warn("Skipping personID=%s, no account found" % p_id)
            continue

        namelist = name_cache_cached.get(p_id,None)
        
        first_name=last_name=worktitle=""
        if namelist:
            first_name = namelist.get(int(co.name_first),"")
            last_name = namelist.get(int(co.name_last),"")
        if not acc_name:
            logger.warn("No account for %s %s (fnr=%s)(pid=%s)" % \
                (first_name, last_name,pnr,p_id))
            acc_name=""


        try:
            original_stedkode = ou_stedkode_mapping[ou_id]
            aux_key = (pid_fnr_dict[p_id], original_stedkode, str(aff_stat))
            tils_info = aff_to_stilling_map[aux_key]
        except KeyError:
            affstr = "%s::%s::%s::%s::::::::::" % (str(aff_stat),sko_sted,sko_name,last_date)
        else:
            affstr = "%s::%s::%s::%s::%s::%s::%s::%s::%s" % (str(aff_stat), sko_sted, sko_name, last_date, tils_info['stillingskode'], tils_info['stillingstittel_paga'], tils_info['prosent'], tils_info['dbh_kat'], tils_info['hovedarbeidsforhold'])


        
        
        person_affs.setdefault(p_id, list()).append(affstr)
        #auth
        auth_str=auth_list.get(acc_id,"")
        #contacts
        contacts = person2contact.get(p_id,None)
        # campus location
        campus = person2campus.get(p_id,None)
        #birth date
        birth_date=persons.get(p_id,"").Format('%d-%m-%Y')
        # home address
        home_address = person2home_address.get(p_id,None)
        #email 
        email=uname2mail.get(acc_name,"")
        # employee number
        employee_number = person2employeeNumber.get(p_id,None)

        attrs = dict()
        for key,val in (('uname',acc_name),
                        ('given',first_name),
                        ('sn',last_name),
                        ('birth',birth_date),
                        #('worktitle',worktitle),
                        ('contacts',contacts),
                        ('campus', campus),
                        ('home_address', home_address),
                        ('auth_str',auth_str),
                        ('employee_number',employee_number),
                        ('email',email)
                        ):
            attrs[key]=val
        if not export_attrs.get(acc_name,None):
            export_attrs[p_id]=attrs
        else:
            logger.error("Why are we here? %s" % attrs)
    return export_attrs,person_affs


def build_csv(outfile):
    
    if not outfile.endswith('.csv'):
        outfile=outfile+'.csv'

    fh = file(outfile,'w')

    for person_id,attrs in export_attrs.items():
        
        affs = person_affs.get(person_id,None)
        affname=sko=sko_name=last_date=affkode=affstatus=""
        for aff in affs:
            affname,sko,sko_name,last_date = aff.split('::')
            affkode,affstatus=affname.split('/')
        
        sep=""
        for txt in (attrs['sn'],attrs['given'],attrs['birth'],attrs['uname'],attrs['home_address'],
                    attrs['email'],affkode,sko,sko_name):
            fh.write("%s%s" % (sep,txt))
            sep=";"
        fh.write('\n')
    fh.close()

def build_xml(outfile):
    logger.info("Start building export, writing to %s" % outfile)
    fh = file(outfile,'w')
    xml = xmlprinter(fh,indent_level=2,data_mode=True,input_encoding='ISO-8859-1')
    xml.startDocument(encoding='utf-8')
    xml.startElement('data')
    xml.startElement('properties')
    xml.dataElement('exportdate', str(mx.DateTime.now()))
    xml.endElement('properties')

    for person_id in export_attrs:
        attrs=export_attrs[person_id]
        xml_attr={'given': attrs['given'],
                  'sn': attrs['sn'],
                  'birth': attrs['birth'],
                  }

        # get person employee number
        employee_number = attrs['employee_number']
        if employee_number:
            for c in employee_number:
                ansattnr =  str(c['external_id'])
                logger.info("c.str:%s" % ansattnr)
                if ansattnr != None:
                    logger.info("collected employee number:%s" % ansattnr)
                    xml_attr['employee_number'] = ansattnr

        
        # get home address
        home_addressinfo = attrs['home_address']
        if home_addressinfo:
            for c in home_addressinfo:
                home_address = c['address_text']
                home_postalnumber = str(c['postal_number'])
                home_city = c['city']
                
                if home_address != None:
                    home_address = home_address
                    xml_attr['home_address'] = home_address
                if home_postalnumber != None:
                    xml_attr['home_postal_code'] = home_postalnumber
                if home_city != None:
                    home_city = home_city
                    xml_attr['home_city'] = home_city

        # get campus 
        campusinfo=attrs['campus']
        if campusinfo:            
            for c in campusinfo:
                campus_name = c['address_text']
                xml_attr['campus'] = campus_name

        #if attrs['worktitle']: xml_attr['worktitle'] = attrs['worktitle']
        xml.startElement('person',xml_attr)

        #print "%s - %s - %s - %s" % (attrs['uname'], attrs['auth_str'], attrs['email'],attrs.get('auth_str') or '*')
        
        xml.emptyElement('account', {'username': attrs['uname'], 
                                     'userpassword': 'x',
                                     'email': attrs['email']})
        affs = person_affs.get(person_id)
        if affs:
            xml.startElement('affiliations')
            for aff in affs:
                affname, sko, sko_name, last_date, tils_stillingskode, tils_stillingstittel, tils_prosent, tils_dbh_kat, hovedarbeidsforhold = aff.split('::')
                affkode,affstatus=affname.split('/')
                xml.emptyElement('aff',{'affiliation': affkode,
                                    'status':affstatus,
                                    'stedkode': sko,
                                    'last_date': last_date,
                                    'stillingskode': tils_stillingskode,
                                    'stillingstittel': tils_stillingstittel,
                                    'prosent': tils_prosent,
                                    'dbh_kategori': tils_dbh_kat,
                                    'hovedarbeidsforhold': hovedarbeidsforhold
                                    })
            xml.endElement('affiliations')
        contactinfo=attrs['contacts']
        if contactinfo:
            xml.startElement('contactinfo')
            for c in contactinfo:
                source=str(co.AuthoritativeSystem(c['source_system']))
                ctype=str(co.ContactInfo(c['contact_type']))
                xml.emptyElement('contact', 
                    {'source':source,
                    'type':ctype,
                    'pref':str(c['contact_pref']),
                    'value':c['contact_value']
                    })
            xml.endElement('contactinfo')
        xml.endElement('person')
    xml.endElement('data')
    xml.endDocument()


def usage(exit_code=0,msg=""):
    if msg:
        print msg
    
    print """Usage: [options]
    -h | --help             : show this message
    -o | --outfile=filname  : write result to filename
    --csv | write a csv file instead of a xml file
    --logger-name=loggername: write logs to logtarget loggername
    --logger-level=loglevel : use this loglevel

    """
    sys.exit(exit_code)


def main():

    default_outfile=os.path.join(cereconf.DUMPDIR,"oid","oid_export_%s.xml" % TODAY)
    user_outfile=None
    exportCSV=False

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'o:hx',
                                   ['outfile=', 'csv','help',])
    except getopt.GetoptError:
        usage(1)
    disk_spread = None
    outfile = None
    for opt, val in opts:
        if opt in ['-o', '--outfile']:
            user_outfile = val
        if opt in ['--csv']:
            exportCSV = True
        elif opt in ['-h', '--help']:
            usage(0)

    if exportCSV and not user_outfile:
        usage(1,"Must specify -o or --outfile when using --csv")

    outfile = user_outfile or default_outfile    
    load_cache()
    load_cb_data()
    if exportCSV:
        build_csv(outfile)
    else:
        build_xml(outfile)
    logger.info("Finished")


if __name__=="__main__":
    main()
