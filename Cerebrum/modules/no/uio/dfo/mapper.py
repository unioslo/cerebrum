# -*- coding: utf-8 -*-
#
# Copyright 2020-2024 University of Oslo, Norway
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
This module defines how we map DFØ values to Cerebrum values for UiO.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging

from Cerebrum.modules.no.dfo import mapper as _base

logger = logging.getLogger(__name__)


# We populate some of the actual mappings at the bottom of this module, in
# order to keep things a bit more readable.  It might be cleaner to move the
# data to a separate module?


class _DfoTitles(_base.DfoTitles):
    """ Work title and personal title mappings for UiO. """

    # Work title from assignment code mapping (`stilling.stillingskode`).
    # Maps to localized WORK_TITLE values in English (en) and Norwegian (nb).
    #
    # Populated from `_ASSIGNMENT_CODES` at the bottom of this module.
    work_title_map = _base.AssignmentTitleMap()

    # Personal title mappings (`ansatt.tittel`).  Maps from a partial/shortname
    # to fully localized `PERSONAL_TITLE` values in English (en) and Norwegian
    # (nb).
    #
    # Populated from `_PERSONAL_TITLES` at the bottom of this module.
    personal_title_map = _base.PersonalTitleMap()

    def _load_work_titles(self, assignment_code_data):
        for k, v in assignment_code_data.items():
            if 'name' in v:
                self.work_title_map.set(k, v['name'])

    def _load_personal_titles(self, personal_titles):
        for k, v in personal_titles.items():
            self.personal_title_map.set(k, v)


class _DfoAffiliations(_base.DfoAffiliations):
    """ Affiliation mappings for UiO. """

    # Employee group (mg/mug) to affiliation map for main assignments.
    #
    # This map overrides the employee main assignment mapping, if the employee
    # is in one of these specified groups:
    employee_group_map = _base.AffiliationMap({
        (8, 50): None,  # Explicitly disallow this MG/MUG
        (9, 90): "TILKNYTTET/ekst_partner",
        (9, 91): "TILKNYTTET/ekst_partner",
        (9, 93): "TILKNYTTET/emeritus",
        (9, 94): "TILKNYTTET/ekst_partner",
        (9, 95): "TILKNYTTET/gjesteforsker",
    })

    # Assignment code to affiliation mapping (`stilling.stillingskode`).
    #
    # Populated from `_ASSIGNMENT_CODES` at the bottom of this module.
    assignment_code_map = _base.AffiliationMap()

    # Backup mappings from assignment category to affiliation
    # (`stilling.stillingskat[].stillingskatId`).
    #
    # This is how we used to map affiliations from DFØ, but is now only used as
    # a fallback mapping if a `stilling.stillingskode` isn't defined in
    # `assignment_code_map`.
    assignment_category_map = _base.AffiliationMap({
        # Administrativt personale
        50078118: "ANSATT/tekadm",

        # Drifts- og teknisk personale/andre tilsatte
        50078119: "ANSATT/tekadm",

        # Unvervisnings- og forskningspersonale
        50078120: "ANSATT/vitenskapelig",
    })

    def _load_assignment_codes(self, assignment_code_data):
        for k, v in assignment_code_data.items():
            if 'affiliation' in v:
                self.assignment_code_map.set(k, v['affiliation'])


def _get_supervised_org_units(employee_data):
    """
    Get the org units where this employee is a manager.

    :param dict employee_data: Normalized employee data

    :rtype: set[int]
    :returns: DFØ org unit ids where the person is a manager
    """
    main_id = employee_data.get('stillingId')
    assignments = employee_data.get('assignments') or {}
    main_assignment = assignments.get(main_id)

    if main_assignment and employee_data.get('lederflagg'):
        return set([main_assignment['organisasjonId']])
    return set()


