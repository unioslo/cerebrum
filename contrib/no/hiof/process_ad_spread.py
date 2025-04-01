#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2007-2025 University of Oslo, Norway
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
Dette scriptet setter AD-attributter for brukere som får AD-spread.

Dette scriptet går gjennom alle brukere med gitt AD-spread. For hver bruker
skal det:

1. Beregnes AD-attributter
    Attributtene bestemmes fra regler i
    :mod:`Cerebrum.modules.no.hiof.ADMappingRules`.  Det finnes regler for:

    - adm (spread `account@ad_adm`)
    - fag (spread `account@ad_fag`)
    - student (spread `account@ad_stud`) - ikke i bruk siden 2015

    Modulen har regler for attributtene `Homedir`, `ProfilePath`, og `DN`
    (ou-plassering).

2. Settes AD-attributter hvis disse mangler
    Hvis ingen attributter er satt, blir disse oppdatert ihht. mapping-reglener
    i punkt 1.

3. Varsles hvis AD-attributter er ute av sync
    Hvis attributter er ute av sync, vil et eget script* varsle HiØ, slik at de
    kan se over, og eventuelt fjerne eksisterende attributter, slik at disse kan
    oppdateres neste gang dette scriptet kjører.

    * Merk: Det finnes ikke lenger et slikt script som varsler HiØ.

Usage: process_AD.py [options]
-a ad_spread : spread_str for spread (domene)
-o fname : utfil
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import six

import cereconf
import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.hiof import ADMappingRules
from Cerebrum.utils import argutils

logger = logging.getLogger(__name__)


def get_account_by_id(db, account_id):
    ac = Factory.get("Account")(db)
    ac.find(int(account_id))
    return ac


def get_ou_by_id(db, ou_id):
    ou = Factory.get("OU")(db)
    ou.find(int(ou_id))
    return ou


def get_stedkode(ou):
    return "%02d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling)


class _CalcError(Exception):
    """ A new set of attributes can't be calculated. """
    pass


def compare_attrs(old_attrs, new_attrs):
    """
    Compare new attributes to old attributes.

    :type old_attrs: dict[str, str]
    :type new_attrs: dict[str, str]

    :returns dict[str, tuple[any, str]]:
        A mapping of {<attr-name>: (<old-value>, <new-value>)} for any
        attr-name that has changed in *new_attrs*.
    """
    values = ((k, old_attrs.get(k), new_attrs[k]) for k in new_attrs)
    return {
        key: (old, new)
        for key, old, new in values
        if not (old and new and new.strip().lower() == old.strip().lower())
    }


