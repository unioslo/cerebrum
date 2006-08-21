#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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


import sys
import locale
import os
import getopt
import time
import string

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
#from Cerebrum.modules.no.uit import access_FS
from Cerebrum.modules.no import access_FS
from Cerebrum import Database
from Cerebrum import Person
from Cerebrum import Group
from Cerebrum.modules.no import Stedkode
from Cerebrum.modules.no.uit import uit_fronter_lib
from Cerebrum.extlib import logging
from Cerebrum.modules import Email
from Cerebrum.modules.no.uit.Email import email_address

db = const = logger = None
fxml = None
romprofil_id = {}

#logging.fileConfig(cereconf.LOGGING_CONFIGFILE_NEW)
#logger = logging.getLogger("console")

#logger = Factory.get_logger("console")
logger = Factory.get_logger("cronjob")


def init_globals():
    global db, const, logger
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    
    #logger = Factory.get_logger("console")
    #logging.fileConfig(cereconf.LOGGING_CONFIGFILE_NEW)
    #logger = logging.getLogger("console")
   
    cf_dir = os.path.join(cereconf.DUMPDIR, 'Fronter')
    log_dir = os.path.join(cereconf.CB_PREFIX,'var','log')

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h:',
                                   ['host=', 'rom-profil=',
                                    'debug-file=', 'debug-level='])
    except getopt.GetoptError:
        usage(1)
    debug_file = os.path.join(log_dir, "x-import.log")
    debug_level = 4
    host = 'uit'
    for opt, val in opts:
        if opt in ('-h', '--host'):
            host = val
        elif opt == '--debug-file':
            debug_file = val
        elif opt == '--debug-level':
            debug_level = val
        elif opt == 'rom-profil':
            profil_navn, profil_id = val.split(':')
            romprofil_id[profil_navn] = profil_id
        else:
            raise ValueError, "Invalid argument: %r", (opt,)

    host_profiles = {'uit': {'emnerom': 128, # old value 1520
                             'studieprogram': 128},# old value 1521
                     'uit2': {'emnerom': 42,
                              'studieprogram': 42},
                     'uit3': {'emnerom': 128, # old value 1520
                              'studieprogram': 128} # old value 1521
                     }
    if host_profiles.has_key(host):
        romprofil_id.update(host_profiles[host])

    filename = os.path.join(cf_dir, 'test.xml')
    if len(args) == 1:
        filename = args[0]
    elif len(args) <> 0:
        usage(2)

    global fxml
    fxml = uit_fronter_lib.FronterXML(filename,
                                  cf_dir = cf_dir,
                                  debug_file = debug_file,
                                  debug_level = debug_level,
                                  fronter = None)

def get_semester():
    t = time.localtime()[0:2]
    this_year = t[0]
    if t[1] <= 6:
        this_sem = 'vår'
        next_year = this_year
        next_sem = 'høst'
    else:
        this_sem = 'høst'
        next_year = this_year + 1
        next_sem = 'vår'
    return ((str(this_year), this_sem), (str(next_year), next_sem))

