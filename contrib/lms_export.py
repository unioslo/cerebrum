#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2007-2008 University of Oslo, Norway
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

# $Id$

import sys
import getopt
import locale

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules.LMS.LMSImport import course2CerebumID
from Cerebrum.modules.no.access_FS import roles_xml_parser

progname = __file__.split("/")[-1]

__doc__ = """
Usage: %s [options]
   -f, --file FILE       Where to generate the exported output. Default: STDOUT
   -h, --help            Prints this message and quits
   -r, --role-file FILE  File that roles should be taken from
   --host HOST           The host that output should be generated for
   --no-import           Do not import data from source system and update groups
   --no-export           Do not generate export to LMS
   -d, --dryrun          Do not commit database changes made during import

* Unless '--no-import' is given, '--role-file' is a mandatory option.
* Unless '--no-export' is given, '--host' is a mandatory option.

This program is a general exporter for populating LMS systems based on
information in Cerebrum and related systems.

The exact sources for import and targets for export, as well as
specific formatting and suchlike, are designated though configuration
that decides which classes and utilities are to be used at various
points in the processing.

""" % progname

__version__ = "$Revision$"
# $Source$


logger = Factory.get_logger("cronjob")

db = Factory.get('Database')()
db.cl_init(change_program=progname[:16])
constants = Factory.get("Constants")(db)

options = {"output": sys.stdout,
           "host": None,
           "dryrun": False,
           "rolefile": None,
           "import": True,
           "export": True}

importer = None
exporter = None

AffiliatedGroups = {}

group_siteid = "nmh-no:fs"
# Inneholder tre av FS-grupper.
fs_supergroup = group_siteid + ":{supergroup}"
subject_supergroup = group_siteid + ":{supersubject}"
class_supergroup = group_siteid + ":{superclass}"

account = Factory.get('Account')(db)
account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
group_creator = account.entity_id

new_acl = {}
new_groupmembers = {}
new_rooms = {}
new_group = {}


def get_group(id):
    """Retrieves group by both numeric id and name."""
    gr = Factory.get('Group')(db)
    if isinstance(id, str):
        gr.find_by_name(id)
    else:
        gr.find(id)
    return gr


def mk_gname(name, prefix=group_siteid):
    if not name.startswith(prefix):
        name = "%s:%s" % (prefix, name)
    return name.lower()


def fnrs2account_ids(rows):
    """Return list of accounts for the persons identified by row(s)."""
    result = []
    for r in rows:
        fnr = "%06d%05d" % (int(r['fodselsdato']), int(r['personnr']))
        if importer.persons.has_key(fnr):
            result.append(importer.persons[fnr])
        else:
            logger.info("Unable to find account for user identified " +
                           "by '%s'" % fnr)
    return result


def parse_xml_roles(fname):
    """
    Parse XML dump of FS roles (roller) and return a mapping structured thus:

    map = { K1 : [ S_1, S_2, ... S_k ],
            ...
            Kn : [ S_1, ..., S_kn ], }

    ... where each K_i is a key falling into one of these four categories:
    undakt, undenh, kursakt, evu; and each S_i is a mapping structured thus:

    map2 = { 'fodselsdato' : ...,
             'personnr'    : ..., }

    S_i are an attempt to mimic db_rows (output from this function is used
    elsewhere where such keys are required).
    """

    result = dict()
    def gimme_lambda(element, data):
        kind = data[roles_xml_parser.target_key]
        if len(kind) > 1:
            logger.warn("Cannot decide on role kind for: %s", kind)
            return
        kind = kind[0]

        if kind in ("undakt", "undenh"):
            key = (data["institusjonsnr"],
                   data["emnekode"],
                   data["versjonskode"],
                   data["terminkode"],
                   data["arstall"],
                   data["terminnr"])
            if kind == "undakt":
                key = key + (data["aktivitetkode"],)

        elif kind in ("evu", ):
            logger.info("Ignoring roles pertaining to EVU-courses for now")
            return

        else:
            logger.warn("%s%s: Wrong role entry kind: %s; '%s'",
                        data["fodselsdato"], data["personnr"], kind, data)
            return


        result.setdefault(key, list()).append(
            { "fodselsdato" : int(data["fodselsdato"]),
              "personnr"    : int(data["personnr"]), })

    roles_xml_parser(fname, gimme_lambda)
    for entry in result.keys():
        logger.debug("Role-mapping: '%s' => '%s'" % (entry, result[entry]))
    return result