class Job(object):
    """
    Class for processing user's AD attributes
    """

    def __init__(self, db, spread):
        """
        Init ad_attr info by setting mapping rules for a AD domain,
        given by spread.

        @param spread_str: account ad spread
        @type  spread_str: str
        """
        self.db = db
        self.spread = spread

        # User to attribute mapping, for users with diff
        self.user_diff_attrs = {}

        co = Factory.get('Constants')(db)
        if self.spread == co.spread_ad_account_fag:
            self.rules = ADMappingRules.Fag()
        elif self.spread == co.spread_ad_account_adm:
            self.rules = ADMappingRules.Adm()
        else:
            # Should we remove ADMappingRules.Student from ADMappingRules?
            raise NotImplementedError("no rules for spread: "
                                      + repr(self.spread))

    @property
    def candidates(self):
        """ iterator over account ids with the with the given ad spread. """
        ac = Factory.get("Account")(self.db)
        for row in ac.list_account_home(home_spread=self.spread,
                                        account_spread=self.spread,
                                        filter_expired=True,
                                        include_nohome=True):
            yield get_account_by_id(self.db, int(row['account_id']))

    def process_ad_attrs(self):
        """
        Check account's AD attributes in AD domain given by spread.
        Perform the following tasks

        1. Calculate new attribute values based on rules defined in
           ADMappingRules.
        2. If a user has old values, compare these with the new ones.
           If there are differences send a report email.
        3. If not old values exists, populate the new ones.
        """
        logger.debug("Processing accounts with spread=%s", repr(self.spread))
        for ac in self.candidates:
            account_repr = "%s (%d)" % (ac.account_name, ac.entity_id)
            # Calculate new ad attr values
            try:
                new_attrs = self.calc_ad_attrs(ac)
            except _CalcError as v:
                logger.warning("Unable to calculate attrs for %s: %s",
                               account_repr, v)
                continue
            except ADMappingRules.MappingError as v:
                logger.warning("Unable to find attrs for %s: %s",
                               account_repr, v)
                continue

            # Check if user already have ad attrs for this domain (spread)
            old_attrs = ac.get_ad_attrs_by_spread(self.spread)
            if old_attrs:
                diff_attrs = compare_attrs(old_attrs, new_attrs)
                if diff_attrs:
                    logger.debug("Review needed for account %s, attrs: %s",
                                 account_repr, repr(diff_attrs))
                continue

            self.populate_ad_attrs(ac, new_attrs)
            logger.info(
                "Set initial attrs for account %s: %s",
                account_repr, repr(new_attrs))

    def calc_ad_attrs(self, account):
        """
        Calculate and return AD attributes for an account.

        :returns dict:
             An attribtue mapping, format: ``{attr-type: attr-value, ...}``
        """
        # Non-personal accounts have their own rules
        if int(account.owner_type) == int(account.const.entity_group):
            return self.calc_nonpersonal_ad_attrs(account)
        # Henter sted fra affiliation med høyest prioritet uavhengig
        # av dens type.
        affs = account.get_account_types()
        if not affs:
            raise Job.CalcError("no account types (affs)")
        sko = get_stedkode(get_ou_by_id(self.db, int(affs[0]['ou_id'])))
        cn = self.rules.getDN(account.account_name, sko)
        return {
            'ad_account_ou': cn[cn.find(",") + 1:],
            'ad_profile_path': self.rules.getProfilePath(account.account_name,
                                                         sko),
            'ad_homedir': self.rules.getHome(account.account_name, sko),
        }

    def calc_nonpersonal_ad_attrs(self, account):
        """
        Calculate and return AD attributes for an non personal
        account.

        @rtype: dict
        @return: {attr_type : attr_value, ...}
        """
        return {
            'ad_account_ou': cereconf.AD_DEFAULT_OU,
            'ad_profile_path': self.rules.getProfilePath(account.account_name),
            'ad_homedir': self.rules.getHome(account.account_name),
        }

    def populate_ad_attrs(self, account, new_attrs):
        """
        populate spread->attr_value mapping as an entity_trait in
        Cerebrum.

        @param new_attrs: attr type -> attr value mapping
        @type  new_attrs: dict
        """
        for attr_type, attr_val in six.iteritems(new_attrs):
            # Before populating spread we must check if there are old
            # values. Account might have attributes for more than one
            # spread. Those must not be deleted
            existing_attrs = account.get_ad_attrs_by_type(attr_type)
            # Update spread -> ad val mapping with new value
            existing_attrs[int(self.spread)] = six.text_type(attr_val)
            account.populate_ad_attrs(attr_type, existing_attrs)
            account.write_db()


def process_ad_attrs(db, spread):
    j = Job(db, spread)
    j.process_ad_attrs()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Calculate AD attributes from spread rules",
    )
    ad_spread_arg = parser.add_argument(
        "-a", "--ad-spread",
        required=True,
        help="Calculate attributes for spread %(metavar)s",
        metavar="<spread>",
    )
    # NOTE: --commit is the default (for backwards compatibility)
    argutils.add_commit_args(parser, default=True)
    Cerebrum.logutils.options.install_subparser(parser)

    args = parser.parse_args(argv)

    spread_str = args.ad_spread
    cron_log_preset = "process_ad_{}".format(
        six.text_type(spread_str).split('@ad_')[1]
    )
    default_log_preset = cron_log_preset if args.commit else "console"
    Cerebrum.logutils.autoconf(default_log_preset, args)

    logger.info("Start %s", parser.prog)

    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)
    with argutils.ParserContext(parser, ad_spread_arg):
        # Should we do this *before* setting up logger (i.e. validate the
        # default cron_log_preset input value?)
        spread = co.get_constant(co.Spread, args.ad_spread)

    db.cl_init(change_program="process_ad")

    process_ad_attrs(db, spread)

    # Commit changes?
    if args.commit:
        logger.info("Committing changes")
        db.commit()
    else:
        logger.info("Rolling back changes (dryrun)")
        db.rollback()

    logger.info("Done %s", parser.prog)


if __name__ == '__main__':
    main()
