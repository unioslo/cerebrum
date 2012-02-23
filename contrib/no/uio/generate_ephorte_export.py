#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2007-2011 University of Oslo, Norway
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

import getopt
import pickle
import sys
import os
import cerebrum_path
import cereconf
from mx import DateTime
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Utils import Factory, XMLHelper, SimilarSizeWriter
from Cerebrum.modules import CLHandler
from Cerebrum.modules.no.uio.Ephorte import EphorteRole
#from Cerebrum.modules.no.uio.Ephorte import EphortePermission

progname = __file__.split("/")[-1]
__doc__ = """
This script generates an XML export for ePhorte.  The XML file is read
by another cerebrum-script, which uses uses ePhortes Web-service
interface to push the data into ePhorte.  Currently little work has
been put into 'standardizing' this XML format.

Usage: %s [options]
  -h: display this message
  -f fname : output filename
  -m <email addr>: Send warnings to email addr

""" % progname

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
ephorte_role = EphorteRole(db)
#ephorte_permission = EphortePermission(db)
ou = Factory.get('OU')(db)
cl = CLHandler.CLHandler(db)

logger = Factory.get_logger("cronjob")
sko_cache = {}
feide_id_cache = {}
uname_cache = {}
primary_account_cache = {}
missing_ou_spread = []


class ExtXMLHelper(XMLHelper):
    def xmlify_tree(self, tag, dta):
        """Write a dict out in xml.  If any values are a list/tuple of
        dicts, iterate over them with contents inside a sub-tag.  I.e.
          {'foo': 'bar', 'gazonk': [{'foo': '123'}]}
        Becomes
          <TAG foo='bar'><gazonk foo='123'/></TAG>
        """

        ret = "<%s " % tag
        attrs = []
        children = []
        for k, v in dta.iteritems():
            if v is None:
                #attrs.append(k)
                pass
            elif isinstance(v, (tuple, list)):
                for t in v:
                    children.append(self.xmlify_tree(k, t))
            else:
                attrs.append("%s=%s" % (k, self.escape_xml_attr(v)))

        ret = "<%s " % tag + (" ".join(attrs))
        if children:
            ret += ">\n" + "".join(["  %s" % c for c in children])
            ret += "</%s>\n" % tag
        else:
            ret += "/>\n"
        return ret


def _get_sko(ou_id):
    ret = sko_cache.get(ou_id)
    if ret is None:
        ou.clear()
        ou.find(ou_id)
        ret = "%02i%02i%02i" % (ou.fakultet, ou.institutt, ou.avdeling)
        sko_cache[ou_id] = ret
    return ret


def _get_uname(account_id):
    ret = uname_cache.get(account_id)
    if ret is None:
        ac.clear()
        ac.find(account_id)
        ret = ac.account_name
        uname_cache[account_id] = ret
    return ret


def _get_feide_id(operator_id):
    ret = feide_id_cache.get(operator_id)
    if ret is None:
        try:
            uname = _get_uname(operator_id)
            ret = uname.upper() + "@UIO.NO"
            feide_id_cache[operator_id] = ret
        except Errors.NotFoundError:
            logger.warn("Could not find account with id %s" % (operator_id))
    return ret or ""


def _get_primary_account(person_id):
    ret = primary_account_cache.get(person_id)
    if ret is None:
        pe.clear()
        try:
            pe.find(person_id)
            account_id = pe.get_primary_account()
            ret = _get_uname(account_id)
            if ret:
                primary_account_cache[person_id] = ret
        except Errors.NotFoundError:
            logger.info("Could not find account for person %s" % person_id)
    return ret or ""


