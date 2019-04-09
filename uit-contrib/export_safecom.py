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
from Cerebrum import Constants
from Cerebrum import Errors
#from Cerebrum import Entity
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError

logger = Factory.get_logger('cronjob')
today_tmp=mx.DateTime.today()
tomorrow_tmp=today_tmp + 1
TODAY=today_tmp.strftime("%Y%m%d")
TOMORROW=tomorrow_tmp.strftime("%Y%m%d")

DEFAULT_PAYXML=os.path.join(cereconf.DUMPDIR, "safecom","safecom_pay_%s.xml" % TODAY)
DEFAULT_TRACKXML=os.path.join(cereconf.DUMPDIR, "safecom","safecom_track_%s.xml" % TODAY)


db = Factory.get('Database')()
co = Factory.get('Constants')(db)
person = Factory.get('Person')(db)
account = Factory.get('Account')(db)
ou = Factory.get('OU')(db)


def get_sko(ou_id):
    ou.clear()
    ou.find(ou_id)
    return "%s%s%s" % (str(ou.fakultet).zfill(2),
                       str(ou.institutt).zfill(2),
                       str(ou.avdeling).zfill(2))
get_sko=memoize(get_sko)


def get_ouinfo(ou_id,perspective):
    #logger.debug("Enter get_ouinfo with id=%s,persp=%s" % (ou_id,perspective))
    ou.clear()
    ou.find(ou_id)
    ou_short_name = ou.get_name_with_language(name_variant=co.ou_name_short,
                                              name_language=co.language_nb)
    ou_name = ou.get_name_with_language(name_variant=co.ou_name,
                                        name_language=co.language_nb)
    ou_acronym = ou.get_name_with_language(name_variant=co.ou_name_acronym,
                                           name_language=co.language_nb)
    res=dict()
    res['name']=ou_name
    res['short_name']=ou_short_name
    res['acronym']=ou_acronym
    acropath=[]
    acropath.append(res['acronym'])
    #logger.debug("got basic info about id=%s,persp=%s" % (ou_id,perspective))

    try:
        sted_sko=get_sko(ou_id)
    except Errors.NotFoundError:
        sted_sko=""
    res['sko']=sted_sko

    # Find company name for this ou_id by going to parent
    visited = []
    parent_id = ou.get_parent(perspective)
    #logger.debug("Find parent to OU id=%s, parent has %s, perspective is %s" % (ou_id,parent_id,perspective))
    while True:
        if (parent_id is None) or (parent_id == ou.entity_id):
            res['company']=ou_name
            break
        ou.clear()
        #logger.debug("Lookup %s in %s" % (parent_id,perspective))
        ou.find(parent_id)
        #logger.debug("THIS line is never reached when processing sito orgunits")
        ou_acronym = ou.get_name_with_language(name_variant=co.ou_name_acronym,
                                               name_language=co.language_nb)
        # Detect infinite loops
        if ou.entity_id in visited:
            raise RuntimeError, "DEBUG: Loop detected: %r" % visited
        visited.append(ou.entity_id)
        acropath.append(ou_acronym)
        parent_id = ou.get_parent(perspective)
        #logger.debug("New parentid is %s" % (parent_id,))
    acropath.reverse()
    res['path']=".".join(acropath)
    #logger.debug("get_ouinfo: return %s" % res)
    return res
get_ouinfo=memoize(get_ouinfo)


def wash_sitosted(name):
    # removes preceeding and trailing numbers and whitespaces
    # samskipnaden has a habit of putting metadata (numbers) in the name... :(
    washed=re.sub(r"^[0-9\ ]+|\,|\&\ |[0-9\ -\.]+$", "",name)
    logger.debug("WASH: '%s'->'%s' " % (name,washed))
    return washed


def get_samskipnadstedinfo(ou_id,perspective):

    res=dict()
    ou.clear()
    ou.find(ou_id)
    ou_name = ou.get_name_with_language(name_variant=co.ou_name,name_language=co.language_nb)
    depname=wash_sitosted(ou.get_name_with_language(co.ou_name_display,
                                                    co.language_nb))
    res['sted']=depname
    # Find company name for this ou_id by going to parents
    visited = []
    while True:
        parent_id=ou.get_parent(perspective)
        logger.debug("Parent to id=%s is %s" % (ou_id,parent_id))
        if (parent_id is None) or (parent_id == ou.entity_id):
            logger.debug("Root for %s is %s, name is  %s" % (ou_id,ou.entity_id,ou_name))
            res['company']=ou_name
            break
        ou.clear()
        ou.find(parent_id)
        ou_name = ou.get_name_with_language(name_variant=co.ou_name,name_language=const.language_nb)
        logger.debug("Current id=%s, name is %s" % (ou.entity_id,ou_name))
        # Detect infinite loops
        if ou.entity_id in visited:
            raise RuntimeError, "DEBUG: Loop detected: %r" % visited
        visited.append(ou.entity_id)
        parentname = wash_sitosted(ou.get_name_with_language(
            co.ou_name_display, co.language_nb))
        res.setdefault('parents',list()).append(parentname)
    res['acropath'].remove(res['company'])
    return res
