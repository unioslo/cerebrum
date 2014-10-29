#!/usr/bin/env python
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


import cerebrum_path
import cereconf
import pprint
import re
import pickle
import sys
import time
import os
import getopt

import xml.sax

from Cerebrum import Errors
from Cerebrum.Utils import Factory

from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError
from Cerebrum.modules.no.uit.EntityExpire import EntityExpire


# Default file locations
t = time.localtime()
dumpdir = os.path.join(cereconf.DUMPDIR,"ou")
default_input_file = os.path.join(dumpdir,'uit_ou_%d%02d%02d.xml' % (t[0], t[1], t[2]))

# Default source system
default_source_system = "system_fs"
default_perspective = "perspective_fs"


OU_class = Factory.get('OU')
SKO_class = Factory.get('Stedkode')
db = Factory.get('Database')()
db.cl_init(change_program='import_OU')
co = Factory.get('Constants')(db)

logger=Factory.get_logger('cronjob')


# <data>
#   <sted fakultetnr="ff" instituttnr="ii" gruppenr="gg"
#         forkstednavn="foo" stednavn="foo bar" akronym="fb"
#         stedkortnavn_bokmal="fooen" stedkortnavn_nynorsk="fooa"
#         stedkortnavn_engelsk="thefoo"
#         stedlangnavn_bokmal="foo baren" stedlangnavn_nynorsk="foo bara"
#         stedlangnavn_engelsk="the foo bar"
#         fakultetnr_for_org_sted="FF" instituttnr_for_org_sted="II"
#         gruppenr_for_org_sted="GG"
#         opprettetmerke_for_oppf_i_kat="X"
#         telefonnr="22851234" innvalgnr="228" linjenr="51234"
#         stedpostboks="1023"
#         adrtypekode_besok_adr="INT" adresselinje1_besok_adr="adr1_besok"
#         adresselinje2_besok_adr="adr2_besok"
#         poststednr_besok_adr="postnr_besok"
#         poststednavn_besok_adr="postnavn_besok" landnavn_besok_adr="ITALIA"
#         adrtypekode_intern_adr="INT" adresselinje1_intern_adr="adr1_int"
#         adresselinje2_intern_adr="adr2_int"
#         poststednr_intern_adr="postnr_int"
#         poststednavn_intern_adr="postnavn_int" landnavn_intern_adr="ITALIA"
#         adrtypekode_alternativ_adr="INT"
#         adresselinje1_alternativ_adr="adr1_alt"
#         adresselinje2_alternativ_adr="adr2_alt"
#         poststednr_alternativ_adr="postnr_alt"
#         poststednavn_alternativ_adr="postnavn_alt"
#         landnavn_alternativ_adr="ITALIA">
#     <komm kommtypekode=("EKSTRA TLF" | "TLF" | "TLFUTL" |
#                         "FAX" | "FAXUTLAND" | "EPOST" | "URL")
#           telefonnr="foo" kommnrverdi="bar">
#     </komm>
#   </sted>
# </data>

class OUData(xml.sax.ContentHandler):
    def __init__(self, sources):
        global source_system
        self.tp = TrivialParser()
        for source_spec in sources:
            source_sys_name, filename = source_spec.split(':')
            logger.debug("source_sys_name %s" % source_sys_name)
            source_system = getattr(co, source_sys_name)
            logger.debug("source_system = %s" % source_system)
            logger.debug("filename = %s" % filename)
            xml.sax.parse(filename, self.tp)

    def __iter__(self):
        return self

    def next(self):
        try:
            return self.tp.org_units.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

class TrivialParser(xml.sax.ContentHandler):
    def __init__(self):
        self.org_units = []

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        if name == 'data':
            pass
        elif name == "sted":
            self.org_units.append(tmp)
        elif name == "komm":
            self.org_units[-1].setdefault("komm", []).append(tmp)
        else:
            raise ValueError, "Unknown XML element %s" % name

    def endElement(self, name):
        pass

def get_stedkode_str(row, suffix=""):
    elems = []
    for key in ('fakultetnr', 'instituttnr', 'gruppenr'):
        elems.append("%02d" % int(row[key+suffix]))
    return "-".join(elems)