def generate_export(fname, spread=co.spread_ephorte_person):
    f = SimilarSizeWriter(fname, "w")
    f.set_size_change_limit(10)
    logger.info("Started ephorte export to %s" % fname)

    ##
    ## TODO
    ##
    ## Her må vi finne alle OU-er som skal eksporteres til ePhorte og
    ## skrive dette i xml-filen. Lagre dette som en dict på format:
    ##
    ## ous = {<sko>: {'sko': <sko>, 'akronym': '', 'short': '', 'long': '',
    ##                'parent': <parent_sko>, 'journalEnhet': ''}}
    ## ous = {}

    persons = {} 
    # Format: entity_id -> {'roles': [],
    #                       'permisions: []'
    #                       'first_name': '',
    #                       'last_name': '',
    #                       'full_name': '',
    #                       'address_text': '',
    #                       'p_o_box': '',
    #                       'postal_number': '',
    #                       'city': '',
    #                       'initials': '',
    #                       'feide_id': '',
    #                       'phone': ''}
    for row in pe.list_all_with_spread(spread):
        #persons[int(row['entity_id'])] = {'roles': [], 'permissions': []}
        persons[int(row['entity_id'])] = {'roles': [],}
    logger.info("Found %d persons with ephorte spread" % len(persons))

    # 1. Check changelog to find persons that have lost
    #    ephorte-spread. These should be marked as deleted    
    # 2. Try also to detect if a person has a new feide id, meaning
    #    that ePhorte potentially will need to set an existing account
    #    to point to this new value
    potential_changed_feideid = {}    
    logger.info("Checking changelog")
    for event in cl.get_events('eph_exp', (
        co.spread_del, co.account_type_add, co.account_type_del,
        co.account_type_mod)):
        cl.confirm_event(event)
        if event['change_type_id'] != int(co.spread_del):
            potential_changed_feideid[int(event['subject_entity'])] = True
            continue
        if persons.has_key(int(event['subject_entity'])):
            continue  # spread has been re-inserted or similar
        change_params = pickle.loads(event['change_params'])
        if change_params['spread'] == int(co.spread_ephorte_person):
            persons[int(event['subject_entity'])] = {'delete': 1}
            logger.debug("Person %s has lost ephorte_spread since last run. " %
                         event['subject_entity'] + "Set person as deletable")
    cl.commit_confirmations()

    if potential_changed_feideid:
        logger.debug("Nr of persons with potential changed feide_id: %d" %
                     len(potential_changed_feideid))
        pid2accounts = {}
        account2pid = {}
        for row in ac.search():
            pid2accounts.setdefault(int(row['owner_id']), []).append(
                {'id': '%s@UIO.NO' % row['name'].upper()})
            account2pid[int(row['account_id'])] = int(row['owner_id'])
        for account_id in potential_changed_feideid.keys():
            # Recently expired users will not be in account2pid
            if not account2pid.has_key(account_id):
                logger.info("Couldn't find user %s. User is probably expired" %
                            account_id)
                continue
            p = persons.get(account2pid[account_id], None)
            if p:
                # Let ephorte know about potential feide-ids for this person
                p['potential_feideid'] = pid2accounts[account2pid[account_id]]
                logger.debug("Potential feide_ids for person %s: %s" %
                             (account2pid[account_id], p['potential_feideid']))

    logger.info("Fetching names...")
    for entity_id, dta in pe.getdict_persons_names(
        source_system=co.system_cached,
        name_types=(co.name_first,
                    co.name_last, co.name_full)).iteritems():
        tmp = persons.get(entity_id, None)
        if tmp is None:
            continue
        # first name can't be longer then 30 chars in ephorte...
        tmp['first_name'] = Utils.shorten_name(dta[int(co.name_first)],
                                               max_length=30,
                                               method='initials',
                                               encoding='iso-8859-1')
        tmp['last_name'] = dta[int(co.name_last)]
        tmp['full_name'] = dta[int(co.name_full)]

    logger.info("Fetching e-mailadresses...")
    for entity_id, email in pe.list_primary_email_address(co.entity_person):
        tmp = persons.get(entity_id, None)
        if tmp is None:
            continue
        tmp['email'] = email

    logger.info("Fetching post-adresses...")
    for row in pe.list_entity_addresses(entity_type=co.entity_person,
                                        source_system=co.system_sap,
                                        address_type=co.address_street):
        tmp = persons.get(int(row['entity_id']), None)
        if tmp is None:
            continue
        tmp['address_text'] = row['address_text']
        tmp['p_o_box'] = row['p_o_box']
        # ephorte web service can't handle postal numbers starting
        # with "N-". Thus strip those for now.
        if row['postal_number']:
            tmp['postal_number'] = row['postal_number'].lstrip("N-")
        else:
            tmp['postal_number'] = ''
        tmp['city'] = row['city']

    logger.info("Fetching Feide-ID and unames...")
    account_id2pid = {}
    for row in ac.list_accounts_by_type(primary_only=True):
        account_id2pid[int(row['account_id'])] = int(row['person_id'])
    for row in ac.list_names(co.account_namespace):
        pid = account_id2pid.get(int(row['entity_id']))
        if pid:
            tmp = persons.get(pid)
            if tmp:
                tmp['initials'] = row['entity_name'].upper()
                tmp['feide_id'] =  tmp['initials']+"@UIO.NO"
    
    logger.info("Fetching contact info...")
    for row in pe.list_contact_info(source_system=co.system_sap,
                                    contact_type=co.contact_phone):
        tmp = persons.get(int(row['entity_id']), None)
        if tmp is None or not row['contact_value']:
            continue
        # Get the highest priority phone number
        if not tmp.get('phone', None):
            tmp['phone'] = row['contact_value']

    # Get OU's with ephorte spread
    # 
    # due to a logical error in ephorte-sync we have to allow
    # non-existing OU's to be assigned roles. the background for
    # this change is available in ePhorte case 2011/14072
    # registrered 10th of november 2011 by Astrid Optun and
    # updated by USIT in january 2012
    #
    # has_ou_ephorte_spread = [row['entity_id'] for row in
    #                         ou.list_all_with_spread(spreads=co.spread_ephorte_ou)]
    # 
    # it would be better to rename/remove has_ou_ephorte_spread-stuff
    # completely, but the rumor has it that we will be re-writing the
    # whole ephorte-sync anyway, so we just cannot be bothered now,
    # Jazz, 2012-02-23
    has_ou_ephorte_spread = [row['ou_id'] for row in ou.search()]
    logger.info("Fetching roles...")
    for row in ephorte_role.list_roles():
        tmp = persons.get(int(row['person_id']), None)
        p_id = int(row['person_id'])
        role_type = str(co.EphorteRole(row['role_type']))
        sko = _get_sko(row['adm_enhet'])
        if tmp is None:
            logger.warn("Person %s has ephorte role, but not ephorte spread" %
                        p_id)
            continue
        if not tmp.has_key('roles'):
            logger.error("person dict has no key 'roles'. This shouldn't happen." +
                         "Person: %s " % p_id)
            continue
        # Check if role's adm_enhet has ephorte spread
        if not row['adm_enhet'] in has_ou_ephorte_spread:
            logger.warn("Person %s has role %s at non-ephorte ou %s" %
                        (p_id, role_type, sko))
            missing_ou_spread.append({'uname':_get_primary_account(p_id),
                                      'role_type':role_type,
                                      'sko':sko})
            continue
        try:
            arkivdel = str(co.EphorteArkivdel(row['arkivdel']))
            journalenhet = str(co.EphorteJournalenhet(row['journalenhet']))
        except (TypeError, Errors.NotFoundError):
            logger.warn("Wrong arkivdel or journalenhet. Skipping this role %s" % row)
            continue

        tmp['roles'].append({
            'role_type': role_type,
            'standard_rolle': row['standard_role'],
            'adm_enhet': sko,
            'arkivdel': arkivdel,
            'journalenhet': journalenhet,
            'rolletittel': row['rolletittel'],
            'stilling': row['stilling'],
            'start_date': row['start_date'],
            'end_date': row['end_date']
            })

    # Check standard role. If a person has more than one role, then
    # one of them should be set as standard role
    for e_id, p in persons.iteritems():
        if not 'roles' in p:
            logger.debug("No roles for person %s" % p)
            continue
        if len(p['roles']) > 1:
            nr_stdroles = len([1 for x in p['roles'] if x['standard_rolle'] == 'T'])
            if nr_stdroles == 0:
                logger.warn('Person %s has %d roles, but no standard role.' % (
                    e_id, len(p['roles'])))
            elif nr_stdroles > 1:
                logger.warn('Person %s has more than one standard role.' % e_id)
                                  
    # logger.info("fetching permissions...")
    # for row in ephorte_permission.list_permission():
    #     tmp = persons.get(int(row['person_id']), None)
    #     if tmp is None:
    #         logger.warn("Person %s has ephorte permissions, but not ephorte spread" %
    #                     row['person_id'])
    #         continue
    #     if not tmp.has_key('permissions'):
    #         logger.error("person dict has no key 'permissions'. This shouldn't happen." +
    #                      "Person: %s " % row['person_id'])
    #         continue
    #     perm_type = row['perm_type']
    #     if perm_type:
    #         perm_type = str(co.EphortePermission(perm_type))
    # 
    #     tmp['permissions'].append({
    #         'perm_type': perm_type,
    #         'adm_enhet': _get_sko(row['adm_enhet']),
    #         'operator': _get_feide_id(row['requestee_id'])
    #         })

    xml = ExtXMLHelper()
    f.write(xml.xml_hdr)
    f.write("<ephortedata>\n")
    # RH 2008-02-01: we don't export ous until ephorte is ready
    #for ou in ous.values():
    #    f.write(xml.xmlify_tree("ou", ou))
    for p in persons.itervalues():
        if not p.has_key('feide_id'):
            continue
        f.write(xml.xmlify_tree("person", p))
    f.write("</ephortedata>\n")
    f.close()
    logger.info("%s written. All done" % fname)


