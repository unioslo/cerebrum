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
import time

import xml.sax

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.modules.no import fodselsnr
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.AutoStud import StudentInfo
from Cerebrum.modules.no.uio import AutoStud

default_personfile = "/cerebrum/dumps/FS/merged_persons.xml"
default_studieprogramfile = "/cerebrum/dumps/FS/studieprogrammer.xml"
group_name = "FS-aktivt-samtykke"
group_desc = "Internal group for students which will be shown online."


studieprog2sko = {}
ou_cache = {}

"""Importerer personer fra FS iht. fs_import.txt."""

def _add_res(entity_id):
    if not group.has_member(entity_id, co.entity_person, co.group_memberop_union):
        group.add_member(entity_id, co.entity_person, co.group_memberop_union)

def _rem_res(entity_id):
    if group.has_member(entity_id, co.entity_person, co.group_memberop_union):
        group.remove_member(entity_id, co.group_memberop_union)

def _get_sko(a_dict, kfak, kinst, kgr, kinstitusjon=None):
    key = "-".join((a_dict[kfak], a_dict[kinst], a_dict[kgr]))
    if not ou_cache.has_key(key):
        ou = Factory.get('OU')(db)
        if kinstitusjon is not None:
            institusjon=a_dict[kinstitusjon]
        else:
            institusjon=cereconf.DEFAULT_INSTITUSJONSNR
        try:
            ou.find_stedkode(int(a_dict[kfak]), int(a_dict[kinst]), int(a_dict[kgr]),
                             institusjon=institusjon)
            ou_cache[key] = ou.ou_id
        except Errors.NotFoundError:
            logger.warn("bad stedkode: %s" % key)
            ou_cache[key] = None
    return ou_cache[key]

def _process_affiliation(aff, aff_status, new_affs, ou):
    # TBD: Should we for example remove the 'opptak' affiliation if we
    # also have the 'aktiv' affiliation?
    if ou is not None:
        new_affs.append((ou, aff, aff_status))

def _ext_address_info(a_dict, kline1, kline2, kline3, kpost, kland):
    ret = {}
    ret['address_text'] = "\n".join([a_dict.get(f, None)
                                     for f in (kline1, kline2)
                                     if a_dict.get(f, None)])
    postal_number = a_dict.get(kpost, '')
    if postal_number:
        postal_number = "%04i" % int(postal_number)
    ret['postal_number'] = postal_number
    ret['city'] =  a_dict.get(kline3, '')
    if len(ret['address_text']) < 2:
        return None
    return ret

def _load_cere_aff():
    fs_aff = {}
    person = Person.Person(db) # ?!?
    for row in person.list_affiliations(source_system=co.system_fs):
	k = "%s:%s:%s" % (row['person_id'],row['ou_id'],row['affiliation'])
        fs_aff[str(k)] = True
    return(fs_aff)

def rem_old_aff():
    person = Person.Person(db)
    for k,v in old_aff.items():
	if v:
	    ent_id,ou,affi = k.split(':')
            person.clear()
	    person.entity_id = int(ent_id)
            person.delete_affiliation(ou, affi, co.system_fs)

