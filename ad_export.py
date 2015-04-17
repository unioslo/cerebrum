#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
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

import os
import sys
import re
import getopt
import mx.DateTime
from pprint import pprint

import cerebrum_path
import cereconf
import adutils
from Cerebrum import Constants
from Cerebrum import Errors
#from Cerebrum import Entity
from Cerebrum.Utils import Factory, simple_memoize
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.modules.no.uit.PagaDataParser import PagaDataParserClass
from Cerebrum.modules.Email import EmailTarget, EmailForward
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError
from Cerebrum.modules.no.uit.Stedkode import StedkodeMixin
#from Cerebrum.modules import PosixUser
#from Cerebrum.modules import PosixGroup
#from Cerebrum.modules.no.uit import Email


max_nmbr_users = 20000
logger = Factory.get_logger('console')

today_tmp=mx.DateTime.today()
tomorrow_tmp=today_tmp + 1
TODAY=today_tmp.strftime("%Y-%m-%d")
TOMORROW=tomorrow_tmp.strftime("%Y-%m-%d")


default_user_file = os.path.join(cereconf.DUMPDIR,'AD','ad_export_%s.xml' % (TODAY))
#default_user_file = 'ad_export_%s.xml' % (TODAY,)
default_employees_file = '/cerebrum/var/dumps/employees/paga_persons_%s.xml' % (TODAY,)
#default_employees_file = '/cerebrum/var/dumps/employees/paga_persons_latest.xml' 



db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)
ou=Factory.get('OU')(db)
#sko=Factory.get('Stedkode')(db)
sko = StedkodeMixin(db)
ef = EmailForward(db)
et = EmailTarget(db)

def get_sko(ou_id):
    sko.clear()
    sko.find(ou_id)
    return "%s%s%s" % (str(sko.fakultet).zfill(2),
                       str(sko.institutt).zfill(2),
                       str(sko.avdeling).zfill(2))
get_sko=simple_memoize(get_sko)

def get_ouinfo(ou_id,perspective):

    #logger.debug("Enter get_ouinfo with id=%s,persp=%s" % (ou_id,perspective))
    #sko=Factory.get('Stedkode')(db)
    sko = StedkodeMixin(db)
    sko.clear()
    sko.find_by_perspective(ou_id,perspective)
    res=dict()
    #res['name']=str(sko.name)
    res['name']= sko.get_name_with_language(co.ou_name_display,name_language=co.language_nb)    
    #res['short_name']=str(sko.short_name)
    res['short_name']= sko.get_name_with_language(co.ou_name_short,name_language=co.language_nb)    
    #res['acronym']=str(sko.acronym)
    res['short_name']= sko.get_name_with_language(co.ou_name_acronym,name_language=co.language_nb)    
    #logger.debug("short name is:%s" % res['short_name'])
    sko.clear()
    #logger.debug("got basic info about id=%s,persp=%s" % (ou_id,perspective))

    try:
        sko.find(ou_id)
        sted_sko="%s%s%s" % (str(sko.fakultet).zfill(2),
                        str(sko.institutt).zfill(2),
                        str(sko.avdeling).zfill(2))
        #logger.debug("found sko for id=%s,persp=%s" % (ou_id,perspective))
        
    except Errors.NotFoundError:
        sted_sko=""
    res['sko']=sted_sko

    
    
    # Find company name for this ou_id by going to parent
    visited = []
    parent_id=sko.get_parent(perspective)
    #logger.debug("Find parent to OU id=%s, parent has %s, perspective is %s" % (ou_id,parent_id,perspective))
    while True:
        if (parent_id is None) or (parent_id == sko.entity_id):
            #logger.debug("Root for %s is %s, name is  %s" % (ou_id,sko.entity_id,sko.name))
            #res['company']=sko.name
            res['company']= sko.get_name_with_language(co.ou_name_display,name_language=co.language_nb)    
            break

        sko.clear()
        #logger.debug("Lookup %s in %s" % (parent_id,perspective))
        sko.find_by_perspective(parent_id,perspective)
        sko_name = sko.get_name_with_language(co.ou_name_display,name_language=co.language_nb)   
        #logger.debug("Lookup returned: id=%s,name=%s" % (sko.entity_id,sko_name))
        # Detect infinite loops
        if sko.entity_id in visited:
            raise RuntimeError, "DEBUG: Loop detected: %r" % visited
        visited.append(sko.entity_id)

        parent_id = sko.get_parent(perspective)
        #logger.debug("New parentid is %s" % (parent_id,))


    return res
