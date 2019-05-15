#!/usr/bin/env python
# -- coding: utf-8 --
#
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


## Uit specific extension to Cerebrum
from __future__ import unicode_literals
import os
import sys
import re
import getopt
import mx.DateTime
from pprint import pprint

import cerebrum_path
import cereconf
#import adutils
from Cerebrum import Constants
from Cerebrum import Errors
#from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.modules.no.uit.PagaDataParser import PagaDataParserClass
from Cerebrum.modules.Email import EmailTarget, EmailForward
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError
#from Cerebrum.modules import PosixUser
#from Cerebrum.modules import PosixGroup
#from Cerebrum.modules.no.uit import Email

logger = Factory.get_logger('console')
today_tmp=mx.DateTime.today()
tomorrow_tmp=today_tmp + 1
TODAY=today_tmp.strftime("%Y-%m-%d")
TOMORROW=tomorrow_tmp.strftime("%Y-%m-%d")
default_user_file = os.path.join(cereconf.DUMPDIR,'AD','ad_export_%s.xml' % (TODAY))
default_employees_file = '/cerebrum/var/dumps/employees/paga_persons_%s.xml' % (TODAY,)
#default_employees_file = '/cerebrum/var/dumps/employees/paga_persons_latest.xml' 


db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)
ou = Factory.get('OU')(db)
ef = EmailForward(db)
et = EmailTarget(db)
name_language = co.language_nb

def get_sko(ou_id):
    ou.clear()
    ou.find(ou_id)
    return "%s%s%s" % (str(ou.fakultet).zfill(2),
                       str(ou.institutt).zfill(2),
                       str(ou.avdeling).zfill(2))
get_sko=memoize(get_sko)


def get_ouinfo_sito(ou_id,perspective):
    #logger.debug("Enter get_ouinfo with id=%s,persp=%s" % (ou_id,perspective))
    ou.clear()
    ou.find(ou_id)

    res=dict()
    res['name'] = ou.get_name_with_language(co.ou_name, name_language)
    res['short_name'] = ou.get_name_with_language(co.ou_name_short,
                                                  name_language)
    res['acronym'] = ou.get_name_with_language(co.ou_name_acronym,
                                               name_language)

    #logger.debug("got basic info about id=%s,persp=%s" % (ou_id,perspective))

    sted_sko=""
    res['sko']=sted_sko
    #logger.debug("..processing..")
    # Find company name for this ou_id by going to parent
    visited = []
    parent_id = ou.get_parent(perspective)
    #logger.debug("Find parent to OU id=%s, parent has %s, perspective is %s" % (ou_id,parent_id,perspective))
    while True:
        if (parent_id is None) or (parent_id == ou.entity_id):
            res['company'] = ou.get_name_with_language(co.ou_name,
                                                       name_language)
            break
        ou.clear()
        #logger.debug("Lookup %s in %s" % (parent_id,perspective))
        ou.find(parent_id)
        # Detect infinite loops
        if ou.entity_id in visited:
            raise RuntimeError, "DEBUG: Loop detected: %r" % visited
        visited.append(ou.entity_id)
        parent_id = ou.get_parent(perspective)
        #logger.debug("New parentid is %s" % (parent_id,))
    return res
get_ouinfo=memoize(get_ouinfo_sito)


