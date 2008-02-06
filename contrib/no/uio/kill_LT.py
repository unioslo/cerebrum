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

"""Remove or copy to source Manual most data registered with source LT.

Note: Name changes schedule a few test-mailboxes to be moved.  Report
these to postmaster, so they can be canceled before they are executed.

Removes:
person_affiliation_source except affiliations marked as deleted:
  Save ANSATT/* -> Manuell/inaktiv_ansatt, unless SAP has same aff/status@ou.
  Save TILKNYTTET/* -> Manuell/gjest,      unless SAP has same aff@ou.
person_name:
  Do not save titles.
  Save other names not overridden in SAP, FS or Manual.
  This causes names from LT to override names from Ureg, which is before
  LT in cereconf.system_lookup_order.
  Cached names which should have been regenerated when LT was moved
  after FS in system_lookup_order, get fixed.
  E-mail addresses are also affected by name changes.
entity_address, entity_contact_info:
  Save OU-data to Manual if not overridden by data from SAP or Manual.
  Check that the remaining OUs have quarantine.
ou_structure[perspective_sap]:
  Not saved.
entity_external_id[externalid_fodselsnr]:
  Saved to Manual if not overridden by data from SAP, FS or Manual.

Remaining LT-data:
LT person_affiliation_source with non-NULL deleted_date,
LT in authoritative_system_code and ou_perspective_code.
"""

Debug = False
Dryrun = Debug

import sys
import getopt

import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum.Entity import EntityContactInfo, EntityAddress
logger = Factory.get_logger("console")
db = Factory.get('Database')()
db.cl_init(change_program="kill_LT")
const, person, ou = [Factory.get(x)(db) for x in 'Constants', 'Person', 'OU']
class CAEntity(EntityContactInfo, EntityAddress, Factory.get("Entity")):
    pass
entity = CAEntity(db)

Log, Info, Warn = None, logger.info, logger.warning
if True:
    Log = file("ltkill.out", "a", 1)
    def Info(txt): print >>Log, txt

system_sap    = int(const.system_sap)
system_fs     = int(const.system_fs)
system_manual = int(const.system_manual)
system_lt     = int(const.system_lt)
better_systems= (system_sap, system_fs, system_manual) # for names and ext.ids

perspective_sap = int(const.perspective_sap)
perspective_lt  = int(const.perspective_lt)

type_ou     = int(const.entity_ou)
type_person = int(const.entity_person)

idtype_fnr  = const.externalid_fodselsnr

drop_names  = (int(const.name_personal_title), int(const.name_work_title))

affiliation_tilknyttet = int(const.affiliation_tilknyttet)
affiliation_ansatt = int(const.affiliation_ansatt)
affiliation_manuell = int(const.affiliation_manuell)
aff2status = {
    affiliation_ansatt: int(const.affiliation_manuell_inaktiv_ansatt),
    affiliation_tilknyttet: int(const.affiliation_manuell_gjest)}

def ckpoint(final=True):
    if not (Debug or Dryrun):
        db.commit()
    elif final:
        db.rollback()

def nint(x):
    if x is not None:
        x = int(x)
    return x

def affiliation():
    """Clean up person_affiliation_source"""
    delrow = dict(deleted_date=True)
    print "affiliation..."
    count_ins = count_del = count_keep = 0
    for ltrow in person.list_affiliations(source_system=system_lt,
                                          include_deleted=False,
                                          fetchall=True):
        if Debug and count_ins >= 100:
            print "Debug done."
            break
        person_id = int(ltrow['person_id'])
        ou_id = int(ltrow['ou_id'])
        affiliation = int(ltrow['affiliation'])
        status = nint(ltrow['status'])
        m_status = aff2status[affiliation]

        person.clear()
        person.find(person_id)

        sys2row = {}
        for row in person.list_affiliations(\
            person_id=person_id, affiliation=affiliation, ou_id=ou_id,
            include_deleted=True):
            sys2row[int(row['source_system'])] = row
        data = "LT affiliation(pers %d, ou %d, aff %d, status %s)" % \
               (person_id, ou_id, affiliation, status)

        if sys2row.get(system_sap, delrow)['deleted_date'] is None \
           and (affiliation == affiliation_tilknyttet
                or status == nint(sys2row[system_sap]['status'])):
            Info("SAP has " + data)
        elif sys2row.get(system_manual, delrow)['deleted_date'] is not None:
            Info("add Manuell for " + data)
            count_ins += 1
            person.add_affiliation(
                ou_id, affiliation_manuell, system_manual, m_status)
        elif m_status != nint(sys2row[system_manual]['status']):
            count_keep += 1
            Info("keep Manual status %s for %s"
                 % (nint(sys2row[system_manual]['status']), data))
        Info("delete " + data)
        count_del += 1
        person.delete_affiliation(ou_id, affiliation, system_lt)
        ckpoint(False)
    person.clear()
    ckpoint()
    Info("*Affiliations: Inserted %d, removed %d, kept manual %d*"
         % (count_ins, count_del, count_keep))

