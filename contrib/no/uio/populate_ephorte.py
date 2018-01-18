#!/usr/bin/env python
# coding: utf-8
u""" This script maintains ePhorte spreads and automatic roles for employees.

It can also send an email report if Cerebrum and ePhorte disagrees about which
organizational units should be active.
"""
import argparse
import itertools
import datetime

import cereconf

from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.no.uio.Ephorte import EphorteRole
from Cerebrum.modules.no.uio.Ephorte import EphortePermission
from Cerebrum.modules.no.uio.EphorteWS import make_ephorte_client

#
# Settings
#
# Ephorte admin group setting
EPHORTE_ADMINS = getattr(cereconf, 'EPHORTE_ADMINS')

# Specific SKOs
EPHORTE_UIO_ROOT_SKO = getattr(cereconf, 'EPHORTE_UIO_ROOT_SKO')

# SKO lists
EPHORTE_FSAT_SKO = getattr(cereconf, 'EPHORTE_FSAT_SKO')
EPHORTE_NIKK_SKO = getattr(cereconf, 'EPHORTE_NIKK_SKO')
EPHORTE_SO_SKO = getattr(cereconf, 'EPHORTE_SO_SKO')
EPHORTE_KDTO_SKO = getattr(cereconf, 'EPHORTE_KDTO_SKO')

# Day filter (when to allow email warnings), and email template
EPHORTE_MAIL_TIME = getattr(cereconf, 'EPHORTE_MAIL_TIME', [])
EPHORTE_MAIL_OU_MISMATCH = getattr(cereconf, 'EPHORTE_MAIL_OU_MISMATCH')

#
# Globals
#
logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
db.cl_init(change_program="populate_ephorte")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
group = Factory.get('Group')(db)
ephorte_role = EphorteRole(db)
ephorte_perm = EphortePermission(db)
ou = Factory.get("OU")(db)
ou_mismatch_warnings = {'sap': [], 'ephorte': []}


class SimpleRole(object):
    """ Ephorte role. """

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
    role['role_type'] = co.EphorteRole(role.get('role_type'))
    return ("role_type={role_type!s}, adm_enhet={adm_enhet!s},"
            " arkivdel={arkivdel!s}, journalenhet={journalenhet!s},"
            " person_id={person_id!s}"
            " standard_role={standard_role!s} auto_role={auto_role!s}"
            " start_date={start_date!s}, end_date={end_date!s}").format(**role)


def format_permission(perm):
    perm['perm_type'] = co.EphortePermission(perm.get('perm_type'))
    return ("perm_type={perm_type!s}, adm_enhet={adm_enhet!s},"
            " requestee_id={requestee_id!s}, person_id={person_id!s},"
            " start_date={start_date!s}, end_date={end_date!s}").format(**perm)