def populate_enhet_groups(enhet_id, role_mapping):
    type_id = enhet_id.split(":")
    enhet_type = type_id.pop(0).lower()

    fs = importer.fs_db

    if not enhet_type == 'kurs':
         raise ValueError, "Unable to handle non-'kurs'-enheter yet"

    Instnr, emnekode, versjon, termk, aar, termnr = type_id

    # Finnes det mer enn en undervisningsenhet knyttet til dette
    # emnet, kun forskjellig på versjonskode og/eller terminnr?  I
    # så fall bør gruppene få beskrivelser som gjør det mulig å
    # knytte dem til riktig undervisningsenhet.
    multi_enhet = []
    multi_id = ":".join((Instnr, emnekode, termk, aar))
    if len(importer.emne_termnr.get(multi_id, {})) > 1:
        multi_enhet.append("%s. termin" % termnr)
    if len(importer.emne_versjon.get(multi_id, {})) > 1:
        multi_enhet.append("v%s" % versjon)
    if multi_enhet:
        enhet_suffix = ", %s" % ", ".join(multi_enhet)
    else:
        enhet_suffix = ""
    logger.debug("Updating groups for %s %s %s%s:" % (
        emnekode, termk, aar, enhet_suffix))

    kurs_id = course2CerebumID('kurs', Instnr, emnekode,
                               versjon, termk, aar, termnr)

    # Enhetsansvar? Fagpersoner?
    all_resp = {}
    try:
        group_identificators = (Instnr, emnekode, versjon, termk, aar, termnr)
        resp = role_mapping[group_identificators]
        logger.debug("Retrieved responsibles for group '%s' (AKA '%s'): %s" %
                     (group_identificators, kurs_id, resp))
        for account_id in fnrs2account_ids(resp):
            all_resp[account_id] = 1
        logger.debug("all_resp: '%s'" % all_resp)
    except KeyError:
        # TODO: This might warrant a warning, but we need to discuss it with NMH
        logger.info("Unable to find any responsibles for '%s'" % kurs_id)
    sync_group(kurs_id, mk_gname("%s:ansvar" % enhet_id),
               "Ansvarlige %s %s %s%s" % (emnekode, termk, aar, enhet_suffix),
               constants.entity_account, all_resp);

    # Alle nåværende undervisningsmeldte samt nåværende+fremtidige
    # eksamensmeldte studenter.
    logger.debug(" student")
    alle_stud = {}
    accounts = fnrs2account_ids(fs.undervisning.list_studenter_underv_enhet(
                                Instnr, emnekode, versjon, termk, aar, termnr))
    for account_id in accounts:
        alle_stud[account_id] = 1

    sync_group(kurs_id, mk_gname("%s:student" % enhet_id),
               "Studenter %s %s %s%s" % (emnekode, termk, aar, enhet_suffix),
               constants.entity_account, alle_stud);


    # Syhnchronize registered activities for the enhet
    for act_code in importer.UndervEnhet[enhet_id].get('aktivitet', {}).keys():
        logger.debug("Looking at act_code: '%s'" % act_code)

        # Aktivitetsansvar
        act_resp = {}
        try:
            group_identificators = (Instnr, emnekode, versjon, termk, aar, termnr, act_code)
            resp = role_mapping[group_identificators]
            logger.debug("Retrieved responsibles for group '%s' (AKA '%s-%s'): %s" %
                         (group_identificators, kurs_id, act_code, resp))
            for account_id in fnrs2account_ids(resp):
                act_resp[account_id] = 1
                logger.debug("act_resp: '%s'" % act_resp)
        except KeyError:
            logger.info("Unable to find any responsibles for '%s-%s'" % (kurs_id, act_code))
        sync_group(kurs_id, mk_gname("%s:%s:ansvar" % (enhet_id, act_code)),
                   "Ansvarlige %s %s %s%s %s" % (emnekode, termk, aar, enhet_suffix,
                                             importer.UndervEnhet[enhet_id]['aktivitet'][act_code]),
                   constants.entity_account, act_resp)


        # Students
        logger.debug(" student:%s" % act_code)
        act_stud = {}
        for account_id in fnrs2account_ids(fs.undervisning.list_aktivitet(
            Instnr, emnekode, versjon, termk, aar, termnr, act_code)):
            act_stud[account_id] = 1

        sync_group(kurs_id, mk_gname("%s:%s:student" % (enhet_id, act_code)),
                   "Studenter %s %s %s%s %s" % (emnekode, termk, aar, enhet_suffix,
                                               importer.UndervEnhet[enhet_id]['aktivitet'][act_code]),
                   constants.entity_account, act_stud)