def rec_make_ou(stedkode, ou, existing_ou_mappings, org_units,
                stedkode2ou, co):
    """Recursively create the ou_id -> parent_id mapping"""
    ou_data = org_units[stedkode]
    org_stedkode = get_stedkode_str(ou_data, suffix='_for_org_sted')
    if not stedkode2ou.has_key(org_stedkode):
        logger.error("Error in dataset:"\
                     " %s references missing STEDKODE: %s, using None" % (
            stedkode, org_stedkode))
        org_stedkode = None
        org_stedkode_ou = None
    elif stedkode == org_stedkode:
        logger.warn("%s has self as parent, using None" % stedkode)
        org_stedkode = None
        org_stedkode_ou = None
    else:
        org_stedkode_ou = stedkode2ou[org_stedkode]

    try:
        if existing_ou_mappings.has_key(stedkode2ou[stedkode]):
            if existing_ou_mappings[stedkode2ou[stedkode]] != org_stedkode_ou:
                # TODO: Update ou_structure
                logger.info("Mapping for %s changed (%s != %s)" % (
                    stedkode, existing_ou_mappings[stedkode2ou[stedkode]],
                    org_stedkode_ou))
                # uitø extension follows.
                # Ou's registred with parent_id as None, or wrong parent_id
                # will have to update their parent_id if a new one is submitted
                # in the stedkode.xml file. This is initially not done
                # this extension fixes this
                query = "update ou_structure set parent_id=%s where ou_id=%s" % (org_stedkode_ou,stedkode2ou[stedkode])
                db.query(query)
            
            return
    except KeyError:
        logger.error("Stedkode %s not found in mapping (may be expired)" % (stedkode))
        return

    if (org_stedkode_ou is not None
        and (stedkode != org_stedkode)
        and (not existing_ou_mappings.has_key(org_stedkode_ou))):
        rec_make_ou(org_stedkode, ou, existing_ou_mappings, org_units,
                          stedkode2ou, co)

    ou.clear()
    ou.find(stedkode2ou[stedkode])
    if stedkode2ou.has_key(org_stedkode):
        logger.debug("setting parent to %s" % stedkode2ou[org_stedkode])
        ou.set_parent(perspective, stedkode2ou[org_stedkode])
    else:
        logger.debug("setting parent to None for %s" % org_stedkode)
        ou.set_parent(perspective, None)
    existing_ou_mappings[stedkode2ou[stedkode]] = org_stedkode_ou

