#!/bin/env python
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
# UiT specific extension to Cerebrum
# This script creates an xml file that our portal project reads.
#


import getopt
import sys
import os
import mx.DateTime

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.extlib.xmlprinter import xmlprinter

db=Factory.get('Database')()
ou = Factory.get('OU')(db)
p=Factory.get('Person')(db)
co=Factory.get('Constants')(db)
ac=Factory.get('Account')(db)
stedkode = Stedkode(db)
logger=Factory.get_logger("console")


def load_cache():
    global account2name,owner2account,persons,uname2mail
    global num2const, name_cache, auth_list, person2contact

    logger.info("Retreiving persons and their birth_dates")
    persons =dict()
    for pers in p.list_persons():
        persons[pers['person_id']]=pers['birth_date']

    logger.info("Retreiving person names")
    name_cache = p.getdict_persons_names( name_types=(co.name_first, \
        co.name_last,co.name_work_title))

    logger.info("Retreiving account names")
    account2name=dict()
    for a in ac.list_names(co.account_namespace):
        account2name[a['entity_id']]=a['entity_name']

    logger.info("Retreiving account emailaddrs")
    uname2mail=ac.getdict_uname2mailaddr()

    logger.info("Retreiving account owners")
    owner2account=dict()
    for a in ac.list(filter_expired=False):
        owner2account[a['owner_id']]=a['account_id']

    logger.info("Retreiving auth strings")
    auth_list=dict()
    auth_type=co.auth_type_md5_b64
    for auth in ac.list_account_authentication(auth_type=auth_type):
        auth_list[auth['account_id']]=auth['auth_data']

    logger.info("Retreiving contact info (phonenrs and such)")
    person2contact=dict()
    for c in p.list_contact_info(entity_type=co.entity_person):
        person2contact.setdefault(c['entity_id'], list()).append(c)

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
    for aff in p.list_affiliations():

        # simple filtering
        aff_status_filter=(co.affiliation_status_student_tilbud,) 
        if aff['status'] in aff_status_filter:
            continue
        
        ou_id = aff['ou_id']
        last_date=aff['last_date'].strftime("%Y-%m-%d")
        if not ou_cache.get(ou_id,None):
            ou.clear()
            ou.find(ou_id)
            stedkode.clear()
            stedkode.find(ou_id)
            sko="%02d%02d%02d"  % ( stedkode.fakultet,stedkode.institutt,
                stedkode.avdeling)
            ou_cache[ou_id]=(ou.name,sko)
        sko_name,sko=ou_cache[ou_id]

        p_id = aff['person_id']
        aff_stat=num2const[aff['status']]
        
        # account
        acc_id=owner2account.get(p_id,None)
        acc_name=account2name.get(acc_id,None)
        if not acc_name:
            logger.error("Skipping personID=%s, no account found" % p_id)
            continue

        namelist = name_cache.get(p_id,None)
        first_name=last_name=worktitle=""
        if namelist:
            first_name = namelist.get(int(co.name_first),"")
            last_name = namelist.get(int(co.name_last),"")
            worktitle = namelist.get(int(co.name_work_title),"")
        if not acc_name:
            logger.warn("No account for %s %s (fnr=%s)(pid=%s)" % \
                (first_name, last_name,pnr,p_id))
            acc_name=""

        affstr = "%s::%s::%s::%s" % (str(aff_stat),sko,sko_name,last_date)
        person_affs.setdefault(p_id, list()).append(affstr)
        #auth
        auth_str=auth_list.get(acc_id,"")
        #contacts
        contacts = person2contact.get(p_id,None)
        #birth date
        birth_date=persons.get(p_id,"").Format('%d-%m-%Y')
        #email 
        email=uname2mail.get(acc_name,"")

        attrs = dict()
        for key,val in (('uname',acc_name),
                        ('given',first_name),
                        ('sn',last_name),
                        ('birth',birth_date),
                        ('worktitle',worktitle),
                        ('contacts',contacts),
                        ('auth_str',auth_str),
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
        for txt in (attrs['sn'],attrs['given'],attrs['birth'],attrs['uname'],
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
        if attrs['worktitle']: xml_attr['worktitle'] = attrs['worktitle']
        xml.startElement('person')
        for key,val in xml_attr.items():
            xml.dataElement(key,val)
        xml.emptyElement('account', {'username': attrs['uname'], 
                                     'userpassword': attrs['auth_str'],
                                     'email': attrs['email']})
        affs = person_affs.get(person_id)
        if affs:
            xml.startElement('affiliations')
            for aff in affs:
                affname,sko,sko_name,last_date = aff.split('::')
                affkode,affstatus=affname.split('/')
                xml.emptyElement('aff',{'affiliation': affkode,
                                    'status':affstatus,
                                    'stedkode': sko,
                                    'last_date':last_date
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
                    'value':str(c['contact_value'])
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
    default_outfile=os.path.join(cereconf.DUMPDIR,"oid","oid_export_%s.xml" % cereconf._TODAY)
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
