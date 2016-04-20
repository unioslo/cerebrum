#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys

import cerebrum_path

from Cerebrum import Errors
from Cerebrum.Utils import Factory, XMLHelper
from Cerebrum.utils.atomicfile import SimilarSizeWriter

progname = __file__.split("/")[-1]
__doc__ = """
This script generates an XML export for ePhorte.  The XML file is read
by another cerebrum-script, which uses uses ePhortes Web-service
interface to push the data into ePhorte.  Currently little work has
been put into 'standardizing' this XML format.

Usage: %s [options]
  -f fname : output filename

""" % progname

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
#ephorte_role = EphorteRole(db)
#ephorte_permission = EphortePermission(db)
ou = Factory.get('OU')(db)
#cl = CLHandler.CLHandler(db)

logger = Factory.get_logger("cronjob")
sko_cache = {}
feide_id_cache = {}

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
        for k, v in dta.items():
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

def _get_feide_id(operator_id):
    ret = feide_id_cache.get(operator_id)
    if ret is None:
        ac.clear()
        try:
            ac.find(operator_id)
        except Errors.NotFoundError:
            logger.warn("Could not find account %s" % (operator_id))
            return ""
        ret = ac.account_name.upper() + "@UIT.NO"
        feide_id_cache[operator_id] = ret
    return ret

def generate_export(fname, spread=co.spread_ephorte_person):
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
        persons[int(row['entity_id'])] = {'roles': [], 'permissions': []}
    logger.info("Found %d persons with ephorte spread" % len(persons))

    # 1. Check changelog to find persons that have lost
    #    ephorte-spread. These should be marked as deleted    
    # 2. Try also to detect if a person has a new feide id, meaning
    #    that ePhorte potentially will need to set an existing account
    #    to point to this new value
##    potential_changed_feideid = {}    
##    logger.info("Checking changelog")
##    for event in cl.get_events('eph_exp', (
##        co.spread_del, co.account_type_add, co.account_type_del,
##        co.account_type_mod)):
##        cl.confirm_event(event)
##        if event['change_type_id'] != int(co.spread_del):
##            potential_changed_feideid[int(event['subject_entity'])] = True
##            continue
##        if persons.has_key(int(event['subject_entity'])):
##            continue  # spread has been re-inserted or similar
##        change_params = pickle.loads(event['change_params'])
##        if change_params['spread'] == int(co.spread_ephorte_person):
##            persons[int(event['subject_entity'])] = {'delete': 1}
##            logger.debug("Person %s has lost ephorte_spread since last run. " %
##                         event['subject_entity'] + "Set person as deletable")
##    cl.commit_confirmations()
##
##    if potential_changed_feideid:
##        logger.debug("Nr of persons with potential changed feide_id: %d" %
##                     len(potential_changed_feideid))
##        pid2accounts = {}
##        account2pid = {}
##        for row in ac.search():
##            pid2accounts.setdefault(int(row['owner_id']), []).append(
##                {'id': '%s@UIO.NO' % row['name'].upper()})
##            account2pid[int(row['account_id'])] = int(row['owner_id'])
##        for account_id in potential_changed_feideid.keys():
##            # Recently expired users will not be in account2pid
##            if not account2pid.has_key(account_id):
##                logger.info("Couldn't find user %s. User is probably expired" %
##                            account_id)
##                continue
##            p = persons.get(account2pid[account_id], None)
##            if p:
##                # Let ephorte know about potential feide-ids for this person
##                p['potential_feideid'] = pid2accounts[account2pid[account_id]]
##                logger.debug("Potential feide_ids for person %s: %s" %
##                             (account2pid[account_id], p['potential_feideid']))

    logger.info("Fetching names...")
    for entity_id, dta in pe.getdict_persons_names(
        source_system=co.system_cached,
        name_types=(co.name_first,
                    co.name_last, co.name_full)).items():
        tmp = persons.get(entity_id, None)
        if tmp is None:
            continue
        tmp['first_name'] = dta[int(co.name_first)]
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
        tmp['postal_number'] = row['postal_number']
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
                #tmp['feide_id'] =  tmp['initials']+"@UIT.NO"
                tmp['feide_id'] =  tmp['initials']
    
    logger.info("Fetching contact info...")
    for row in pe.list_contact_info(#source_system=co.system_paga,
                                    contact_type=co.contact_phone):
        tmp = persons.get(int(row['entity_id']), None)
        if tmp is None or not row['contact_value']:
            continue
        if len(row['contact_value'])==5:
            row['contact_value']='776'+row['contact_value']
        tmp['phone'] = row['contact_value']

##    logger.info("Fetching roles...")
##    for row in ephorte_role.list_roles():
##        tmp = persons.get(int(row['person_id']), None)
##        if tmp is None:
##            logger.warn("Person %s has ephorte role, but not ephorte spread" %
##                        row['person_id'])
##            continue
##        if not tmp.has_key('roles'):
##            logger.error("person dict has no key 'roles'. This shouldn't happen." +
##                         "Person: %s " % row['person_id'])
##            continue
##
##        arkivdel = row['arkivdel']
##        if arkivdel:
##            arkivdel = str(co.EphorteArkivdel(arkivdel))
##        journalenhet = row['journalenhet']
##        if journalenhet:
##            journalenhet = str(co.EphorteJournalenhet(journalenhet))
##        
##        tmp['roles'].append({
##            'role_type': str(co.EphorteRole(row['role_type'])) ,
##            'standard_rolle': row['standard_role'],
##            'adm_enhet': _get_sko(row['adm_enhet']),
##            'arkivdel': arkivdel,
##            'journalenhet': journalenhet,
##            'rolletittel': row['rolletittel'],
##            'stilling': row['stilling'],
##            'start_date': row['start_date'],
##            'end_date': row['end_date']
##            })
##                                  
##    logger.info("fetching permissions...")
##    for row in ephorte_permission.list_permission():
##        tmp = persons.get(int(row['person_id']), None)
##        if tmp is None:
##            logger.warn("Person %s has ephorte permissions, but not ephorte spread" %
##                        row['person_id'])
##            continue
##        if not tmp.has_key('permissions'):
##            logger.error("person dict has no key 'permissions'. This shouldn't happen." +
##                         "Person: %s " % row['person_id'])
##            continue
##        perm_type = row['perm_type']
##        if perm_type:
##            perm_type = str(co.EphortePermission(perm_type))
##
##        tmp['permissions'].append({
##            'perm_type': perm_type,
##            'adm_enhet': _get_sko(row['adm_enhet']),
##            'operator': _get_feide_id(row['requestee_id'])
##            })

    xml = ExtXMLHelper()
    f = SimilarSizeWriter(fname, "w")
    f.set_size_change_limit(50)
    f.write(xml.xml_hdr)
    f.write("<ephortedata>\n")
    # RH 2008-02-01: we don't export ous until ephorte is ready
    #for ou in ous.values():
    #    f.write(xml.xmlify_tree("ou", ou))
    for p in persons.values():
        if not p.has_key('feide_id'):
            continue
        f.write(xml.xmlify_tree("person", p))
    f.write("</ephortedata>\n")
    f.close()
    logger.info("%s written. XML write done" % fname)
    

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'f:', ['help'])
    except getopt.GetoptError:
        usage(1)

    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-f',):
            generate_export(val)
    if not opts:
        usage(1)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