def get_ouinfo(ou_id,perspective):
    #logger.debug("Enter get_ouinfo with id=%s,persp=%s" % (ou_id,perspective))

    ou.clear()
    ou.find(ou_id)

    # Determine if OU is quarantined
    if ou.get_entity_quarantine(qtype=co.quarantine_ou_notvalid) != []:
        return False

    res=dict()
    res['name'] = ou.get_name_with_language(co.ou_name, name_language)
    try:
        res['short_name'] = ou.get_name_with_language(co.ou_name_short,
                                                      name_language)
    except Errors.NotFoundError:
        res['short_name'] = ""
    try:
        res['acronym'] = ou.get_name_with_language(co.ou_name_acronym,
                                                   name_language)
    except Errors.NotFoundError:
        res['acronym'] = ""
    ou.clear()
    #logger.debug("got basic info about id=%s,persp=%s" % (ou_id,perspective))

    try:
        ou.find(ou_id)
        sted_sko = u'{:02}{:02}{:02}'.format(ou.fakultet, ou.institutt,
                                             ou.avdeling)
        #logger.debug("found sko for id=%s,persp=%s" % (ou_id,perspective))

    except Errors.NotFoundError:
        sted_sko=""
    res['sko']=sted_sko
    #logger.debug("..processing..")
    # Find company name for this ou_id by going to parent
    visited = []
    parent_id = ou.get_parent(perspective)
    #logger.debug("Find parent to OU id=%s, parent has %s, perspective is %s" % (ou_id,parent_id,perspective))
    while True:
        if (parent_id is None) or (parent_id == ou.entity_id):
            res['company'] = ou.get_name_with_language(co.ou_name,
                                                       name_language)
            break
        ou.clear()
        #logger.debug("Lookup %s in %s" % (parent_id,perspective))
        ou.find(parent_id)
        logger.debug("Lookup returned: id=%s,name=%s" % (ou.entity_id,
                                                         ou.name))
        # Detect infinite loops
        if ou.entity_id in visited:
            raise RuntimeError, "DEBUG: Loop detected: %r" % visited
        visited.append(ou.entity_id)
        parent_id = ou.get_parent(perspective)
        #logger.debug("New parentid is %s" % (parent_id,))
    # import pprint; pprint.pprint(res); 1/0
    return res
get_ouinfo=memoize(get_ouinfo)


def wash_sitosted(name):
    # removes preceeding and trailing numbers and whitespaces
    # samskipnaden has a habit of putting metadata (numbers) in the name... :(
    washed=re.sub(r"^[0-9\ ]+|\,|\&\ |[0-9\ -\.]+$", "",name)
    #logger.debug("WASH: '%s'->'%s' " % (name,washed))
    return washed


def get_samskipnadstedinfo(ou_id,perspective):

    res=dict()
    ou.clear()
    ou.find(ou_id)
    depname = wash_sitosted(ou.get_name_with_language(
        name_variant=co.ou_name_display,
        name_language=co.language_nb))
    
    res['sted']=depname
    # Find company name for this ou_id by going to parents
    visited = []
    while True:
        parent_id = ou.get_parent(perspective)
        #logger.debug("Parent to id=%s is %s" % (ou_id,parent_id))
        if (parent_id is None) or (parent_id == ou.entity_id):
            res['company'] = ou.get_name_with_language(
                name_variant=co.ou_name,
                name_language=co.language_nb)
            break
        ou.clear()
        ou.find(parent_id)
        # Detect infinite loops
        if ou.entity_id in visited:
            raise RuntimeError, "DEBUG: Loop detected: %r" % visited
        visited.append(ou.entity_id)
        parentname = wash_sitosted(ou.get_name_with_language(
            name_variant=co.ou_name_display,
            name_language=co.language_nb))
        res.setdefault('parents',list()).append(parentname)
    res['parents'].remove(res['company'])
    return res
get_samskipnadstedinfo=memoize(get_samskipnadstedinfo)


