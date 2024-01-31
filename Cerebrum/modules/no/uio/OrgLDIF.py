# -*- coding: utf-8 -*-
#
# Copyright 2004-2022 University of Oslo, Norway
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

from __future__ import unicode_literals

import logging
import re
from collections import defaultdict
from itertools import product

from Cerebrum.modules.OrgLDIF import OrgLdifGroupMixin
from Cerebrum.modules.OrgLDIF import postal_escape_re
from Cerebrum.modules.feide.ldif_mixins import NorEduAuthnLevelMixin
from Cerebrum.modules.no.OrgLDIF import NorEduOrgLdifMixin
from Cerebrum.modules.no.OrgLDIF import NorEduSmsAuthnMixin
from Cerebrum.modules.no.OrgLDIF import OrgLdifCourseMixin
from Cerebrum.modules.no.OrgLDIF import OrgLdifEntitlementsMixin
from Cerebrum.modules.LDIFutils import (
    hex_escape_match,
    normalize_IA5String,
    verify_IA5String,
)
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.Utils import make_timer

logger = logging.getLogger(__name__)

# Replace these characters with spaces in OU RDNs.
ou_rdn2space_re = re.compile('[#\"+,;<>\\\\=\0\\s]+')


class _UioGroupMixin(OrgLdifGroupMixin, NorEduOrgLdifMixin):

    # TODO: We only inherit from norEduLDIFMixin here in order to get the
    #       objectClass entries in the same order as before (i.e. uioMembership
    #       after norEdu objectClass entries).
    #       This is done to reduce the change in the output file - the entries
    #       could be swapped around in order without consequence.

    # Attributes and values for OrgLdifGroupMixin
    person_memberof_attr = 'uioMemberOf'
    person_memberof_class = 'uioMembership'