class PopulateEphorte(object):
    """ Ephorte sync client. """

    def __init__(self, ewsclient):
        "Pre-fetch information about OUs in ePhorte and Cerebrum."

        # Special sko, ignore:
        ephorte_sko_ignore = ['null', '[Ufordelt]']
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
            # Specal case, SO
            if sko in EPHORTE_SO_SKO:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_so),
                    int(co.ephorte_journenhet_so))
            # Special case, NIKK
            elif sko in EPHORTE_NIKK_SKO:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_nikk),
                    int(co.ephorte_journenhet_nikk))
            # Special case, FSAT
            elif sko in EPHORTE_FSAT_SKO:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_fsat),
                    int(co.ephorte_journenhet_fsat))
            # Special case, KDTO
            elif sko in EPHORTE_KDTO_SKO:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_kdto),
                    int(co.ephorte_journenhet_kdto))
            # Default case
            else:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_uio),
                    int(co.ephorte_journenhet_uio))
        logger.info("Found info about %d sko in cerebrum" % len(self.ouid2sko))

        logger.info("Finding OUs with spread ePhorte_ou")
        self.sap_ephorte_ouid2name = {}
        ou_id2name = dict((r["entity_id"], r["name"])
                          for r in ou.search_name_with_language(
                          entity_type=co.entity_ou,
                          name_language=co.language_nb,
                          name_variant=co.ou_name_display))

        # due to a logical error in ephorte-sync we have to allow
        # non-existing OU's to be assigned roles. the background for
        # this change is available in ePhorte case 2011/14072
        # registrered 10th of november 2011 by Astrid Optun and
        # updated by USIT in january 2012
        #
        # for row in ou.search(spread=co.spread_ephorte_ou):
        for row in ou.search():
            self.sap_ephorte_ouid2name[int(row['ou_id'])] = ou_id2name.get(
                row["ou_id"], "")
        logger.info("Found %d ous with spread ePhorte_ou" %
                    len(self.sap_ephorte_ouid2name.keys()))
        #
        # GRUSOMT HACK
        #
        # Ideelt burde vi syncet OU'er til ePhorte, men det gjør vi altså ikke.
        # Det gamle grusomme hacket med å dumpe OU-tabell fra ePhorte og lese
        # inn denne, er erstattet med å lese inn OU'er fra ny web service.
        # Vi får ikke lenger start og sluttdato, så det blir slutt på å
        # rapportere steder som ikke er aktive.
        logger.info(
            "Fetching OU info from ePhorte WS %s reading ephorte %s/%s",
            ewsclient.wsdl,
            ewsclient.customer_id,
            ewsclient.database)
        ephorte_ous = ewsclient.get_all_org_units()

        self.app_ephorte_ouid2name = {}
        for eou in ephorte_ous:
            ephorte_sko = eou['OrgId']
            ephorte_name = eou['Name']
            ou_id = self.sko2ou_id.get(ephorte_sko)
            if ou_id is None:
                if ephorte_sko not in ephorte_sko_ignore:
                    logger.warn("Unknown ePhorte sko: '%s'" % ephorte_sko)
                continue
            self.app_ephorte_ouid2name[ou_id] = ephorte_name
        logger.info("Found %d ephorte sko from app." %
                    len(self.app_ephorte_ouid2name.keys()))

        for ou_id in (set(self.app_ephorte_ouid2name.keys()) -
                      set(self.sap_ephorte_ouid2name.keys())):
            # Add ou to list that is sent in warn mail
            ou_mismatch_warnings['ephorte'].append(
                (self.ouid2sko[ou_id], self.app_ephorte_ouid2name[ou_id]))
            logger.info(
                "OU (%6s: %s) in ePhorte, but has no ePhorte spread" % (
                    self.ouid2sko[ou_id], self.app_ephorte_ouid2name[ou_id]))
        for ou_id in (set(self.sap_ephorte_ouid2name.keys()) -
                      set(self.app_ephorte_ouid2name.keys())):
            # Add ou to list that is sent in warn mail
            ou_mismatch_warnings['sap'].append(
                (self.ouid2sko[ou_id], self.sap_ephorte_ouid2name[ou_id]))
            logger.info(
                "OU (%6s, %s) has ePhorte spread, but is not in ePhorte" % (
                    self.ouid2sko[ou_id], self.sap_ephorte_ouid2name[ou_id]))
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
            int(co.ephorte_role_sy),
            self.sko2ou_id[EPHORTE_UIO_ROOT_SKO],
            int(co.ephorte_arkivdel_sak_uio),
            int(co.ephorte_journenhet_uio),
            standard_role=False,
            auto_role=False)

    def map_ou_to_role(self, ou_id):
        arkiv, journal = self.ouid_2roleinfo[ou_id]
        return SimpleRole(int(co.ephorte_role_sb), ou_id, arkiv, journal)

    def find_person_info(self, person_id):
        ret = {'person_id': person_id}
        try:
            pe.clear()
            pe.find(person_id)
            tmp_id = pe.get_external_id(source_system=co.system_sap,
                                        id_type=co.externalid_sap_ansattnr)
            ret['sap_ansattnr'] = tmp_id[0]['external_id']
            ret['first_name'] = pe.get_name(source_system=co.system_sap,
                                            variant=co.name_first)
            ret['last_name'] = pe.get_name(source_system=co.system_sap,
                                           variant=co.name_last)
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

    @memoize
    def map_person_to_ou(self):
        logger.info("Mapping person affiliations to ePhorte OU")
        # person -> {ou_id:1, ...}
        person_to_ou = {}
        non_ephorte_ous = []

        # Find where an employee has an ANSATT affiliation and check
        # if that ou is an ePhorte ou. If not try to map to nearest
        # ePhorte OU as specified in ephorte-sync-spec.rst
        for row in itertools.chain(
                pe.list_affiliations(
                    source_system=co.system_sap,
                    affiliation=co.affiliation_ansatt),
                pe.list_affiliations(
                    source_system=co.system_sap,
                    affiliation=co.affiliation_tilknyttet,
                    status=co.affiliation_tilknyttet_ekst_forsker)):
            ou_id = int(row['ou_id'])
            if ou_id is not None and ou_id not in self.app_ephorte_ouid2name:
                if ou_id not in non_ephorte_ous:
                    non_ephorte_ous.append(ou_id)
                    logger.debug(
                        "OU %s is not an ePhorte OU. Try parent: %s" % (
                            self.ouid2sko[ou_id],
                            self.ouid2sko.get(self.ou_id2parent.get(ou_id))))
                ou_id = self.ou_id2parent.get(ou_id)

            # No ePhorte OU found.
            if ou_id is None or ou_id not in self.app_ephorte_ouid2name:
                sko = self.ouid2sko[int(row['ou_id'])]
                tmp_msg = "Failed mapping '%s' to known ePhorte OU. " % sko
                if self.find_person_info(row['person_id'])['uname']:
                    tmp_msg += "Skipping affiliation %s@%s for user %s" % (
                        co.affiliation_ansatt, sko,
                        self.find_person_info(row['person_id'])['uname'])
                else:
                    tmp_msg += "Skipping affiliation %s@%s for person %s" % (
                        co.affiliation_ansatt, sko, row['person_id'])
                # ephorte support must deal with this and they should be
                # informed
                logger.warning(tmp_msg)
                continue

            person_to_ou.setdefault(int(row['person_id']), {})[ou_id] = 1
        return person_to_ou

    def map_person_to_roles(self):
        logger.info("Mapping persons to existing ePhorte roles")
        person_to_roles = {}
        for row in ephorte_role.list_roles():
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
        has_ephorte_spread = set([int(row["entity_id"]) for row in
                                  pe.list_all_with_spread(
                                      co.spread_ephorte_person)])

        # Ideally, the group should have persons as members, but bofh
        # doesn't have much support for that, so we map user->owner_id
        # instead
        superusers = []
        group.find_by_name(EPHORTE_ADMINS)
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
            existing_roles = person_to_roles.get(person_id, [])
            # Add saksbehandler role for each ephorte ou where an
            # employee has an affiliation
            for t in ous:
                auto_roles.append(self.map_ou_to_role(t))
            if person_id in superusers:
                auto_roles.append(self._superuser_role)
            # All employees shall have ephorte spread
            if person_id not in has_ephorte_spread:
                pe.clear()
                pe.find(person_id)
                pe.add_spread(co.spread_ephorte_person)

            for ar in auto_roles:
                # Check if role should be added
                if ar in existing_roles:
                    existing_roles.remove(ar)
                else:
                    logger.info("Adding role (pid=%i): %s" % (person_id, ar))
                    ephorte_role.add_role(person_id, ar.role_type,
                                          ar.adm_enhet, ar.arkivdel,
                                          ar.journalenhet)
            for er in existing_roles:
                # Only saksbehandler role that has been given
                # automatically can be removed. Any other roles have
                # been given in bofh and should not be touched.
                if er.auto_role and er.role_type == int(co.ephorte_role_sb):
                    logger.info("Removing role (pid=%i): %s" % (person_id, er))
                    ephorte_role.remove_role(person_id, er.role_type,
                                             er.adm_enhet, er.arkivdel,
                                             er.journalenhet)

                if er.standard_role == 'T':
                    std_role = True

            if not std_role:
                for er in existing_roles:
                    if er.role_type == int(co.ephorte_role_sb):
                        ephorte_role.set_standard_role_val(
                            person_id,
                            co.ephorte_role_sb,
                            er.adm_enhet,
                            int(co.EphorteArkivdel(er.arkivdel)),
                            int(co.EphorteJournalenhet(er.journalenhet)),
                            'T')
                        logger.info(
                            "Added standard role for %d, '%s, %d, %s, %s'",
                            person_id, str(co.ephorte_role_sb), er.adm_enhet,
                            str(co.EphorteArkivdel(er.arkivdel)),
                            str(co.EphorteJournalenhet(er.journalenhet)))
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
        logger.info('{} persons should have ePhorte spread'.format(
            len(should_have_spread)))
        logger.info('{} persons have ePhorte spread'.format(
            len(has_spread)))
        logger.info('{} persons should lose ePhorte spread'.format(
            len(victims)))
        for person_id in victims:
            logger.info('Removing ePhorte data for person_id:{}'.format(
                person_id))
            pe.clear()
            pe.find(person_id)
            for perm in ephorte_perm.list_permission(person_id=person_id):
                logger.info('Removing permission: {}'.format(
                    format_permission(dict(perm))))
                ephorte_perm.remove_permission(person_id=person_id,
                                               perm_type=perm['perm_type'],
                                               sko=perm['adm_enhet'])
            for role in ephorte_role.list_roles(person_id=person_id):
                logger.info('Removing role: {}'.format(
                    format_role(dict(role))))
                ephorte_role.remove_role(person_id=person_id,
                                         role=role['role_type'],
                                         sko=role['adm_enhet'],
                                         arkivdel=role['arkivdel'],
                                         journalenhet=role['journalenhet'])
            pe.delete_spread(co.spread_ephorte_person)
        logger.info('Done depopulating')