num2const=dict()
class ad_export:

    def __init__(self, userfile):
        self.userfile = userfile


    def load_cbdata(self):

        logger.info("Loading stillingtable")
        self.stillingmap = load_stillingstable()

        logger.info('Generating dict of PAGA persons affiliations and their stillingskoder, dbh_kat, etc')
        PagaDataParserClass(default_employees_file, scan_person_affs)

        logger.info("Loading PagaIDs")
        self.pid2pagaid=dict()
        for row in person.list_external_ids(id_type=co.externalid_paga_ansattnr,
                                            source_system=co.system_paga):
            self.pid2pagaid[row['entity_id']]=row['external_id']

        logger.info("Loading Sito IDs")
        self.pid2sitoid=dict()
        for row in person.list_external_ids(id_type=co.externalid_sito_ansattnr,
                                            source_system=co.system_sito):
            self.pid2sitoid[row['entity_id']]=row['external_id']
        logger.info("Start get constants")
        for c in dir(co):
            tmp = getattr(co, c)
            if isinstance(tmp, _CerebrumCode):
               num2const[int(tmp)] = tmp
        self.person_affs = self.list_affiliations()
        logger.info("#####") 
        logger.info("Cache person names")
        self.cached_names=person.getdict_persons_names(
                                 source_system=co.system_cached,
                                 name_types=(co.name_first,co.name_last))

        logger.info("Cache AD accounts")
        self.ad_accounts=account.search(
                              spread=int(co.spread_uit_ad_account),
                              expire_start=TOMORROW)
        logger.info("Build helper translation tables")
        self.accid2ownerid = dict()
        self.ownerid2accid = dict()
        self.accname2accid=dict()
        self.accid2accname=dict()
        self.accid2accaff=dict()
        for acct in self.ad_accounts:
            self.accid2ownerid[int(acct['account_id'])]=int(acct['owner_id'])
            self.ownerid2accid[int(acct['owner_id'])]=int(acct['account_id'])
            self.accname2accid[acct['name']]=int(acct['account_id'])
            self.accid2accname[int(acct['account_id'])]=acct['name']
        self.account_affs=dict()
        aff_cached=0
        logger.info("Caching account affiliations.")
        for row in  account.list_accounts_by_type(filter_expired=True,
                                             primary_only=False,
                                             fetchall=False):
            self.account_affs.setdefault(row['account_id'],list()).append((row['affiliation'],row['ou_id']))
            aff_cached+=1
        logger.debug("Cached %d affiliations" % (aff_cached,))

        # quarantines
        logger.info("Loading account quarantines...")
        self.account_quarantines = dict()
        for row in account.list_entity_quarantines(entity_types=co.entity_account,quarantine_types=[co.quarantine_tilbud,co.quarantine_generell,co.quarantine_slutta]):
            acc_name = self.accid2accname.get(int(row['entity_id']))
            q = num2const[int(row['quarantine_type'])]
            self.account_quarantines.setdefault(acc_name,list()).append(q)

        logger.info("Retrieving account emailaddrs")
        self.uname2mail=account.getdict_uname2mailaddr(primary_only=False)
        logger.info("Retrieving account primaryemailaddrs")
        self.uname2primarymail=account.getdict_uname2mailaddr(primary_only=True)

        logger.info("Loading email targets")
        self.mailtargetid2entityid=dict()
        for row in et.list_email_targets_ext():
            self.mailtargetid2entityid[row['target_id']]=row['target_entity_id']

        logger.info("Retreiving email forwards")
        self.email_forwards=dict()
        self.uname2forwards=dict()
        for row in ef.list_email_forwards():
            if row['enable']=="T":
                e_id=self.mailtargetid2entityid[row['target_id']]
                try:
                    uname=self.accid2accname[e_id]
                except KeyError:
                    #logger.warn("Entity_id %s not found in accid2accname, account does not have AD spread?" % (e_id))
                    continue
                #logger.debug("email target %s resolved to %s" % (row['target_id'],uname))
                self.uname2forwards[uname]=row['forward_to']
                #logger.debug("Forward cached: %s -> %s" % (uname,row['forward_to']))

        logger.info("Retrieving contact info (phonenrs and such)")
        self.person2contact=dict()
        for c in person.list_contact_info(entity_type=co.entity_person):
            self.person2contact.setdefault(c['entity_id'], list()).append(c)

        logger.info("Retrieve contact info (phonenrs and such) for account objects")
        # uit account stuff
        self.account2contact=dict()
        # valid uit source systems
        for c in person.list_contact_info(entity_type=co.entity_account):
            #logger.debug("appending uit data:%s" % c)
            self.account2contact.setdefault(c['entity_id'], list()).append(c)


        logger.info("Retreiving person campus loaction")
        self.person2campus=dict()
        for c in person.list_entity_addresses(entity_type=co.entity_person,source_system=co.system_paga,address_type=co.address_location):
            self.person2campus.setdefault(c['entity_id'], list()).append(c)
        logger.info("Cache done")


    def list_affiliations(self):
        person_affs = dict()
        skip_source = []
        skip_source.append(co.system_lt)
        #skip_source.append(co.system_hitos)
        for aff in person.list_affiliations():
            #logger.debug("now processing person id:%s" % aff['person_id'])
            #logger.debug("affs are:%s" % aff)
            # simple filtering
            aff_status_filter=(co.affiliation_status_student_tilbud,)
            if aff['status'] in aff_status_filter:
               continue
            if aff['source_system'] in skip_source:
               logger.warn('Skip affiliation, unwanted source system %s' % aff)
               continue
            p_id = aff['person_id']
            ou_id = aff['ou_id']
            source_system = aff['source_system']

            if (source_system==co.system_sito):
                perspective_code=co.perspective_sito
                ou_info = get_ouinfo_sito(ou_id,perspective_code)
            else:
                perspective_code=co.perspective_fs
                ou_info=get_ouinfo(ou_id,perspective_code)
                if ou_info == False:
                	# this is is quarantined, continue with next affiliation
                	logger.debug("ou id:%s is quarantined, continue with next affiliation" % ou_id)
                	continue
            last_date=aff['last_date'].strftime("%Y-%m-%d")
            try:
                #logger.debug("ou id:%s, perspective code:%s" % (ou_id,perspective_code))

                sko = ou_info['sko']
                company=ou_info['company']
                #logger.debug("Person from %s(company=%s), ID=%s, OU=(%s), sko:%s" %(source_system,ou_info['company'],p_id,ou_id,sko))
            except EntityExpiredError,msg:
                logger.error("person id:%s affiliated to expired ou:%s. Do not export" % (p_id,ou_id))
                continue
            except Errors.NotFoundError:
                logger.error("OU id=%s not found on person %s. DB integrety error!" % (ou_id,p_id))
                continue
            aff_stat=num2const[aff['status']]
            affinfo = {'affstr': str(aff_stat).replace('/','-'),
                       'sko': sko,
                       'lastdate':last_date,
                       'company': company}
            #logger.debug("person id:%s, has affiliation:%s" %(p_id,aff['source_system']))
            if(aff['source_system'] == co.system_paga):
                paga_id = self.pid2pagaid.get(p_id,None)
                #logger.info("have paga id:%s" % (paga_id))
                try:
                    aux_key = (paga_id,sko,str(aff_stat))
                    tils_info = aff_to_stilling_map[aux_key]
                except KeyError:
                    pass
                else:
                    affinfo['stillingskode']=tils_info['stillingskode']
                    affinfo['stillingstittel']=tils_info['stillingstittel_paga']
                    affinfo['prosent']=tils_info['prosent']
                    affinfo['dbh_kat']=tils_info['dbh_kat']
                    affinfo['hovedarbeidsforhold']=tils_info['hovedarbeidsforhold']
            elif(aff['source_system'] == co.system_sito):
                # get worktitle from person_name table for samskipnaden
                # Need to look it up  because cached names in script only contains names
                # from cached name variants, and worktitle is not there
                sito_id = self.pid2sitoid.get(p_id,None)
                person.clear()
                person.find(p_id)
                try:
                    worktitle=person.get_name(co.system_sito,co.name_work_title)
                    affinfo['stillingstittel']=worktitle
                except Errors.NotFoundError:
                    logger.info("Unable to find title for person:%s" % sito_id)

                sitosted=get_samskipnadstedinfo(ou_id,perspective_code)
                #logger.debug("FROM LOOKUP: %s" % sitosted)
                affinfo['company']=sitosted['company']
                affinfo['sted']=sitosted['sted']
                affinfo['parents']=",".join(sitosted['parents'])
                logger.debug("processing sito person:%s", sito_id)
                #logger.debug("affs:%s", affinfo )

            tmp=person_affs.get(p_id,list())
            if affinfo not in tmp:
                #logger.info("appending:%s" % affinfo)
                tmp.append(affinfo)
                person_affs[p_id]=tmp

        return person_affs


    def build_cbdata(self):
        logger.info("Processing cerebrum info...")
        count = 0
        self.userexport=list()
        for item in self.ad_accounts:
            count +=1
            if (count%500 == 0):
                logger.info("Processed %d accounts" % count)
            acc_id = item['account_id']
            name = item['name']
            owner_id = item['owner_id']
            owner_type=item['owner_type']
            expire_date=item['expire_date'].strftime("%Y-%m-%d")
            emails=self.uname2mail.get(name,"")
            forward=self.uname2forwards.get(name,"")
            namelist = self.cached_names.get(owner_id, None)
            first_name=last_name=worktitle=""
            try:
                first_name = namelist.get(int(co.name_first))
                last_name = namelist.get(int(co.name_last))
            except AttributeError:
                if owner_type == co.entity_person:
                    logger.error("Failed to get name for a_id/o_id=%s/%s"  %  \
                                 (acc_id,owner_id))
                else:
                    logger.warn("No name found for a_id/o_id=%s/%s, ownertype was %s" % \
                                 (acc_id,owner_id,owner_type))

            # now to get any email forward addresses
            entry=dict()
            entry['name']=name
            if name.endswith(cereconf.USERNAME_POSTFIX['sito']):
                upndomain = cereconf.SITO_PRIMARY_MAILDOMAIN
            else:
                upndomain = cereconf.INSTITUTION_DOMAIN_NAME
            entry['userPrincipalName']="%s@%s" % (name,upndomain)
            entry['givenName'] = first_name
            entry['sn'] = last_name
            entry['expire'] = expire_date
            entry['emails'] = emails
            entry['forward'] = forward
            self.userexport.append(entry)


    def build_xml(self,acctlist=None):

        incrMAX=20
        if ((acctlist is not None) and (len(acctlist)> incrMAX)):
            logger.error("Too many changes in incremental mode")
            return

        logger.info("Start building export, writing to %s" % self.userfile)
        validate = re.compile('^[a-z][a-z][a-z][0-9][0-9][0-9]$')
        validate_guests = re.compile('^gjest[0-9]{2}$')
        validate_sito = re.compile('^[a-z][a-z][a-z][0-9][0-9][0-9]%s$' % (cereconf.USERNAME_POSTFIX['sito']))
        fh = file(self.userfile,'w')
        xml = xmlprinter(fh,indent_level=2,data_mode=True,input_encoding='ISO-8859-1')
        xml.startDocument(encoding='utf-8')
        xml.startElement('data')
        xml.startElement('properties')
        xml.dataElement('tstamp', str(mx.DateTime.now()))
        if acctlist:
            type="incr"
        else:
            type="fullsync"
        xml.dataElement('type', type)
        xml.endElement('properties')

        xml.startElement('users')
        for item in self.userexport:
            if (acctlist is not None) and (item['name'] not in acctlist):
               continue
            if (not (validate.match(item['name']) or 
                     (validate_guests.match(item['name'])) or
                     (validate_sito.match(item['name']))
                    )):
                logger.error("Username not valid for AD: %s" % (item['name'],))
                continue
            xml.startElement('user')
            xml.dataElement('samaccountname',item['name'])
            xml.dataElement('userPrincipalName',item['userPrincipalName'])
            xml.dataElement('sn',item['sn'])
            xml.dataElement('givenName',item['givenName'])
            xml.dataElement('accountExpire',str(item['expire']))
            xml.startElement('proxyAddresses')
            emtmp=list()
            for email in item['emails']:
                email=email.strip()
                attrs = dict()
                primaryemail = self.uname2primarymail.get(item['name'],None)
                if email == primaryemail:
                   attrs['primary']="yes"
                if email not in emtmp:
                    xml.dataElement('mail',email,attrs)
                    emtmp.append(email)
            xml.endElement('proxyAddresses')

            accid=self.accname2accid[item['name']]
            contact=self.person2contact.get(self.accid2ownerid[accid])

            #
            # In some cases the person object AND the account object will have different contact information.
            # If an account object contains contact data of the same type as the person object and from the same source,
            # the account contact data will superseede the person object contact data of that type.
            # To facilitate this, we will parse the person2contact dict and account2contact dict and replace
            # the relevant contact data in the person2contact dict.
            # If the account object contains contact data not in contact list, the relevant data will be appended to the contact list.
            # The person2contact dict will then be used when writing the xml file.
            #
            #logger.debug("contact contains:%s" % contact)
            contact_account = self.account2contact.get(accid)
            #logger.debug("contact_account contains:%s" % contact_account)
            if contact and contact_account:
                new_contact = {}
                for a in contact_account:
                    already_exists = False
                    replaced = False
                    for c in contact:
                        if a['contact_type'] == c['contact_type'] and a['source_system'] == c['source_system']:
                            already_exists = True
                            if not any(d['contact_value'] == a['contact_value'] for d in contact):
                                logger.debug("replace:%s with: %s" % (c['contact_value'],a['contact_value']))
                                c['contact_value']  = a['contact_value']                                
                                replaced = True
                    if already_exists == False and replaced == False:
                        #logger.debug("new entry from account:%s" % a)
                        new_contact.update(a)
                    
                if len(new_contact) > 0:
                    #logger.debug("appending the following:%s" % new_contact)
                    contact.append(new_contact)

                                


            # get campus information
            campus=self.person2campus.get(self.accid2ownerid[accid])
            if campus:
                for c in campus:
                    campus_name = str(c['address_text'].encode('utf-8'))
                    xml.dataElement('l',str(campus_name))
            if(item['forward'] !=''):
                xml.dataElement('targetAddress',str(item['forward']))
            if contact:
                xml.startElement('contactinfo')
                for c in contact:
                   source=str(co.AuthoritativeSystem(c['source_system']))
                   ctype=str(co.ContactInfo(c['contact_type']))
                   xml.emptyElement('contact',
                                              {'source':source,
                                              'type':ctype,
                                              'pref':str(c['contact_pref']),
                                              'value':str(c['contact_value'].encode('utf-8'))
                                              })
                xml.endElement('contactinfo')

            person_affs = self.person_affs.get(self.accid2ownerid[accid],list())
            account_affs=self.account_affs.get(accid,list())
            #logger.debug("Person Affs : %s " % (person_affs,))
            #logger.debug("Account Affs: %s " % (account_affs,))
            resaffs=list()
            #logger.debug("---------------------------")
            for person_aff in person_affs:
                #logger.debug("Person Aff is %s" % (person_aff['affstr'],))
                for acc_aff,ou_id in account_affs:
                    paff=person_aff['affstr'].split('-')[0] # first elment in "ansatt-123456"
                    aaff=str(num2const[acc_aff])
                    #logger.debug("Matching paff='%s' against aaff='%s'" % (paff,aaff))
                    if (paff == aaff):
                        #logger.debug("Aff match! %s" % (paff,))
                        person_aff['affstr'] = person_aff['affstr'].replace('sys_x-ansatt','sys_xansatt')
                        resaffs.append(person_aff)
                        break # leave inner for loop
                    else:
                        #logger.debug("Aff mismatch! Paff(%s)!=Aaaf(%s)" % (paff,aaff))
                        pass
            #logger.debug("-------------------------**")
            #logger.debug("Filterd Person Affs: %s " % (resaffs,))
            if resaffs:
                xml.startElement('affiliations')
                for aff in resaffs:
                    #dumps content of dict as xml attributes
                    xml.emptyElement('aff',aff)
                xml.endElement('affiliations')

            quarantines = self.account_quarantines.get(item['name'])

            if quarantines:
                quarantines = sort_quarantines(quarantines)
                xml.startElement('quarantines')
                for q in quarantines:
                    xml.emptyElement('quarantine', {'qname': str(q)})
                xml.endElement('quarantines')

            xml.endElement('user')
        xml.endElement('users')
        xml.endElement('data')
        xml.endDocument()


