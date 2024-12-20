#!/usr/bin/env python
# coding: utf-8
""" This script maintains Elements spreads and automatic roles for employees.

It can also send an email report if Cerebrum and Elements disagrees about which
organizational units should be active.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import argparse
import datetime
import six

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils import argutils
from Cerebrum.utils import date_compat
from Cerebrum.utils.email import mail_template as mail_template_util
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.no.uio.Elements import ElementsRole
from Cerebrum.modules.no.uio.Elements import ElementsPermission
from Cerebrum.modules.no.uio.ElementsWS import make_elements_client

#
# Settings
#
# Elements admin group setting
ELEMENTS_ADMINS = getattr(cereconf, 'EPHORTE_ADMINS')

# Specific SKOs
ELEMENTS_UIO_ROOT_SKO = getattr(cereconf, 'EPHORTE_UIO_ROOT_SKO')
ELEMENTS_EGNE_SAKER_SKO = getattr(cereconf, 'EPHORTE_EGNE_SAKER_SKO')

# SKO lists
ELEMENTS_FSAT_SKO = getattr(cereconf, 'EPHORTE_FSAT_SKO')
ELEMENTS_KDTO_SKO = getattr(cereconf, 'EPHORTE_KDTO_SKO')

# Day filter (when to allow email warnings), and email template
ELEMENTS_MAIL_TIME = getattr(cereconf, 'EPHORTE_MAIL_TIME', [])
ELEMENTS_MAIL_OU_MISMATCH = getattr(cereconf, 'EPHORTE_MAIL_OU_MISMATCH')

MAX_OU_LEVELS_TO_CLIMB_IN_SEARCH_OF_ELEMENTS_OU = 2

#
# Globals
#
logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
db.cl_init(change_program="populate_elements")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
group = Factory.get('Group')(db)
elements_role = ElementsRole(db)
elements_perm = ElementsPermission(db)
ou = Factory.get("OU")(db)
ou_mismatch_warnings = {'sap': [], 'elements': []}


@six.python_2_unicode_compatible
class SimpleRole(object):
    """ Elements role. """

    def __init__(self, role_type, adm_enhet, arkivdel, journalenhet,
                 standard_role=True, auto_role=True):
        self.role_type = role_type
        self.adm_enhet = adm_enhet
        self.arkivdel = arkivdel
        self.journalenhet = journalenhet
        self.auto_role = auto_role
        self.standard_role = standard_role

    def __eq__(self, b):
        return (self.role_type == b.role_type and
                self.adm_enhet == b.adm_enhet and
                self.arkivdel == b.arkivdel and
                self.journalenhet == b.journalenhet)

    def __str__(self):
        return ("role_type={0.role_type!s}, adm_enhet={0.adm_enhet!s},"
                " arkivdel={0.arkivdel!s}, journalenhet={0.journalenhet!s},"
                " standard_role={0.standard_role!s}").format(self)


def format_role(role):
    role['role_type'] = co.ElementsRole(role.get('role_type'))
    return ("role_type={role_type!s}, adm_enhet={adm_enhet!s},"
            " arkivdel={arkivdel!s}, journalenhet={journalenhet!s},"
            " person_id={person_id!s}"
            " standard_role={standard_role!s} auto_role={auto_role!s}"
            " start_date={start_date!s}, end_date={end_date!s}").format(**role)


def format_permission(perm):
    perm['perm_type'] = co.ElementsPermission(perm.get('perm_type'))
    return ("perm_type={perm_type!s}, adm_enhet={adm_enhet!s},"
            " requestee_id={requestee_id!s}, person_id={person_id!s},"
            " start_date={start_date!s}, end_date={end_date!s}").format(**perm)


class PopulateElements(object):
    """ Elements sync client. """

    select_affiliations = (
        ('DFO_SAP', 'ANSATT'),
        ('DFO_SAP', 'TILKNYTTET/ekst_partner'),
        ('GREG', 'TILKNYTTET/ekst_partner'),
    )

    def __init__(self, ewsclient):
        "Pre-fetch information about OUs in Elements and Cerebrum."

        # Special sko, ignore:
        elements_sko_ignore = ['null', '[Ufordelt]']
        # stedkode -> ouid:
        self.sko2ou_id = {}
        # ouid -> (arkivdel, journalenhet):
        self.ouid_2roleinfo = {}
        # ouid -> stedkode:
        self.ouid2sko = {}

        logger.info("Fetching OU info from Cerebrum")
        for row in ou.get_stedkoder():
            sko = "%02i%02i%02i" % tuple([
                int(row[x]) for x in ('fakultet', 'institutt', 'avdeling')])
            ou_id = int(row['ou_id'])
            self.ouid2sko[ou_id] = sko
            self.sko2ou_id[sko] = ou_id
            # Special case, FSAT
            if sko in ELEMENTS_FSAT_SKO:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.elements_arkivdel_sak_fsat),
                    int(co.elements_journenhet_fsat))
            # Special case, KDTO
            elif sko in ELEMENTS_KDTO_SKO:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.elements_arkivdel_sak_kdto),
                    int(co.elements_journenhet_kdto))
            # Default case
            else:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.elements_arkivdel_sak),
                    int(co.elements_journenhet_sp))
        logger.info("Found info about %d sko in cerebrum" % len(self.ouid2sko))

        logger.info("Finding OUs with spread elements_ou")
        self.sap_elements_ouid2name = {}
        ou_id2name = dict((r["entity_id"], r["name"])
                          for r in ou.search_name_with_language(
                          entity_type=co.entity_ou,
                          name_language=co.language_nb,
                          name_variant=co.ou_name_display))

        # due to a logical error in elements-sync we have to allow
        # non-existing OU's to be assigned roles. the background for
        # this change is available in ePhorte case 2011/14072
        # registrered 10th of november 2011 by Astrid Optun and
        # updated by USIT in january 2012
        #
        # for row in ou.search(spread=co.spread_elements_ou):
        for row in ou.search():
            self.sap_elements_ouid2name[int(row['ou_id'])] = ou_id2name.get(
                row["ou_id"], "")
        logger.info("Found %d ous with spread elements_ou" %
                    len(self.sap_elements_ouid2name.keys()))
        #
        # GRUSOMT HACK
        #
        # Ideelt burde vi syncet OU'er til Elements, men det gjør vi altså ikke.
        # Det gamle grusomme hacket med å dumpe OU-tabell fra ePhorte og lese
        # inn denne, er erstattet med å lese inn OU'er fra ny web service.
        # Vi får ikke lenger start og sluttdato, så det blir slutt på å
        # rapportere steder som ikke er aktive.
        logger.info(
            "Fetching OU info from Elements WS %s reading elements %s/%s",
            ewsclient.wsdl,
            ewsclient.config_id,
            ewsclient.database)
        elements_ous = ewsclient.get_all_org_units()

        self.app_elements_ouid2name = {}
        for eou in elements_ous:
            elements_sko = eou['OrgId']
            elements_name = eou['Name']
            ou_id = self.sko2ou_id.get(elements_sko)
            if ou_id is None:
                if elements_sko not in elements_sko_ignore:
                    logger.warn("Unknown Elements sko: '%s'" % elements_sko)
                continue
            self.app_elements_ouid2name[ou_id] = elements_name
        logger.info("Found %d Elements sko from app." %
                    len(self.app_elements_ouid2name.keys()))

        for ou_id in (set(self.app_elements_ouid2name.keys()) -
                      set(self.sap_elements_ouid2name.keys())):
            # Add ou to list that is sent in warn mail
            ou_mismatch_warnings['elements'].append(
                (self.ouid2sko[ou_id], self.app_elements_ouid2name[ou_id]))
            logger.info(
                "OU (%6s: %s) in Elements, but has no Elements spread" % (
                    self.ouid2sko[ou_id], self.app_elements_ouid2name[ou_id]))
        for ou_id in (set(self.sap_elements_ouid2name.keys()) -
                      set(self.app_elements_ouid2name.keys())):
            # Add ou to list that is sent in warn mail
            ou_mismatch_warnings['sap'].append(
                (self.ouid2sko[ou_id], self.sap_elements_ouid2name[ou_id]))
            logger.info(
                "OU (%6s, %s) has Elements spread, but is not in Elements" % (
                    self.ouid2sko[ou_id], self.sap_elements_ouid2name[ou_id]))
        #
        # GRUSOMT HACK SLUTT
        #

        # Find the OU hierarchy
        self.ou_id2parent = {}
        for row in ou.get_structure_mappings(co.perspective_sap):
            i = row['parent_id'] and int(row['parent_id']) or None
            self.ou_id2parent[int(row['ou_id'])] = i

        # superuser-rollen skal ha UiOs rotnode som adm_enhet
        self._superuser_role = SimpleRole(
            int(co.elements_role_sy),
            self.sko2ou_id[ELEMENTS_UIO_ROOT_SKO],
            int(co.elements_arkivdel_sak),
            int(co.elements_journenhet_sp),
            standard_role=False,
            auto_role=False)

    def map_ou_to_role(self, ou_id):
        arkiv, journal = self.ouid_2roleinfo[ou_id]
        return SimpleRole(int(co.elements_role_sb), ou_id, arkiv, journal)

    def find_person_info(self, person_id):
        ret = {'person_id': person_id}
        try:
            pe.clear()
            pe.find(person_id)
        except Errors.NotFoundError:
            logger.warn("Couldn't find person with id %s" % person_id)

        try:
            a_id = ac.list_accounts_by_type(person_id=person_id,
                                            primary_only=True)
            ac.clear()
            ac.find(a_id[0]['account_id'])
            ret['uname'] = ac.account_name
        except (Errors.NotFoundError, IndexError):
            logger.info("Couldn't find primary account for person %s" %
                        person_id)
            ret['uname'] = ""

        return ret

    def _select_affiliations(self):
        # TODO: co/pe should be non-global
        seen = set()
        for source_str, aff_str in self.select_affiliations:
            source = co.get_constant(co.AuthoritativeSystem, source_str)
            aff, status = co.get_affiliation(aff_str)
            for row in pe.list_affiliations(source_system=source,
                                            affiliation=aff,
                                            status=status):
                t = (int(row['person_id']), int(row['ou_id']))
                if t in seen:
                    # No reaason to yield the same pair twice
                    continue
                yield t
                seen.add(t)

    @memoize
    def map_person_to_ou(self):
        logger.info("Mapping person affiliations to Elements OU")
        # person -> {ou_id:1, ...}
        person_to_ou = {}
        level2num_persons = {}

        # Find where person has a selected aff and check
        # if that ou is an Elements ou. If not try to map to nearest
        # Elements OU as specified in ephorte-sync-spec.rst
        for person_id, ou_id in self._select_affiliations():
            elements_ou_id, levels_climbed = self.resolve_to_elements_ou(ou_id)

            # No Elements OU found.
            if elements_ou_id is None:
                sko = self.ouid2sko[ou_id]
                if self.find_person_info(person_id)['uname']:
                    obj_type = "account"
                    obj_value = self.find_person_info(person_id)['uname']
                else:
                    obj_type = "person"
                    obj_value = person_id
                # elements support must deal with this and they should be
                # informed
                logger.warning("Failed mapping '%s' to known Elements OU. "
                               "Skipping affiliation for %s %s",
                               sko, obj_type, obj_value)
                continue

            if levels_climbed not in level2num_persons:
                level2num_persons[levels_climbed] = 0
            level2num_persons[levels_climbed] += 1

            person_to_ou.setdefault(person_id, {})[elements_ou_id] = 1

        for levels_climbed, num_persons in level2num_persons.items():
            logger.info(
                'Number of times where an Elements OU was found %s '
                'parent-levels above a persons affiliation OU: %s',
                levels_climbed, num_persons)

        logger.info(
            '(The maximum number of parent-OU-levels above a persons '
            'affiliation OU that will be looked up in search of an '
            'Elements OU: %s',
            MAX_OU_LEVELS_TO_CLIMB_IN_SEARCH_OF_ELEMENTS_OU)

        return person_to_ou

    def resolve_to_elements_ou(self, ou_id):
        levels_climbed = 0
        non_elements_ous = []

        while ou_id not in self.app_elements_ouid2name:

            levels_climbed += 1
            parent_ou_id = self.ou_id2parent.get(ou_id)

            if (levels_climbed >
                    MAX_OU_LEVELS_TO_CLIMB_IN_SEARCH_OF_ELEMENTS_OU or
                    # expression under: this ou is root ou
                    parent_ou_id is None):
                return None, 0

            if ou_id not in non_elements_ous:
                non_elements_ous.append(ou_id)
                logger.debug(
                    "OU %s is not an Elements OU. Trying parent: %s" % (
                        self.ouid2sko[ou_id], self.ouid2sko[parent_ou_id]))

            ou_id = parent_ou_id

        return ou_id, levels_climbed

    def map_person_to_roles(self):
        logger.info("Mapping persons to existing Elements roles")
        person_to_roles = {}
        for row in elements_role.list_roles():
            person_to_roles.setdefault(int(row['person_id']), []).append(
                SimpleRole(int(row['role_type']),
                           int(row['adm_enhet']),
                           row['arkivdel'],
                           row['journalenhet'],
                           row['standard_role'],
                           auto_role=(row['auto_role'] == 'T')))
        return person_to_roles

    def populate_roles(self):
        """Automatically add roles and spreads for employees. """
        logger.info("Start populating roles")
        person_to_ou = self.map_person_to_ou()
        person_to_roles = self.map_person_to_roles()
        has_elements_spread = set([int(row["entity_id"]) for row in
                                  pe.list_all_with_spread(
                                      co.spread_ephorte_person)])

        # Ideally, the group should have persons as members, but bofh
        # doesn't have much support for that, so we map user->owner_id
        # instead
        superusers = []
        group.find_by_name(ELEMENTS_ADMINS)
        for account_id in set([int(row["member_id"])
                               for row in group.search_members(
                                   group_id=group.entity_id,
                                   indirect_members=True,
                                   member_type=co.entity_account)]):
            ac.clear()
            ac.find(account_id)
            superusers.append(int(ac.owner_id))

        # All neccessary data has been fetched. Now we can check if
        # persons have the roles they should have.
        logger.info("Start comparison of roles")
        std_role = False
        for person_id, ous in person_to_ou.items():
            auto_roles = []  # The roles an employee automatically should get
            existing_roles_to_be_removed = person_to_roles.get(person_id, [])
            # Add saksbehandler role for each elements ou where an
            # employee has an affiliation
            for t in ous:
                auto_roles.append(self.map_ou_to_role(t))
            if person_id in superusers:
                auto_roles.append(self._superuser_role)
            # All employees should have access to their own cases
            for role in (co.elements_role_ar, co.elements_role_of):
                auto_roles.append(SimpleRole(
                    int(role),
                    self.sko2ou_id[ELEMENTS_EGNE_SAKER_SKO],
                    int(co.elements_arkivdel_sak),
                    int(co.elements_journenhet_sp),
                    standard_role=False,
                    auto_role=True))
            # All employees shall have elements spread
            if person_id not in has_elements_spread:
                pe.clear()
                pe.find(person_id)
                pe.add_spread(co.spread_ephorte_person)

            for ar in auto_roles:
                # Check if role should be added
                if ar in existing_roles_to_be_removed:
                    existing_roles_to_be_removed.remove(ar)
                else:
                    uname = self.find_person_info(person_id)['uname']
                    logger.info("Adding role (pid=%i, uname=%s): %s" %
                                (person_id, uname, ar))
                    elements_role.add_role(person_id, ar.role_type,
                                          ar.adm_enhet, ar.arkivdel,
                                          ar.journalenhet)
            for er in existing_roles_to_be_removed:
                # Only saksbehandler role that has been given
                # automatically can be removed. Any other roles have
                # been given in bofh and should not be touched.
                if er.auto_role and er.role_type == int(co.elements_role_sb):
                    uname = self.find_person_info(person_id)['uname']
                    logger.info("Removing role (pid=%i, uname=%s): %s" %
                                (person_id, uname, er))
                    elements_role.remove_role(person_id, er.role_type,
                                             er.adm_enhet, er.arkivdel,
                                             er.journalenhet)

                if er.standard_role == 'T':
                    std_role = True

            if not std_role:
                for er in existing_roles_to_be_removed:
                    if er.role_type == int(co.elements_role_sb):
                        elements_role.set_standard_role_val(
                            person_id,
                            co.elements_role_sb,
                            er.adm_enhet,
                            int(co.ElementsArkivdel(er.arkivdel)),
                            int(co.ElementsJournalenhet(er.journalenhet)),
                            'T')
                        logger.info(
                            "Added standard role for %d, '%s, %d, %s, %s'",
                            person_id, co.elements_role_sb, er.adm_enhet,
                            co.ElementsArkivdel(er.arkivdel),
                            co.ElementsJournalenhet(er.journalenhet))
                        break
        logger.info("Done populating roles")

    def depopulate(self):
        """Remove spreads, roles and permissions for non-employees."""
        logger.info("Start depopulating")
        should_have_spread = set(self.map_person_to_ou().keys())
        logger.info("Fetching existing spreads")
        has_spread = set([int(row["entity_id"]) for row in
                          pe.list_all_with_spread(co.spread_ephorte_person)])
        victims = has_spread - should_have_spread
        logger.info('%d persons should have Elements spread',
                    len(should_have_spread))
        logger.info('%d persons have Elements spread',
                    len(has_spread))
        logger.info('%d persons should lose Elements spread',
                    len(victims))
        for person_id in victims:
            uname = self.find_person_info(person_id)['uname']
            logger.info(
                'Removing Elements data for person_id: %s, uname: %s',
                person_id, uname)
            pe.clear()
            pe.find(person_id)
            for perm in elements_perm.list_permission(person_id=person_id):
                perm = dict(perm)
                perm["start_date"] = date_compat.get_date(perm["start_date"])
                perm["end_date"] = date_compat.get_date(perm["end_date"])
                logger.info('Removing permission: %s',
                            format_permission(dict(perm)))
                elements_perm.remove_permission(person_id=person_id,
                                               perm_type=perm['perm_type'],
                                               sko=perm['adm_enhet'])
            for role in elements_role.list_roles(person_id=person_id):
                role = dict(role)
                role["start_date"] = date_compat.get_date(role["start_date"])
                role["end_date"] = date_compat.get_date(role["end_date"])
                logger.info('Removing role: %s', format_role(dict(role)))
                elements_role.remove_role(person_id=person_id,
                                         role=role['role_type'],
                                         sko=role['adm_enhet'],
                                         arkivdel=role['arkivdel'],
                                         journalenhet=role['journalenhet'])
            pe.delete_spread(co.spread_ephorte_person)
        logger.info('Done depopulating')


def mail_warnings(mailto, debug=False):
    """
    If warnings of certain types occur, send those as mail to address
    specified in mailto. If cereconf.ELEMENTS_MAIL_TIME is specified,
    just send if time when script is run matches with specified time.
    """
    # Check if we should send mail today
    if datetime.datetime.now().strftime('%A') not in ELEMENTS_MAIL_TIME:
        logger.info('Not mailing warnings today')
        return
    if ou_mismatch_warnings['elements'] or ou_mismatch_warnings['sap']:
        sap_warnings = '\n'.join([
            "%6s  %s" % x for x in ou_mismatch_warnings['sap']])
        elements_warnings = '\n'.join([
            "%6s  %s" % x for x in ou_mismatch_warnings['elements']])
        substitute = {'SAP_WARNINGS': sap_warnings,
                      'ELEMENTS_WARNINGS': elements_warnings}
        send_mail(mailto, ELEMENTS_MAIL_OU_MISMATCH, substitute, debug=debug)


def send_mail(mailto, mail_template, substitute, debug=False):
    ret = mail_template_util(mailto, mail_template, substitute=substitute,
                             debug=debug)
    if ret:
        logger.info("Not sending mail:\n%s" % ret)
    else:
        logger.info("Sending mail to: %s" % mailto)


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-r", "--populate-roles",
        action="store_true",
        default=False,
        help="Populate auto roles",
    )
    parser.add_argument(
        "--depopulate",
        action="store_true",
        default=False,
        help="Remove Elements spread/roles/perms for non-employees",
    )
    parser.add_argument(
        "--mail-warnings-to",
        action="store",
        help="Send warnings to (email address)",
    )
    parser.add_argument(
        "--config",
        default='sync_elements.cfg',
        help="Config file for elements communications (see sync_elements.py)",
    )
    argutils.add_commit_args(parser)

    args = parser.parse_args(inargs)
    elements_ws_client, ecfg = make_elements_client(args.config)

    pop = PopulateElements(elements_ws_client)

    if args.populate_roles:
        pop.populate_roles()
    if args.depopulate:
        pop.depopulate()
    if args.mail_warnings_to:
        mail_warnings(args.mail_warnings_to, debug=not args.commit)

    if args.commit:
        db.commit()
        logger.info("Committing changes")
    else:
        db.rollback()
        logger.info("DRYRUN: Rolling back changes")


if __name__ == '__main__':
    main()