def process_person_callback(person_info):
    """Called when we have fetched all data on a person from the xml
    file.  Updates/inserts name, address and affiliation
    information."""
    
    try:
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                                  int(person_info['personnr'])))
        fnr = fodselsnr.personnr_ok(fnr)
        logger.info2("Process %s " % (fnr), append_newline=0)

        (year, mon, day) = fodselsnr.fodt_dato(fnr)
        if (year < 1970
            and getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1):
            # Seems to be a bug in time.mktime on some machines
            year = 1970
    except fodselsnr.InvalidFnrError:
        logger.warn("Ugyldig fødselsnr: %s" % fnr)
        return

    gender = co.gender_male
    if(fodselsnr.er_kvinne(fnr)):
        gender = co.gender_female

    etternavn = fornavn = None
    studentnr = None
    affiliations = []
    address_info = None
    aktiv_sted = []
    # Iterate over all person_info entries and extract relevant data    
    for dta_type in person_info.keys():
        x = person_info[dta_type]
	p = x[0]
        if isinstance(p, str):
            continue
        # Get name
        if dta_type in ('aktiv','tilbud','evu', 'privatist_studieprogram',):
            etternavn = p['etternavn']
            fornavn = p['fornavn']
        if p.has_key('studentnr_tildelt'):
            studentnr = p['studentnr_tildelt']
	else: 
	    logger.info("\n%s mangler studentnr!" % fnr)
        # Get address
        if address_info is None:
	    if dta_type in ('privatist_studieprogram',):
            	address_info = _ext_address_info(p, 'adrlin1_semadr',
            	'adrlin2_semadr', 'adrlin3_semadr',
            	'postnr_semadr', 'adresseland_semadr')
            	if address_info is None:
               		address_info = _ext_address_info( p,
                    	'adrlin1_hjemsted', 'adrlin2_hjemsted',
                    	'adrlin3_hjemsted', 'postnr_hjemsted',
                    	'adresseland_hjemsted')
            elif dta_type in ('evu',):
                address_info = _ext_address_info(p, 'adrlin1_hjem',
                'adrlin2_hjem', 'adrlin3_hjem', 'postnr_hjem',
                'adresseland_hjem')
                if address_info is None:
                	address_info = _ext_address_info(p,
                    	'adrlin1_hjemsted', 'adrlin2_hjemsted',
                    	'adrlin3_hjemsted', 'postnr_hjemsted',
                    	'adresseland_hjemsted')
            elif dta_type in ('tilbud',):
                	address_info = _ext_address_info(p,
                    	'adrlin1_hjemsted', 'adrlin2_hjemsted',
                    	'adrlin3_hjemsted', 'postnr_hjemsted',
                    	'adresseland_hjemsted')

        # Get affiliations
        # Lots of changes here compared to import_FS.py @ uio
	# TODO: split import_FS into a common part and organization spesific parts
        if dta_type in ('aktiv', ):
	  for row in x:
	      # aktiv_sted is necessary in order to avoid different affiliation statuses
	      # to a same 'stedkode' to be overwritten 
              # e.i. if a person has both affiliations status 'tilbud' and
	      # aktive to a single stedkode we want to register the status 'aktive'
	      # in cerebrum
              if studieprog2sko[row['studieprogramkode']] is not None:
                  aktiv_sted.append(int(studieprog2sko[row['studieprogramkode']]))
		  _process_affiliation(co.affiliation_student,
				       co.affiliation_status_student_aktiv, affiliations,
				       studieprog2sko[row['studieprogramkode']])
	elif dta_type in ('evu',):
	  for row in x:
	        _process_affiliation(co.affiliation_student,
				     co.affiliation_status_student_evu,
				     affiliations, studieprog2sko[row['studieprogramkode']])
        elif dta_type in ('privatist_studieprogram', ):
	  for row in x:
                _process_affiliation(co.affiliation_student,
				     co.affiliation_status_student_privatist,
				     affiliations, studieprog2sko[row['studieprogramkode']])
        elif dta_type in ('tilbud', ):
	  for row in x:
              subtype = co.affiliation_status_student_tilbud
              if studieprog2sko[row['studieprogramkode']] in aktiv_sted:
                  subtype = co.affiliation_status_student_aktiv
	      _process_affiliation(co.affiliation_student,
                                   subtype, affiliations,
                                   studieprog2sko[row['studieprogramkode']])
	# HiA does not have "real" evu-students yet. this means that the evu-students get 
	# an affiliation in much the same way as other students, commenting this code out
	# might present a problem at a later time an should be considered as a temporary
	# solution
        #elif dta_type in ('evu', ):
        #    _process_affiliation(co.affiliation_student,
        #                         co.affiliation_status_student_evu,
        #                         affiliations, _get_sko(p, 'faknr_adm_ansvar',
        #                         'instituttnr_adm_ansvar', 'gruppenr_adm_ansvar'))
            
            
    if etternavn is None:
        logger.warn("Ikke noe navn på %s" % fnr)
        return

    # TODO: If the person already exist and has conflicting data from
    # another source-system, some mechanism is needed to determine the
    # superior setting.
    
    new_person = Factory.get('Person')(db)
    if fnr2person_id.has_key(fnr):
        new_person.find(fnr2person_id[fnr])
    new_person.populate(db.Date(year, mon, day), gender)

    new_person.affect_names(co.system_fs, co.name_first, co.name_last)
    new_person.populate_name(co.name_first, fornavn)
    new_person.populate_name(co.name_last, etternavn)


    if studentnr is not None:
        new_person.affect_external_id(co.system_fs,
                                      co.externalid_fodselsnr,
                                      co.externalid_studentnr)
        new_person.populate_external_id(co.system_fs, co.externalid_studentnr,
                                        studentnr)
    else:
        new_person.affect_external_id(co.system_fs,
                                      co.externalid_fodselsnr)
    new_person.populate_external_id(co.system_fs, co.externalid_fodselsnr, fnr)

    if address_info is not None:
        new_person.populate_address(co.system_fs, co.address_post, **address_info)
    # if this is a new Person, there is no entity_id assigned to it
    # until written to the database.
    op = new_person.write_db()
    for a in affiliations:
        ou, aff, aff_status = a
        new_person.populate_affiliation(co.system_fs, ou, aff, aff_status)
	if include_delete:
	    key_a = "%s:%s:%s" % (new_person.entity_id,ou,int(aff))
	    if old_aff.has_key(key_a):
	    	old_aff[key_a] = False

    op2 = new_person.write_db()
    if op is None and op2 is None:
        logger.info2("**** EQUAL ****")
    elif op == True:
        logger.info2("**** NEW ****")
    else:
        logger.info2("**** UPDATE ****")

    # Reservations    
    if gen_groups:
        should_add = False
        for dta_type in person_info.keys():
            p = person_info[dta_type][0]
            if isinstance(p, str):
                continue
            # We only fetch the column in these queries
            if dta_type not in ('tilbud', 'aktiv', 'privatist_studieprogram', 
				'evu',):
                continue
            # If 'status_reserv_nettpubl' == "N": add to group
            if p.get('status_reserv_nettpubl', "") == "N":
                should_add = True
            else:
                should_add = False
        if should_add:
            # The student has explicitly given us permission to be
            # published in the directory.
            _add_res(new_person.entity_id)
        else:
            # The student either hasn't registered an answer to
            # the "Can we publish info about you in the directory"
            # question at all, or has given an explicit "I don't
            # want to appear in the directory" answer.
            _rem_res(new_person.entity_id)
    db.commit()



