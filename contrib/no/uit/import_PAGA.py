#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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
Import data from Paga.

Creates/updates person objects in Cerebrum from an XML file.

Configuration
-------------
The following cereconf values affects the Paga import:

DEFAULT_INSTITUSJONSNR
    Default institution number for OUs to use in the Cerebrum database.

DEFAULT_LOGGER_TARGET
    The default log preset to use for this script

EMPLOYEE_PERSON_SPREADS
    Default spreads for person objects from Paga

EMPLOYEE_PERSON_SPREADS_PERCENTAGE
    Required employment percentage required to get the default
    ``EMPLOYEE_PERSON_SPREADS`` spreads.

GRACEPERIOD_EMPLOYEE
    Keep old affiliation for ``GRACEPERIOD_EMPLOYEE`` days after it was last
    seen in an import.

PAGA_EARLYDAYS
    Accept roles from Paga with a start date that is ``PAGA_EARLYDAYS`` days
    into the future.
"""
from __future__ import unicode_literals

import argparse
import datetime
import logging

import mx.DateTime

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.modules.no.uit.PagaDataParser import PagaDataParserClass
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.utils.argutils import add_commit_args
from Cerebrum.utils.funcwrap import memoize

logger = logging.getLogger(__name__)


def parse_date(date_str):
    """
    Parse a date on the strftime format "%Y-%m-%d".

    :rtype: datetime.date
    :return: Returns the date object
    """
    if not date_str:
        raise ValueError('Invalid date %r' % (date_str, ))
    args = (int(date_str[0:4]),
            int(date_str[5:7]),
            int(date_str[8:10]))
    return datetime.date(*args)


def conv_name(fullname):
    fullname = fullname.strip()
    return fullname.split(None, 1)


@memoize
def get_sted(db, fakultet, institutt, gruppe):
    fakultet, institutt, gruppe = int(fakultet), int(institutt), int(gruppe)
    stedkode = (fakultet, institutt, gruppe)

    def filter_addr(addr_rows):
        if len(addr_rows) < 1:
            return None
        else:
            return {k: addr_rows[0][k]
                    for k in ('address_text', 'p_o_box', 'postal_number',
                              'city', 'country')}

    ou = Factory.get('OU')(db)
    const = Factory.get('Constants')(db)
    try:
        ou.find_stedkode(fakultet, institutt, gruppe,
                         institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
        addr_street = filter_addr(
            ou.get_entity_address(source=const.system_paga,
                                  type=const.address_street))
        if addr_street and not addr_street['country']:
            addr_text = addr_street['address_text']
            short_name = ou.get_name_with_language(
                name_variant=const.ou_name_short,
                name_language=const.language_nb,
                default=None)
            addr_street['address_text'] = "\n".join(
                x for x in (short_name, addr_text) if x)

        addr_post = filter_addr(
            ou.get_entity_address(source=const.system_paga,
                                  type=const.address_post))

        fax = ou.get_contact_info(source=const.system_paga,
                                  type=const.contact_fax)
        if len(fax) > 0:
            fax = fax[0]['contact_value']
        else:
            fax = None

        return {
            'id': int(ou.entity_id),
            'fax': fax,
            'addr_street': addr_street,
            'addr_post': addr_post,
        }
    except Errors.NotFoundError:
        logger.error("Bad stedkode=%r", stedkode)
        return None


def _determine_affiliations(db, const, pe, person):
    """
    Determine affiliations in order of significance

    :param pe: A populated Cerebrum.Person object to calculate affs for
    :param person: A dict with person data.
    """
    paga_nr = int(person['ansattnr'])
    ret = {}
    tittel = None
    prosent_tilsetting = -1
    for t in person.get('tils', ()):
        if not type_is_active(t):
            logger.warning("Ignoring inactive 'tils' record for "
                           "paga_id=%r (%r)", paga_nr, t)
            continue

        pros = float(t['stillingsandel'])
        if t['tittel'] == 'professor II':
            pros = pros / 5.0
        if prosent_tilsetting < pros:
            prosent_tilsetting = pros
            tittel = t['tittel']
        if (t['tjenesteforhold'] == 'T') and (pros == 0.0):
            aff_stat = const.affiliation_status_timelonnet_midlertidig
        elif t['hovedkategori'] == 'TEKN':
            aff_stat = const.affiliation_status_ansatt_tekadm
        elif t['hovedkategori'] == 'ADM':
            aff_stat = const.affiliation_status_ansatt_tekadm
        elif t['hovedkategori'] == 'VIT':
            aff_stat = const.affiliation_status_ansatt_vitenskapelig
        else:
            logger.error("Unknown hovedkat: %r", t['hovedkategori'])
            continue

        fakultet, institutt, gruppe = (t['fakultetnr_utgift'],
                                       t['instituttnr_utgift'],
                                       t['gruppenr_utgift'])
        sted = get_sted(db, fakultet, institutt, gruppe)
        if sted is None:
            continue
        k = "%s:%s:%s" % (pe.entity_id, sted['id'],
                          int(const.affiliation_ansatt))
        if k not in ret:
            ret[k] = sted['id'], const.affiliation_ansatt, aff_stat

    if tittel:
        pe.add_name_with_language(name_variant=const.work_title,
                                  name_language=const.language_nb,
                                  name=tittel)

    if person.get('gjest'):
        logger.error("Gjest records not implemented!")
    for g in person.get('gjest', ()):
        if not type_is_active(g):
            logger.warning("Ignoring inactive 'gjest' record for "
                           "paga_id=%r (%r)", paga_nr, t)
            continue
    return ret


def determine_contact(const, person):
    # TODO: Check if this is being used or may be used
    ret = []
    for t in person.get('arbtlf', ()):
        if int(t['telefonnr']):
            ret.append((const.contact_phone, t['telefonnr']))
        if int(t['linjenr']):
            ret.append((const.contact_phone,
                        "%i%05i" % (int(t['innvalgnr']), int(t['linjenr']))))
    for k in person.get('komm', ()):
        if k['kommtypekode'] in ('ARBTLF', 'EKSTRA TLF', 'JOBBTLFUTL'):
            if 'kommnrverdi' in k:
                val = k['kommnrverdi']
            elif 'telefonnr' in k:
                val = int(k['telefonnr'])
            else:
                continue
            ret.append((const.contact_phone, val))
        if k['kommtypekode'] in ('FAX', 'FAXUTLAND'):
            if 'kommnrverdi' in k:
                val = k['kommnrverdi']
            elif 'telefonnr' in k:
                val = int(k['telefonnr'])
            else:
                continue
            ret.append((const.contact_fax, val))
    return ret


def person_has_active(person, entry_type):
    """
    Determine if the person represented by PERSON has active ENTRY_TYPE
    entries.  'active' is defined as: dato_fra <= now <= dato_til.
    ENTRY_TYPE can be either 'tils' or 'gjest'
    """
    data = person.get(entry_type, list())
    for entry in data:
        if type_is_active(entry):
            return True
    return False


def type_is_active(entry_type):
    """
    Check whether given entry is active.

    :param entry_type:
        A dictionary representing either a 'tils' record or a 'gjest' record.
    """
    today = datetime.date.today()
    pre_days = datetime.timedelta(
        days=int(getattr(cereconf, 'PAGA_EARLYDAYS', 0)))

    dato_fra = parse_date(entry_type['dato_fra'])
    try:
        dato_til = parse_date(entry_type.get('dato_til'))
    except ValueError:
        dato_til = None
        pass

    earliest = dato_fra - pre_days
    is_active = today >= earliest and (dato_til is None or today <= dato_til)

    if not is_active:
        logger.debug('Inactive entry, earliest=%r, from=%r, to=%r',
                     earliest, dato_fra, dato_til)
    return is_active


def get_stillingsandel(person):
    prosent_tilsetting = 0
    for tils in person.get('tils', ()):
        if not type_is_active(tils):
            continue

        if not tils['hovedkategori'] in ('TEKN', 'ADM', 'VIT'):
            # this tils has unknown hovedkat, ignore it
            continue

        pros = float(tils['stillingsandel'])
        prosent_tilsetting += pros
    return prosent_tilsetting


def set_person_spreads(db, const, pe, person):
    """
    Apply person spreads to employee object.

    Add ansatt spreads if person has ANSATT affiliation and has a
    stillingsandel higher than cereconf.EMPLOYEE_PERSON_SPREADS_PERCENTAGE.
    Spreads to add are listed in cereconf.EMPLOYEE_PERSON_SPREADS

    :param pe: A populated Cerebrum.Person object to apply spreads to
    :param person: A dict with person data.
    """
    employee_person_spreads = [int(const.Spread(x))
                               for x in cereconf.EMPLOYEE_PERSON_SPREADS]

    affs = list(pe.get_affiliations())
    is_ansatt = False
    for aff in affs:
        if aff['affiliation'] == int(const.affiliation_ansatt):
            percentage = get_stillingsandel(person)
            if percentage > cereconf.EMPLOYEE_PERSON_SPREADS_PERCENTAGE:
                is_ansatt = True
                break

    if is_ansatt:
        spreads_to_add = employee_person_spreads

        # only add spreads this person doesn't already have
        curr_spreads = pe.get_spread()
        for s in curr_spreads:
            if s['spread'] in spreads_to_add:
                spreads_to_add.remove(s['spread'])

        for spread in spreads_to_add:
            pe.add_spread(spread)
    else:
        # remove employee spreads for those with is_ansatt == False
        spreads_to_remove = employee_person_spreads

        # only remove employee spreads this person already has
        curr_spreads = pe.get_spread()
        for s in curr_spreads:
            if s['spread'] in spreads_to_remove:
                pe.delete_spread(s['spread'])


def is_y2k_problem(year_chk, year):
    curr_year = datetime.date.today().year

    # If the difference between year_chk and year is exactly 100,
    # and year_chk is 100 years or more in the past,
    # it is highly likely that there is a y2k problem with year_chk.
    return abs(year_chk - year) == 100 and year_chk <= (curr_year - 100)


def cmp_birthdates(birthdate, from_ssn):
    return (
        (from_ssn.year == birthdate.year or
         is_y2k_problem(from_ssn.year, birthdate.year)) and
        from_ssn.month == birthdate.month and from_ssn.day == birthdate.day)


def _populate_existing(pe, id_type, id_value):
    """
    Find and populate a person object by external id.

    :rtype: bool
    :return: True if person object was found.
    """
    if not id_value:
        return False
    try:
        pe.find_by_external_id(id_type, str(id_value))
        logger.debug("Found existing person_id=%r with %s=%r",
                     pe.entity_id, id_type, id_value)
        return True
    except Errors.NotFoundError:
        return False


class SkipPerson(Exception):
    """
    Invalid person data given.
    """
    pass


class PersonProcessor(object):
    """
    Callable object that imports dict-like person objects.

    Used as a callback for py:class:`PagaDataParserClass`.
    """

    def __init__(self, db, old_affs):
        """
        :type old_affs: set
        :param old_affs:
            A set with all previously known Paga-affiliations.

            Each item should be a string on the format
            <person-id>:<ou-id>:<aff-code>.  Any affiliation seen during
            processing will be removed from the set.
        """
        self.db = db
        self.const = Factory.get('Constants')(db)
        self.old_affs = old_affs if old_affs is not None else set()

    def __call__(self, person):
        """
        Import a person object.

        :param person_dict: A dict-like person object.
        """
        try:
            employee_id = int(person['ansattnr'])
        except Exception:
            logger.error('Unable to process paga_id=%r, invalid identifier',
                         person['ansattnr'])
            return

        try:
            self._process_person(person)
        except SkipPerson as e:
            logger.error('Unable to process paga_id=%r, %s', employee_id, e)
        except Exception:
            logger.critical('Unable to process paga_id=%r, unhandled error',
                            employee_id, exc_info=True)
            raise

    def _process_person(self, person):
        db = self.db
        const = self.const
        paga_nr = int(person['ansattnr'])
        logger.info("Processing paga_id=%r", paga_nr)

        try:
            birthdate = parse_date(person['fodselsdato'])
        except ValueError as e:
            raise SkipPerson("Invalid birth date (%s)" % (e, ))

        if person['kjonn'] == 'M':
            gender = const.gender_male
        else:
            gender = const.gender_female

        fnr = person['fnr']
        if fnr and fnr[6:11] != '00000':
            try:
                fodselsnr.personnr_ok(fnr)
            except Exception as e:
                raise SkipPerson("Invalid fnr (%s)" % (e, ))

            gender_chk = const.gender_male
            if fodselsnr.er_kvinne(fnr):
                gender_chk = const.gender_female

            if gender_chk != gender:
                raise SkipPerson(
                    "Inconsistent gender (gender=%r, ssn=%r)" %
                    (gender, gender_chk))

            fnr_date = datetime.date(*(fodselsnr.fodt_dato(fnr)))
            if not cmp_birthdates(birthdate, fnr_date):
                raise SkipPerson(
                    "Inconsistent birth date (date=%r, ssn=%r)" %
                    (birthdate, fnr_date))

        # Passport data
        national_id_type = person['edag_id_type']
        origin_country = person['country']
        if not origin_country:
            origin_country = 'NO'
        if person['edag_id_nr']:
            # generate external id on the form:
            # <2-char national id>-<national_id>
            national_id_val = '%s-%s' % (origin_country, person['edag_id_nr'])
        else:
            national_id_val = None

        # Abort early if there are no valid identifiers from the source system:
        if not any((fnr and fnr[6:11] != '00000',
                    national_id_type == 'passnummer' and national_id_val,)):
            # TODO: Wouldn't it be enough with ansattnr?
            raise SkipPerson("No valid identifier (fnr, passnummer)")

        new_person = Factory.get('Person')(db)

        identifiers = [(const.externalid_paga_ansattnr, paga_nr),
                       (const.externalid_fodselsnr, fnr)]
        if national_id_type == 'passnummer' and national_id_val:
            identifiers.append((const.externalid_pass_number, national_id_val))
        for id_type, id_value in identifiers:
            if _populate_existing(new_person, id_type, id_value):
                break

        if not person.get('fornavn', '').strip():
            raise SkipPerson("Missing first name")
        if not person.get('etternavn', '').strip():
            raise SkipPerson("Missing last name")

        new_person.populate(mx.DateTime.DateFrom(birthdate), gender)

        new_person.affect_names(const.system_paga,
                                const.name_first,
                                const.name_last)
        new_person.affect_external_id(const.system_paga,
                                      const.externalid_fodselsnr,
                                      const.externalid_paga_ansattnr,
                                      const.externalid_pass_number)
        new_person.populate_name(const.name_first, person['fornavn'])
        new_person.populate_name(const.name_last, person['etternavn'])

        if fnr and fnr[6:11] != '00000':
            # do not import external id where external_id type is fnr and
            # fnr[6-11] =='00000'
            new_person.populate_external_id(const.system_paga,
                                            const.externalid_fodselsnr,
                                            fnr)
        if national_id_type == 'passnummer' and national_id_val:
            new_person.populate_external_id(const.system_paga,
                                            const.externalid_pass_number,
                                            national_id_val)
        new_person.populate_external_id(const.system_paga,
                                        const.externalid_paga_ansattnr,
                                        paga_nr)

        # If it's a new person, we need to call write_db() to have an entity_id
        # assigned to it.
        op = new_person.write_db()

        if person.get('tittel_personlig'):
            new_person.add_name_with_language(
                name_variant=const.personal_title,
                name_language=const.language_nb,
                name=person['tittel_personlig'])

        # work_title is set by _determine_affiliations
        affiliations = _determine_affiliations(self.db, self.const,
                                               new_person, person)
        new_person.populate_affiliation(const.system_paga)
        if 'fakultetnr_for_lonnsslip' in person:
            sted = get_sted(db,
                            person['fakultetnr_for_lonnsslip'],
                            person['instituttnr_for_lonnsslip'],
                            person['gruppenr_for_lonnsslip'])
            if sted is not None:
                if sted['addr_street'] is not None:
                    new_person.populate_address(
                        const.system_paga, type=const.address_street,
                        **sted['addr_street'])
                if sted['addr_post'] is not None:
                    new_person.populate_address(
                        const.system_paga, type=const.address_post,
                        **sted['addr_post'])

        if 'lokasjon' in person:
            logger.debug('Populating paga_id=%r location address with '
                         'source=%s, type=%s, text=%r',
                         paga_nr, const.system_paga, const.address_location,
                         person['lokasjon'])
            new_person.populate_address(source_system=const.system_paga,
                                        type=const.address_location,
                                        address_text=person['lokasjon'])
        else:
            logger.warning("No location address for paga_id=%r", paga_nr)

        for k, v in affiliations.items():
            ou_id, aff, aff_stat = v
            new_person.populate_affiliation(const.system_paga, ou_id,
                                            int(aff), int(aff_stat))
            self.old_affs.discard(k)
        c_prefs = {}
        new_person.populate_contact_info(const.system_paga)

        for c_type, value in determine_contact(const, person):
            c_type = int(c_type)
            pref = c_prefs.get(c_type, 0)
            new_person.populate_contact_info(const.system_paga,
                                             c_type, value, pref)
            c_prefs[c_type] = pref + 1

        #
        # Also add personal/home street address if it exists in the import file
        #
        priv_addr = (person.get('adresse'),
                     person.get('postnr'),
                     person.get('poststed'))
        if any(priv_addr):
            logger.debug("Setting additional home address: %s %s %s",
                         priv_addr[0], priv_addr[1], priv_addr[2])
            # TODO: Address country? Should probably use const.human2constant()
            # country_code = new_person.get_country_code(origin_country)
            # TODO: Is there really a guaranteed connection between passport
            #       origin country and home address?
            new_person.populate_address(const.system_paga,
                                        const.address_post_private,
                                        priv_addr[0], None, priv_addr[1],
                                        priv_addr[2], None)

        op2 = new_person.write_db()

        set_person_spreads(self.db, self.const, new_person, person)

        if op is None and op2 is None:
            logger.info("EQUAL: No change to person with paga_id=%r", paga_nr)
        elif op:
            logger.info("NEW: Created new person with paga_id=%r", paga_nr)
        else:
            logger.info("UPDATE: Updated person with paga_id=%r (%s, %s)",
                        paga_nr, op, op2)


def load_paga_affiliations(db):
    """
    Fetch all affiliations from the paga source system.

    :rtype: set
    :return:
        A set with *affiliation keys*.  Each affiliation key should be a string
        on the format <person_id>:<ou_id>:<affiliation_code>
    """
    pe = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)
    affi_list = set()
    for row in pe.list_affiliations(source_system=const.system_paga):
        key_l = "%s:%s:%s" % (row['person_id'], row['ou_id'],
                              row['affiliation'])
        affi_list.add(key_l)
    return affi_list


def remove_old_affiliations(db, affiliations):
    """
    Remove affiliations.

    Only removes affiliations if the affiliation source `last_date` indicates
    that it should be deleted.

    :param affiliations:
        An iterable with *affiliation keys*.
    """
    pe = Factory.get('Person')(db)
    const = Factory.get('Constants')(db)

    employee_person_spreads = [
        int(const.Spread(x))
        for x in cereconf.EMPLOYEE_PERSON_SPREADS]
    today = datetime.date.today()
    grace_period = datetime.timedelta(days=cereconf.GRACEPERIOD_EMPLOYEE)

    for aff_key in affiliations:
        [ent_id, ou, affi] = [int(x) for x in aff_key.split(':')]
        pe.clear()
        pe.entity_id = int(ent_id)
        affs = pe.list_affiliations(
            ent_id,
            affiliation=affi,
            ou_id=ou,
            source_system=const.system_paga)
        for aff in affs:
            last_date = aff['last_date'].pydate()
            end_grace_period = last_date + grace_period
            if today > end_grace_period:
                logger.warning(
                    "Deleting system_paga affiliation for "
                    "person_id=%s,ou=%s,affi=%s last_date=%s,grace=%s",
                    ent_id, ou, affi, last_date, grace_period)
                pe.delete_affiliation(ou, affi, const.system_paga)

            if today > last_date:
                # person is no longer an employee, delete employee spreads
                # for this person.  Spreads to delete are listed in
                # cereconf.EMPLOYEE_PERSON_SPREADS
                for s in employee_person_spreads:
                    pe.delete_spread(s)


default_log_preset = getattr(cereconf, 'DEFAULT_LOGGER_TARGET', 'console')


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description="Import Paga XML files into the Cerebrum database")

    parser.add_argument(
        '-p', '--person-file',
        help='Read and import persons from %(metavar)s',
        metavar='xml-file',
    )
    parser.add_argument(
        '--delete', '--include-delete',
        dest='delete',
        action='store_true',
        default=False,
        help='Delete old affiliations',
    )
    add_commit_args(parser)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf(default_log_preset, args)

    logger.info('Start of %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()
    db.cl_init(change_program=parser.prog)

    if args.delete:
        old_affs = load_paga_affiliations(db)
    else:
        old_affs = None

    if args.person_file:
        person_callback = PersonProcessor(db, old_affs=old_affs)
        PagaDataParserClass(args.person_file, person_callback)

    if args.delete:
        remove_old_affiliations(db, old_affs)

    if args.commit:
        logger.info('Commiting changes')
        db.commit()
    else:
        logger.info('Rolling back changes')
        db.rollback()
    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