class UioOrgLdif(NorEduSmsAuthnMixin,
                 NorEduAuthnLevelMixin,
                 OrgLdifCourseMixin,
                 _UioGroupMixin,
                 OrgLdifEntitlementsMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with UiO modifications."""

    def __init__(self, *args, **kwargs):
        super(UioOrgLdif, self).__init__(*args, **kwargs)

        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
        self.attr2syntax['uioVisiblePrivateMobile'] = \
            self.attr2syntax['mobile']
        self.attr2syntax['uioPrimaryMail'] = (None, verify_IA5String,
                                              normalize_IA5String),
        self.ou_quarantined = {}

    def init_ou_dump(self):
        super(UioOrgLdif, self).init_ou_dump()
        self.get_ou_quarantines()
        ou2parent = dict((c, p)
                         for p, ous in self.ou_tree.items()
                         for c in ous)

        class Id2ou(dict):
            # For missing id2ous, cache and return nearest parent or None
            def __missing__(self, key):
                val = self[key] = self[ou2parent.get(key)]
                return val

        self.ou_id2ou_uniq_id = Id2ou(self.ou_id2ou_uniq_id)
        self.ou_id2ou_uniq_id.setdefault(None, None)

    def test_omit_ou(self):
        return (not self.ou.has_spread(self.const.spread_ou_publishable)) or \
            self.ou_quarantined.get(self.ou.entity_id, False)

    def get_ou_quarantines(self):
        for row in self.ou.list_entity_quarantines(
                entity_types=self.const.entity_ou,
                quarantine_types=self.const.quarantine_ou_notvalid,
                only_active=True):
            self.ou_quarantined[int(row['entity_id'])] = True

    def init_attr2id2contacts(self):
        # Changes from superclass:
        # - Include 'mobile' as well
        # - OUs get their contact info from the address_source_system
        contact_sources = (
            (self.const.entity_ou,
             getattr(self.const,
                     self.config.org.parent.get('address_source_system'))),
            (self.const.entity_person,
             getattr(self.const,
                     self.config.org.parent.get('contact_source_system'))),
        )
        contact_types = (
            ('telephoneNumber', self.const.contact_phone),
            ('mobile', self.const.contact_mobile_phone),
            ('uioVisiblePrivateMobile',
             self.const.contact_private_mobile_visible),
            ('facsimileTelephoneNumber', self.const.contact_fax)
        )
        sourced_contact_types = list(product(contact_sources, contact_types))
        sourced_contact_types.append((
            (None, None),
            ('labeledURI', self.const.contact_url),
        ))

        contacts = [
            (attr, self.get_contacts(
                contact_type=contact_type,
                source_system=source_system,
                entity_type=entity_type,
                convert=self.attr2syntax[attr][0],
                verify=self.attr2syntax[attr][1],
                normalize=self.attr2syntax[attr][2]))
            for (entity_type, source_system), (attr, contact_type)
            in sourced_contact_types]

        self.id2labeledURI = contacts[-1][1]
        self.attr2id2contacts = [v for v in contacts if v[1]]

    def make_address(self, sep,
                     p_o_box, address_text, postal_number, city, country):
        # Changes from superclass:
        # Weird algorithm for when to use p_o_box.
        # Append "Blindern" to postbox.
        if country:
            country = self.const.Country(country).country
        if (p_o_box and int(postal_number or 0) / 100 == 3):
            address_text = "Pb. %s - Blindern" % p_o_box
        else:
            address_text = (address_text or "").strip()
        post_nr_city = None
        if city or (postal_number and country):
            post_nr_city = " ".join(filter(None, (postal_number,
                                                  (city or "").strip())))
        val = "\n".join(filter(None, (address_text, post_nr_city, country)))
        if sep == '$':
            val = postal_escape_re.sub(hex_escape_match, val)
        return val.replace("\n", sep)

    def init_person_titles(self):
        # Change from original: Search titles first by system_lookup_order,
        # then within each system let personal title override work title.
        timer = make_timer(logger, 'Fetching personal titles...')
        titles = defaultdict(dict)
        for name_type in (self.const.personal_title, self.const.work_title):
            for row in self.person.search_name_with_language(
                    entity_type=self.const.entity_person,
                    name_variant=name_type,
                    name_language=self.languages):
                titles[int(row['entity_id'])].setdefault(
                    int(row['name_language']), row['name'])
        self.person_titles = dict([(p_id, t.items())
                                   for p_id, t in titles.items()])
        timer("...personal titles done.")

    def init_account_mail(self, use_mail_module):
        u""" Cache account mail addresses.

        This method adds to the general to fill the primary email attribute
        This is done to prepare for changing the normal email attribute

        :param bool use_mail_module:
            If True, Cerebrum.modules.Email will be used to populate this
            cache; otherwise the `self.account_mail` dict will be None.
        """
        super(UioOrgLdif, self).init_account_mail(use_mail_module)
        if use_mail_module:
            timer = make_timer(
                logger,
                "Doing UiO specific changes to account e-mail addresses...")
            self.account_primary_mail = self.account_mail.copy()
            # We don't want to import this if mod_email isn't present.
            from Cerebrum.modules.Email import EmailTarget
            targets = EmailTarget(self.db).list_email_target_addresses
            mail = {}
            for row in targets(target_type=self.const.email_target_account,
                               domain='uio.no', uname_local=True):
                # Can only return username@uio.no so no need for any checks
                mail[int(row['target_entity_id'])] = "@".join(
                    (row['local_part'], row['domain']))
            self.account_mail.update(mail)
            timer("...UiO specfic account e-mail addresses done.")

    def make_uioPersonScopedAffiliation(self, p_id, pri_aff, pri_ou):
        # [primary|secondary]:<affiliation>@<status>/<stedkode>
        ret = []
        pri_aff_str, pri_status_str = pri_aff
        for aff, status, ou in self.affiliations[p_id]:
            # populate the caches
            if aff in self.aff_cache:
                aff_str = self.aff_cache[aff]
            else:
                aff_str = str(self.const.PersonAffiliation(aff))
                self.aff_cache[aff] = aff_str
            if status in self.status_cache:
                status_str = self.status_cache[status]
            else:
                status_str = str(self.const.PersonAffStatus(status).str)
                self.status_cache[status] = status_str
            p = 'secondary'
            if (aff_str == pri_aff_str and
                    status_str == pri_status_str and ou == pri_ou):
                p = 'primary'
            ou = self.ou_id2ou_uniq_id[ou]
            if ou:
                ret.append(''.join((p, ':', aff_str, '/', status_str, '@',
                                    ou)))
        return ret

    def make_person_entry(self, row, person_id):
        """ Extend with UiO functionality. """
        dn, entry, alias_info = super(UioOrgLdif,
                                      self).make_person_entry(row, person_id)
        account_id = int(row['account_id'])

        if not dn:
            return dn, entry, alias_info

        # Add person ID
        entry['uioPersonId'] = str(person_id)

        # Add scoped affiliations
        pri_edu_aff, pri_ou, pri_aff = self.make_edu_person_primary_aff(
            person_id)
        entry['uioPersonScopedAffiliation'] = \
            self.make_uioPersonScopedAffiliation(person_id, pri_aff, pri_ou)

        # uio attributes require uioPersonObject
        entry['objectClass'].append('uioPersonObject')

        if self.account_primary_mail:
            mail = self.account_primary_mail.get(account_id)
            if mail:
                entry['uioPrimaryMail'] = mail

        # Locked accounts needs to be a uioFeideHiddenPerson to be locked from
        # Feide non-password authentication schemes.  Note that autopassord is
        # exempt from this - the password is invalid, but the account should
        # still be allowed into Feide services through ID-porten auth.
        #
        # If/when the ID-porten pilot is over and other institutions need
        # this, the functionality should be moved into a separate, generic
        # mixin that allows us to customize:
        #   - Quarantine types to exempt from uioFeideHiddenPerson
        #   - Feide locking mechanism (or at the very least the name of the
        #     objectClass)
        feide_lock_exempt = set((
            int(self.const.quarantine_autopassord),
        ))
        relevant_quarantines = [
            q for q in self.acc_locked_quarantines.get(account_id) or ()
            if q not in feide_lock_exempt]
        if QuarantineHandler(self.db, relevant_quarantines).is_locked():
            entry['objectClass'].append('uioFeideHiddenPerson')
            logger.debug('uioFeideHiddenPerson for account_id=%r',
                         account_id)

        return dn, entry, alias_info

    def _calculate_edu_ous(self, p_ou, s_ous):
        return s_ous

    def init_person_selections(self, *args, **kwargs):
        """ Extend with UiO settings for person selections.

        This is especially for `no.uio.OrgLDIF.is_person_visible()`, as UiO has
        some special needs in how to interpret visibility of persons due to
        affiliations for reservation and consent, which behaves differently in
        SAPUiO and FS.

        """
        super(UioOrgLdif, self).init_person_selections(*args, **kwargs)
        # Set what affiliations that should be checked for visibility from SAP
        # and FS. The default is to set the person to NOT visible, which
        # happens for all persons that doesn't have _any_ of the affiliations
        # defined here.
        ansatt = int(self.const.affiliation_ansatt)
        tilkn_aff = int(self.const.affiliation_tilknyttet)
        # TODO: Temporarily comment out affiliated people, see CRB-3696
        # TODO: Except TILKNYTTET/emeritus, see CRB-3763
        self.visible_sap_affs = ()
        self.visible_sap_statuses = (
            (ansatt, int(self.const.affiliation_status_ansatt_tekadm)),
            (ansatt, int(self.const.affiliation_status_ansatt_vitenskapelig)),
            (ansatt, int(self.const.affiliation_status_ansatt_perm)),
            # (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_stip)),
            # (tilkn_aff, int(self.const.affiliation_tilknyttet_frida_reg)),
            # (tilkn_aff, int(self.const.affiliation_tilknyttet_innkjoper)),
            # (tilkn_aff, int(self.const.
            #                 affiliation_tilknyttet_assosiert_person)),
            # (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_forsker)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_emeritus)),
            # (tilkn_aff, int(self.const.
            #                 affiliation_tilknyttet_gjesteforsker)),
            # (tilkn_aff, int(self.const.affiliation_tilknyttet_bilag)),
            # (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_partner)),
        )
        student = int(self.const.affiliation_student)
        self.fs_aff_statuses = (
            (student, int(self.const.affiliation_status_student_aktiv)),
            (student, int(self.const.affiliation_status_student_drgrad)),
            (student, int(self.const.affiliation_status_student_emnestud)))
        self.sap_res = self.init_person_group("DFO-elektroniske-reservasjoner")
        self.manuelt_samtykke = self.init_person_group("manuelt-aktivt-samtykke")
        self.fs_samtykke = self.init_person_group("FS-aktivt-samtykke")

    def is_person_visible(self, person_id):
        """ Override with UiO specific visibility.

        At UiO, visibility is controlled differently depending on what source
        system the person is from. SAPUiO has reservations, while FS has active
        consents. Since we don't fetch source systems per affiliation from
        Cerebrum in `OrgLDIF`, we only guess.

        The reason for this override, is to support priority. SAP has priority
        over FS, which can't be implemented through the configuration as of
        today.

        Note that the settings in `cereconf.LDAP_PERSON['visible_selector']` is
        ignored by this override. The list of affiliations are hardcoded in the
        method `init_person_selections`.

        """
        # TODO: this could be changed to check the trait 'reserve_public'
        # later, so we don't have to check group memberships.
        #
        # The trait behaves in the following manner:
        # Every person should be 'invisible', except if:
        #  * The person has a trait of the type 'reserve_public', and
        #  * The trait's numval is set to 0
        # This means that a missing trait should be considered as a
        # reservation.

        if person_id in self.manuelt_samtykke:
            return True

        p_affs = self.affiliations[person_id]
        # If there is an affiliation from SAP then consider
        # reservations/permissions from SAP only.
        for (aff, status, ou) in p_affs:
            if aff in self.visible_sap_affs:
                return person_id not in self.sap_res
            if (aff, status) in self.visible_sap_statuses:
                return person_id not in self.sap_res
        # Otherwise, if there is an affiliaton STUDENT/<aktiv, emnestud or
        # drgrad>,
        # check for permission from FS to make the person visible.
        for (aff, status, ou) in p_affs:
            if (aff, status) in self.fs_aff_statuses:
                return person_id in self.fs_samtykke
        # Otherwise hide the person.
        return False