def main():
    global verbose, ou, db, co, logger, fnr2person_id, gen_groups, group, \
							old_aff, include_delete
    verbose = 0
    include_delete = False
    opts, args = getopt.getopt(sys.argv[1:], 'vp:s:gdf', [
        'verbose', 'person-file=', 'studieprogram-file=',
        'generate-groups','include-delete', ])

    personfile = default_personfile
    studieprogramfile = default_studieprogramfile
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            verbose += 1
        elif opt in ('-p', '--person-file'):
            personfile = val
        elif opt in ('-s', '--studieprogram-file'):
            studieprogramfile = val
        elif opt in ('-g', '--generate-groups'):
            gen_groups = True
	elif opt in ('-d', '--include-delete'):
	    include_delete = True
    if "system_fs" not in cereconf.SYSTEM_LOOKUP_ORDER:
        print "Check your config, SYSTEM_LOOKUP_ORDER is wrong!"
        sys.exit(1)
    logger = AutoStud.Util.ProgressReporter("./fsi-run.log.%i" % os.getpid(),
                                            stdout=verbose)
    logger.info("Started")
    db = Factory.get('Database')()
    db.cl_init(change_program='import_FS')
    ou = Factory.get('OU')(db)
    co = Factory.get('Constants')(db)

    group = Factory.get('Group')(db)
    try:
	group.find_by_name(group_name)
    except Errors.NotFoundError:
	group.clear()
	ac = Factory.get('Account')(db)
	ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
	group.populate(ac.entity_id, co.group_visibility_internal,
                       group_name, group_desc)
	group.write_db()
    if getattr(cereconf, "ENABLE_MKTIME_WORKAROUND", 0) == 1:
        logger.warn("Warning: ENABLE_MKTIME_WORKAROUND is set")

    for s in StudentInfo.StudieprogDefParser(studieprogramfile):
        studieprog2sko[s['studieprogramkode']] = \
            _get_sko(s, 'faknr_studieansv', 'instituttnr_studieansv',
                     'gruppenr_studieansv')

    # create fnr2person_id mapping, always using fnr from FS when set
    person = Factory.get('Person')(db)
    if include_delete:
	old_aff = _load_cere_aff()
    fnr2person_id = {}
    for p in person.list_external_ids(id_type=co.externalid_fodselsnr):
        if co.system_fs == p['source_system']:
            fnr2person_id[p['external_id']] = p['person_id']
        elif not fnr2person_id.has_key(p['external_id']):
            fnr2person_id[p['external_id']] = p['person_id']
    StudentInfo.StudentInfoParser(personfile, process_person_callback, logger)
    if include_delete:
	rem_old_aff()
    db.commit()
    logger.info("Completed")

if __name__ == '__main__':
    main()


# arch-tag: ca21cc6d-a220-4125-9c0f-d21b524ef73d