get_samskipnadstedinfo=memoize(get_samskipnadstedinfo)


num2const=dict()
class safecom_export:

    def __init__(self,payfile,trackfile):
        self.userfile_pay=payfile
	self.userfile_track=trackfile
	logger.debug("Will write payfile to %s" % payfile)
	logger.debug("Will write trackfile to %s" % trackfile)

    def load_cbdata(self):
        logger.info("Start get constants")
        for c in dir(co):
            tmp = getattr(co, c)
            if isinstance(tmp, _CerebrumCode):
               num2const[int(tmp)] = tmp

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
        logger.info("Caching account primary affiliations.")
        for row in  account.list_accounts_by_type(filter_expired=True,
                                             primary_only=False,
                                             fetchall=False):
            self.account_affs.setdefault(row['account_id'],list()).append((row['affiliation'],row['ou_id']))

        logger.info("Cache person affs")
        self.person_affs = self.list_affiliations()
	pay_accounts=self.get_safecom_mode()

        logger.info("Cache person names")
        self.cached_names=person.getdict_persons_names(
                                 source_system=co.system_cached,
                                 name_types=(co.name_first,co.name_last))

        logger.info("Retrieving account primaryemailaddrs")
        self.uname2primarymail=account.getdict_uname2mailaddr(primary_only=True)

    def get_safecom_mode(self):
	self.pay=[]
	self.track=[]
	pay_filter=[co.affiliation_status_student_aktiv, co.affiliation_status_student_alumni,
		    co.affiliation_status_student_evu, co.affiliation_status_student_opptak, 
		    co.affiliation_status_student_perm, co.affiliation_status_student_privatist,
		    co.affiliation_status_student_sys_x, co.affiliation_status_student_tilbud,
		    co.affiliation_status_flyt_hih_student_aktiv,co.affiliation_status_flyt_hin_student_aktiv,
                    co.affiliation_status_student_emnestud]


        for account,values in self.account_affs.iteritems():
            pay = True
            try:
                account_owner_id = self.accid2ownerid[account]
                for single_aff in values:
                    aff= single_aff[0]
                    ou = single_aff[1]

                    # have account aff and ou. find correct entry in person_affiliation_source
                    aff_data=self.person_affs.get(account_owner_id,None)
                    if not aff_data:
                        # no valid person_affiliation_source entry (exipred ?)
                        logger.debug("no valid person_affiliation_source for person:%s (expired?)" % account_owner_id)
                        continue
                    for item in aff_data:
                        temp_aff_stat = item['affstatus']
                        temp_ou = item['ou_id']
                        temp_aff = item['affiliation']

                        if temp_aff == aff and ou == temp_ou:                            
                            if aff == co.affiliation_student:
                                if temp_aff_stat not in pay_filter:
                                    pay = False
                                    continue
                            if aff  == co.affiliation_ansatt_sito:
                                pay = False
                                continue
                            if aff == co.affiliation_ansatt:
                                pay = False
                                continue
                            if aff == co.affiliation_tilknyttet:
                                if temp_aff_stat not in pay_filter:
                                    pay = False
                                    continue
                            
                #print "PAY == %s " % pay
                if pay == False:
                    self.track.append(account)
                elif pay == True:
                    self.pay.append(account)
            except KeyError,m:
                logger.warn("account:%s has no valid owner" % account)
                continue        

        
    def list_affiliations(self):
        person_affs = dict()
        skip_source = []
        skip_source.append(co.system_lt)
        for aff in person.list_affiliations():
            # simple filtering
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
            #logger.debug("perspective code is:%s" % perspective_code) 
            try:

                ou_info=get_ouinfo(ou_id,perspective_code)
                #logger.debug("-- line check --")
                sko = ou_info['sko']
                #logger.debug("sko is:%s" % sko)
	        path=ou_info['path']
                #logger.debug("path is:%s" % path)
            except EntityExpiredError,msg:
                logger.error("person id:%s affiliated to expired ou:%s. Do not export" % (p_id,ou_id))
                continue
            except Errors.NotFoundError:
                logger.debug("OU id=%s not found on person %s. DB integrety error (this MAY be caused by parent sito ou not having stedkode)." % (ou_id,p_id))
                #sys.exit(1)

	    if source_system==co.system_sito:
		path="Norges arktiske studentsamskipnad" # TODO fix hardcoding!!
            aff_stat=num2const[aff['status']]
            affinfo = {'affstr': str(aff_stat),
		       'affiliation':aff['affiliation'],
		       'ou_id':ou_id,
		       'affstatus':aff['status'],
                       'sko': sko,
                       'path':path,
			}
	    tmp=person_affs.get(p_id,list())
            if affinfo not in tmp:
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

	    accaffs=self.account_affs.get(acc_id,None)
	    persaffs=self.person_affs.get(owner_id,None)
	    #logger.debug("%s: ACCAFF: %s" % (name,accaffs))
	    #logger.debug("%s: PERAFF: %s" % (name,persaffs))
	    costcode=""
	    if accaffs==None:
		costcode=""
	    elif persaffs==None:
		costcode=""
	    else:
		primaryaff,primary_ou=accaffs[0]
		costcode=""	
		for paff in persaffs:
		    if paff['affiliation']==primaryaff and paff['ou_id']==primary_ou:
			costcode="%s@%s" % (paff['affstr'],paff['path'])
			#logger.debug("%s: CostCode is %s" % (name,costcode)) 
	    if costcode == "":
		logger.debug("Account %s without affiliations. Do not process" % name)
		continue # account in grace to be closed, cannot calculate new status.	
		
	    if acc_id in self.pay:
  		mode="Pay"
                #logger.debug("%s has mode pay" % acc_id)
	    else:
		mode="Track"
                #logger.debug("%s has mode track" % acc_id)
            owner_type=item['owner_type']
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

	    entry=dict()
            entry['UserLogon']="%s" % (name,)
            entry['FullName'] = "%s %s" % (first_name, last_name)
	    primaryemail = self.uname2primarymail.get(item['name'],"")
            entry['Email'] = primaryemail
            entry['CostCode'] = costcode 
	    entry['Mode']=mode
            self.userexport.append(entry)


    def build_xml(self):

        logger.info("Start building pay export, writing to %s" % self.userfile_pay)
        fh_pay = file(self.userfile_pay,'w')
        xml_pay = xmlprinter(fh_pay,indent_level=2,data_mode=True,input_encoding='ISO-8859-1')
        xml_pay.startDocument(encoding='utf-8')
        xml_pay.startElement('UserList')
        logger.info("Start building track export, writing to %s" % self.userfile_track)
        fh_trk = file(self.userfile_track,'w')
        xml_trk = xmlprinter(fh_trk,indent_level=2,data_mode=True,input_encoding='ISO-8859-1')
        xml_trk.startDocument(encoding='utf-8')
        xml_trk.startElement('UserList')
        for item in self.userexport:
            #logger.debug("Processing user:%s" % item['UserLogon'])
	    if item['Mode'] == "Pay":
            	xml_pay.startElement('User')
	        xml_pay.dataElement('UserLogon',item['UserLogon'])
            	xml_pay.dataElement('CostCode',item['CostCode'])
            	xml_pay.dataElement('FullName',item['FullName'])
            	xml_pay.dataElement('Email',item['Email'])
            	xml_pay.endElement('User')
	    elif item['Mode'] == "Track":
                xml_trk.startElement('User')
	        xml_trk.dataElement('UserLogon',item['UserLogon'])
            	xml_trk.dataElement('CostCode',item['CostCode'])
            	xml_trk.dataElement('FullName',item['FullName'])
            	xml_trk.dataElement('Email',item['Email'])
            	xml_trk.endElement('User')
	    else: 
		logger.error("MODE invalid: %s" % (item['Mode'],))

        xml_pay.endElement('UserList')
        xml_pay.endDocument()
        xml_trk.endElement('UserList')
        xml_trk.endDocument()
 	logger.info("Writing done")	

