#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Tromso, Norway
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


progname = __file__.split("/")[-1]
__doc__="""
This script creates dump of Fronter groups from BAS to an XML file
that can be imported into Active Directory

usage:: %s [options]

options is
    -h | --help          : show this
    --exportfile         : filname to write resulting xml to
    --studeprogfile      : filename containing studieprog data from FS
    --undenhfile         : filename containing undervisningsenhet data from FS
    --logger-name name   : log name to use
    --logger-level level : log level to use
""" % ( progname, )

import getopt
import sys
import os
import re
from sets import Set
import mx.DateTime
import locale
from pprint import pprint
import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.modules.no.uit import access_FS
from Cerebrum.modules.no.Stedkode import Stedkode

db = Factory.get('Database')()
ac = Factory.get('Account')(db)
gr = Factory.get('Group')(db)
co = Factory.get('Constants')(db)

db.cl_init(change_program=progname)
logger=Factory.get_logger('console')

# Define default file locations
default_log_dir = os.path.join(cereconf.CB_PREFIX,'var','log')
default_export_file = os.path.join(cereconf.DUMPDIR,'AD','autogroups-undervisning.xml')
default_studieprog_file = os.path.join(cereconf.DUMPDIR, 'FS', 'studieprogrammer.xml')
default_undenh_file = os.path.join(cereconf.DUMPDIR, 'FS', 'undervisningenheter.xml')

#FIXME: Move to cereconf
autogroups_maildomain="auto.uit.no"

#needed to get corret lower/upper casing of norwegian characters
locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

# Populer dicter for "emnekode -> emnenavn" og "fakultet ->
# [emnekode ...]".
emne_info = {}
stprog_info = {}
fak_emner = {}

#resulting groups dict
group_dict=dict()
agrgroup_dict=dict()

# common prefix for all Fronter groups in cerebrum
fg_prefix="internal:uit.no:fs:186"

def get_skoinfo(fak,inst,avd):
    # Two digit stings each

    logger.debug("Enter get_skoinfo with sko=%s%s%s" % (fak,inst,avd))
    #sko=Factory.get('Stedkode')(db)
    sko = Stedkode(db)
    sko.clear()
    sko.find_stedkode(fakultet=fak,institutt=inst,avdeling=avd,institusjon=186) #TODO 186 from config
    res=dict()
    res['name']=str(sko.get_name_with_language(co.ou_name, co.language_nb, default=''))
    res['short_name']=str(sko.get_name_with_language(co.ou_name_short, co.language_nb, default=''))
    res['acronym']=str(sko.get_name_with_language(co.ou_name_acronym, co.language_nb, default=''))    
    perspective=co.perspective_fs
    root=False
    acrolist=list()
    acrolist.append(res['acronym'])
    while not root:
        currentid=sko.entity_id
        parentid=sko.get_parent(perspective)
        if parentid != None:
            sko.clear()
            sko.find(parentid)
            acrolist.append(str(sko.get_name_with_language(co.ou_name_acronym, co.language_nb, default='')))
        else:
            root=currentid
    acrolist.reverse()
    res['path']=".".join(acrolist)
    return res
get_skoinfo=memoize(get_skoinfo)


def GetUndenhFile(xmlfile):
    logger.debug("Parsing %s "% (xmlfile,))
    def finn_emne_info(element, attrs):
        #if element <> 'undenhet':
        if element <> 'enhet':
            return
        emnenavnfork = attrs['emnenavnfork']
        emnenavn=attrs['emnenavn_bokmal']
        emnekode = attrs['emnekode'].lower()
        faknr=attrs['faknr_kontroll']
        instnr=attrs['instituttnr_kontroll']
        avdnr=attrs['gruppenr_kontroll']
        emne_info[emnekode] = {'navn':attrs['emnenavn_bokmal'],
                               'fak':faknr,
                               'inst':instnr, 
                               'avd':avdnr,
                               'emnenavnfork' : emnenavnfork,
                               'emnenavn':emnenavn
                               } 
        fak_emner.setdefault(faknr, []).append(emnekode)
        
    access_FS.underv_enhet_xml_parser(xmlfile,finn_emne_info)

    