def load_acc2name():
    #etarget = Email.EmailTarget(db)
    #ea = Email.EmailAddress(db)
    #rewrite = Email.EmailDomain(db).rewrite_special_domains
    person = Person.Person(db)
    account = Factory.get('Account')(db)
    #const = Factory.get('Constants')(db)
    logger.debug('Loading person/user-to-names table')
    ret = {}
    my_email = {}
    front = uit_fronter_lib.uitfronter(db)
    """	Followin field in fronter_lib.hiafronter.list_cf_persons
	person_id, account_id, external_id, name, entity_name,
	fs_l_name, fs_f_name, local_part, domain """
    
    for pers in front.list_cf_persons():
	#logger.debug("Loading person: %s" % pers['name'])
	if not (pers['fs_f_name'] and pers['fs_l_name']):
	    l_name, f_name = get_names(pers['person_id'])
	else:
	    l_name, f_name = pers['fs_l_name'],pers['fs_f_name']
        
        #UIT: added next line to get email address for account going to classfronter
        person.clear()
        person.find(pers['person_id'])
        primary_account = person.get_primary_account()
        account.clear()
        account.find(primary_account)
        try:
            my_email = account.get_primary_mailaddress()
        except Errors.NotFoundError:
            # Person has no mail account. Drop person. Log an error an continue on next
            logger.error("Person %s %s with account %s (acc_id=%d) has no mail adress"  % (f_name,
                                                                                           l_name,
                                                                                           account.account_name,
                                                                                           account.entity_id))
            continue
        
        
        ret[pers['account_id']] = {
            'NAME': pers['entity_name'],
            'FN': pers['name'],
            'GIVEN': f_name,
            'FAMILY': l_name,
            #'EMAIL': '@'.join((pers['entity_name'],'%s' % my_email_domain)),
            'EMAIL': my_email,
            'USERACCESS': 2,
            #'PASSWORD': 1,
            'PASSWORD_TYPE':1,
            #'PASSWORD_CRYPT': auth_data,
            'EMAILCLIENT': 1}
       
    return ret

def get_names(person_id):
    name_tmp = {}
    person = Factory.get('Person')(db)
    person.find(person_id)
    for names in person.get_all_names():
	if int(names['source_system']) <> int(const.system_cached):
	    sys_key = int(names['source_system'])
            sys_names = name_tmp.setdefault(sys_key, [])
	    name_li = "%s:%s" % (names['name_variant'], names['name'])
            sys_names.append(name_li)
    last_n = first_n = None
    for a_sys in cereconf.SYSTEM_LOOKUP_ORDER:
	sys_key = int(getattr(const, a_sys))
        for p_name in name_tmp.get(sys_key, []):
            var_n, nam_n = p_name.split(':')
            if (int(var_n) == int(const.name_last)):
                last_n = nam_n
            elif (int(var_n) == int(const.name_first)):
                first_n = nam_n
            else: pass
            if first_n is not None and last_n is not None:
                return (last_n, first_n)
    return ("*Ukjent etternavn*", "*Ukjent fornavn*")

def get_ans_fak(fak_list, ent2uname):
    fak_res = {}
    person = Factory.get('Person')(db)
    stdk = Stedkode.Stedkode(db)
    for fak in fak_list:
        ans_list = []
        # Get all stedkoder in one faculty
        for ou in stdk.get_stedkoder(fakultet=int(fak)):
            # get persons in the stedkode
            for pers in person.list_affiliations(source_system=const.system_lt,
                                        affiliation=const.affiliation_ansatt,
                                        ou_id=int(ou['ou_id'])):
                person.clear()
                #person.entity_id = int(pers['person_id'])
                try:
		    person.find(int(pers['person_id']))
                    acc_id = person.get_primary_account()
                except Errors.NotFoundError:
                    logger.error("Person pers_id: %d , no valid account!" % \
                                 person.entity_id)
                    break
		if acc_id and ent2uname.has_key(acc_id):
		    uname = ent2uname[acc_id]['NAME']
		    if uname not in ans_list:
			ans_list.append(uname)
		else:
		    logger.error("Person pers_id: %d have no account!" % \
							person.entity_id)
        fak_res[int(fak)] = ans_list
    return fak_res