#
# program usage
#
def usage(exitcode=0):
    print """Usage: [options]
    -p | --payfile filename   : write Safecom Pay users to filename
    -t | --trackfile filename : write Safecom Track user to filename
    -h | --help               : show this message
    -o | --out filname        : writes to given filename
    --logger-name name        : Use logger target name, ex console or cronjob
    --logger-level level      : level can be: DEBUG, INFO, WARNING, ERROR, CRITICAL
    """
    sys.exit(exitcode)



def main():
    global payfile
    global trackfile

    payfile=DEFAULT_PAYXML
    trackfile=DEFAULT_TRACKXML
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ho:p:t:',
                                   ['help',"out=","payfile=","trackfile="])
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt in ['-o', '--out']:
            outfile=val
        elif opt in ['-p', '--payfile']:
            payfile=val
        elif opt in ['-t', '--trackfile']:
            trackfile=val
        elif opt in ['-h', '--help']:
            usage(0)
        else:
            usage(1)

    start=mx.DateTime.now()
    worker = safecom_export(payfile,trackfile)
    worker.load_cbdata()
    worker.build_cbdata()
    worker.build_xml()
    stop=mx.DateTime.now()
    logger.info("Started %s ended %s" %  (start,stop))
    logger.info("Script running time was %s " % ((stop-start).strftime("%M minutes %S secs")))


if __name__ == '__main__':
    main()