def import_org_units(sources):

    #print sources
    
    #ou = OU_class(db)
    sko = SKO_class(db)
    ex = EntityExpire
    
    expire_ou = []
    all = sko.list_all_with_perspective(co.perspective_fs)
    for a in all:
        #print"ou_id:%s" % a['ou_id']
        expire_ou.append(a['ou_id'])
    #print "############################### BEFORE: "
    #print expire_ou

    org_units = {}

    i = 1
    stedkode2ou = {}

    for k in OUData(sources):
        
        i += 1
        org_units[get_stedkode_str(k)] = k
        if verbose:
            logger.info("Processing %s '%s'" % (get_stedkode_str(k),
                                                k['forkstednavn']),)
        sko.clear()
        try:
            sko.find_stedkode(k['fakultetnr'], k['instituttnr'], k['gruppenr'],
                             institusjon=k.get('institusjonsnr',
                                               cereconf.DEFAULT_INSTITUSJONSNR))
        except Errors.NotFoundError:
            pass
        except EntityExpiredError:
            logger.warning('OU expired %s%s%s - handle this carefully' %
                         (k['fakultetnr'], k['instituttnr'], k['gruppenr']))

            #
            # expired ou re-appearing in import file. handle it.
            #
            ex = EntityExpire(db)
            ret = ex.is_expired(sko.ou_id)
            if ret == True:
                #
                # an incoming ou id is expired. delete expire tuple to activate ou
                #
                
                logger.warning("EXPIRED ou_id:%s reappearing in import file. remove expired date" %(sko.ou_id))
                
                # find entity_expire tuple
                ex.clear()
                ex.find(sko.ou_id,"1970-01-01")
                
                # update tuple with None value
                ex.populate_expire_date(None)
                
                #write new entity_expire value to database
                ex.write_db()
                
                # delete ou from list of org_structures to update
                del org_units[get_stedkode_str(k)]
                expire_ou.remove(sko.ou_id)
                #commit changes
                db.commit()
                
                # We continue as there is no need to process this OU.
                # The relevant ou informasion is already in the database
                continue
            else:
                    logger.error("NOT expired")
            
        sko.populate(k['stednavn'], k['fakultetnr'],
                    k['instituttnr'], k['gruppenr'],
                    institusjon=k.get('institusjonsnr',
                                      cereconf.DEFAULT_INSTITUSJONSNR),
                    acronym=k.get('akronym', None),
                    short_name=k['forkstednavn'],
                    display_name=k['display_name'],
                    sort_name=k['sort_key'])
        p_o_box = k.get('stedpostboks', None)
        if p_o_box == '0' or k.get('adrtypekode_intern_adr', '') != 'INT':
            p_o_box = None
        if p_o_box or k.has_key('adresselinje1_intern_adr'):
            which = '_intern_adr'
        else:
            which = '_besok_adr'
        adrlines = filter(None, (k.get('adresselinje1' + which, None),
                                 k.get('adresselinje2' + which, None) ))
        city = k.get('poststednavn' + which, '')
        # TODO: get country
        country = None
        if p_o_box or adrlines or city or country:
            postal_number = k.get('poststednr' + which, '')
            if postal_number:
                postal_number = "%04i" % int(postal_number)
            sko.populate_address(source_system, co.address_post,
                                address_text = "\n".join(adrlines),
                                p_o_box = p_o_box,
                                postal_number = postal_number,
                                city = city,
                                country = country)
        adrlines = filter(None, (k.get('adresselinje1_besok_adr', None),
                                 k.get('adresselinje2_besok_adr', None) ))
        city = k.get('poststednavn_besok_adr', None)
        # TODO: get country
        country = None
        if adrlines or city or country:
            postal_number = k.get('poststednr_besok_adr', None)
            if postal_number:
                postal_number = "%04i" % int(postal_number)
            sko.populate_address(source_system, co.address_street,
                                address_text = "\n".join(adrlines),
                                postal_number = postal_number,
                                city = city,
                                country = country)
        n = 0
        nrtypes = {'EKSTRA TLF': co.contact_phone,
                   'TLF': co.contact_phone,
                   'TLFUTL': co.contact_phone,
                   'FAX': co.contact_fax,
                   'FAXUTLAND': co.contact_fax}
        txttypes = {'EPOST': co.contact_email,
                    'URL': co.contact_url}
        for t in k.get('komm', []):
            n += 1       # TODO: set contact_pref properly
            if nrtypes.has_key(t['kommtypekode']):
                nr = t.get('telefonnr', t.get('kommnrverdi', None))
                if nr is None:
                    logger.warn("unknown contact: %s" % str(t))
                    continue
                sko.populate_contact_info(source_system, nrtypes[t['kommtypekode']],
                                         nr, contact_pref=n)
            elif txttypes.has_key(t['kommtypekode']):
                sko.populate_contact_info(source_system,
                                         txttypes[t['kommtypekode']],
                                         t['kommnrverdi'], contact_pref=n)
	n += 1
	if k.has_key('innvalgnr') and k.has_key('linjenr'):
	    phone_value = "%s%05i" % (k['innvalgnr'], int(k['linjenr']))
            sko.populate_contact_info(source_system, co.contact_phone,
					phone_value, contact_pref=n)
        if int(k.get('telefonnr', 0)):
            n += 1
            sko.populate_contact_info(source_system, co.contact_phone,
					k['telefonnr'], contact_pref=n)
        op = sko.write_db()
        if (k.get('opprettetmerke_for_oppf_i_kat') and
            not sko.has_spread(co.spread_ou_publishable)):
            sko.add_spread(co.spread_ou_publishable)
        op2 = sko.write_db()
        
        try:
            expire_ou.remove(sko.ou_id)
        except Exception:
            pass
        
        if verbose:
            if op is None and op2 is None:
                logger.info("**** EQUAL ****")
            elif op:
                logger.info("**** NEW ****")
            else:
                loggger.info("**** UPDATE ****")

        stedkode = get_stedkode_str(k)
        # Not sure why this casting to int is required for PostgreSQL
        stedkode2ou[stedkode] = int(sko.entity_id)
        db.commit()


    # Expire all OUs in expire_ou list
    t = time.localtime()
    for e in expire_ou:
        sko.clear()
        #print "id:%s" % e['ou_id']
        try:
            sko.find(e)
        except EntityExpiredError:
            # expired ou, ignore it
            continue
        sko.populate_expire_date("%02d%02d%02d" % (t[0], t[1], t[2]))
        sko.write_db()

    #print "############################### AFTER: "
    #print expire_ou
    #print len(expire_ou)

    existing_ou_mappings = {}
    for node in sko.get_structure_mappings(perspective):
        existing_ou_mappings[int(node['ou_id'])] = node['parent_id']

    # Now populate ou_structure
    if verbose:
        logger.info("Populate ou_structure")
    for stedkode in org_units.keys():
        rec_make_ou(stedkode, sko, existing_ou_mappings, org_units,
                    stedkode2ou, co)
    db.commit()

def usage(exitcode=0):
    print """Usage: [options] [file ...]
Imports OU data from systems that use 'stedkoder', primarily used to
import from UoOs LT system.

    -v | --verbose              increase verbosity
    -p | --perspective NAME     name of perspective to use
    -s | --source-spec SPEC     colon-separated (source-system, filename) pair

    """
    sys.exit(exitcode)

def main():
    global verbose, perspective

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vp:s:',
                                   ['verbose',
                                    'perspective=',
                                    'source-spec='])
    except getopt.GetoptError:
        usage(1)


    verbose = 0
    perspective = getattr(co, default_perspective)
    sources = []
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-p', '--perspective',):
            perspective = getattr(co, val)
        elif opt in ('-s', '--source-spec'):
            sources.append(val)
            logger.debug("VAL=%s" % val)
    
    if len(sources) == 0:
        sources.append(default_source_system+':'+default_input_file)

    logger.debug(sources)
    import_org_units(sources)


if __name__ == '__main__':
    main()