#
# sort all quarantines and return the one with the lowest number
# As of now the different quarantines and their order are
# slutta : 1
# generell: 2
# tilbud : 3
#
def sort_quarantines(quarantines):
    #pprint(quarantines)
    if co.quarantine_slutta in quarantines:
        return [co.quarantine_slutta]
    elif co.quarantine_generell in quarantines:
        return [co.quarantine_generell]
    elif co.quarantine_tilbud in quarantines:
        return [co.quarantine_tilbud]
    else:
        logger.warn("unknown quarantine:%s" % quarantines)
        return -1


#stillingskode_map = dict()
def load_stillingstable():
    global stillingskode_map
    sql = """
        SELECT stillingskode,stillingstittel,stillingstype
        FROM [:table schema=cerebrum name=person_stillingskoder]
        """
    stillingskode_map = dict()
    for row in db.query(sql,dict()):
        stillingskode_map[str(row['stillingskode'])]={'stillingstittel': row['stillingstittel'],
                                         'stillingstype': row['stillingstype']
                                         }


aff_to_stilling_map=dict()
def scan_person_affs(person):
    global aff_to_stilling_map

    fnr = person['fnr']
    pagaid = person['ansattnr']

    for t in person.get('tils', ()):
        earliest = mx.DateTime.DateFrom(t.get("dato_fra")) - mx.DateTime.DateTimeDelta(cereconf.PAGA_EARLYDAYS)
        dato_fra = mx.DateTime.DateFrom(t.get("dato_fra"))
        dato_til = mx.DateTime.DateFrom(t.get("dato_til"))

        if (mx.DateTime.today() < earliest) or (dato_til and (mx.DateTime.today() > dato_til)):
            #logger.warn("Not active, earliest: %s, dato_fra: %s, dato_til:%s" % (earliest, dato_fra,dato_til))
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
        tmp=stillingskode_map.get(stillingskode,None)
        if tmp:
            stillingstittel=tmp['stillingstittel']
            dbh_kat=tmp['stillingstype']
        else:
            # default to fileinfo
            stillingstittel = t['tittel']
            dbh_kat = t['dbh_kat']

        hovedarbeidsforhold = ''
        if t.has_key('hovedarbeidsforhold'):
            hovedarbeidsforhold = t['hovedarbeidsforhold']

        aux_key = (pagaid, stedkode, str(tilknytning))
        aux_val = {'stillingskode': stillingskode,
                   'stillingstittel_paga': t['tittel'],
                   'stillingstittel': stillingstittel,
                   'prosent': pros,
                   'dbh_kat': dbh_kat,
                   'hovedarbeidsforhold':hovedarbeidsforhold}
