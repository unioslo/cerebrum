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

import re
import os
import sys
import getopt

import xml.sax

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr





group_name = "LT-elektroniske-reservasjoner"
group_desc = "Internal group for people from LT which will not be shown online"
ignore_gjestetypekode_group = ('IKKE ANGIT','EKST. KONS')



class LTDataParser(xml.sax.ContentHandler):
    """This class is used to iterate over all users in LT. """

    def __init__(self, filename, call_back_function):
        self.call_back_function = call_back_function        
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name == 'data':
            pass
        elif name in ("arbtlf", "komm", "tils", "bilag",
                      "gjest", "rolle", "res", "permisjon"):
            tmp = {}
            for k in attrs.keys():
                tmp[k] = attrs[k].encode('iso8859-1')
            self.p_data[name] = self.p_data.get(name, []) + [tmp]
        elif name == "person":
            self.p_data = {}
            for k in attrs.keys():
                self.p_data[k] = attrs[k].encode('iso8859-1')
        else:
            print "WARNING: unknown element: %s" % name

    def endElement(self, name):
        if name == "person":
            self.call_back_function(self.p_data)

def _add_res(entity_id):
    if not group.has_member(entity_id, const.entity_person, const.group_memberop_union):
        group.add_member(entity_id, const.entity_person, const.group_memberop_union)
        group.write_db()

def _rem_res(entity_id):
    if group.has_member(entity_id, const.entity_person, const.group_memberop_union):
        group.remove_member(entity_id, const.group_memberop_union)
        group.write_db()

def conv_name(fullname):
    fullname = fullname.strip()
    return fullname.split(None, 1)