def process_kursdata(role_mapping):
    logger.info("Starting retrieval of groups and participants from FS")
    #importer.get_emner()
    importer.get_undervisningsenheter()
    importer.get_undervisningsaktiviteter()

    for k in importer.UndervEnhet.keys():
        populate_enhet_groups(k, role_mapping)

    # Update level 2 groups, i.e. the group that contains all groups
    # pertaining to a particular "enhet"
    logger.info("Updating 'enhet'-groups:")
    for kurs_id in AffiliatedGroups.keys():
        if kurs_id == fs_supergroup:
            continue
        rest = kurs_id.split(":")
        enhet_type = rest.pop(0).lower()
        if enhet_type == 'kurs':
            instnr, emnekode, versjon, termk, aar = rest
            sync_group(subject_supergroup, mk_gname(kurs_id),
                       importer.enhet_names[kurs_id],
                       constants.entity_group,
                       AffiliatedGroups[kurs_id])
        else:
            logger.warn("Unknown type <%s> for 'enhet' <%s>" % (type, k))

        # Done processing this group; remove it from later iterations
        del AffiliatedGroups[kurs_id]

    logger.info(" ... done")

    # Now the only remaining group is the root supergroup
    logger.info("Updating course supergroup")
    try:
        sync_group(None, subject_supergroup, "Root of the course-tree containing all course-based groups",
                   constants.entity_group, AffiliatedGroups[subject_supergroup])
    except KeyError, ke:
        # This really shouldn't happen during normal operations...
        logger.error("Unable to find course supergroup among groups to be synced. "
                     "This can only happen if no courses are to be sync'ed, "
                     "which sounds very very wrong.")
        raise Errors.CerebrumError("No courses are set to being sync'ed")
    logger.info(" ... done")


def process_classdata():
    importer.get_classes()

    for class_id in importer.classes:
        group_name = mk_gname(class_id)
        group_type, institution, program_code, year, term_code = class_id.split(":")
        group_desc = "%s %s %s" % (program_code, term_code.capitalize(), year)

        students = {}
        for student in importer.classes[class_id]:
            students[student] = 1

        sync_group(class_supergroup, group_name, group_desc,
                   constants.entity_account, students)

    logger.info("Updating class supergroup")
    sync_group(None, class_supergroup, "Root of the class-tree containing all class-based groups",
               constants.entity_group, AffiliatedGroups[class_supergroup])
    logger.info(" ... done")


def sync_group(affil, gname, descr, mtype, memb, recurse=True):
    logger.debug(("sync_group(parent:'%s'; groupname:'%s'; description:'%s'; " +
                  "membertype:'%s'; members:'%s'; recurse:'%s')") %
                 (affil, gname, descr, mtype, memb.keys(), recurse))
    if mtype == constants.entity_group:   # memb has group_name as keys
        members = {}
        for tmp_gname in memb.keys():
            grp = get_group(tmp_gname)
            members[int(grp.entity_id)] = 1
    else:
        # memb has account_id as keys
        members = memb.copy()

    if affil is not None:
        AffiliatedGroups.setdefault(affil, {})[gname] = 1

    try:
        group = get_group(gname)
    except Errors.NotFoundError:
        group = Factory.get('Group')(db)
        group.clear()
        group.populate(
            creator_id=group_creator,
            visibility=constants.group_visibility_all,
            name=gname,
            description=descr,
            group_type=constants.group_type_unknown,
        )
        group.write_db()
    else:
        # Update description if it has changed
        if group.description != descr:
            group.description = descr
            group.write_db()

        if group.is_expired():
            # Extend the group's life by 6 months
            from mx.DateTime import now, DateTimeDelta
            group.expire_date = now() + DateTimeDelta(6*30)
            group.write_db()

        # Make sure the group is listed for export to LMS
        if not group.has_spread(constants.spread_lms_group):
            group.add_spread(constants.spread_lms_group)

        for member in group.search_members(group_id=group.entity_id,
                                           member_type=mtype,
                                           member_filter_expired=False):
            member = int(member["member_id"])
            if members.has_key(member):
                del members[member]
            else:
                logger.debug("sync_group(): Deleting member %d" % member)
                group.remove_member(member)

    for member in members.keys():
        group.add_member(member)