#        logger.info("From PAGA file: key: %s => %s" % (aux_key,aux_val))
        aff_to_stilling_map[aux_key] = aux_val


#
# program usage
#
def usage(exitcode=0):
    print """Usage: [options]
    -h | --help             : show this message
    -a | --account username : export single account. NB DOES NOT WORK!
    -o | --out filname      : writes to given filename
    -t | --type [incr|fullsync] : use only fullsync!
    """
    sys.exit(exitcode)



def main():
    global default_user_file
    global default_group_file
    global outfile

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ha:o:',
                                   ['account=','help',"type=","out="])
    except getopt.GetoptError:
        usage(1)
    deftype="fullsync"
    type=deftype
    outfile=default_user_file
    one_account=acctlist=None
    for opt, val in opts:
        if opt in ['-a', '--account']:
            one_account = val
        elif opt in ['--type']:
            if (val =="incr" or val == "fullsync"):
                type=val
        elif opt in ['-o', '--out']:
            outfile=val
        elif opt in ['-h', '--help']:
            usage(0)
        else:
            pass

    if (type=="incr"):
        acctlist=one_account.split(",")

        #logger.debug("Type is %s, accts is %s" % (type,acctlist))

    start=mx.DateTime.now()
    worker = ad_export(outfile)
    worker.load_cbdata()
    worker.build_cbdata()
    worker.build_xml(acctlist)
    stop=mx.DateTime.now()
    logger.debug("Started %s ended %s" %  (start,stop))
    logger.debug("Script running time was %s " % ((stop-start).strftime("%M minutes %S secs")))


if __name__ == '__main__':
    main()