def register_spread_groups(emne_info, stprog_info):
    group = Factory.get('Group')(db)
    for r in group.search(spread=const.spread_uit_fronter):
        #print "GROUP.SEARCH: %s" % r
        gname = r['name']
        gname_el = gname.split(':')
        if gname_el[4] == 'undenh':
            # Nivå 3: internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
            #           TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR
            #
            # De interessante gruppene (som har brukermedlemmer) er på
            # nivå 4.
            instnr = gname_el[3]
            ar, term, emnekode, versjon, terminnr = gname_el[5:10]
            #print "AR = '%s'" % ar
            #print "emnekode = '%s'" % emnekode
            #print "term = '%s'" % term
            if int(ar) < 2006:
                #print "CONTINUE"
                continue
            #print "emne_info emnekode = '%s'" % emne_info[emnekode]
            fak_sko = "%02d0000" % emne_info[emnekode]['fak']

            # Rom for undervisningsenheten.
            emne_id_prefix = '%s:fs:emner:%s:%s:%s:%s' % (
                cereconf.INSTITUTION_DOMAIN_NAME,
                ar, term, instnr, fak_sko)
            my_emne_id_prefix = '%s:fs:emner:%s:%s:emnerom:%s:%s' % (
                cereconf.INSTITUTION_DOMAIN_NAME,
                ar, term, instnr, fak_sko)

            
            emne_sted_id = 'STRUCTURE:%s' % my_emne_id_prefix

            # UIT: we need to represent emenrom with an indication of which termin this
            # emenroom is for. f.eks a room with terminkode 1,2 and 3 would need something like
            # (course_name - semester 1)
            # (course_name - semester 2)
            # (course_name - semester 3)
            # This to diffenrentiate between the different semesters a course can be in.
            #if terminnr != "1":
            #    termin_representation = "%s. semester" % terminnr
            #    emne_rom_id = 'ROOM:%s:undenh:%s (%s):%s:%s' % (emne_id_prefix,emnekode,termin_representation,versjon,terminnr)
            #else:
            emne_rom_id = 'ROOM:%s:undenh:%s:%s:%s' % (
                emne_id_prefix, emnekode, versjon, terminnr)

            #print "--> emnerom = %s" % emne_rom_id
            ##print "emnenavnfork == '%s'" % emne_info[emnekode]['emnenavnfork'] # UIT

            #UIT register_room with versjon and int(terminnr) substituted with emne_info[emnekode]['emnenavnfork']
            termin_representation = "%s. Sem" % terminnr
            register_room('%s - %s (%s)' %
                          (emnekode.upper(), emne_info[emnekode]['emnenavnfork'],termin_representation),
                          emne_rom_id, emne_sted_id,
                          profile=romprofil_id['emnerom'])

            #register_room('%s (ver %s, %d. termin)' %
            #              (emnekode.upper(), versjon, int(terminnr)),
            #              emne_rom_id, emne_sted_id,
            #              profile=romprofil_id['emnerom'])


            # Grupper for studenter, forelesere og studieveileder på
            # undervisningsenheten.
            group.clear()
            group.find(r['group_id'])
	    for op, subg_id, subg_name in \
                    group.list_members(None, int(const.entity_group),
                                       get_entity_name=True)[0]:
                # Nivå 4: internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
                #           TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR:KATEGORI
                subg_name_el = subg_name.split(':')
                # Fjern "internal:"-prefiks.
                if subg_name_el[0] == 'internal':
                    subg_name_el.pop(0)
                kategori = subg_name_el[9]
                parent_id = 'STRUCTURE:%s:fs:emner:%s:%s:%s' % (
                    subg_name_el[0],    # DOMAIN
                    subg_name_el[4],    # ARSTALL
                    subg_name_el[5],    # TERMINKODE
                    kategori
                    )
                if kategori == 'student':
                    title = 'Studenter på '
                    rettighet = uit_fronter_lib.Fronter.ROLE_WRITE
                elif kategori == 'foreleser':
                    title = 'Forelesere på '
                    rettighet = uit_fronter_lib.Fronter.ROLE_DELETE
                elif kategori == 'studieleder':
                    title = 'Studieledere for '
                    rettighet = uit_fronter_lib.Fronter.ROLE_DELETE
                else:
                    raise RuntimeError, "Ukjent kategori: %r" % (kategori,)
                #title += '%s (ver %s, %d. termin)' % (
                #    subg_name_el[6].upper(), # EMNEKODE
                #    subg_name_el[7],    # VERSJONSKODE
                #    int(subg_name_el[8])) # TERMINNR
                # UIT TITLE:
                title += '%s' % (subg_name_el[6].upper()) # EMNEKODE

                fronter_gname = ':'.join(subg_name_el)
                print "$15"
                register_group(title, fronter_gname, parent_id,
                               allow_contact=True)
                group.clear()
                group.find(subg_id)
                user_members = [
                    row[2]  # username
                    for row in group.list_members(None,
                                                  const.entity_account,
                                                  get_entity_name=True)[0]]
                ##print "2.group_name = %s"% fronter_gname
                ##for i in user_members:
                ##    print"members: %s" % (i)

                if user_members:
                    register_members(fronter_gname, user_members)
                register_room_acl(emne_rom_id, fronter_gname, rettighet)

	elif gname_el[4] == 'studieprogram':
            ##print "gname data = %s" % (gname_el)
            # En av studieprogram-grenene på nivå 3.  Vil eksportere
            # gruppene på nivå 4.
            group.clear()
            group.find(r['group_id'])
	    # Legges inn new group hvis den ikke er opprettet
            for op, subg_id, subg_name in \
                    group.list_members(None, int(const.entity_group),
                                       get_entity_name=True)[0]:
                subg_name_el = subg_name.split(':')
                # Fjern "internal:"-prefiks.
                if subg_name_el[0] == 'internal':
                    subg_name_el.pop(0)
                fronter_gname = ':'.join(subg_name_el)
                institusjonsnr = subg_name_el[2]
                stprog = subg_name_el[4]
                #if(stprog_info[stprog]['fak'] != 'samfkhf'
                fak_sko = '%02d0000' % stprog_info[stprog]['fak']
                # Opprett fellesrom for dette studieprogrammet.
                fellesrom_sted_id = ':'.join((
                    'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME,
                    'fs', 'fellesrom', subg_name_el[2], # institusjonsnr
                    fak_sko))
                fellesrom_stprog_rom_id = ':'.join((
                    'ROOM', cereconf.INSTITUTION_DOMAIN_NAME, 'fs',
                    'fellesrom', 'studieprogram', stprog))
                register_room(stprog.upper(), fellesrom_stprog_rom_id,
                              fellesrom_sted_id,
                              profile=romprofil_id['studieprogram'])
                if subg_name_el[-1] == 'student':
                    brukere_studenter_id = ':'.join((
                        'STRUCTURE', cereconf.INSTITUTION_DOMAIN_NAME,
                        'fs', 'brukere', subg_name_el[2], # institusjonsnr
                        fak_sko, 'student'))
                    brukere_stprog_id = brukere_studenter_id + \
                                        ':%s' % stprog
                    print "$18"
                    register_group(stprog.upper(), brukere_stprog_id,
                                   brukere_studenter_id)
                    print "$19"
                    register_group(
                        'Studenter på %s' % subg_name_el[6], # kullkode
                        fronter_gname, brukere_stprog_id,
                        allow_contact=True)
                    # Gi denne studiekullgruppen 'skrive'-rettighet i
                    # studieprogrammets fellesrom.
                    register_room_acl(fellesrom_stprog_rom_id, fronter_gname,
                                      uit_fronter_lib.Fronter.ROLE_WRITE)
                elif subg_name_el[-1] == 'studieleder':
                    fellesrom_studieledere_id = fellesrom_sted_id + \
                                                ':studieledere'
                    print "$20"
                    register_group("Studieledere", fellesrom_studieledere_id,
                                   fellesrom_sted_id)
                    print "$21"
                    register_group(
                        "Studieledere for program %s" % stprog.upper(),
                        fronter_gname, fellesrom_studieledere_id,
                        allow_contact=True)
                    # Gi studieleder-gruppen 'slette'-rettighet i
                    # studieprogrammets fellesrom.
                    register_room_acl(fellesrom_stprog_rom_id, fronter_gname,
                                       uit_fronter_lib.Fronter.ROLE_DELETE)
                else:
                    raise RuntimeError, \
                          "Ukjent studieprogram-gruppe: %r" % (gname,)

                # Synkroniser medlemmer i Cerebrum-gruppa til CF.
                group.clear()
                group.find(subg_id)
                user_members = [
                    row[2]  # username
                    for row in group.list_members(None,
                                                  const.entity_account,
                                                  get_entity_name=True)[0]]
                #print "1.group_name = %s" % fronter_gname
                ##for i in user_members:
                    ##print"members: %s" % (i)
                if user_members:
                    register_members(fronter_gname, user_members)
        else:
            raise RuntimeError, \
                  "Ukjent type gruppe eksportert: %r" % (gname,)