def import_data():
    global importer
    importer = Factory.get("LMSImport")()

    logger.info("Parsing role file %s", options["rolefile"])
    role_mapping = parse_xml_roles(options["rolefile"])
    # print role_mapping
    logger.info("Parsing roles complete")
    process_kursdata(role_mapping)
    process_classdata()

    if options["dryrun"]:
        logger.info("Dry run. Rolling back imported updates...")
        db.rollback()
    else:
        logger.info("Committing all imported updates...")
        db.commit()


def get_group_members(group_id):
    group = Factory.get("Group")(db)
    group.clear()
    group.find(group_id)
    group_members = []
    for member in group.search_members(group_id=group.entity_id): # Spread?
        user_entity_id = int(member["member_id"])
        try:
            account = exporter.user_entity_id2account[user_entity_id]
            group_members.append(account)
        except KeyError:
            logger.info("Person with entity_id '%s' " % user_entity_id +
                        "does not have an account that is exported to LMS")
    return group_members


def export_data(output_stream):
    global exporter
    exporter = Factory.get("LMSExport")(output=output_stream,
                                        host=options["host"])

    exporter.gather_people_information()

    exporter.begin()

    exporter.export_people()

    group = Factory.get("Group")(db)

    fag_id = "nmh.no:fs:kurs"
    fag_name = "NMH: Fag"
    logger.debug("Exporting root-node for 'fag': '%s' - '%s'",
                 fag_id, fag_name)
    exporter.group_to_xml(id=fag_id, grouptype="Toppnode",
                          parentcode=exporter.IDstcode, grouptype_level=1,
                          nameshort=fag_name, namelong=fag_name,
                          namefull=fag_name)

    root_groupname = subject_supergroup
    group.find_by_name(root_groupname)

    for enhet in group.search_members(group_id=group.entity_id): # Spread?
        enhet_group_id = int(enhet["member_id"])
        group.clear()
        group.find(enhet_group_id)
        enhet_id = group.group_name
        enhet_name = group.description
        logger.debug("Exporting enhet: '%s' - '%s'" % (enhet_id, enhet_name))
        exporter.group_to_xml(id=enhet_id, grouptype="Undenhet",
                              parentcode=fag_id, grouptype_level=2,
                              nameshort=enhet_name, namelong=enhet_name,
                              namefull=enhet_name)

        subgroups = {}
        activities = {}

        # Need to assemble proper groups by activity
        for subgroup in group.search_members(group_id=group.entity_id):
            subgroup_groupid = int(subgroup["member_id"])
            group.clear()
            group.find(subgroup_groupid)

            subgroup_id = group.group_name
            id_elements = subgroup_id.split(":")
            act_id = ":".join(id_elements[:-1])
            # Need to treat the main/enhet membership groups a bit specially...
            if len(id_elements) == 10:
                # Flag for activity representing main group
                activities[act_id] = "all"
                logger.debug("Found 'all'-activity: '%s'" % act_id)
            else:
                activities[act_id] = "act"
                logger.debug("Found normal activity: '%s'" % act_id)

            subgroups[subgroup_id] = subgroup_groupid

        logger.debug("Subgroups: '%s'" % subgroups)

        for activity in activities.keys():
            # .. and this is where they get special treatment
            if activities[activity] == "all":
                activity_id = enhet_id
                # No need to create this group, since we'll use the
                # main "enhet"-group for it.

            else:
                activity_id = activity
                group.clear()
                group.find(subgroups[activity + ":ansvar"])
                name_elements = group.description.split(" ")
                act_name = " ".join(name_elements[1:])

                logger.debug("Exporting activity: '%s' - '%s'" % (activity_id, act_name))
                exporter.group_to_xml(id=activity_id,
                                      grouptype="Undaktivitet", parentcode=enhet_id,
                                      grouptype_level=3, nameshort=act_name, namelong=act_name,
                                      namefull=act_name)

            resp_group_id = subgroups[activity + ":ansvar"]
            stud_group_id = subgroups[activity + ":student"]
            responsibles = get_group_members(resp_group_id)
            students = get_group_members(stud_group_id)

            logger.debug("Exporting a total of '%s/%s' members in group '%s'",
                         len(responsibles), len(students), activity_id)
            exporter.membership_to_xml(activity_id, responsibles, students)

    # Class export
    root_class_id = "nmh.no:fs:kull"
    root_class_name = "NMH: Kull"
    logger.debug("Exporting root-node for 'class': '%s' - '%s'",
                 root_class_id, root_class_name)
    exporter.group_to_xml(id=root_class_id, grouptype="Toppnode",
                          parentcode=exporter.IDstcode, grouptype_level=1,
                          nameshort=root_class_name, namelong=root_class_name,
                          namefull=root_class_name)

    group.clear()
    group.find_by_name(class_supergroup)
    for class_group in group.search_members(group_id=group.entity_id):
        class_group_id = int(class_group["member_id"])
        group.clear()
        group.find(class_group_id)
        class_id = group.group_name
        class_name = group.description
        logger.debug("Exporting class: '%s' - '%s'" % (class_id, class_name))
        exporter.group_to_xml(id=class_id, grouptype="Class",
                              parentcode=root_class_id, grouptype_level=2,
                              nameshort=class_name, namelong=class_name,
                              namefull=class_name)

        responsibles = []
        students = get_group_members(class_group_id)
        logger.debug("Exporting a total of '%s/%s' members in group '%s'" %
                     (len(responsibles), len(students), class_id))
        exporter.membership_to_xml(class_id, responsibles, students)

    # Faculty export
    root_faculty_id = "nmh.no:fs:faculty"
    root_faculty_name = "NMH: Ansatte"
    logger.debug("Exporting root-node for 'faculty': '%s' - '%s'",
                 root_faculty_id, root_faculty_name)
    exporter.group_to_xml(id=root_faculty_id, grouptype="Toppnode",
                          parentcode=exporter.IDstcode, grouptype_level=1,
                          nameshort=root_faculty_name,
                          namelong=root_faculty_name,
                          namefull=root_faculty_name)

    faculty_members = []
    # TBD: Who should be admin(s) for the faculty group?
    faculty_responsibles = []
    for faculty_member in exporter.faculty.itervalues():
        # Order doesn't matter here in any way, so we just take all
        # the values for faculty in whatever order we get them
        faculty_members.append(faculty_member["username"])
    logger.debug("Exporting a total of '%s/%s' members in group '%s'",
                 len(faculty_responsibles), len(faculty_members),
                 root_faculty_id)
    exporter.membership_to_xml(root_faculty_id, [], faculty_members)


    exporter.end()