get_ouinfo=simple_memoize(get_ouinfo)


num2const=dict()


class ad_export:

    def __init__(self, userfile):
        #self.sko = Factory.get('Stedkode')(db)
        self.userfile = userfile


    def load_cbdata(self):


        logger.info("Loading stillingtable")
        self.stillingmap = load_stillingstable()


        logger.info('Generating dict of PAGA persons affiliations and their stillingskoder, dbh_kat, etc')
        PagaDataParserClass(default_employees_file, scan_person_affs)

        #logger.info("Generating dict of HiFm person affiliations and their stillingskoder")
        #scan_hifm_person_affs()
        
        #logger.info("Loading HiFmIDs")
        #self.pid2hifmid=dict()
        #for row in person.list_external_ids(id_type=co.externalid_hifm_ansattnr,
        #                                    source_system=co.system_hifm):
        #    self.pid2hifmid[row['entity_id']]=row['external_id']

        
        logger.info("Loading PagaIDs")
        self.pid2pagaid=dict()
        for row in person.list_external_ids(id_type=co.externalid_paga_ansattnr,
                                            source_system=co.system_paga):
            self.pid2pagaid[row['entity_id']]=row['external_id']

        logger.info("Loading Sito IDs")
        self.pid2sitoid=dict
        for row in person.list_external_ids(id_type=co.externalid_paga_ansattnr,
                                            source_system=co.system_sito):
            self.pid2sitoid[row['entity_id']]=row['external_id']



        logger.info("Start get constants")
        for c in dir(co):
            tmp = getattr(co, c)
            if isinstance(tmp, _CerebrumCode):
               num2const[int(tmp)] = tmp



        logger.info("Cache person affs")
        self.person_affs = self.list_affiliations()

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
            logger.debug("Collected account id : %s from database" % int(acct['account_id']))
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
                    logger.warn("Entity_id %s not found in accid2accname, account does not have AD spread?" % (e_id))
                    continue
                #logger.debug("email target %s resolved to %s" % (row['target_id'],uname))
                self.uname2forwards[uname]=row['forward_to']
                #logger.debug("Forward cached: %s -> %s" % (uname,row['forward_to']))

        logger.info("Retrieving contact info (phonenrs and such)")
        self.person2contact=dict()
        for c in person.list_contact_info(entity_type=co.entity_person):
            self.person2contact.setdefault(c['entity_id'], list()).append(c)

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
        logger.warn("for each person affiliation do...")
        for aff in person.list_affiliations():
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
            else:
                perspective_code=co.perspective_fs
            last_date=aff['last_date'].strftime("%Y-%m-%d")
            try:                
                ou_info=get_ouinfo(ou_id,perspective_code)
                sko = ou_info['sko']
                company=ou_info['company']
                #logger.debug("Person from %s(company=%s), ID=%s, OU=(%s), sko:%s" %(source_system,ou_info['company'],p_id,ou_id,sko)
            except EntityExpiredError,msg:
                logger.error("person id:%s affiliated to expired ou:%s. Do not export" % (p_id,ou_id))
                continue
            except Errors.NotFoundError:
                logger.error("OU id=%s not found on person %s. DB integrety error!" % (ou_id,p_id))
                sys.exit(1)
                
            aff_stat=num2const[aff['status']]
            affinfo = {'affstr': str(aff_stat).replace('/','-'),
                       'sko': sko,
                       'lastdate':last_date,
                       'company': company}

            #if (aff['source_system'] == co.system_hifm):
            #
            #    logger.info("source is hifm")
            #elif(aff['source_system'] == co.system_paga):
            #    paga_id = self.pid2pagaid.get(p_id,None)
            #    logger.info("source is paga")
            #else:
            #    logger.info("unwanted source system:%s" % aff['source_system'])
            #    continue

            #try:
            #    logger.info("paga_id is:%s" % paga_id)
            #    logger.info("hifm_id is:%s" % hifm_id)
            #except:
            #    logger.info("unable to write paga and hifm id")
            # if (aff['source_system'] == co.system_hifm):
            #     hifm_id = self.pid2hifmid.get(p_id,None)
            #     #if hifm_id:
            #     #logger.info("have hifm id:%s" % hifm_id)
            #     try:
            #         #logger.info("hifm_id:%s, sko:%s, aff_stat:%s" % (hifm_id,sko,str(aff_stat)))
            #         aux_key = (hifm_id,sko,str(aff_stat))
            #         #logger.info("type:%s" % type(aux_key))
            #         #logger.info("aux key:%s" % (aux_key,))
            #         tils_info = hifm_aff_to_stilling_map[aux_key]
            #         #logger.info("tils info:%s" % (tils_info))
            #     except KeyError:
            #         #logger.info("unable to get aux_key and or tils_info")
            #         pass
            #     else:
            #         #logger.info("setting affinfo")
            #         #affinfo['stillingskode']=tils_info['stillingskode']
            #         affinfo['stillingstittel']=tils_info['stillingstittel']

            #         # Hardcoding hovedarbeidsforhold to H.
            #         # why? because the AD import script now will correctly process stillingstittel withouth
            #         # the need for editing the script. This is also ok, since employees from HiFm comes to UiT
            #         # with at most _ONE_ work affiliation.
                    
            #         affinfo['hovedarbeidsforhold'] = 'H'
                   
                   
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

            tmp=person_affs.get(p_id,list())
            if affinfo not in tmp:
                #logger.info("appending:%s" % affinfo)
                tmp.append(affinfo)
                person_affs[p_id]=tmp

        return person_affs


    def build_cbdata(self):

        logger.info("Processing cerebrum info...")
        count = 0