ou_cache = {}
def get_sted(fakultet, institutt, gruppe):
    fakultet, institutt, gruppe = int(fakultet), int(institutt), int(gruppe)
    stedkode = (fakultet, institutt, gruppe)
    
    if not ou_cache.has_key(stedkode):
        ou = Factory.get('OU')(db)
        try:
            ou.find_stedkode(fakultet, institutt, gruppe,
                             institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
            addr_street = ou.get_entity_address(source=const.system_lt,
                                                type=const.address_street)
            if len(addr_street) > 0:
                addr_street = addr_street[0]
                address_text = addr_street['address_text']
                if not addr_street['country']:
                    address_text = "\n".join(
                        filter(None, (ou.short_name, address_text)))
                addr_street = {'address_text': address_text,
                               'p_o_box': addr_street['p_o_box'],
                               'postal_number': addr_street['postal_number'],
                               'city': addr_street['city'],
                               'country': addr_street['country']}
            else:
                addr_street = None
            addr_post = ou.get_entity_address(source=const.system_lt,
                                                type=const.address_post)
            if len(addr_post) > 0:
                addr_post = addr_post[0]
                addr_post = {'address_text': addr_post['address_text'],
                             'p_o_box': addr_post['p_o_box'],
                             'postal_number': addr_post['postal_number'],
                             'city': addr_post['city'],
                             'country': addr_post['country']}
            else:
                addr_post = None
            fax = ou.get_contact_info(source=const.system_lt,
                                      type=const.contact_fax)
            if len(fax) > 0:
                fax = fax[0]['contact_value']
            else:
                fax = None
            ou_cache[stedkode] = {'id': int(ou.ou_id),
                                  'fax': fax,
                                  'addr_street': addr_street,
                                  'addr_post': addr_post}
            ou_cache[int(ou.ou_id)] = ou_cache[stedkode]
        except Errors.NotFoundError:
            logger.warn("bad stedkode: %s" % str(stedkode))
            ou_cache[stedkode] = None
    return ou_cache[stedkode]

def determine_affiliations(person):
    "Determine affiliations in order of significance"
    ret = {}
    tittel = None
    prosent_tilsetting = -1
    for t in person.get('tils', ()):
        fakultet, institutt, gruppe = (t['fakultetnr_utgift'],
                                       t['instituttnr_utgift'],
                                       t['gruppenr_utgift'])
        pros = float(t['prosent_tilsetting'])
        if t['tittel'] == 'professor II':
            pros = pros / 5.0
        if prosent_tilsetting < pros:
            prosent_tilsetting = pros
            tittel = t['tittel']
        if t['hovedkat'] == 'ØVR':
            aff_stat = const.affiliation_status_ansatt_tekadm
        elif t['hovedkat'] == 'VIT':
            aff_stat = const.affiliation_status_ansatt_vit
        else:
            logger.warn("Unknown hovedkat: %s" % t['hovedkat'])
            continue
        sted = get_sted(fakultet, institutt, gruppe)
        if sted is None:
            continue
	k = "%s:%s:%s" % (new_person.entity_id,sted['id'],
                          int(const.affiliation_ansatt)) 
	if not ret.has_key(k):
	    ret[k] = sted['id'],const.affiliation_ansatt, aff_stat
    if tittel:
        new_person.populate_name(const.name_work_title, tittel)
    for b in person.get('bilag', ()):
        sted = get_sted(b['fakultetnr_kontering'],
                        b['instituttnr_kontering'],
                        b['gruppenr_kontering'])
        if sted is None:
            continue
	k = "%s:%s:%s" % (new_person.entity_id,sted['id'],
                                        int(const.affiliation_ansatt))
	if not ret.has_key(k):
	    ret[k] = sted['id'], const.affiliation_ansatt,\
                   		const.affiliation_status_ansatt_bil
    for g in person.get('gjest', ()):
        if g['gjestetypekode'] == 'EMERITUS':
            aff_stat = const.affiliation_tilknyttet_emeritus
        elif g['gjestetypekode'] == 'PCVAKT':
            aff_stat = const.affiliation_tilknyttet_pcvakt
        elif g['gjestetypekode'] == 'UNIRAND':
            aff_stat = const.affiliation_tilknyttet_unirand
        elif g['gjestetypekode'] == 'GRP-LÆRER':
            aff_stat = const.affiliation_tilknyttet_grlaerer
	elif g['gjestetypekode'] == 'EF-STIP':
	    aff_stat = const.affiliation_tilknyttet_ekst_stip
	elif g['gjestetypekode'] == 'BILAGSLØN':
	    aff_stat = const.affiliation_tilknyttet_bilag
	elif (g['gjestetypekode'] == 'EF-FORSKER' or g['gjestetypekode'] == 'SENIORFORS'):
	    aff_stat = const.affiliation_tilknyttet_ekst_forsker
	elif g['gjestetypekode'] == 'GJ-FORSKER':
	    aff_stat = const.affiliation_tilknyttet_gjesteforsker
	elif g['gjestetypekode'] == 'SIVILARB':
	    aff_stat = const.affiliation_tilknyttet_sivilarbeider
	elif g['gjestetypekode'] == 'EKST. PART':
	    aff_stat = const.affiliation_tilknyttet_ekst_partner
	elif (g['gjestetypekode'] == 'REGANSV' or g['gjestetypekode'] == 'REG-ANSV'):
	    aff_stat = const.affiliation_tilknyttet_frida_reg
        elif (g['gjestetypekode'] == 'ST-POL FRI' or g['gjestetypekode'] =='ST-POL UTV'):
            aff_stat = const.affiliation_tilknyttet_studpol
        elif (g['gjestetypekode'] == 'ST-ORG FRI' or g['gjestetypekode'] =='ST-ORG UTV'):
            aff_stat = const.affiliation_tilknyttet_studorg
	# Some known gjestetypekode can't be maped to any known affiliations
	# at the moment. Group defined above in head.  
	elif g['gjestetypekode'] in ignore_gjestetypekode_group:
	    logger.info("No registrations of gjestetypekode: %s" % g['gjestetypekode'])
	    continue
        else:
            logger.warn("Unknown gjestetypekode: %s" % g['gjestetypekode'])
            continue
        sted = get_sted(g['fakultetnr'],
                        g['instituttnr'],
                        g['gruppenr'])
        if sted is None:
            continue
	k = "%s:%s:%s" % (new_person.entity_id,sted['id'],
                                        int(const.affiliation_tilknyttet))
	if not ret.has_key(k):
	    ret[k] = sted['id'], const.affiliation_tilknyttet, aff_stat
    return ret

def determine_contact(person):
    # TODO: we have no documentation on how data are registered in
    # these LT tables, so this is guesswork...
    ret = []
    for t in person.get('arbtlf', ()):
        if int(t['telefonnr']):
            ret.append((const.contact_phone, t['telefonnr']))
        if int(t['linjenr']):
            ret.append((const.contact_phone,
                        "%i%05i" % (int(t['innvalgnr']), int(t['linjenr']))))
    for k in person.get('komm', ()):
        if k['kommtypekode'] in ('ARBTLF', 'EKSTRA TLF', 'JOBBTLFUTL'):
            if k.has_key('kommnrverdi'):
                val = k['kommnrverdi']
            elif k.has_key('telefonnr'):
                val = int(k['telefonnr'])
            else:
                continue
            ret.append((const.contact_phone, val))
        if k['kommtypekode'] in ('FAX', 'FAXUTLAND'):
            if k.has_key('kommnrverdi'):
                val = k['kommnrverdi']
            elif k.has_key('telefonnr'):
                val = int(k['telefonnr'])
            else:
                continue
            ret.append((const.contact_fax, val))
    return ret

def determine_reservations(person):
    # TODO: Use something "a bit more defined and permanent".
    # This is a hack. For now we set a reservation on non-guests with
    # any 'ELKAT' reservation except 'PRIVADR' and 'PRIVTLF', and
    # on guests without 'ELKAT'+'GJESTEOPPL' anti-reservations.
    res_on_pers = person.has_key('gjest') and not person.has_key('tils')
    for r in person.get('res', ()):
        if r['katalogkode'] == "ELKAT":
            if r['felttypekode'] not in ("PRIVADR", "PRIVTLF"):
                res_on_pers = r['felttypekode'] != "GJESTEOPPL"
    if res_on_pers:
        _add_res(new_person.entity_id)
    else:
        _rem_res(new_person.entity_id)
        
def process_person(person):
    fnr = fodselsnr.personnr_ok(
        "%02d%02d%02d%05d" % (int(person['fodtdag']), int(person['fodtmnd']),
                              int(person['fodtar']), int(person['personnr'])))

    # FIXME: How ugly are the logs now?
    # logger.info2("Process %s " % fnr, append_newline=0)
    logger.info("Process %s", fnr) 
    new_person.clear()
    gender = const.gender_male
    if(fodselsnr.er_kvinne(fnr)):
        gender = const.gender_female

    (year, mon, day) = fodselsnr.fodt_dato(fnr)
    try:
        new_person.find_by_external_id(const.externalid_fodselsnr, fnr)
    except Errors.NotFoundError:
        pass
    except Errors.TooManyRowsError:
        try:
            new_person.find_by_external_id(
                const.externalid_fodselsnr, fnr, const.system_lt)
        except Errors.NotFoundError:
            pass
    if (person.get('fornavn', ' ').isspace() or
        person.get('etternavn', ' ').isspace()):
        logger.warn("Ikke noe navn for %s" % fnr)
        return
    new_person.populate(db.Date(year, mon, day), gender)
    new_person.affect_names(const.system_lt, const.name_first, const.name_last,
						const.name_personal_title)
    new_person.affect_external_id(const.system_lt, const.externalid_fodselsnr)
    new_person.populate_name(const.name_first, person['fornavn'])
    new_person.populate_name(const.name_last, person['etternavn'])
    if person.get('tittel_personlig',''):
	new_person.populate_name(const.name_personal_title,\
					 	person['tittel_personlig'])
    new_person.populate_external_id(
        const.system_lt, const.externalid_fodselsnr, fnr)

    # If it's a new person, we need to call write_db() to have an entity_id
    # assigned to it.
    op = new_person.write_db()

    # work_title is set by determine_affiliations
    new_person.affect_names(const.system_lt, const.name_work_title)
    affiliations = determine_affiliations(person)
    new_person.populate_affiliation(const.system_lt)
    contact = determine_contact(person)
    got_fax = filter(lambda x: x[0] == const.contact_fax, contact)
    if person.has_key('fakultetnr_for_lonnsslip'):
        sted = get_sted(person['fakultetnr_for_lonnsslip'],
                        person['instituttnr_for_lonnsslip'],
                        person['gruppenr_for_lonnsslip'])
        if sted is not None:
            if sted['addr_street'] is not None:
                new_person.populate_address(
                    const.system_lt, type=const.address_street,
                    **sted['addr_street'])
            if sted['addr_post'] is not None:
                new_person.populate_address(
                    const.system_lt, type=const.address_post,
                    **sted['addr_post'])
            if not got_fax and sted['fax'] is not None:
                # Add fax number for work place with a non-NULL fax
                # to person's contact info.
                contact.append((const.contact_fax, sted['fax']))
                got_fax = True
    for k,v in affiliations.items():
	ou_id, aff, aff_stat = v
        new_person.populate_affiliation(const.system_lt, ou_id,\
						int(aff), int(aff_stat))
#       if not got_fax:
#           sted = get_sted(ou_id)
#           if sted is not None and sted['fax'] is not None:
#               # Add fax of the first affiliation with a non-NULL fax
#               # to person's contact info.
#               contact.append((const.contact_fax, sted['fax']))
#               got_fax = True
	if include_del:
	    if cere_list.has_key(k):
		cere_list[k] = False
    c_prefs = {}
    new_person.populate_contact_info(const.system_lt)
    for c_type, value in contact:
        c_type = int(c_type)
        pref = c_prefs.get(c_type, 0)
        new_person.populate_contact_info(const.system_lt, c_type, value, pref)
        c_prefs[c_type] = pref + 1
    op2 = new_person.write_db()
    if gen_groups == 1:
        # determine_reservation() needs new_person.entity_id to be
        # set; this should always be the case after write_db() is
        # done.
        determine_reservations(person)
    if op is None and op2 is None:
        logger.info("**** EQUAL ****")
    elif op == True:
        logger.info("**** NEW ****")
    else:
        logger.info("**** UPDATE ****")

def usage(exitcode=0):
    print """Usage: import_LT.py -p personfile [-v] [-g] [-d]"""
    sys.exit(exitcode)
# end usage



def load_all_affi_entry():
    affi_list = {}
    for row in new_person.list_affiliations(source_system=const.system_lt):
	key_l = "%s:%s:%s" % (row['person_id'],row['ou_id'],row['affiliation'])
	affi_list[key_l] = True
    return(affi_list)
# end load_all_affi_entry



def clean_affi_s_list():
    for k,v in cere_list.items():
	if v:
	    ent_id,ou,affi = k.split(':')
	    new_person.clear()
	    #new_person.find(int(ent_id))
	    new_person.entity_id = int(ent_id)
	    new_person.delete_affiliation(ou, affi, const.system_lt)
# end clean_affi_s_list



def main():
    global db, new_person, const, ou, logger, gen_groups, group
    global cere_list, include_del, test_list

    logger = Factory.get_logger("cronjob")
    logger.info("Starting import_LT")
    
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   'p:gdr',
                                   ['person-file=',
                                    'group', 'include_delete',
                                    'dryrun'])
    except getopt.GetoptError:
        usage(1)
    # yrt

    gen_groups = 0
    verbose = 0
    personfile = None
    include_del = False
    dryrun = False
    
    for opt, val in opts:
        if opt in ('-p', '--person-file'):
            personfile = val
        elif opt in ('-g', '--group'):
            gen_groups = 1
	elif opt in ('-d', '--include_delete'):
	    include_del = True
        elif opt in ('-r', '--dryrun'):
            dryrun = True
        # fi
    # od

    db = Factory.get('Database')()
    db.cl_init(change_program='import_LT')
    const = Factory.get('Constants')(db)
    group = Factory.get('Group')(db)
    try:
	group.find_by_name(group_name)
    except Errors.NotFoundError:
	group.clear()
        ac = Factory.get('Account')(db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        group.populate(ac.entity_id, const.group_visibility_internal,
                       group_name, group_desc)
        group.write_db()
    # yrt

    ou = Factory.get('OU')(db)
    new_person = Factory.get('Person')(db)
    if include_del:
	cere_list = load_all_affi_entry()
    # fi

    if personfile is not None:
        LTDataParser(personfile, process_person)
    # fi

    if include_del:
	clean_affi_s_list()
    # fi

    if dryrun:
        db.rollback()
        logger.info("All changes rolled back")
    else:
        db.commit()
        logger.info("Committed all changes")
    # fi
# end main





if __name__ == '__main__':
    main()
# fi

# arch-tag: 2a13af18-1044-4476-ac05-532ac829524c