new_acl = {}
def register_room_acl(room_id, group_id, role):
    new_acl.setdefault(room_id, {})[group_id] = {'role': role}

def register_structure_acl(node_id, group_id, contactAccess, roomAccess):
    new_acl.setdefault(node_id, {})[group_id] = {'gacc': contactAccess,
                                                 'racc': roomAccess}

new_groupmembers = {}
def register_members(gname, members):
    new_groupmembers[gname] = members

new_rooms = {}
def register_room(title, id, parentid, profile):
    new_rooms[id] = {
        'title': title,
        'parent': parentid,
        'CFid': id,
        'profile': profile}

new_group = {}
def register_group(title, id, parentid,
                   allow_room=False, allow_contact=False):
    """Adds info in new_group about group."""

    # inserting function to filter out institution number different than 186
        
    #start,end = id.split(":",2)

    #print "temp id check= %s" % (id)
    #sys.exit(1)
    found = -1
    found2 = -1
    found = id.find(":195:")
    found2 = id.find(":4902:")
    #print "found = %s" % found
    if ((found == -1) and (found2 == -1)):
        
            
        print "##############################"
        print "title = %s" % title
        print "parent = %s" % parentid
        print "allow_room =%s" % allow_room
        print "allow_contact = %s" % allow_contact
        print "CFid = %s " % id
        print "##############################"
            
        new_group[id] = { 'title': title,
                          'parent': parentid,
                          'allow_room': allow_room,
                          'allow_contact': allow_contact,
                          'CFid': id,
                          }
    else:
        logger.warn("not inserting: '%s'" % id)
        #print "not inserting -> " % id