def refresh():
    name(True)

def name(refresh_only=False):
    """
    Clean up person_name, also affecting email addresses.
    If refresh_only, only update Cached names.
    """
    print "name%s..." % ["", " refresh"][refresh_only]
    count_del = count_ins = 0
    name_types = [int(row['code']) for row in person.list_person_name_codes()]
    ltnames = person.getdict_persons_names(
        source_system=system_lt, name_types=name_types)
    for person_id, lt_variant2name in ltnames.iteritems():
        if Debug and count_ins == 300:
            print "Debug done."
            break
        person.clear()
        person.find(person_id)
        if not refresh_only:
            need_variants = set(lt_variant2name).difference(drop_names)
            for row in person.get_all_names():
                if int(row['source_system']) in better_systems:
                    need_variants.discard(int(row['name_variant']))
            if need_variants:
                person.affect_names(system_manual, *need_variants)
                for variant in need_variants:
                    count_ins += 1
                    Info("insert Manual name person_id=%d variant=%d '%s'"
                         % (person_id, variant, lt_variant2name[variant]))
                    person.populate_name(variant, lt_variant2name[variant])
                person.write_db()
                person.clear()
                person.find(person_id)
            for variant, name in lt_variant2name.iteritems():
                count_del += 1
                Info("delete LT name person_id=%d variant=%d '%s'"
                     % (person_id, variant, name))
                person.get_name(system_lt, variant)
                person._delete_name(system_lt, variant)
        person._update_cached_names()
        ckpoint(False)
    person.clear()
    ckpoint()
    if refresh_only:
        Info("*Person_name: Updated %d*" % len(ltnames.keys()))
    else:
        Info("*Person_name: Inserted %d, removed %d*" % (count_ins, count_del))

def contact():
    """Clean up entity_address and entity_contact_info"""
    print "contact..."
    id2type = {}
    for entity_type in type_person, type_ou:
        for row in entity.list_all_with_type(entity_type):
            id2type[int(row['entity_id'])] = entity_type

    ins_a_count = del_a_count = ins_c_count = del_c_count = 0
    sap_OUs = dict([(int(row['ou_id']), nint(row['parent_id']))
                    for row in ou.get_structure_mappings(perspective_sap)])
    sap_OUs = set(sap_OUs).union(set(sap_OUs.values()))
    sap_OUs.discard(None)
    quarantines = set(
        [int(row['entity_id'])
         for row in ou.list_entity_quarantines(entity_types=type_ou,
                                               only_active=False)])

    etype_map = {type_ou: ("ou", ou), type_person: ("person", person)}

    def mklist(listfunc, typename):
        data2type = {}
        for row in listfunc(source_system=system_lt):
            entity_id = int(row['entity_id'])
            data2type.setdefault(int(row['entity_id']), set()
                                 ).add(int(row[typename]))
        manual_data = set()
        for row in listfunc(source_system=system_manual):
            entity_id = int(row['entity_id'])
            manual_data.add(int(row['entity_id']))
        return data2type, manual_data
    addr2type, manual_addr = mklist(
        entity.list_entity_addresses, 'address_type')
    contact2type, manual_contact = mklist(
        entity.list_contact_info, 'contact_type')

    for entity_id in set(addr2type).union(set(contact2type)):
        entity_type = id2type[entity_id]
        in_sap = (entity_id in sap_OUs)
        if entity_type == type_ou:
            if not in_sap and entity_id not in quarantines:
                Warn("Addr/contact: Skip ou_id %d: not in SAP, no quarantine"
                     % entity_id)
                continue
        typename, e = etype_map[entity_type]
        e.clear()
        e.find(entity_id)

        for address_type in addr2type.get(entity_id, ()):
            if entity_id in manual_addr:
                Warn("Addr: Skip %s_id %d: Already has manual address"
                     % (typename, entity_id))
                continue
            for row in list(e.get_entity_address(
                source=system_lt, type=address_type)):
                if entity_type == type_ou and not in_sap:
                    Info("add Manual address: ou_id=%d, type=%d, '%s'" %
                         (entity_id, address_type, row['address_text']))
                    ins_a_count += 1
                    e.add_entity_address(system_manual, address_type,
                                         row['address_text'],
                                         row['p_o_box'],
                                         row['postal_number'],
                                         row['city'],
                                         row['country'])
                Info("delete LT address: %s_id=%d, type=%d, '%s'" %
                     (typename, entity_id, address_type,
                      row['address_text']))
                del_a_count += 1
                e.delete_entity_address(system_lt, address_type)

        for contact_type in contact2type.get(entity_id, ()):
            if entity_id in manual_contact:
                Warn("Contact: Skip %s_id %d: Already has manual contact"
                     % (typename, entity_id))
                continue
            do_del = 0
            for row in e.get_contact_info(
                source=system_lt, type=contact_type):
                if entity_type == type_ou and not in_sap:
                    Info("add Manual contact: ou_id=%d, type=%d, '%s'" %
                         (entity_id, contact_type, row['contact_value']))
                    ins_c_count += 1
                    e.add_contact_info(system_manual, contact_type,
                                         row['contact_value'],
                                         pref=row['contact_pref'],
                                         description=row['description'])
                del_c_count += 1
                do_del += 1
            if do_del:
                Info("delete %d LT contacts: %s_id=%d, type=%d" %
                     (do_del, typename, entity_id, contact_type))
                e.delete_contact_info(system_lt, contact_type)

        ckpoint(False)
    e.clear()
    ckpoint()
    Info("*Addrs/contacts: Inserted %d/%d, removed %d/%d*"
         % (ins_a_count, ins_c_count, del_a_count, del_c_count))

