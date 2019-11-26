#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

__copyright__ = """Copyright 2008 University of Oslo, Norway

This file is part of Cerebrum.

Cerebrum is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

Cerebrum is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with Cerebrum; if not, write to the Free Software Foundation,
Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""

# $Id$

import sys
import re

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.access_FS import make_fs

__doc__ = """
This is a nice module that you should use correctly.

"""

__version__ = "$Revision$"
__docformat__ = "restructuredtext"


db = Factory.get('Database')()
constants = Factory.get("Constants")(db)
logger = Factory.get_logger("cronjob")


def course2CerebumID(coursetype, *courseinfo):
    """Make a Cerebrum-specific group/course-ID from the primary key
    that an 'undervisningsenhet' or EVU-course has. This ID will not
    be changed for the duration of a course, e.g. upon entering a new
    term.

    :Parameters:
      coursetype : String
        Different types have different info, and this identifies the
        type to determine which processing courseinfo should receive.
      courseinfo : list
        All info that should be used in constructing the ID for this course.

    'coursetype' should be either 'KURS' ('undervisningsenhet') or
    'EVU' (EVU-course).

    """
    coursetype = coursetype.lower()
    if not coursetype in ('kurs'):
        raise ValueError, "ERROR: Unknown coursetype <%s> (%s)" % (coursetype, courseinfo)

    # Coursetype must now be "kurs"
    if len(courseinfo) != 6:
        raise ValueError, ("ERROR: 'Undervisningsenhet' should be identified " +
                           "by 6 fields, not <%s>" % ">, <".join(courseinfo))

    instnr, emnecode, version, termk, year, termnr = courseinfo
    termnr = int(termnr)
    year = int(year)
    tmp_termk = re.sub('[^a-zA-Z0-9]', '_', termk).lower()
    # Find 'termk' and 'year' (termnr - 1) terms ago
    if (tmp_termk == 'h_st'):
        if (termnr % 2) == 1:
            termk = 'høst'
        else:
            termk = 'vår'
        year -= int((termnr - 1) / 2)
    elif tmp_termk == 'v_r':
        if (termnr % 2) == 1:
            termk = 'vår'
        else:
            termk = 'høst'
        year -= int(termnr / 2)
    else:
        # Here's to crossing our fingers that there won't be any other
        # terms that 'høst' and 'vår'....
        raise ValueError, ("ERROR: Unknown terminkode <%s> for " +
                           "emnekode <%s>." % (termk, emnekode))

    # Note that termnr isn't part of the returned string. It has
    # become implicit by our calculations for 'year' and 'termk' for
    # when 'termnr' equals 1.
    ret = "%s:%s:%s:%s:%s:%s" % (coursetype, instnr, emnecode, version,
                                 termk, year)
    return ret.lower()




class LMSImport(object):
    """Generic superclass for handling import of informatin for LMS
    purposes.

    Not meant for instantiation directly; clients should instead call
    the 'get'-method with a suitable parametre to get the proper
    importer.
    
    """

    def __init__(self):
        ac = Factory.get('Account')(db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        self.group_creator = ac.entity_id
        "Account that will be used as creator of the generated groups."
        self.sitename = "generic-site.org"
        "Site identifier that will be included in the ID of generated groups."
        self.persons = {}
        self.assemble_person_to_account_id_mappings()
        

    def assemble_person_to_account_id_mappings(self):
        """Assembles a mapping for all persons where the key is their
        'fødselsnummer' and the value is the numeric ID for their
        primary account.

        """
        logger.debug("assemble_person_to_account_id_mappings start")
        person = Factory.get('Person')(db)
        
        everyone = person.list_affiliations()
        for individual in everyone:
            person.clear()
            person.find(individual["person_id"])
            primary_account_id = person.get_primary_account()
            fnr = person.get_external_id(id_type=constants.externalid_fodselsnr)[0]["external_id"]
            if primary_account_id is None:
                identifier = "person_ent_id:'%s'" % individual["person_id"]
                logger.info("Primary account is None for person: %s" % identifier)
            else:
                self.persons[fnr] = primary_account_id
        logger.debug("assemble_person_to_account_id_mappings done")
        

    def sync_group(self, affil, gname, descr, mtype, memb, visible=False, recurse=True):
        """Synchonizes a group in Cerebrum based on the data that has been
        read/generated from the import system.

        :Parameters:

          affil : 
            Test
          gname : String
            Name of the group we wish to synchronize 
          descr : String
            Description of the group, should it need to be created
          mtype : EntityTypeCode
            Signifies if the members given in memb are group-names or account ids
          memb : list
            list of names or IDs identifying who should be members of this group.
          visible : Boolean
            Whether or not this group should be found outside Cerebrum
          recurse : Boolean
            test

        :return: None
            
        """
        logger.debug("sync_group(%s; %s; %s; %s; %s; %s; %s)" %
                     (affil, gname, descr, mtype, memb.keys(), visible, recurse))
        
        if mtype == constants.entity_group:   # memb has group_name as keys
            members = {}
            for tmp_gname in memb.keys():
                grp = get_group(tmp_gname)
                members[int(grp.entity_id)] = 1
        else:                          # memb has account_id as keys
            members = memb.copy()

        try:
            group = get_group(gname)
        except Errors.NotFoundError:
            group = Factory.get('Group')(db)
            group.clear()
            group.populate(
                creator_id=self.group_creator,
                visibility=correct_visib,
                name=gname,
                description=descr,
                # TODO: Should probably be group_type_lms
                group_type=constants.group_type_unknown,
            )
            group.write_db()



class FSImport(LMSImport):
    """Class for handling FS-import of information for LMS purposes."""

    def __init__(self):
        LMSImport.__init__(self)
        self.fs_db = make_fs()
        self.UndervEnhet = {}
        self.not_exported_to_lms = {}
        self.enhet_names = {}
        self.emne_versjon = {}
        self.emne_termnr = {}
        self.emner = {}
        self.classes = {}
        """Contains a mapping of class-IDs to a list of the entity IDs
        of the primary accounts of the students belonging to that
        class. See 'get_classes()'."""
        logger.debug("FSImport initialized")


    def get_undervisningsenheter(self):
        logger.info("Retrieving 'enheter'")
        for enhet in self.fs_db.undervisning.list_undervisningenheter():
            # Prefix all "undervisningsenheter"-keys with "kurs" for
            # easy identification
            enhet_id = "kurs:%s:%s:%s:%s:%s:%s" % (
                enhet['institusjonsnr'], enhet['emnekode'],
                enhet['versjonskode'], enhet['terminkode'],
                enhet['arstall'], enhet['terminnr'])
            cere_id = course2CerebumID("kurs", enhet['institusjonsnr'], enhet['emnekode'],
                                       enhet['versjonskode'], enhet['terminkode'],
                                       enhet['arstall'], enhet['terminnr'])

            if enhet['status_eksport_lms'] == 'N':
                logger.info("Enhet '%s' set in FS to not be exported to LMS" % enhet_id)
                self.not_exported_to_lms[enhet_id] = True
                continue
            
            if self.UndervEnhet.has_key(enhet_id):
                raise ValueError, "Duplicate undervisningsenhet: '%s'" % enhet_id
            
            self.UndervEnhet[enhet_id] = {'aktivitet': {}}
            multi_id = ":".join([str(x).lower() for x in
                                 (enhet['institusjonsnr'], enhet['emnekode'],
                                  enhet['terminkode'], enhet['arstall'])])
            # Is there more than one "enhet" associated with this
            #"emnecode" this term?
            self.emne_versjon.setdefault(multi_id, {})[enhet['versjonskode']] = 1
            self.emne_termnr.setdefault(multi_id, {})[enhet['terminnr']] = 1
            self.enhet_names[cere_id] = "%s %s %s %s. termin" % (enhet['emnekode'],
                                                      enhet['terminkode'],
                                                      enhet['arstall'], enhet['terminnr'])
        logger.debug("Found %s 'undervisningsenheter'" % len(self.UndervEnhet))
        logger.info("Done retrieving 'enheter'")


    def get_undervisningsaktiviteter(self):
        logger.info("Retrieving activities")
        for akt in self.fs_db.undervisning.list_aktiviteter():
            enhet_id = "kurs:%s:%s:%s:%s:%s:%s" % (
                akt['institusjonsnr'], akt['emnekode'],
                akt['versjonskode'], akt['terminkode'],
                akt['arstall'], akt['terminnr'])
            akt_code_and_name = "%s - %s" % (akt['aktivitetkode'], akt['aktivitetsnavn'])

            if enhet_id in self.not_exported_to_lms:
                logger.debug("Enhet '%s' for activity '%s' is not exported to LMS. Skipping" %
                             (enhet_id, akt_code_and_name))
                continue

            if akt['status_eksport_lms'] == 'N':
                logger.info("Activity '%s' (from enhet '%s') set in FS to not be exported to LMS" %
                            (akt_code_and_name, enhet_id))
                continue
            
            if not self.UndervEnhet.has_key(enhet_id):
                logger.warning("Non-existing 'enhet' '%s' has activities" % enhet_id)
                continue
            if self.UndervEnhet[enhet_id]['aktivitet'].has_key(akt['aktivitetkode']):
                raise ValueError, "Duplicate undervisningsaktivitet '%s:%s'" % (
                    enhet_id, akt['aktivitetkode'])
            
            self.UndervEnhet[enhet_id]['aktivitet'][akt['aktivitetkode']] = akt['aktivitetsnavn']
            logger.debug("Added activity: '%s'" % akt_code_and_name)
        logger.info("Done retrieving activities")


    def get_classes(self):
        logger.info("Retrieving classes from FS")
        for fs_class in self.fs_db.info.list_kull():
            program_code = fs_class["studieprogramkode"]
            term_code = fs_class["terminkode"]
            year = fs_class["arstall"]
            institution = fs_class["institusjonsnr_studieansv"]
            class_id = "kull:%s:%s:%s:%s" % (institution, program_code, year, term_code)
            logger.debug("Retrieving students for class '%s'" % class_id)

            class_students = []
            for student in self.fs_db.undervisning.list_studenter_kull(program_code,
                                                            term_code, year):
                fnr = "%06i%05i" % (student["fodselsdato"], student["personnr"])
                if fnr in self.persons:
                    class_students.append(self.persons[fnr])
                else:
                    logger.info("No primary account registered for fnr '%s'. Skipping" % fnr)

            logger.debug("Students in class '%s': '%s'" % (class_id, class_students))

            self.classes[class_id] = class_students
        
        logger.info("Done retrieving classes from FS")
        

    def get_emner(self):
        for emne in self.fs_db.info.list_emner():
            emne_id = "emne:%s" % emne["emnekode"]
            emne_id = emne_id.lower()
            self.emner[emne_id] = {"name": emne["emnenavn_bokmal"]}
            logger.debug("Found emne '%s': '%s'" % (emne_id, emne["emnenavn_bokmal"]))
        logger.info("Found %s 'emner'" % len(self.emner))




class UiOLMSImport(FSImport):
    """"""

    def __init__(self):
        FSImport.__init__(self)
        self.sitename = "uio.no"
        logger.debug("UiOLMSImport initialized")



class NMHLMSImport(FSImport):
    """"""

    def __init__(self):
        FSImport.__init__(self)
        self.sitename = "nmh.no"
        logger.debug("NMHLMSImport initialized")