def GetStudieprogFile(xmlfile):
    logger.debug("Parsing %s "% (xmlfile,))
    def finn_stprog_info(element, attrs):
        if element == 'studprog':
            stprog = attrs['studieprogramkode'].lower()
            #stprog=stprog.decode('iso-8859-1').encode('utf-8')
            faknr = attrs['faknr_studieansv']
            instnr = attrs['instituttnr_studieansv']
            avdnr = attrs['gruppenr_studieansv']
            navn= attrs['studieprognavn']
            stprog_info[stprog] = {'fak':faknr,
                                   'inst':instnr,
                                   'avd':avdnr,
							       'navn':navn
							      }
    access_FS.studieprog_xml_parser(xmlfile,finn_stprog_info)

uname2accid=dict()
accid2uname=dict()
def GetADAccounts():
    logger.info("Retreiving active accounts with AD spread")
    for acc in ac.search(spread=co.spread_uit_ad_account):
        #if acc['account_id'] not in has_aff:
        #    logger.debug("Skipping account %s, no active affiliations" % (acc['name'],))
        #    continue
        uname2accid[acc['name']]=acc['account_id']
        accid2uname[acc['account_id']]=acc['name']
    logger.debug("loaded %d accounts from cerebrum" % len(uname2accid))

 
def GetUndenhGroups():
    grp_search_term="%s:undenh*:student" % fg_prefix
    logger.debug("Search for %s" % grp_search_term)
    groups=gr.search(name=grp_search_term)
    for group in groups:
        members=gr.search_members(group_id=group['group_id'])
        member_list=list()
        for member in members:
            uname=accid2uname.get(member['member_id'],"")
            if (uname == ""):
                gname=group['name'].replace("%s:" % fg_prefix,'')
                logger.error("group %s has member %s, that is not in usercache" % (gname,member))
            else:
                member_list.append(uname)
        if len(member_list)==0:
                logger.warn("No members in group %s" % group['group_id'])
                continue

        gname=group['name'].replace("%s:" % fg_prefix,'')
        # gname should look like this now "undenh:2013:h\xf8st:inf-3982:1:1:student'"
        parts=gname.split(":")
        (type,aar,sem,emnekode,versjonskode,terminkode,rolle)=gname.split(":")
        ad_commonname= ".".join(("emner",emnekode,aar,sem,versjonskode,terminkode,rolle))
        # ad_commonname should look like 'emner.inf-3982.2013.høst.1.1.student'
        ad_samaccountname=ad_commonname
        email_lp=ac.wash_email_local_part(ad_samaccountname)
        ad_samaccountname=email_lp
        ad_mailnickname=".".join((emnekode,aar,sem,versjonskode,terminkode,rolle))
        ad_email="@".join((email_lp,autogroups_maildomain))
        ad_descr="Studenter emne %s (%s) %s/%s Ver(%s) Termin(%s)" % (emnekode.upper(), emne_info[emnekode]['emnenavn'], aar,sem,versjonskode,terminkode)
        ad_displayname=ad_descr
        fak=str(emne_info[emnekode]['fak'])
        inst=str(emne_info[emnekode]['inst'])
        avd=str(emne_info[emnekode]['avd'])
        sko="%s%s%s" % (fak,inst,avd)
        skoinfo=get_skoinfo(fak,inst,avd)

        logger.debug("Group:%s, emne:%s, CN:%s, mail=%s, descr=%s" %  (gname,emnekode,ad_commonname,ad_email,ad_descr))
        group_dict[gname]={'name'          : ad_commonname,
					       'samaccountname': ad_samaccountname,
                           'mail'          : ad_email,
					       'description'   : ad_descr,
                           'displayname'   : ad_displayname,
					       'members'       : ",".join(member_list),
                           'mailNickName'  : ad_mailnickname,
                           'extensionAttribute1': type, #undenh 
                           'extensionAttribute2': emnekode,
                           'extensionAttribute3': aar,  # år 
                           'extensionAttribute4': sem,  # sem
                           'extensionAttribute5': versjonskode,
                           'extensionAttribute6': terminkode,
                           'extensionAttribute7': rolle,
                           'extensionAttribute8': emne_info[emnekode]['emnenavn'],
                           'extensionAttribute9': emne_info[emnekode]['emnenavnfork'],
                           'extensionAttribute10' :skoinfo['name'],
                           'extensionAttribute11' :skoinfo['acronym'],
                           'extensionAttribute12' :skoinfo['path'],
                           #'extensionAttribute13' :'',
                           #'extensionAttribute14' :'',
                           #'extensionAttribute15' :''
					       }
        