def perspective():
    """Remove ou_structure[perspective_lt]"""
    print "perspective..."
    ou_list = []
    lt_structure = dict([(int(row['ou_id']), nint(row['parent_id']))
                         for row in ou.get_structure_mappings(perspective_lt)])
    while lt_structure:
        for ou_id, parent_id in lt_structure.items():
            if parent_id not in lt_structure or parent_id == ou_id:
                ou_list.append((ou_id, parent_id))
                del lt_structure[ou_id]
    for ou_id, parent_id in reversed(ou_list):
        Info("delete LT perspective %d -> %s" % (ou_id, parent_id))
        ou.clear()
        ou.find(ou_id)
        ou.unset_parent(perspective_lt)
        ckpoint(False)
    ou.clear()
    ckpoint()
    Info("*Perspective: removed %d*" % len(ou_list))

def fnr():
    """Clean up entity_external_id[externalid_fodselsnr]"""
    print "fnr..."
    count_del = count_ins = 0
    ids = [int(row['entity_id'])
           for row in person.list_external_ids(
        source_system=system_lt, id_type=idtype_fnr, entity_type=type_person)]
    for entity_id in ids:
        if Debug and count_ins == 300:
            print "Debug done."
            break
        need, ltrow = True, None
        for row in person.list_external_ids(id_type=idtype_fnr,
                                            entity_id=entity_id):
            s = int(row['source_system'])
            if s == system_lt:
                ltrow = row
            elif s in better_systems:
                need = False
        if not ltrow: continue
        person.clear()
        person.find(entity_id)
        if need:
            Info("insert Manual fnr (external_id=%s entity_id=%d"
                 % (ltrow['external_id'], entity_id))
            count_ins += 1
            person._set_external_id(
                source_system=system_manual, id_type=idtype_fnr,
                external_id=ltrow['external_id'], update=False)
        Info("delete LT fnr (external_id=%s entity_id=%d"
             % (ltrow['external_id'], entity_id))
        count_del += 1
        person._delete_external_id(source_system=system_lt, id_type=idtype_fnr)
        ckpoint(False)
    person.clear()
    ckpoint()
    Info("*External_id: Inserted %d, removed %d*" % (count_ins, count_del))

def main():
    prog_opts = ["affiliation","refresh","name","contact","perspective","fnr"]
    try:
        opts, args = getopt.getopt(sys.argv[1:], "", prog_opts)
    except getopt.GetoptError, e:
        sys.exit(str(e))
    if args:
        sys.exit("Invalid arguments: " + " ".join(args))
    if opts:
        opts = [opt[2:] for opt, val in opts]
    else:
        prog_opts.remove("refresh")
        opts = prog_opts
    if "refresh" in opts and "name" in opts:
        sys.exit("Options --refresh and --name incompatible")

    for opt in prog_opts:
        if opt in opts:
            globals()[opt]()

    if Log: Log.close()

if __name__ == '__main__':
    main()