def mail_warnings(mailto, debug=False):
    """
    If warnings of certain types occur, send those as mail to address
    specified in mailto. If cereconf.EPHORTE_MAIL_TIME is specified,
    just send if time when script is run matches with specified time.
    """

    # Check if we should send mail today
    mail_today = False
    today = DateTime.today()
    for day in getattr(cereconf, 'EPHORTE_MAIL_TIME', []):
        if getattr(DateTime, day, None) == today.day_of_week:
            mail_today = True
    
    if mail_today and missing_ou_spread:
        mail_txt = os.linesep.join(['%-10s   %-9s   %s' % (
            v['uname'], v['role_type'], v['sko']) for v in missing_ou_spread])
        substitute = {'WARNINGS': mail_txt}
        send_mail(mailto, cereconf.EPHORTE_MAIL_WARNINGS3, substitute,
                  debug=debug)



def send_mail(mailto, mail_template, substitute, debug=False):
    ret = Utils.mail_template(mailto, mail_template, substitute=substitute,
                              debug=debug)
    if ret:
        logger.debug("Not sending mail:\n%s" % ret)
    else:
        logger.debug("Sending mail to: %s" % mailto)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hf:m:',
                                   ['help', 'fname', 'mail-warnings-to='])
    except getopt.GetoptError:
        usage(1)

    mail_warnings_to = None
    fname = None
    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
        elif opt in ('-f', '--fname'):
            fname = val
        elif opt in ('-m', '--mail-warnings-to',):
            mail_warnings_to = val
    if not opts or not fname:
        usage(1)
    
    generate_export(fname)

    if mail_warnings_to:
        mail_warnings(mail_warnings_to)


def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