def GetStudieprogramgroups():
    grp_search_term="%s:studieprogram*:student" % fg_prefix
    logger.debug("Search term: %s" % grp_search_term)
    groups=gr.search(name=grp_search_term)
    for group in groups:
        gname=group['name'].replace("%s:" % fg_prefix,'')
        # gname should look like this now "studieprogram:ph-far:studiekull:2009:høst:student"
        (type,stprogkode,xx,aar,sem,rolle)=gname.split(":")

        # Skip this group if it isn't in stprog_info
        # Note: this implies a mismatch between the database and studieprogfile.
        if stprogkode not in stprog_info.keys():
            logger.warning("Group %s is missing in stprog_info", group['group_id'])
            continue

        ad_commonname= ".".join((type,stprogkode,aar,sem,rolle))
        ad_samaccountname=ad_commonname
        email_lp=ac.wash_email_local_part(ad_samaccountname)
        ad_samaccountname=email_lp
        ad_mailnickname=ac.wash_email_local_part(".".join((stprogkode,aar,sem,rolle)))        
        ad_email="@".join((email_lp,autogroups_maildomain))
        ad_descr="Studenter studieprogram %s (%s) kull %s/%s" % (stprogkode.upper(), stprog_info[stprogkode]['navn'], aar,sem)
        ad_displayname=ad_descr
        logger.debug("Group:%s, stprog:%s, CN:%s, mail=%s, descr=%s" %  (gname,stprogkode,ad_commonname,ad_email,ad_descr))

        members=gr.search_members(group_id=group['group_id'])
        member_list=list()
        for member in members:
            # Check if member['member_id'] is in accid2uname before appending it to member_list
            uname = accid2uname.get(member['member_id'], "")
            if (uname == ""):
              logger.error("Group %s has member %s that is not in usercache", gname, member)
            else:
              logger.debug("--->Adding %s" % (uname))
              member_list.append(uname)

        fak=str(stprog_info[stprogkode]['fak'])
        inst=str(stprog_info[stprogkode]['inst'])
        avd=str(stprog_info[stprogkode]['avd'])
        skoinfo=get_skoinfo(fak,inst,avd)
        group_dict[gname]={'name'          : ad_commonname,
					       'samaccountname': ad_samaccountname,
                           'mail'          : ad_email,
					       'description'   : ad_descr,
                           'displayname'   : ad_displayname,
					       'members'       : ",".join(member_list),
                           'mailNickname'  : ad_mailnickname,

                           'extensionAttribute1' : type,
                           'extensionAttribute2' : stprogkode,
                           'extensionAttribute3' : aar,
                           'extensionAttribute4' : sem,
                           'extensionAttribute5' : '',
                           'extensionAttribute6' : '',
                           'extensionAttribute7' : rolle,
                           'extensionAttribute8': stprog_info[stprogkode]['navn'],
                           'extensionAttribute9' : '',
                           'extensionAttribute10':skoinfo['name'],
                           'extensionAttribute11':skoinfo['acronym'],
                           'extensionAttribute12':skoinfo['path'],
                           #'extensionAttribute13' :'',
                           #'extensionAttribute14' :'',
                           #'extensionAttribute15' :''
					       }


