#!/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

# kbj005 2015.02.25: Copied from Leetah.

import os
import sys
import getopt
import mx.DateTime
import time

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError
from Cerebrum.Utils import Factory
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.Constants import _SpreadCode, _CerebrumCode

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
logger = Factory.get_logger('cronjob')
sko = Stedkode(db)
DEFAULT_OUTPUT = os.path.join(cereconf.DUMPDIR, "safecom","safecom_%s.xml" % time.strftime("%Y%m%d"))

__filename__=os.path.basename(sys.argv[0])
__doc__ = """

Usage %s options
options is

   -o | --output File to write to. Default is %s
   --logger-name <name>  : Which logger to use
   --logger-level <name  : Which loglevel to use

""" % (__filename__, DEFAULT_OUTPUT)


def write_export(spread, output):

    logger.info("Caching names")
    pe = Factory.get('Person')(db)
    cached_names = pe.getdict_persons_names(source_system=co.system_cached, name_types=(co.name_first,co.name_last))

    logger.info("Caching OU names and ou 2 stedkode mappings")
    ou = Factory.get("OU")(db)
    OU2Stedkodemap = dict()
    OU2name = dict()
    for row in sko.get_stedkoder():
        #print "adding:%02d%02d%02d to ou list" % (row['fakultet'],row['institutt'],row['avdeling'])
        OU2Stedkodemap[int(row["ou_id"])] = ("%02d%02d%02d" % ( int(row["fakultet"]),
                                                                int(row["institutt"]),
                                                                int(row["avdeling"])))
        sko.clear()
        try:
            sko.find(int(int(row["ou_id"])))
        except EntityExpiredError:
            logger.warn("ou:%s is expired. not exported" % row['ou_id'])
            continue
        OU2name[int(row["ou_id"])] = sko.get_name_with_language(co.ou_name_display, co.language_nb, default='')
    for i in OU2Stedkodemap:
        if i == '321400':
            print "### %s ###" % i
        #print i
    logger.info("Getting constant mappings")
    num2const = dict()
    for c in dir(co):
        tmp = getattr(co, c)
        if isinstance(tmp, _CerebrumCode):
            num2const[int(tmp)] = tmp

    logger.info("Getting person affiliation to status map")
    aff_list = pe.list_affiliations()
    aff_map = dict()
    for aff in aff_list:
        aux = (aff['person_id'], aff['ou_id'], aff['affiliation'])
        if aux in aff_map and num2const[aff['status']] != aff_map[aux]:
            logger.warn("Overwriting affiliation status %s for person %s with new status %s" % (aff_map[aux], aff['person_id'], num2const[aff['status']]))
        aff_map[aux] = num2const[aff['status']]

    logger.info("Getting accounts with spread %s" % (spread))
    ac = Factory.get('Account')(db)
    account_list = ac.list_all_with_spread(spread)

    logger.info("Processing and writing account list")



    fp = file(output,'w')
    xml = xmlprinter(fp,indent_level=2,data_mode=True,input_encoding='ISO-8859-1')
    xml.startDocument(encoding='utf-8')

    xml.startElement('UserList')


    for account in account_list:
        ac.clear()
        ac.find(account['entity_id'])

        name = cached_names.get(ac.owner_id, None)
        first_name = ""
        last_name = ""
        if name is not None:
            first_name = name.get(co.name_first)
            last_name = name.get(co.name_last)

        mail = ""
        try:
            mail = ac.get_primary_mailaddress()
        except:
            logger.warn("User %s lacks primary mail address" % (ac.account_name))

        primary_aff = None
        sko_sted = "000000"
        skoname = "N/A"
        aff_str = "N/A"

        try:
            primary_aff = ac.get_account_types(owner_id = ac.owner_id, filter_expired = False)[0]
        except IndexError:
            logger.warn("Affiliation_dropped for %s. No affiliation found" % (ac.account_name))

        if primary_aff is not None:
            try:
                sko_sted = OU2Stedkodemap[primary_aff['ou_id']]
                skoname = OU2name[primary_aff['ou_id']]
            except KeyError:
                logger.warn("SKO dropped for: %s. Invalid OU in primary affiliation: %s" % (ac.account_name, primary_aff['ou_id']))

        if primary_aff is not None:
            try:
                aff = (primary_aff['person_id'], primary_aff['ou_id'], primary_aff['affiliation'])
                aff_str = aff_map[aff]
            except KeyError:
                logger.warn("Affiliation string dropped for: %s. Invalid affiliation: %s" % (ac.account_name, aff))

        xml.startElement('User')
        xml.dataElement('UserLogon', ac.account_name)
        xml.dataElement('FullName', "%s %s" % (first_name, last_name))
        xml.dataElement('EMail', mail)
        xml.dataElement('CostCode', "%s@%s" % (aff_str, sko_sted))
        xml.endElement('User')

    xml.endElement('UserList')
    xml.endDocument()

    logger.info("Finished writing export file - %d records written" % (len(account_list)))


def usage(exit_code=0,m=None):
    if m:
        print m
    print __doc__
    sys.exit(exit_code)
    

def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'o:h',
                                  ['output','help'])
    except getopt.GetoptError,m:
        usage(1,m)

    spread = co.spread_uit_ad_account
    output = DEFAULT_OUTPUT
    for opt,val in opts:
        if opt in('-o','--output'):
            output = val
        if opt in('-h','--help'):
            usage()

    write_export(spread, output)


if __name__=='__main__':
    main()