class EmployeeMapper(_base.EmployeeMapper):
    """ Employee mapper for UiO. """

    # Use our custom mappers
    get_titles = _DfoTitles()
    get_affiliations = _DfoAffiliations()

    # Set custom date offsets ("grace period")
    start_offset = datetime.timedelta(days=-6)
    end_offset = datetime.timedelta(days=0)

    def translate(self, reference, employee_data):
        person = super(EmployeeMapper, self).translate(reference,
                                                       employee_data)

        # eksternbruker isn't populated at uio - all active employees should be
        # considered
        person.enable = True

        # set reservation
        setattr(person, 'reserved',
                employee_data.get('reservasjonPublisering'))

        # A list of org units where this person is considered a manager
        # Each org unit is a list of (id_type, id_value) pairs
        ou_terms = [[('DFO_OU_ID', org_id)]
                    for org_id in _get_supervised_org_units(employee_data)]
        setattr(person, 'leader_ous', ou_terms)
        return person


#
# Assignment code (stillingskode) mappings for affiliation and title mappers.
#
# This is loaded into the _DfoAffiliations.affiliation_code_map, and
# _DfoTitles.work_title_map
#
_ASSIGNMENT_CODES = {
    20000214: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Rector",
            'nb': "Rektor",
        },
    },
    20000389: {
        'affiliation': "ANSATT/tekadm",
    },
    20000400: {
        'affiliation': "ANSATT/tekadm",
    },
    20000782: {
        'name': {
            'en': "Senior Consultant",
            'nb': "Overlege",
        },
    },
    20000787: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Specialist Dentist",
            'nb': "Spesialtannlege",
        },
    },
    20000790: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Occupational Nurse",
            'nb': "Bedriftssykepleier",
        },
    },
    20000791: {
        'affiliation': "ANSATT/tekadm",
    },
    20000795: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Specialist Psychologist",
            'nb': "Spesialpsykolog",
        },
    },
    20000796: {
        'name': {
            'en': "Chief Psychologist",
            'nb': "Sjefpsykolog",
        },
    },
    20000807: {
        'affiliation': "ANSATT/tekadm",
    },
    20000810: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Specialist Nurse",
            'nb': "Spesialistutdannet sykepleier",
        },
    },
    20000816: {
        'affiliation': "ANSATT/tekadm",
    },
    20000820: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Head Nurse",
            'nb': "Oversykepleier",
        },
    },
    20000826: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Children's Nurse",
            'nb': "Barnepleier",
        },
    },
    20000829: {
        'affiliation': "ANSATT/tekadm",
    },
    20000830: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Kindergarten Assistant",
            'nb': "Barnehageassistent",
        },
    },
    20000832: {
        'affiliation': "ANSATT/tekadm",
    },
    20000835: {
        'name': {
            'en': "Physical Therapist Instructor",
            'nb': "Instruktør/fysioterapeut",
        },
    },
    20000852: {
        'affiliation': "ANSATT/tekadm",
    },
    20000892: {
        'name': {
            'en': "Kindergarten Assistant",
            'nb': "Barnehageassistent",
        },
    },
    20000947: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Kindergarten Teacher",
            'nb': "Førskolelærer",
        },
    },
    20000948: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Kindergarten Manager",
            'nb': "Styrer",
        },
    },
    20001003: {
        'affiliation': "ANSATT/tekadm",
    },
    20001004: {
        'affiliation': "ANSATT/vitenskapelig",
    },
    20001007: {
        'affiliation': "ANSATT/vitenskapelig",
    },
    20001009: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Lecturer",
            'nb': "Universitetslektor",
        },
    },
    20001010: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Assistant Professor",
            'nb': "Amanuensis",
        },
    },
    20001011: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Associate Professor",
            'nb': "Førsteamanuensis",
        },
    },
    20001012: {
        'name': {
            'en': "University College Professor",
            'nb': "Høgskoledosent",
        },
    },
    20001013: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Professor",
            'nb': "Professor",
        },
    },
    20001015: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Dentist Instructor",
            'nb': "Instruktørtannlege",
        },
    },
    20001016: {
        'affiliation': "ANSATT/vitenskapelig",
    },
    20001017: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Doctoral Research Fellow",
            'nb': "Stipendiat",
        },
    },
    20001018: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Research Assistant",
            'nb': "Vitenskapelig assistent",
        },
    },
    20001019: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Research Assistant",
            'nb': "Vitenskapelig assistent",
        },
    },
    20001020: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Research Assistant",
            'nb': "Vitenskapelig assistent",
        },
    },
    20001032: {
        'affiliation': "ANSATT/tekadm",
    },
    20001033: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Clinical Coordinator",
            'nb': "Klinikkavdelingsleder",
        },
    },
    20001054: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Head of Office",
            'nb': "Kontorsjef",
        },
    },
    20001055: {
        'name': {
            'en': "Personnel Manager",
            'nb': "Personalsjef",
        },
    },
    20001056: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Financial Manager",
            'nb': "Økonomisjef",
        },
    },
    20001058: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Head of Administration",
            'nb': "Administrasjonssjef",
        },
    },
    20001059: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Assistant Director",
            'nb': "Underdirektør",
        },
    },
    20001060: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Director of Department",
            'nb': "Avdelingsdirektør",
        },
    },
    20001061: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Assistant Director",
            'nb': "Assisterende direktør",
        },
    },
    20001062: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Director",
            'nb': "Direktør",
        },
    },
    20001063: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Secretary",
            'nb': "Førstesekretær",
        },
    },
    20001065: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Executive Officer",
            'nb': "Konsulent",
        },
    },
    20001068: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Secretary",
            'nb': "Fullmektig",
        },
    },
    20001069: {
        'affiliation': "ANSATT/tekadm",
    },
    20001070: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Secretary",
            'nb': "Sekretær",
        },
    },
    20001077: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Head Librarian",
            'nb': "Hovedbibliotekar",
        },
    },
    20001078: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "General Services Officer",
            'nb': "Betjent",
        },
    },
    20001079: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "General Services Officer",
            'nb': "Førstebetjent",
        },
    },
    20001083: {
        'name': {
            'en': "Engineer",
            'nb': "Ingeniør",
        },
    },
    20001084: {
        'affiliation': "ANSATT/tekadm",
    },
    20001085: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Principal Engineer",
            'nb': "Avdelingsingeniør",
        },
    },
    20001087: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Head Engineer",
            'nb': "Overingeniør",
        },
    },
    20001088: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Chief Engineer",
            'nb': "Sjefingeniør",
        },
    },
    20001089: {
        'affiliation': "ANSATT/tekadm",
    },
    20001090: {
        'affiliation': "ANSATT/tekadm",
    },
    20001091: {
        'affiliation': "ANSATT/tekadm",
    },
    20001092: {
        'affiliation': "ANSATT/tekadm",
    },
    20001093: {
        'affiliation': "ANSATT/tekadm",
    },
    20001094: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Head Architect",
            'nb': "Overarkitekt",
        },
    },
    20001095: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Chief Architect",
            'nb': "Sjefarkitekt",
        },
    },
    20001096: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Laboratory Assistant",
            'nb': "Laboratorieassistent",
        },
    },
    20001097: {
        'name': {
            'en': "Laboratory Assistant",
            'nb': "Laborant",
        },
    },
    20001098: {
        'name': {
            'en': "Head of Laboratory",
            'nb': "Laborantleder",
        },
    },
    20001108: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Researcher",
            'nb': "Forsker",
        },
    },
    20001109: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Researcher",
            'nb': "Forsker",
        },
    },
    20001110: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Researcher",
            'nb': "Forsker",
        },
    },
    20001111: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Director",
            'nb': "Forskningssjef",
        },
    },
    20001113: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Project Manager",
            'nb': "Prosjektleder",
        },
    },
    20001115: {
        'affiliation': "ANSATT/tekadm",
    },
    20001117: {
        'affiliation': "ANSATT/tekadm",
    },
    20001119: {
        'affiliation': "ANSATT/tekadm",
    },
    20001120: {
        'affiliation': "ANSATT/tekadm",
    },
    20001124: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Kitchen Manager",
            'nb': "Kjøkkensjef",
        },
    },
    20001125: {
        'affiliation': "ANSATT/tekadm",
    },
    20001126: {
        'affiliation': "ANSATT/tekadm",
    },
    20001127: {
        'affiliation': "ANSATT/tekadm",
    },
    20001128: {
        'affiliation': "ANSATT/tekadm",
    },
    20001129: {
        'affiliation': "ANSATT/tekadm",
    },
    20001130: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Cleaner",
            'nb': "Renholder",
        },
    },
    20001132: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Cleaning Coordinator",
            'nb': "Renholdsleder",
        },
    },
    20001136: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Works Technician",
            'nb': "Driftstekniker",
        },
    },
    20001137: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Works Coordinator",
            'nb': "Driftsleder",
        },
    },
    20001138: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Assistant",
            'nb': "Assistent",
        },
    },
    20001180: {
        'affiliation': "ANSATT/tekadm",
    },
    20001181: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Senior Engineer",
            'nb': "Senioringeniør",
        },
    },
    20001182: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Senior Architect",
            'nb': "Seniorarkitekt",
        },
    },
    20001183: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Researcher",
            'nb': "Forsker",
        },
    },
    20001190: {
        'affiliation': "ANSATT/tekadm",
    },
    20001198: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Senior Lecturer",
            'nb': "Førstelektor",
        },
    },
    20001199: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Academic Librarian",
            'nb': "Universitetsbibliotekar",
        },
    },
    20001200: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Senior Academic Librarian",
            'nb': "Førstebibliotekar",
        },
    },
    20001203: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Skilled worker with craft certificate",
            'nb': "Fagarbeider med fagbrev",
        },
    },
    20001211: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Section Manager",
            'nb': "Seksjonssjef",
        },
    },
    20001216: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Operation Technician",
            'nb': "Driftsoperatør",
        },
    },
    20001217: {
        'name': {
            'en': "Engineer",
            'nb': "Ingeniør",
        },
    },
    20001220: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Special Adviser",
            'nb': "Spesialrådgiver",
        },
    },
    20001260: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Clinical Director",
            'nb': "Avdelingstannlege",
        },
    },
    20001275: {
        'affiliation': "ANSATT/tekadm",
    },
    20001282: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Occupational Physiotherapist",
            'nb': "Bedriftsfysioterapeut",
        },
    },
    20001304: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Psychologist with clinical speciality",
            'nb': "Psykolog med godkjent spesialitet",
        },
    },
    20001308: {
        'affiliation': "ANSATT/tekadm",
    },
    20001352: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Postdoctoral Fellow",
            'nb': "Postdoktor",
        },
    },
    20001353: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Dentist Instructor with clinical speciality",
            'nb': "Instruktørtannlege med spesialisering",
        },
    },
    20001362: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Apprentice",
            'nb': "Lærling",
        },
    },
    20001363: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Senior Executive Officer",
            'nb': "Seniorkonsulent",
        },
    },
    20001364: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Senior Adviser",
            'nb': "Seniorrådgiver",
        },
    },
    20001378: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Doctoral Research Fellow",
            'nb': "Stipendiat",
        },
    },
    20001379: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Clinical Secretary",
            'nb': "Klinikksekretær",
        },
    },
    20001404: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Professor",
            'nb': "Professor",
        },
    },
    20001407: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Administrative Manager",
            'nb': "Avdelingsleder",
        },
    },
    20001408: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Higher Executive Officer",
            'nb': "Førstekonsulent",
        },
    },
    20001409: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Secretary",
            'nb': "Sekretær",
        },
    },
    20001410: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Librarian",
            'nb': "Bibliotekar",
        },
    },
    20001411: {
        'affiliation': "ANSATT/tekadm",
    },
    20001423: {
        'affiliation': "ANSATT/vitenskapelig",
    },
    20001424: {
        'affiliation': "ANSATT/vitenskapelig",
    },
    20001429: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Trainee",
            'nb': "Aspirant",
        },
    },
    20001433: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Senior Secretary",
            'nb': "Seniorsekretær",
        },
    },
    20001434: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Adviser",
            'nb': "Rådgiver",
        },
    },
    20001446: {
        'affiliation': "ANSATT/tekadm",
    },
    20001447: {
        'name': {
            'en': "General Services Officer",
            'nb': "Betjent",
        },
    },
    20001472: {
        'affiliation': "ANSATT/tekadm",
    },
    20001473: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Programme Coordinator",
            'nb': "Studieleder",
        },
    },
    20001474: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Dean",
            'nb': "Dekan",
        },
    },
    20001475: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Head of Department",
            'nb': "Instituttleder",
        },
    },
    20001476: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "PhD Candidate",
            'nb': "Spesialistkandidat",
        },
    },
    20001511: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Research Technician",
            'nb': "Forskningstekniker",
        },
    },
    20001512: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Research Technician",
            'nb': "Forskningstekniker",
        },
    },
    20001513: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Senior Research Technician",
            'nb': "Seniorforskningstekniker",
        },
    },
    20001514: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Chief Research Technician",
            'nb': "Ledende forskningstekniker",
        },
    },
    20001515: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Senior Librarian",
            'nb': "Spesialbibliotekar",
        },
    },
    20001532: {
        'affiliation': "ANSATT/vitenskapelig",
        'name': {
            'en': "Professor",
            'nb': "Dosent",
        },
    },
    20001533: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Dental Hygienist",
            'nb': "Tannpleier",
        },
    },
    20001538: {
        'affiliation': "ANSATT/vitenskapelig",
    },
    20001545: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "Dental Nurse",
            'nb': "Tannhelsesekretær",
        },
    },
    20008013: {
        'affiliation': "ANSATT/vitenskapelig",
    },
    20008028: {
        'affiliation': "ANSATT/vitenskapelig",
    },
    20009131: {
        'affiliation': "ANSATT/tekadm",
        'name': {
            'en': "University Director",
            'nb': "Universitetsdirektør",
        },
    },
    20009200: {
        'affiliation': "ANSATT/tekadm",
    },
    20009301: {
        'affiliation': "ANSATT/vitenskapelig",
    },
}