def aggregateStudieprogramgroups():

    stprogs=dict()
    fakprogs=dict()
    import pprint
    pp=pprint.PrettyPrinter(indent=4)

    for gname,gdata in group_dict.iteritems():
        if gdata['extensionAttribute1'] != "studieprogram":
            continue
        key=gdata['extensionAttribute2']
        data=gdata['samaccountname']
        stprogs.setdefault(key, list()).append(data)

        fakkey=gdata['extensionAttribute12']
        items=fakkey.split(".")
        # add this prog to current org level and all parents
        for i in range(len(items)):
            proglevel=".".join(items[0:i+1])
            fakprogs.setdefault(proglevel, list()).append(data)

    #print pp.pprint(stprogs)
    #print pp.pprint(fakprogs)

    for stprogkode,gdata in stprogs.iteritems():
        logger.debug("AGGRPROG: stprogkode=%s" % (stprogkode,) )
        washed_stprogkode=ac.wash_email_local_part(stprogkode)        
        ad_commonname="studieprogram.%s.studenter" % (washed_stprogkode)
        ad_samaccountname=ad_commonname
        ad_email="@".join((ad_samaccountname,"auto.uit.no"))
        ad_descr="Studenter studieprogram %s (%s) Alle kull" % (stprogkode.upper(), stprog_info[stprogkode]['navn'])
        ad_displayname=ad_descr
        ad_mailnickname="%s.studenter" % (washed_stprogkode)


        agrgroup_dict[stprogkode]={
                           'name'          : ad_commonname,
					       'samaccountname': ad_samaccountname,
                           'mail'          : ad_email,
					       'description'   : ad_descr,
                           'displayname'   : ad_displayname,
					       'members'       : ",".join(gdata),
                           'mailNickname'  : ad_mailnickname,

#                           'extensionAttribute1' : type,
#                           'extensionAttribute2' : stprogkode,
#                           'extensionAttribute3' : aar,
#                           'extensionAttribute4' : sem,
#                           'extensionAttribute5' : '',
#                           'extensionAttribute6' : '',
#                           'extensionAttribute7' : rolle,
#                           'extensionAttribute8' : stprog_info[stprogkode]['navn'],
#                           'extensionAttribute9' : '',
#                           'extensionAttribute10': skoinfo['name'],
#                           'extensionAttribute11': skoinfo['acronym'],
#                           'extensionAttribute12': skoinfo['path'],
#                           'extensionAttribute13': '',
#                           'extensionAttribute14': '',
#                           'extensionAttribute15': ''
					       }

    for fakpath,gdata in fakprogs.iteritems():
        logger.debug("FAKPROG: fakpath=%s" % (fakpath,) )
        washed_fakpath=ac.wash_email_local_part(fakpath)
        ad_commonname="studieprogram.%s.studenter" % (washed_fakpath)
        ad_samaccountname=ad_commonname
        ad_email="@".join((ad_samaccountname,"auto.uit.no"))
        ad_descr="Studenter studieprogrammer ved %s" % (fakpath,)
        ad_displayname=ad_descr
        ad_mailnickname="%s.studenter" % (washed_fakpath)
        agrgroup_dict[fakpath]={
                           'name'          : ad_commonname,
					       'samaccountname': ad_samaccountname,
                           'mail'          : ad_email,
					       'description'   : ad_descr,
                           'displayname'   : ad_displayname,
					       'members'       : ",".join(gdata),
                           'mailNickname'  : ad_mailnickname,

#                           'extensionAttribute1' : type,
#                           'extensionAttribute2' : stprogkode,
#                           'extensionAttribute3' : aar,
#                           'extensionAttribute4' : sem,
#                           'extensionAttribute5' : '',
#                           'extensionAttribute6' : '',
#                           'extensionAttribute7' : rolle,
#                           'extensionAttribute8' : stprog_info[stprogkode]['navn'],
#                           'extensionAttribute9' : '',
#                           'extensionAttribute10': skoinfo['name'],
#                           'extensionAttribute11': skoinfo['acronym'],
#                           'extensionAttribute12': skoinfo['path'],
#                           'extensionAttribute13': '',
#                           'extensionAttribute14': '',
#                           'extensionAttribute15': ''
					       }
 