def output_group_xml():
    """Generer GROUP-elementer uten forover-referanser."""
    done = {}
    def output(id):
        #for k,v in new_group.items():
        #    print k,v
        if id in done:
            return

        #print "id=(%s)" % id
        data = new_group[id]
        parent = data['parent']
        #print "..parent=(%s)" % parent
        if parent <> id:
            output(parent)
        fxml.group_to_XML(data['CFid'], uit_fronter_lib.Fronter.STATUS_ADD, data)
        done[id] = True
    for group in new_group.iterkeys():
        #print "##############new group='%s'" % group
        output(group)

def usage(exitcode):
    print "Usage: export_xml_fronter.py OUTPUT_FILENAME"
    sys.exit(exitcode)



def main():
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591')) # edited 7 july. removing iso88591

    init_globals()

    fxml.start_xml_head()

    # Finn `account_id` -> account-data for alle brukere.
    acc2names = load_acc2name()
    # Spytt ut PERSON-elementene.
    for user in acc2names.itervalues():
	# 2 = recstatus modify fix denne senere # uit
	fxml.user_to_XML(user['NAME'],2,user)

    # Registrer en del semi-statiske strukturnoder.
    root_node_id = "STRUCTURE:ClassFronter structure root node"

    print "$16"
    register_group('Universitetet i Tromsø', root_node_id, root_node_id)

    manuell_node_id = 'STRUCTURE:%s:manuell' % \
                      cereconf.INSTITUTION_DOMAIN_NAME
    print "$17"
    register_group('Manuell', manuell_node_id, root_node_id,
                   allow_room=True)

    emner_id = 'STRUCTURE:%s:fs:emner' % cereconf.INSTITUTION_DOMAIN_NAME
    print "$11#"
    register_group('Emner', emner_id, root_node_id)

    this_sem, next_sem = get_semester()
    emner_this_sem_id = emner_id + ':%s:%s' % tuple(this_sem)
    emner_next_sem_id = emner_id + ':%s:%s' % tuple(next_sem)
    print "$10#"
    register_group('Emner %s %s' % (this_sem[1].upper(), this_sem[0]),
                   emner_this_sem_id, emner_id)
    print "$9#"
    register_group('Emner %s %s' % (next_sem[1].upper(), next_sem[0]),
                   emner_next_sem_id, emner_id)

    emnerom_this_sem_id = emner_this_sem_id + ':emnerom'
    emnerom_next_sem_id = emner_next_sem_id + ':emnerom'
    print "$8#"
    register_group('Emnerom %s %s' % (this_sem[1].upper(), this_sem[0]),
                   emnerom_this_sem_id, emner_this_sem_id)
    print "$7#"
    register_group('Emnerom %s %s' % (next_sem[1].upper(), next_sem[0]),
                   emnerom_next_sem_id, emner_next_sem_id)

    for sem, sem_node_id in ((this_sem, emner_this_sem_id),
                             (next_sem, emner_next_sem_id)):
        for suffix, title in (
            ('student', 'Studenter %s %s' % (sem[1].upper(),
                                             sem[0])),
            ('foreleser', 'Forelesere %s %s' % (sem[1].upper(),
                                                sem[0])),
            ('studieleder', 'Studieledere %s %s' % (sem[1].upper(),
                                                    sem[0]))):
            node_id = sem_node_id + ':' + suffix
            #print "7"
            print "$6#"
            register_group(title, node_id, sem_node_id)

    brukere_id= 'STRUCTURE:%s:fs:brukere' % cereconf.INSTITUTION_DOMAIN_NAME
    print "$5#"
    register_group('Brukere', brukere_id, root_node_id)

    #fellesrom_id = 'STRUCTURE:%s:fs:fellesrom' % \
    fellesrom_id = 'STRUCTURE:%s:fs:fellesrom:186:000000' % \
                   cereconf.INSTITUTION_DOMAIN_NAME
    print "$4#"
    register_group('Fellesrom', fellesrom_id, root_node_id)

    # Populer dicter for "emnekode -> emnenavn" og "fakultet ->
    # [emnekode ...]".
    emne_info = {}
    fak_emner = {}
    def finn_emne_info(element, attrs):
        
        if element <> 'undenhet':
            return
        #print "##emnenavnfork = %s" % attrs['emnenavnfork']
        #print "##attrs['emnekode'] = %s " % attrs['emnekode']
        emnenavnfork = attrs['emnenavnfork']
        emnekode = attrs['emnekode'].lower()
        faknr = int(attrs['faknr_kontroll'])
        emne_info[emnekode] = {'navn': attrs['emnenavn_bokmal'],
                               'fak': faknr, 'emnenavnfork' : emnenavnfork} # UIT: added emnenavnfork
        fak_emner.setdefault(faknr, []).append(emnekode)
    
    #access_FS.underv_enhet_xml_parser("/cerebrum/var/dumps/FS/imports/underv_enhet.xml",
    #                                  finn_emne_info)

    
    access_FS.underv_enhet_xml_parser(cereconf.UIT_UNDERV_ENHET_FILE,
                                      finn_emne_info)
    

    stprog_info = {}
    def finn_stprog_info(element, attrs):
        if element == 'studprog':
            stprog = attrs['studieprogramkode'].lower()
            faknr = int(attrs['faknr_studieansv'])
            stprog_info[stprog] = {'fak': faknr}
    access_FS.studieprog_xml_parser(cereconf.UIT_STUDIEPROG_FILE,
                                    finn_stprog_info)
    # Henter ut ansatte per fakultet
    fak_temp = fak_emner.keys() # UIT
    fak_temp.append(74) # UIT. We add 74 (which is UVETT)
    fak_temp.append(99) # UIT. we add 99 (which is external units)
    ans_dict = get_ans_fak(fak_temp,acc2names)  # UIT
    #ans_dict = get_ans_fak(fak_emner.keys(),acc2names) 

    # Opprett de forskjellige stedkode-korridorene.
    ou = Stedkode.Stedkode(db)
    #print "FOO =%s" % fak_emner.items()
    #temp = fak_emner.keys()
    #temp_fak_value = 0
    #temp.append(temp_fak_value)
    #fak_temp = fak_emner.keys() # UIT
    #fak_temp.append(74) # UIT. We add 74 (which is UVETT)

    #for faknr in fak_emner.keys():
    #    print "faknr = %s" % faknr
    #sys.exit(1)
    for faknr in fak_temp: # UIT
        
        fak_sko = "%02d0000" % faknr
        
        ou.clear()
        try:
	    ou.find_stedkode(faknr, 0, 0,
                             institusjon = cereconf.DEFAULT_INSTITUSJONSNR)
	except Errors.NotFoundError:
	    logger.error("Finner ikke stedkode for fakultet %d", faknr)
            faknavn = '*Ikke registrert som fakultet i FS*'
        else:
            if ou.acronym:
                faknavn = ou.acronym
            else:
                faknavn = ou.short_name
        fak_ans_id = "%s:sap:gruppe:%s:%s:ansatte" % \
                     (cereconf.INSTITUTION_DOMAIN_NAME,
                      cereconf.DEFAULT_INSTITUSJONSNR,
                      fak_sko)
        ans_title = "Ansatte ved %s" % faknavn
        print "$12#"
        register_group(ans_title, fak_ans_id, brukere_id,
                       allow_contact=True)
        ans_memb = ans_dict[int(faknr)]

        ##print "1.group_name = %s" % fak_ans_id
        ##for i in ans_memb:
        ##    print"members: %s" % (i)
        register_members(fak_ans_id, ans_memb)
        for sem_node_id in (emnerom_this_sem_id,
                            emnerom_next_sem_id):
            fak_node_id = sem_node_id + \
                          ":%s:%s" % (cereconf.DEFAULT_INSTITUSJONSNR,
                                      fak_sko)
            print "$13#"
            register_group(faknavn, fak_node_id, sem_node_id,
                           allow_room=True)
        brukere_sted_id = brukere_id + \
                          ":%s:%s" % (cereconf.DEFAULT_INSTITUSJONSNR,
                                      fak_sko)
        print "$3#"
        register_group(faknavn, brukere_sted_id, brukere_id)
        brukere_studenter_id = brukere_sted_id + ':student'
        print "$2#"
        register_group('Studenter ved %s' % faknavn,
                       brukere_studenter_id, brukere_sted_id)
        fellesrom_sted_id = ("STRUCTURE:uit.no:fs:fellesrom") # UIT
        
        #fellesrom_sted_id = fellesrom_id + ":%s:%s" % (
        fellesrom_sted_id = fellesrom_sted_id + ":%s:%s" % (
            cereconf.DEFAULT_INSTITUSJONSNR, fak_sko)
        print "$1#"
        register_group(faknavn, fellesrom_sted_id, fellesrom_id,
                       allow_room=True)

    register_spread_groups(emne_info, stprog_info)

    output_group_xml()
    for room, data in new_rooms.iteritems():
        fxml.room_to_XML(data['CFid'], uit_fronter_lib.Fronter.STATUS_ADD, data)

    for node, data in new_acl.iteritems():
        fxml.acl_to_XML(node, uit_fronter_lib.Fronter.STATUS_ADD, data)
        

    ### lets print out all members in a group
    ##for gname,member in new_groupmembers.iteritems():
    ##    print "gname = %s,member = %s" %(gname,member)

    for gname, members in new_groupmembers.iteritems():
        fxml.personmembers_to_XML(gname, uit_fronter_lib.Fronter.STATUS_ADD,
                                  members)
    fxml.end()





if __name__ == '__main__':
    main()

# arch-tag: afa8c990-b426-11da-8ea8-699d23c0e39e