#        old_forward =''
        
        self.userexport=list()
        for item in self.ad_accounts:
            count +=1
            if (count%500 == 0):
                logger.info("Processed %d accounts" % count)
            
            acc_id = item['account_id']
            name = item['name']
            owner_id = item['owner_id']
            owner_type=item['owner_type']
            #logger.warn("account id:%s" % item['account_id'])
            #logger.warn("expire date is:%s" % item['expire_date'])
            try:
                    expire_date=item['expire_date'].strftime("%Y-%m-%d")
            except AttributeError:
                logger.warn("Account id:%s has no expire date" % item['account_id'])
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

            #FIXME: hardcoded values is bad!
            if name.endswith(cereconf.USERNAME_POSTFIX['sito']):
                upndomain = cereconf.SITO_PRIMARY_MAILDOMAIN
                #upndomain="sito.no"
            else:
                upndomain = cereconf.INSTITUTION_DOMAIN_NAME
                #upndomain="uit.no"
            entry['userPrincipalName']="%s@%s" % (name,upndomain)
            entry['givenName'] = first_name
            entry['sn'] = last_name
            try:
                entry['expire'] = expire_date
            except UnboundLocalError:
                logger.warn("user:%s has no expire date" % entry['userPrincipalName'])
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
        #validate_sito = re.compile('^[a-z][a-z][a-z][0-9][0-9][0-9]-s$')
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
            try:
                xml.dataElement('accountExpire',str(item['expire']))
            except KeyError:
                logger.warn("cannot set expiredate in xml for principalname:%s" % item['userPrincipalName'])
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
            # get campus information
            campus=self.person2campus.get(self.accid2ownerid[accid])
            if campus:
                for c in campus:
                    campus_name = str(c['address_text'])
                    print "campus:%s" % campus_name
                    xml.dataElement('l',str(campus_name))
                    #sys.exit(1)
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
                                              'value':str(c['contact_value'])
                                              })
                xml.endElement('contactinfo')


            # This is wrong. need to send only person affs that matches account affs
            #affs = self.person_affs.get(self.accid2ownerid[accid])
            
            
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
    #return stillingmap
    
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
# Create a list of dicts containing all affilition information for hifm employees.
# This is to be used when generating hifm stillingsdata in the ad export file.
# Key is:   hifm_id,sko,aff_stat.
# value is:  stillingskode, stillingstittel
#
hifm_aff_to_stilling_map = dict()
def scan_hifm_person_affs():
    global hifm_aff_to_stilling_map
    person.clear()
    person_liest = []
    #sko = Factory.get('Stedkode')(db)
    #
    # list_affiliation returns: person_id,ou_id,affiliation,source_system,status,deleted_date,create_date,last_date
    #
    person_list = person.list_affiliations(source_system = co.system_hifm,affiliation=co.affiliation_ansatt)
    for i in person_list:
        # Get stedkode
        ou_id = i[1]
        stedkode = get_sko(ou_id)
        #print "ou id is:%s and collected sko:%s" % (ou_id,stedkode)

        # Get aff_stat
        aff_stat = i[4]
        if aff_stat == co.affiliation_status_ansatt_tekadm:
            #print "is tekadm"
            tilknytning = co.affiliation_status_ansatt_tekadm
        elif aff_stat == co.affiliation_status_ansatt_vitenskapelig:
            #print "is vitenskapelig"
            tilknytning = co.affiliation_status_ansatt_vitenskapelig
        else:
            logger.warn("ERROR: unknown  aff stat: %s "% aff_stat)

        # get affiliation
        #affiliation = i[2]
        #if affiliation == co.affiliatio
        
        # populate person object
        person_id = i[0]
        person.clear()
        person.find(person_id)

        # get hifm stillingstittel
        logger.info("operating on person_id:%s" % person_id)
        try:
            person_title = person.get_name(source_system = co.system_hifm, variant = co.name_work_title)
        except Errors.NotFoundError:
            logger.info("person_id:%s has no title from HiFm" % person_id)
            continue
        #person_title = person_title.decode("utf-8").encode("iso8859-1")

        # Get hifm employee number        
        external_ids = person.get_external_id(source_system = co.system_hifm,id_type = co.externalid_hifm_ansattnr)
        try:
            #print "external_ids:%s" % external_ids[0][2]
            hifm_id = external_ids[0][2]
        except:
            logger.info("unable to get hifm ansatt nr for person_id:%s" % person_id)
            hifm_id = ""

        # get affiliation type (staff,factuly)
        

        # all relevant info collected. populate
        if hifm_id != "" and (len(person_title) > 2):
            logger.info("has stillingstittel:%s" % person_title)
            aux_key = (hifm_id,stedkode,str(tilknytning))
            aux_val = {'stillingstittel':  person_title}

            #print "aux_key:%s" % (aux_key,)
            hifm_aff_to_stilling_map[aux_key] = aux_val
        
        
        
    