_PERSONAL_TITLES = {
    "Adm. leder": {
        'en': "Head of Administration",
        'nb': "Administrativ leder",
    },
    "Adm.sjef": {
        'en': "Head of Administration",
        'nb': "Administrasjonssjef",
    },
    "Advokat": {
        'en': "Lawyer",
        'nb': "Advokat",
    },
    "Anskaffelserådg": {
        'en': "Purchasing Adviser",
        'nb': "Anskaffelsesrådgiver",
    },
    "Ansvar.redaktør": {
        'en': "Managing Editor",
        'nb': "Ansvarlig redaktør",
    },
    "Ass. IT-dir": {
        'en': "Assistant Director of Information Technology",
        'nb': "Assisterende IT-direktør",
    },
    "Ass. fak.dir": {
        'en': "Assistant Faculty Director",
        'nb': "Assisterende fakultetsdirektør",
    },
    "Ass. univ.dir": {
        'en': "Deputy University Director",
        'nb': "Assisterende universitetsdirektør",
    },
    "Ass.forsk.leder": {
        'en': "Assistant Head of Research",
        'nb': "Assisterende forskningsleder",
    },
    "Ass.gr.leder": {
        'en': "Assistant Head of Group",
        'nb': "Assisterende gruppeleder",
    },
    "Ass.museumsdir": {
        'en': "Assistant Museum Director",
        'nb': "Assisterende museumsdirektør",
    },
    "Ass.personaldir": {
        'en': "Assistant Director of personnel",
        'nb': "Assisterende personaldirektør",
    },
    "Ass.seksj.leder": {
        'en': "Assistant Head of Section",
        'nb': "Assisterende seksjonsleder",
    },
    "Ass.senterleder": {
        'en': "Assistant Centre Director",
        'nb': "Assisterende senterleder",
    },
    "Assistent": {
        'en': "Assistant",
        'nb': "Assistent",
    },
    "Direktør": {
        'en': "Director",
        'nb': "Direktør",
    },
    "Direktør VØS": {
        'en': "Director of Corporate Governance and Finance",
        'nb': "Direktør for virksomhets- og økonomistyring",
    },
    "Drift/vedl.dir": {
        'en': "Works and Maintenance Director",
        'nb': "Drifts- og vedlikeholdsdirektør",
    },
    "Driftsingeniør": {
        'en': "Works Engineer",
        'nb': "Driftsingeniør",
    },
    "Eiendomsdir": {
        'en': "Estate Director",
        'nb': "Eiendomsdirektør",
    },
    "Eksamenskons": {
        'en': "Examination Officer",
        'nb': "Eksamenskonsulent",
    },
    "F.am.II": {
        'en': "Associate Professor II",
        'nb': "Førsteamanuensis II",
    },
    "Fagreferent": {
        'en': "Research Librarian",
        'nb': "Fagreferent",
    },
    "Fak.dir": {
        'en': "Faculty Director",
        'nb': "Fakultetsdirektør",
    },
    "Feltassistent": {
        'en': "Archeological Assistant",
        'nb': "Feltassistent",
    },
    "Feltleder": {
        'en': "Archaeological Supervisor",
        'nb': "Feltleder",
    },
    "Feltleder 1": {
        'en': "Archaeological Surveyor",
        'nb': "Feltleder 1",
    },
    "Formgiver": {
        'en': "Designer",
        'nb': "Formgiver",
    },
    "Forsk.gr.leder": {
        'en': "Head of Research Group",
        'nb': "Forskningsgruppeleder",
    },
    "Forsk.konsulent": {
        'en': "Research Consultant",
        'nb': "Forskningskonsulent",
    },
    "Forsk.rådgiver": {
        'en': "Research Adviser",
        'nb': "Forskningsrådgiver",
    },
    "Forskerassist.": {
        'en': "Research Assistant",
        'nb': "Forskerassistent",
    },
    "Forskningsleder": {
        'en': "Head of Research",
        'nb': "Forskningsleder",
    },
    "Forvalt.sjef": {
        'en': "Head of Property Management Section",
        'nb': "Forvaltningssjef",
    },
    "Fotograf": {
        'en': "Photographer",
        'nb': "Fotograf",
    },
    "Fung. IT-dir": {
        'en': "ActingDirector of Information Technology",
        'nb': "Fungerende IT-direktør",
    },
    "Fung.direktør": {
        'en': "Acting Director",
        'nb': "Fungerende direktør",
    },
    "Fung.fak.dir": {
        'en': "Acting Faculty Director",
        'nb': "Fungerende fakultetsdirektør",
    },
    "Fung.forsk.led": {
        'en': "Acting Head of Research",
        'nb': "Fungerende forskningsleder",
    },
    "Fung.museumsdir": {
        'en': "Acting Museum Director",
        'nb': "Fungerende museumsdirektør",
    },
    "Fung.seksj.led": {
        'en': "Acting Head of Section",
        'nb': "Fungerende seksjonsleder",
    },
    "Fung.senterled": {
        'en': "Acting Centre Director",
        'nb': "Fungerende senterleder",
    },
    "Førsteam. II": {
        'en': "Adjunct Associate Professor",
        'nb': "Førsteamanuensis II",
    },
    "Gjesteforeleser": {
        'en': "Visiting Lecturer",
        'nb': "Gjesteforeleser",
    },
    "Gjesteforsker": {
        'en': "Visiting Researcher",
        'nb': "Gjesteforsker",
    },
    "Glassblåser": {
        'en': "Glass Blower",
        'nb': "Glassblåser",
    },
    "Grafisk ansvarl": {
        'en': "Graphic Designer",
        'nb': "Grafisk ansvalig/ansvarleg",
    },
    "Gruppeleder": {
        'en': "Head of Group",
        'nb': "Gruppeleder",
    },
    "H.Tillitsvalgt": {
        'en': "Trade Union Offical",
        'nb': "Hovedtillitsvalgt",
    },
    "HMS-koordinator": {
        'en': "HSE Coordinator",
        'nb': "HMS-koordinator",
    },
    "HR-sjef": {
        'en': "HR Manager",
        'nb': "HR-sjef",
    },
    "Hjelpelærer": {
        'en': "Assistant Teacher",
        'nb': "Hjelpelærer",
    },
    "Hovedvernombud": {
        'en': "Senior Safety Representative",
        'nb': "Hovedvernombud",
    },
    "Husøkonom": {
        'en': "Cleaning Manager",
        'nb': "Husøkonom",
    },
    "IT-direktør": {
        'en': "Director of Information Technology",
        'nb': "IT-direktør",
    },
    "IT-leder": {
        'en': "IT Coordinator",
        'nb': "IT-leder",
    },
    "IT-sikker.sjef": {
        'en': "IT Safety Supervisor",
        'nb': "IT-sikkerhetssjef",
    },
    "Innkjøpskons": {
        'en': "Purchasing Officer",
        'nb': "Innkjøpskonsulent",
    },
    "Innkjøpssjef": {
        'en': "Purchasing Manager",
        'nb': "Innkjøpssjef",
    },
    "Journalist": {
        'en': "Journalist",
        'nb': "Journalist",
    },
    "Jur. rådgiver": {
        'en': "Legal Adviser",
        'nb': "Juridisk rådgiver",
    },
    "Klinikknestled": {
        'en': "Assisting Clinical Coordinator",
        'nb': "Nestleder klinikk",
    },
    "Klinikkoord": {
        'en': "Clinical Coordinator",
        'nb': "Klinikkoordinator",
    },
    "Klinisk stip": {
        'en': "Clinical Doctoral Research Fellow",
        'nb': "Klinisk stipendiat",
    },
    "Komm.direktør": {
        'en': "Director of Communication",
        'nb': "Kommunikasjonsdirektør",
    },
    "Komm.rådgiver": {
        'en': "Communications Adviser",
        'nb': "Kommunkasjonsrådgiver",
    },
    "Konservator": {
        'en': "Conservator",
        'nb': "Konservator",
    },
    "Koordinator": {
        'en': "Coordinator",
        'nb': "Koordinator",
    },
    "Lab.assistant": {
        'en': "Laboratory Assistant",
        'nb': "Laboratorieasssistent",
    },
    "Leder BOT": {
        'en': "General Manager BOT",
        'nb': "Daglig leder BOT",
    },
    "Leder MUSIT": {
        'en': "General Manager MUSIT",
        'nb': "Daglig leder MUSIT",
    },
    "Lokal HMS-koord": {
        'en': "Local HSE Coordinator",
        'nb': "Lokal HMS-koordinator",
    },
    "Lønningssjef": {
        'en': "Compensation and Benefits Manager",
        'nb': "Lønningssjef",
    },
    "Museumsdirektør": {
        'en': "Museum Director",
        'nb': "Museumsdirektør",
    },
    "Nestleder": {
        'en': "Assisting Head of Office",
        'nb': "Nestleder",
    },
    "Nettredaktør": {
        'en': "Web Editor",
        'nb': "Nettredaktør",
    },
    "OPA-persdir": {
        'en': "Director of organization and personnel",
        'nb': "Organisasjons- og personaldirektør",
    },
    "OU-direktør": {
        'en': "Director of Organisational Development",
        'nb': "OU-direktør",
    },
    "Områdeleder": {
        'en': "Area Maintenance Manager",
        'nb': "Områdeleder",
    },
    "Org.rådgiver": {
        'en': "Organisational Adviser",
        'nb': "Organisasjonsrådgiver",
    },
    "Parksjef": {
        'en': "Park Manager",
        'nb': "Parksjef",
    },
    "Pensjonist": {
        'en': "Pensioner",
        'nb': "Pensjonist",
    },
    "Personaldir": {
        'en': "Director of Personnel",
        'nb': "Personaldirektør",
    },
    "Personalkonsulent": {
        'en': "Personnel Officer",
        'nb': "Personalkonsulent",
    },
    "Personalleder": {
        'en': "Personnel Coordinator",
        'nb': "Personalleder",
    },
    "Plan/prosj.dir": {
        'en': "Director of the Planning and Project Subdepartment",
        'nb': "Plan- og prosjektdirektør",
    },
    "Plan/utred.sjef": {
        'en': "Planning Manager",
        'nb': "Plan- og utredningssjef",
    },
    "Planlegger": {
        'en': "Planning Coordinator",
        'nb': "Planlegger",
    },
    "Prod.leder": {
        'en': "Production Manager",
        'nb': "Produksjonsleder",
    },
    "Prod/regissør": {
        'en': "Producer and Director",
        'nb': "Produsent og regissør",
    },
    "Prodekan": {
        'en': "Pro-Dean",
        'nb': "Prodekan",
    },
    "Produsent": {
        'en': "Producer",
        'nb': "Produsent",
    },
    "Prof-II": {
        'en': "Professor II",
        'nb': "Professor II",
    },
    "Prof.emeritus": {
        'en': "Professor Emeritus",
        'nb': "Professor emeritus",
    },
    "Professor II": {
        'en': "Adjunct Professor",
        'nb': "Professor II",
    },
    "Programkons": {
        'en': "Programme Officer",
        'nb': "Programkonsulent",
    },
    "Prorektor": {
        'en': "Pro-Rector",
        'nb': "Prorektor",
    },
    "Prosj.kontroll": {
        'en': "Project Controller",
        'nb': "Prosjektkontroller",
    },
    "Prosjektdir": {
        'en': "Project Director",
        'nb': "Prosjektdirektør",
    },
    "Prosjektleder": {
        'en': "Project Manager",
        'nb': "Prosjektleder",
    },
    "Prosjektsjef": {
        'en': "Head of Project Section",
        'nb': "Prosjektsjef",
    },
    "Psyk.spesialist": {
        'en': "Clinical Psychologist",
        'nb': "Psykologspesialist",
    },
    "Redaktør": {
        'en': "Editor",
        'nb': "Redaktør",
    },
    "Regnskapskontr": {
        'en': "Accounts Controller",
        'nb': "Regnskapskontroller",
    },
    "Regnskapsmedarb": {
        'en': "Accounts Officer",
        'nb': "Regnskapsmedarbeider",
    },
    "Regnskapssjef": {
        'en': "Chief Accountant",
        'nb': "Regnskapssjef",
    },
    "Rekvirent": {
        'en': "Requisitioner",
        'nb': "Rekvirent",
    },
    "Renholdssjef": {
        'en': "Head of Cleaning Section",
        'nb': "Renholdssjef",
    },
    "Resepsjonmedarb": {
        'en': "Receptionist",
        'nb': "Resepsjonsmedarbeider",
    },
    "Revisjonssjef": {
        'en': "Auditing Director",
        'nb': "Revisjonssjef",
    },
    "Seksjonsleder": {
        'en': "Head of Office",
        'nb': "Seksjonsleder",
    },
    "Seniorforsker": {
        'en': "Senior Researcher",
        'nb': "Seniorforsker",
    },
    "Senterdirektør": {
        'en': "Centre Director",
        'nb': "Senterdirektør",
    },
    "Senterleder": {
        'en': "Centre Director",
        'nb': "Senterleder",
    },
    "Sikkerhetsrådgiv": {
        'en': "Security Adviser",
        'nb': "Sikkerhets- og beredskapsrådgiver",
    },
    "Sjef byggdrift": {
        'en': "Operations Manager",
        'nb': "Sjef bygningsdrift",
    },
    "Stabsdirektør": {
        'en': "Staff Director",
        'nb': "Stabsdirektør",
    },
    "Studentbetjent": {
        'en': "Student Officer",
        'nb': "Studentbetjent",
    },
    "Studentprest": {
        'en': "University Chaplain ",
        'nb': "Studentprest",
    },
    "Studiekonsulent": {
        'en': "Student Adviser",
        'nb': "Studiekonsulent",
    },
    "Studieleder": {
        'en': "Programme Coordinator",
        'nb': "Studieleder",
    },
    "Utgravn.leder": {
        'en': "Archaeological Field Officer",
        'nb': "Utgravningsleder",
    },
    "Utstill.design": {
        'en': "Exhibition Designer",
        'nb': "Utstilingsdesigner",
    },
    "Vedlikeh.sjef": {
        'en': "Maintencance Manager",
        'nb': "Vedlikeholdssjef",
    },
    "Veterinær": {
        'en': "Veterinarian",
        'nb': "Veterinær",
    },
    "Viserektor": {
        'en': "Vice-Rector",
        'nb': "Viserektor",
    },
    "Webrådgiver": {
        'en': "Web Adviser",
        'nb': "Webrådgiver",
    },
    "Yrkeshygieniker": {
        'en': "Occupational Hygienist",
        'nb': "Yrkeshygieniker",
    },
    "Økonomikons": {
        'en': "Financial Officer",
        'nb': "Økonomikonsulent",
    },
    "Økonomikontr": {
        'en': "Financial Controller",
        'nb': "Økonomikontroller",
    },
    "Økonomileder": {
        'en': "Financial Coordinator",
        'nb': "Økonomileder",
    },
    "Økonomirådgiver": {
        'en': "Financial Adviser",
        'nb': "Økonomirådgiver",
    },
}


EmployeeMapper.get_affiliations._load_assignment_codes(_ASSIGNMENT_CODES)
EmployeeMapper.get_titles._load_work_titles(_ASSIGNMENT_CODES)
EmployeeMapper.get_titles._load_personal_titles(_PERSONAL_TITLES)
