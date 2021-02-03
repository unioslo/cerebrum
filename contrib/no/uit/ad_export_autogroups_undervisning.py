#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
"""
This script creates dump of Fronter groups from BAS to an XML file
that can be imported into Active Directory
"""
from __future__ import unicode_literals

import argparse
import locale
import logging

import cereconf
from Cerebrum import logutils
from Cerebrum.Utils import Factory
from Cerebrum.extlib.xmlprinter import xmlprinter
from Cerebrum.modules.no.uit import access_FS
from Cerebrum.utils.date import now
from Cerebrum.utils.date_compat import to_mx_format
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)

# FIXME: Move to cereconf
autogroups_maildomain = "auto.uit.no"

# needed to get corret lower/upper casing of norwegian characters
locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

# Populer dicter for "emnekode -> emnenavn" og "fakultet ->
# [emnekode ...]".
emne_info = {}
stprog_info = {}
fak_emner = {}

# resulting groups dict
group_dict = dict()

# common prefix for all Fronter groups in cerebrum
fg_prefix = "uit.no:fs"


@memoize
def get_skoinfo(db, co, fak, inst, avd):
    # Two digit stings each

    logger.debug("Enter get_skoinfo with sko=%s%s%s", fak, inst, avd)
    ou = Factory.get('OU')(db)
    ou.clear()
    ou.find_stedkode(fakultet=fak, institutt=inst, avdeling=avd,
                     institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
    res = dict()
    res['name'] = ou.get_name_with_language(co.ou_name, co.language_nb,
                                            default='')
    res['short_name'] = ou.get_name_with_language(co.ou_name_short,
                                                  co.language_nb, default='')
    res['acronym'] = ou.get_name_with_language(co.ou_name_acronym,
                                               co.language_nb, default='')
    perspective = co.perspective_fs
    root = False
    acrolist = list()
    acrolist.append(res['acronym'])
    while not root:
        currentid = ou.entity_id
        parentid = ou.get_parent(perspective)
        if parentid is not None:
            ou.clear()
            ou.find(parentid)
            acrolist.append(ou.get_name_with_language(co.ou_name_acronym,
                                                      co.language_nb,
                                                      default=''))
        else:
            root = currentid
    acrolist.reverse()
    res['path'] = ".".join(acrolist)
    return res


def get_undenh_file(xmlfile):
    logger.debug("Parsing %s ", xmlfile)

    def finn_emne_info(element, attrs):
        # if element <> 'undenhet':
        if element != 'enhet':
            return
        emnenavnfork = attrs['emnenavnfork']
        emnenavn = attrs['emnenavn_bokmal']
        emnekode = attrs['emnekode'].lower()
        faknr = attrs['faknr_kontroll']
        instnr = attrs['instituttnr_kontroll']
        avdnr = attrs['gruppenr_kontroll']
        emne_info[emnekode] = {'navn': attrs['emnenavn_bokmal'],
                               'fak': faknr,
                               'inst': instnr,
                               'avd': avdnr,
                               'emnenavnfork': emnenavnfork,
                               'emnenavn': emnenavn
                               }
        fak_emner.setdefault(faknr, []).append(emnekode)

    access_FS.underv_enhet_xml_parser(xmlfile, finn_emne_info)


def get_studieprog_file(xmlfile):
    logger.debug("Parsing %s ", xmlfile)

    def finn_stprog_info(element, attrs):
        if element == 'studprog':
            stprog = attrs['studieprogramkode'].lower()
            # stprog=stprog.decode('iso-8859-1').encode('utf-8')
            faknr = attrs['faknr_studieansv']
            instnr = attrs['instituttnr_studieansv']
            avdnr = attrs['gruppenr_studieansv']
            navn = attrs['studieprognavn']
            stprog_info[stprog] = {'fak': faknr,
                                   'inst': instnr,
                                   'avd': avdnr,
                                   'navn': navn
                                   }

    access_FS.studieprog_xml_parser(xmlfile, finn_stprog_info)


uname2accid = dict()
accid2uname = dict()


def get_ad_accounts(co, ac):
    logger.info("Retreiving active accounts with AD spread")
    for acc in ac.search(spread=co.spread_uit_ad_account):
        # if acc['account_id'] not in has_aff:
        #    continue
        uname2accid[acc['name']] = acc['account_id']
        accid2uname[acc['account_id']] = acc['name']
    logger.debug("loaded %d accounts from cerebrum", len(uname2accid))


def is_this_or_next_semester(group_name):
    this_sem, next_sem = access_FS.get_semester()
    this_sem_yr, this_sem_sem = this_sem
    next_sem_yr, next_sem_sem = next_sem

    this_sem_str = this_sem_sem + ':' + this_sem_yr
    next_sem_str = next_sem_sem + ':' + next_sem_yr

    if (this_sem_str in group_name) or (next_sem_str in group_name):
        return True
    else:
        return False


def get_undenh_groups(db, co, ac, gr):
    grp_search_term = "%s:kurs*:student" % fg_prefix
    logger.debug("Search for %s", grp_search_term)
    groups = gr.search(name=grp_search_term)
    for group in groups:
        gname = group['name'].replace("%s:" % fg_prefix, '')
        if not is_this_or_next_semester(gname):
            continue

        members = gr.search_members(group_id=group['group_id'])
        member_list = list()
        for member in members:
            uname = accid2uname.get(member['member_id'], "")
            if uname == "":
                logger.error(
                    "group %s has member %s, that is not in usercache",
                    gname, member)
            else:
                member_list.append(uname)
        if len(member_list) == 0:
            logger.warn("No members in group %s (%s)",
                        group['group_id'], group['name'])
            continue

        # gname should look like this now
        # "kurs:186:bed-2049:1:v�r:2018:1:student"
        (kurs, org, emnekode, versjonskode, sem, aar, terminkode,
         rolle) = gname.split(":")

        ad_commonname = ".".join(
            ("emner", emnekode, aar, sem, versjonskode, terminkode, rolle))
        # ad_commonname should look like "emner.bed-2049.2018.v�r.1.1.student"
        ad_samaccountname = ad_commonname
        email_lp = ac.wash_email_local_part(ad_samaccountname)
        ad_samaccountname = email_lp
        ad_mailnickname = ".".join(
            (emnekode, aar, sem, versjonskode, terminkode, rolle))
        ad_email = "@".join((email_lp, autogroups_maildomain))
        try:
            ad_descr = "Studenter emne %s (%s) %s/%s Ver(%s) Termin(%s)" % (
                emnekode.upper(), emne_info[emnekode]['emnenavn'], aar, sem,
                versjonskode, terminkode)
        except KeyError:
            logger.debug(
                "Emnekode: %s does not exist in undenh file. "
                "Continue to next entry", emnekode)
            continue
        ad_displayname = ad_descr
        fak = emne_info[emnekode]['fak']
        inst = emne_info[emnekode]['inst']
        avd = emne_info[emnekode]['avd']
        skoinfo = get_skoinfo(db, co, fak, inst, avd)

        logger.debug("Group:%s, emne:%s, CN:%s, mail=%s, descr=%s",
                     gname, emnekode, ad_commonname, ad_email, ad_descr)
        group_dict[gname] = {'name': ad_commonname,
                             'samaccountname': ad_samaccountname,
                             'mail': ad_email,
                             'description': ad_descr,
                             'displayname': ad_displayname,
                             'members': ",".join(member_list),
                             'mailNickName': ad_mailnickname,
                             'extensionAttribute1': kurs,  # undenh
                             'extensionAttribute2': emnekode,
                             'extensionAttribute3': aar,  # �r
                             'extensionAttribute4': sem,  # sem
                             'extensionAttribute5': versjonskode,
                             'extensionAttribute6': terminkode,
                             'extensionAttribute7': rolle,
                             'extensionAttribute8': emne_info[emnekode][
                                 'emnenavn'],
                             'extensionAttribute9': emne_info[emnekode][
                                 'emnenavnfork'],
                             'extensionAttribute10': skoinfo['name'],
                             'extensionAttribute11': skoinfo['acronym'],
                             'extensionAttribute12': skoinfo['path'],
                             # 'extensionAttribute13' :'',
                             # 'extensionAttribute14' :'',
                             # 'extensionAttribute15' :''
                             }


def get_studieprogramgroups(db, co, ac, gr):
    grp_search_term = "%s:kull*:student" % fg_prefix
    logger.debug("Search term: %s", grp_search_term)
    groups = gr.search(name=grp_search_term)
    for group in groups:
        gname = group['name'].replace("%s:" % fg_prefix, '')
        # gname should look like this now "kull:barock:h�st:2013:student"
        (kull, stprogkode, sem, aar, rolle) = gname.split(":")
        kull = 'studieprogram'  # type should be "studieprogram", not "kull"

        # Skip this group if it isn't in stprog_info
        # Note: this implies a mismatch between the database and
        # studieprogfile.
        if stprogkode not in stprog_info.keys():
            logger.warning("Group %s is missing in stprog_info",
                           group['group_id'])
            continue

        ad_commonname = ".".join((kull, stprogkode, aar, sem, rolle))
        ad_samaccountname = ad_commonname
        email_lp = ac.wash_email_local_part(ad_samaccountname)
        ad_samaccountname = email_lp
        ad_mailnickname = ac.wash_email_local_part(
            ".".join((stprogkode, aar, sem, rolle)))
        ad_email = "@".join((email_lp, autogroups_maildomain))
        ad_descr = "Studenter studieprogram %s (%s) kull %s/%s" % (
            stprogkode.upper(), stprog_info[stprogkode]['navn'], aar, sem)
        ad_displayname = ad_descr
        logger.debug("Group:%s, stprog:%s, CN:%s, mail=%s, descr=%s",
                     gname, stprogkode, ad_commonname, ad_email, ad_descr)

        members = gr.search_members(group_id=group['group_id'])
        member_list = list()
        for member in members:
            # Check if member['member_id'] is in accid2uname before appending
            # it to member_list
            uname = accid2uname.get(member['member_id'], "")
            if uname == "":
                logger.error("Group %s has member %s that is not in usercache",
                             gname, member)
            else:
                logger.debug("--->Adding %s", uname)
                member_list.append(uname)
        if len(member_list) == 0:
            logger.warn("No members in group %s (%s)",
                        group['group_id'], group['name'])
            continue

        fak = stprog_info[stprogkode]['fak']
        inst = stprog_info[stprogkode]['inst']
        avd = stprog_info[stprogkode]['avd']
        skoinfo = get_skoinfo(db, co, fak, inst, avd)
        group_dict[gname] = {'name': ad_commonname,
                             'samaccountname': ad_samaccountname,
                             'mail': ad_email,
                             'description': ad_descr,
                             'displayname': ad_displayname,
                             'members': ",".join(member_list),
                             'mailNickname': ad_mailnickname,

                             'extensionAttribute1': kull,
                             'extensionAttribute2': stprogkode,
                             'extensionAttribute3': aar,
                             'extensionAttribute4': sem,
                             'extensionAttribute5': '',
                             'extensionAttribute6': '',
                             'extensionAttribute7': rolle,
                             'extensionAttribute8': stprog_info[stprogkode][
                                 'navn'],
                             'extensionAttribute9': '',
                             'extensionAttribute10': skoinfo['name'],
                             'extensionAttribute11': skoinfo['acronym'],
                             'extensionAttribute12': skoinfo['path'],
                             # 'extensionAttribute13' :'',
                             # 'extensionAttribute14' :'',
                             # 'extensionAttribute15' :''
                             }


def aggregate_studieprogram_groups(ac):
    stprogs = dict()
    fakprogs = dict()
    agrgroup_dict = dict()

    for gname, gdata in group_dict.iteritems():
        if gdata['extensionAttribute1'] != "studieprogram":
            continue
        key = gdata['extensionAttribute2']
        data = gdata['samaccountname']
        stprogs.setdefault(key, list()).append(data)

        fakkey = gdata['extensionAttribute12']
        items = fakkey.split(".")
        # add this prog to current org level and all parents
        for i in range(len(items)):
            proglevel = ".".join(items[0:i + 1])
            fakprogs.setdefault(proglevel, list()).append(data)

    for stprogkode, gdata in stprogs.iteritems():
        logger.debug("AGGRPROG: stprogkode=%s", stprogkode)
        washed_stprogkode = ac.wash_email_local_part(stprogkode)
        ad_commonname = "studieprogram.%s.studenter" % washed_stprogkode
        ad_samaccountname = ad_commonname
        ad_email = "@".join((ad_samaccountname, "auto.uit.no"))
        ad_descr = "Studenter studieprogram %s (%s) Alle kull" % (
            stprogkode.upper(), stprog_info[stprogkode]['navn'])
        ad_displayname = ad_descr
        ad_mailnickname = "%s.studenter" % washed_stprogkode

        agrgroup_dict[stprogkode] = {
            'name': ad_commonname,
            'samaccountname': ad_samaccountname,
            'mail': ad_email,
            'description': ad_descr,
            'displayname': ad_displayname,
            'members': ",".join(gdata),
            'mailNickname': ad_mailnickname,
            # 'extensionAttribute1' : type,
            # 'extensionAttribute2' : stprogkode,
            # 'extensionAttribute3' : aar,
            # 'extensionAttribute4' : sem,
            # 'extensionAttribute5' : '',
            # 'extensionAttribute6' : '',
            # 'extensionAttribute7' : rolle,
            # 'extensionAttribute8' : stprog_info[stprogkode]['navn'],
            # 'extensionAttribute9' : '',
            # 'extensionAttribute10': skoinfo['name'],
            # 'extensionAttribute11': skoinfo['acronym'],
            # 'extensionAttribute12': skoinfo['path'],
            # 'extensionAttribute13': '',
            # 'extensionAttribute14': '',
            # 'extensionAttribute15': ''
        }

    for fakpath, gdata in fakprogs.iteritems():
        logger.debug("FAKPROG: fakpath=%s", fakpath)
        washed_fakpath = ac.wash_email_local_part(fakpath)
        ad_commonname = "studieprogram.%s.studenter" % washed_fakpath
        ad_samaccountname = ad_commonname
        ad_email = "@".join((ad_samaccountname, "auto.uit.no"))
        ad_descr = "Studenter studieprogrammer ved %s" % (fakpath,)
        ad_displayname = ad_descr
        ad_mailnickname = "%s.studenter" % washed_fakpath
        agrgroup_dict[fakpath] = {
            'name': ad_commonname,
            'samaccountname': ad_samaccountname,
            'mail': ad_email,
            'description': ad_descr,
            'displayname': ad_displayname,
            'members': ",".join(gdata),
            'mailNickname': ad_mailnickname,
            # 'extensionAttribute1' : type,
            # 'extensionAttribute2' : stprogkode,
            # 'extensionAttribute3' : aar,
            # 'extensionAttribute4' : sem,
            # 'extensionAttribute5' : '',
            # 'extensionAttribute6' : '',
            # 'extensionAttribute7' : rolle,
            # 'extensionAttribute8' : stprog_info[stprogkode]['navn'],
            # 'extensionAttribute9' : '',
            # 'extensionAttribute10': skoinfo['name'],
            # 'extensionAttribute11': skoinfo['acronym'],
            # 'extensionAttribute12': skoinfo['path'],
            # 'extensionAttribute13': '',
            # 'extensionAttribute14': '',
            # 'extensionAttribute15': ''
        }
    return agrgroup_dict


def write_xml(agrgroup_dict, xmlfile):
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
                <!-- this name will show in Addressbook -->
                <displayname>displayname of group</displayname>
                <member>usera,userb,userc,userd</member>
                <mail>samaccountname@auto.uit.no</mail>
                <!-- startswith emnekode/progkode (searchable in adrbook) -->
                <mailnickname>alias@auto.uit.no</mailnickname>
                <!-- undenh or studierprogram -->
                <extensionAttribute1>type</extensionAttribute1>
                <!-- emnekode or studieprogramkode -->
                <extensionAttribute2>emnekode</extensionAttribute2>
                <!-- year -->
                <extensionAttribute3>2014</extensionAttribute3>
                <!-- semester -->
                <extensionAttribute4>høst</extensionAttribute4>
                <!-- only for emner -->
                <extensionAttribute5>versjonskode</extensionAttribute5>
                <!-- only for emner -->
                <extensionAttribute6>terminkode</extensionAttribute6>
                <!-- only student at present -->
                <extensionAttribute7>rolle</extensionAttribute7>
                <!-- full name of emne or studieprogram -->
                <extensionAttribute8>emne or stprognavn</extensionAttribute8>
                <!-- short versjon of nr 8 -->
                <extensionAttribute9>
                    emne or studieprog forkortelse
                </extensionAttribute9>
                <!-- ansvarlig enhets fulle navn -->
                <extensionAttribute10>
                    Institutt for samfunnsmedisin
                </extensionAttribute10>
                <!-- ansvarlig enhets forkortelse -->
                <extensionAttribute11>ISM</extensionAttribute11>
                <!-- ansvarlig enhets plassering i org -->
                <extensionAttribute12>UiT.Helsefak.ISM</extensionAttribute12>
                <extensionAttribute13></extensionAttribute13>
                <extensionAttribute14><extensionAttribute14>
                <extensionAttribute15></extensionAttribute15>
            </group>
            <group>
            ...
            </group>
        </groups>
    </data>
    </xml>
    """

    logger.info("Writing results to '%s'", xmlfile)
    fh = open(xmlfile, 'w')
    xml = xmlprinter(fh, indent_level=2, data_mode=True,
                     input_encoding='ISO-8859-1')
    xml.startDocument(encoding='utf-8')
    xml.startElement('data')
    xml.startElement('properties')
    xml.dataElement('tstamp', to_mx_format(now()))
    xml.endElement('properties')
    xml.startElement('groups')
    for grpname, gdata in group_dict.iteritems():
        xml.startElement('group')
        logger.debug("Writing %s", grpname)
        keys = gdata.keys()
        keys.sort()
        for k in keys:
            xml.dataElement(k, gdata[k])
        xml.endElement('group')

    for grpname, gdata in agrgroup_dict.iteritems():
        xml.startElement('group')
        logger.debug("Writing %s", grpname)
        keys = gdata.keys()
        keys.sort()
        for k in keys:
            xml.dataElement(k, gdata[k])
        xml.endElement('group')

    xml.endElement('groups')
    xml.endElement('data')
    xml.endDocument()
    logger.info("Writing results to '%s' done", xmlfile)


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--studieprogfile',
        required=True,
        help='Read FS study programs (studieprogrammer) from %(metavar)s',
        metavar='<file>',
    )
    parser.add_argument(
        '--undenhfile',
        required=True,
        help='Read FS course units (undervisningsenheter) from %(metavar)s',
        metavar='<file>',
    )
    parser.add_argument(
        '--exportfile',
        required=True,
        help='Write XML to %(metavar)s',
        metavar='<file>',
    )

    logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    logutils.autoconf('cronjob', args)

    logger.debug("setting studieprogfile to '%s'", args.studieprogfile)
    logger.debug("setting undenhfile to '%s'", args.undenhfile)
    logger.debug("setting exportfile to '%s'", args.exportfile)
    start = now()

    db = Factory.get('Database')()
    ac = Factory.get('Account')(db)
    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)

    db.cl_init(change_program='ad_export_autogroups_undervisning')

    get_undenh_file(xmlfile=args.undenhfile)
    get_studieprog_file(xmlfile=args.studieprogfile)
    get_ad_accounts(co, ac)
    get_undenh_groups(db, co, ac, gr)
    get_studieprogramgroups(db, co, ac, gr)
    agrgroup_dict = aggregate_studieprogram_groups(ac)
    write_xml(agrgroup_dict, args.exportfile)

    stop = now()
    logger.debug("Started %s, ended %s", start, stop)
    logger.debug("Script running time was %s", str(stop - start))


if __name__ == '__main__':
    main()