#def get_sko(ou_id):
#    sko.clear()
#    try:
#        sko.find_by_perspective(ou_id,co.perspective_fs)
#    except Errors.NotFoundError:
#        # Persons has an affiliation to a non-fs ou.
#        # Return NoneNoneNone
#        print "unable to find stedkode. Return NoneNoneNone"
#        return "NoneNoneNone"
#    print "returning:%s%s%s" % (sko.fakultet,sko.institutt,sko.avdeling)
#    return "%02s%02s%02s" % (sko.fakultet,sko.institutt,sko.avdeling)
#get_sko=simple_memoize(get_sko)


#
# program usage
#
def usage(exitcode=0):
    print """Usage: [options]
    -h | --help show this message
    -a | --account : export single account.
    """
    sys.exit(exitcode)



def main():
    global default_user_file
    global default_group_file

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ha:',
                                   ['account=','help',"type="])
    except getopt.GetoptError:
        usage(1)
    deftype="fullsync"
    type=deftype
    one_account=acctlist=None
    for opt, val in opts:
        if opt in ['-a', '--account']:
            one_account = val
        elif opt in ['--type']:
            if (val =="incr" or val == "fullsync"):
                type=val
        elif opt in ['-h', '--help']:
            usage(0)
        else:
            pass

    if (type=="incr"):
        acctlist=one_account.split(",")

    logger.debug("Type is %s, accts is %s" % (type,acctlist))


    start=mx.DateTime.now()
    worker = ad_export(default_user_file)
    worker.load_cbdata()
    worker.build_cbdata()
    worker.build_xml(acctlist)
    stop=mx.DateTime.now()
    logger.debug("Started %s ended %s" %  (start,stop))
    logger.debug("Script running time was %s " % ((stop-start).strftime("%M minutes %S secs")))
#.strftime("%Y-%m-%d %H:%M:%S")
if __name__ == '__main__':
    main()