def writeXML(xmlfile=default_export_file):
    """
    write results to file

    produce this:
    <xml encoding="utf-8">
    <data>
        <properties>
            <tstamp>2013-05-12 15:44</tstamp>
        </properties>
        <groups>
    	    <group>
	    	    <name>AD navn</name>
		        <samaccountname>sam_name_of_group</samaccountname>
		        <description>some descriptive text</description>
                <displayname>displayname of group</displayname>         # this name will show in Addressbook
		        <member>usera,userb,userc,userd</member>
                <mail>samaccountname@auto.uit.no</mail>
                <mailnickname>alias@auto.uit.no</mailnickname>          # startswith emnekode/stprogrkode. Easy searchable in adrbook
                <extensionAttribute1>type</extensionAttribute1>         #undenh or studierprogram
                <extensionAttribute2>emnekode</extensionAttribute2>     # emnekode or studieprogramkode 
                <extensionAttribute3>2014</extensionAttribute3>         # year  
                <extensionAttribute4>høst</extensionAttribute4>         # semester
                <extensionAttribute5>versjonskode</extensionAttribute5> # only for emner
                <extensionAttribute6>terminkode</extensionAttribute6>   # only for emner
                <extensionAttribute7>rolle</extensionAttribute7>        # only student at present
                <extensionAttribute8>emne or stprognavn</extensionAttribute8>               # full name of emne or studieprogram
                <extensionAttribute9>emne or studieprog forkortelse</extensionAttribute9>   # short versjon of nr 8
                <extensionAttribute10>Institutt for samfunnsmedisin</extensionAttribute10>  # ansvarlig enhets fulle navn
                <extensionAttribute11>ISM</extensionAttribute11>                            # ansvarlig enhets forkortelse
                <extensionAttribute12>UiT.Helsefak.ISM</extensionAttribute12>               # ansvarlig enhets plassering i org
<!--            <extensionAttribute13></extensionAttribute13>
                <extensionAttribute14><extensionAttribute14>
                <extensionAttribute15></extensionAttribute15>
-->
	        </group>
	        <group>
	        ...
	        </group>
        </groups>
    </data>
    </xml>
    """

    logger.info("Writing results to '%s'" % (xmlfile,))
    fh = open(xmlfile,'w')
    xml = xmlprinter(fh,indent_level=2,data_mode=True,input_encoding='ISO-8859-1')
    xml.startDocument(encoding='utf-8')
    xml.startElement('data')
    xml.startElement('properties')
    xml.dataElement('tstamp', str(mx.DateTime.now()))
    xml.endElement('properties')
    xml.startElement('groups')
    for grpname,gdata in group_dict.iteritems():
        xml.startElement('group')
        logger.debug("Writing %s" % grpname)
        keys=gdata.keys()
        keys.sort()
        for k in keys:
            xml.dataElement(k,gdata[k])
        xml.endElement('group')

    for grpname,gdata in agrgroup_dict.iteritems():
        xml.startElement('group')
        logger.debug("Writing %s" % grpname)
        keys=gdata.keys()
        keys.sort()
        for k in keys:
            xml.dataElement(k,gdata[k])
        xml.endElement('group')

    xml.endElement('groups')
    xml.endElement('data')
    xml.endDocument()
    logger.info("Writing results to '%s' done" % (xmlfile,))


def usage(exitcode=0,msg=None):
    if msg:
        print "Error: %s" % msg
    print __doc__
    sys.exit(exitcode)
 

def main():
    # can be overridden from commandline
    studieprogfile=default_studieprog_file
    undenhfile=default_undenh_file
    exportfile=default_export_file

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ha:',
                                   ['help','studieprogfile=','undenhfile=','exportfile='])
    except getopt.GetoptError,m:
        usage(exitcode=1,msg=m)
    for opt, val in opts:
        if opt in ['-h', '--help']:
            usage()
        elif opt in ['--studieprogfile']:
            logger.debug("setting studieprogfile to '%s'" % val)
            studieprogfile=val
        elif opt in ['--undenhfile']:
            logger.debug("setting undenhfile to '%s'" % val)
            undenhfile=val
        elif opt in ['--exportfile']:
            logger.debug("setting exportfile to '%s'" % val)
            exportfile=val
        else:
            pass

    start=mx.DateTime.now()

    GetUndenhFile(xmlfile=undenhfile)
    GetStudieprogFile(xmlfile=studieprogfile)
    GetADAccounts()
    GetUndenhGroups()
    GetStudieprogramgroups()
    aggregateStudieprogramgroups()
    writeXML(xmlfile=exportfile)
    
    stop=mx.DateTime.now()
    logger.debug("Started %s, ended %s" %  (start,stop))
    logger.debug("Script running time was %s" % ((stop-start).strftime("%M minutes %S secs")))


if __name__ == '__main__':
    main()