def mail_warnings(mailto, debug=False):
    """
    If warnings of certain types occur, send those as mail to address
    specified in mailto. If cereconf.EPHORTE_MAIL_TIME is specified,
    just send if time when script is run matches with specified time.
    """
    # Check if we should send mail today
    if datetime.datetime.now().strftime('%A') not in EPHORTE_MAIL_TIME:
        logger.info('Not mailing warnings today')
        return
    if ou_mismatch_warnings['ephorte'] or ou_mismatch_warnings['sap']:
        sap_warnings = '\n'.join([
            "%6s  %s" % x for x in ou_mismatch_warnings['sap']])
        ephorte_warnings = '\n'.join([
            "%6s  %s" % x for x in ou_mismatch_warnings['ephorte']])
        substitute = {'SAP_WARNINGS': sap_warnings,
                      'EPHORTE_WARNINGS': ephorte_warnings}
        send_mail(mailto, EPHORTE_MAIL_OU_MISMATCH, substitute, debug=debug)


def send_mail(mailto, mail_template, substitute, debug=False):
    ret = Utils.mail_template(mailto, mail_template, substitute=substitute,
                              debug=debug)
    if ret:
        logger.info("Not sending mail:\n%s" % ret)
    else:
        logger.info("Sending mail to: %s" % mailto)


def _make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-r", "--populate-roles",
        action="store_true",
        default=False,
        help=u"Populate auto roles")
    parser.add_argument(
        "--depopulate",
        action="store_true",
        default=False,
        help=u"Remove ePhorte spread/roles/perms for non-employees")
    parser.add_argument(
        "--mail-warnings-to",
        action="store",
        help=u"Send warnings to (email address)")
    parser.add_argument(
        "--commit",
        action="store_true",
        help=u"Commit to database")
    parser.add_argument(
        "--config",
        default='sync_ephorte.cfg',
        help=u"Config file for ephorte communications (see sync_ephorte.py)")
    return parser


def main(args=None):
    args = _make_parser().parse_args(args)
    ephorte_ws_client, ecfg = make_ephorte_client(args.config)
    pop = PopulateEphorte(ephorte_ws_client)

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