def usage(message=None):
    """Gives user info on how to use the program and its options."""
    if message is not None:
        print >>sys.stderr, "\n%s" % message

    print >>sys.stderr, __doc__


def main(argv=None):
    """Main processing hub for program."""
    if argv is None:
        argv = sys.argv

    # Handles upper- and lowercasing of strings containing
    # e.g. Norwegian characters
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    try:
        opts, args = getopt.getopt(argv[1:],
                                   "hf:dr:",
                                   ["help", "file=", "host=",
                                    "dryrun", "role-file=",
                                    "no-import", "no-export"])
    except getopt.GetoptError, error:
        usage(message=error.msg)
        return 1

    output_stream = options["output"]

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ('-f', '--file',):
            options["output"] = val
        if opt in ('--host',):
            options["host"] = val
        if opt in ('--dryrun',):
            options["dryrun"] = True
        if opt in ('-r', '--role-file',):
            options["rolefile"] = val
        if opt in ('--no-import',):
            options["import"] = False
        if opt in ('--no-export',):
            options["export"] = False

    if options["import"]:
        import_data()

    if options["export"]:
        if options["output"] != sys.stdout:
            output_stream = SimilarSizeWriter(options["output"], "w")
            output_stream.max_pct_change = 50

        export_data(output_stream)

        if output_stream != sys.stdout:
            output_stream.close()

    return 0


if __name__ == "__main__":
    logger.info("Starting program '%s'" % progname)
    return_value = main()
    logger.info("Program '%s' finished" % progname)
    sys.exit(return_value)
