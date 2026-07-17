#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2004-2018 University of Oslo, Norway
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
Build groups from FS data structures.


Hierarchy:

::

    FsSupergroup
        FsEvuSubtree
            FsEvuCourse
                FsEvuCourseUsers
        FsProgramSubtree
            FsProgram
                FsProgramRole
                    FsProgramRoleUsers
                FsProgramYear
                    FsProgramYearUsers
        FsUnitSubtree
            FsUnitTerm
                FsUnitSubject
                    FsUnitUsers


"""

from __future__ import generators, unicode_literals

import datetime
import getopt
import os
import sys

import six

import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.date import parse_date
from Cerebrum.modules import Email
from Cerebrum.modules.no import access_FS
from Cerebrum.modules.fs.fs_group import (FsGroupCategorizer,
                                          set_default_expire_date,
                                          get_grace,
                                          should_postpone_expire_date)

# Define all global variables, to avoid pychecker warnings.
db = logger = fnr2account_id = const = fs_group_categorizer = None


def safe_join(elements, sep=' '):
    """As string.join(), but ensures `sep` isn't part of any element."""
    for i in range(len(elements)):
        if elements[i].find(sep) != -1:
            raise ValueError(
                "Join separator %r found in element #%d (%r)" %
                (sep, i, elements[i]))
    return sep.join(elements)


def get_account(name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(name)
    return ac


def get_group(id):
    gr = Factory.get('Group')(db)
    if isinstance(id, six.string_types):
        gr.find_by_name(id)
    else:
        gr.find(id)
    return gr


def destroy_group(group_id, max_recurse):
    if max_recurse is None:
        logger.fatal("destroy_group(%r) vil ikke slette permanent gruppe.",
                     group_id)
        sys.exit(1)
    gr = get_group(group_id)
    logger.debug("destroy_group(%s/%d, %d) [After get_group]",
                 gr.group_name, gr.entity_id, max_recurse)
    if max_recurse < 0:
        logger.fatal("destroy_group(%s): Recursion too deep", gr.group_name)
        sys.exit(3)

    if gr.get_extensions():
        logger.fatal("destroy_group(%s): Group is %r",
                     gr.group_name, gr.get_extensions())
        sys.exit(4)

    # If this group is a member of other groups, remove those
    # memberships.
    for r in gr.search(member_id=gr.entity_id, indirect_members=False):
        parent = get_group(r['group_id'])
        logger.debug("removing %s from group %s",
                     gr.group_name, parent.group_name)
        parent.remove_member(gr.entity_id)

    # If a e-mail target is of type multi and has this group as its
    # destination, delete the e-mail target and any associated
    # addresses.  There can only be one target per group.
    et = Email.EmailTarget(db)
    try:
        et.find_by_email_target_attrs(target_type=const.email_target_multi,
                                      target_entity_id=gr.entity_id)
    except Errors.NotFoundError:
        pass
    else:
        logger.debug("found email target referencing %s", gr.group_name)
        ea = Email.EmailAddress(db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            logger.debug("deleting address %s@%s",
                         r['local_part'], r['domain'])
            ea.delete()
        et.delete()
    # Fetch group's members (*before* the group is deleted)
    members = [int(x["member_id"]) for x in
               gr.search_members(group_id=gr.entity_id,
                                 member_type=const.entity_group)]
    logger.debug("destroy_group() subgroups: %r", members)

    # Remove any spreads the group has
    for row in gr.get_spread():
        gr.delete_spread(row['spread'])
    # Delete the parent group (which implicitly removes all membership
    # entries representing direct members of the parent group)
    gr.delete()
    # Destroy any subgroups (down to level max_recurse).  This needs
    # to be done after the parent group has been deleted, in order for
    # the subgroups not to be members of the parent anymore.
    for subg_id in members:
        destroy_group(subg_id, max_recurse - 1)


class _GroupTree(object):
    """ Abstract FS group tree. """

    # Dersom destroy_group() kalles med max_recurse == None, aborterer
    # programmet.
    max_recurse = None

    # De fleste automatisk opprettede gruppene skal ikke ha noen
    # spread.
    spreads = ()

    def __init__(self):
        self.subnodes = {}
        self.users = {}

    def name_prefix(self):
        prefix = ()
        parent = getattr(self, 'parent', None)
        if parent is not None:
            prefix += parent.name_prefix()
        prefix += getattr(self, '_prefix', ())
        return prefix

    def name(self):
        name_elements = self.name_prefix()
        name_elements += getattr(self, '_name', ())
        return safe_join(name_elements, ':').lower()

    def description(self):
        pass

    def list_matches(self, gtype, data, category):
        if self.users:
            raise RuntimeError(
                "list_matches() not overriden for user-containing group.")
        for subg in self.subnodes.values():
            for match in subg.list_matches(gtype, data, category):
                yield match

    def list_matches_1(self, *args, **kws):
        ret = [x for x in self.list_matches(*args, **kws)]
        if len(ret) == 1:
            return ret
        elif len(ret) == 0:
            # I praksis viser det seg at mange "aktive" studenter har
            # registreringer på utgåtte studieprogrammer o.l., slik at
            # list_matches returnerer 0 grupper.  Den situasjonen er
            # det lite dette scriptet kan gjøre med, og det bør derfor
            # ikke føre til noen ERROR-loggmelding.
            logger.debug("Ikke gyldig kull eller studieprog: args=%r", args)
            return ()
        logger.warn("Matchet for mange: self=%r, args=%r, kws=%r, ret=%r",
                    self, args, kws, ret)
        return ()

    def sync(self):
        logger.debug("Start: _GroupTree.sync(), name = %s", self.name())
        db_group = self.create_or_get_group()
        if db_group.is_expired():
            return None

        sub_ids = {}
        if self.users:
            # Gruppa inneholder minst en person, og skal dermed
            # populeres med *kun* primærbrukermedlemmer.  Bygg opp
            # oversikt over primærkonto-id'er i 'sub_ids'.
            for fnr in self.users.keys():
                a_ids = fnr2account_id.get(fnr)
                if a_ids is not None:
                    primary_account_id = int(a_ids[0])
                    sub_ids[primary_account_id] = const.entity_account
                else:
                    logger.warn("Fant ingen bruker for fnr=%r (XML = %r)",
                                fnr, self.users[fnr])
        else:
            # Gruppa har ikke noen personmedlemmer, og skal dermed
            # populeres med *kun* evt. subgruppemedlemmer.  Vi sørger
            # for at alle subgrupper synkroniseres først (rekursivt),
            # og samler samtidig inn entity_id'ene deres i 'sub_ids'.
            for subg in self.subnodes:
                sub_group_id = subg.sync()
                if sub_group_id:
                    sub_ids[int(sub_group_id)] = const.entity_group
        # I 'sub_ids' har vi nå en oversikt over hvilke entity_id'er
        # som skal bli gruppens medlemmer.  Foreta nødvendige inn- og
        # utmeldinger.
        for row in db_group.search_members(group_id=db_group.entity_id):
            member_id = int(row["member_id"])
            member_type = int(row["member_type"])
            if member_id in sub_ids:
                del sub_ids[member_id]
            else:
                db_group.remove_member(member_id)
                if member_type == const.entity_group:
                    destroy_group(member_id, self.max_recurse)

        for member_id in sub_ids.keys():
            db_group.add_member(member_id)
        # Synkroniser gruppens spreads med lista angitt i
        # self.spreads.
        want_spreads = {}
        for s in self.spreads:
            want_spreads[int(s)] = 1
        for row in db_group.get_spread():
            spread = int(row['spread'])
            if spread in want_spreads:
                del want_spreads[spread]
            else:
                db_group.delete_spread(spread)
        for new_spread in want_spreads.keys():
            db_group.add_spread(new_spread)
        logger.debug("Ferdig: _GroupTree.sync(), name = %s", self.name())
        return db_group.entity_id

    def create_or_get_group(self):
        """Create a group with group_name self.name() if it does not exist

        If a group is created, set a default expire date on it. If a group
        already exists, check whether its expire date should be postponed.

        :returns: a (newly created) group
        """
        today = datetime.date.today()
        try:
            gr = get_group(self.name())
        except Errors.NotFoundError:
            gr = Factory.get('Group')(db)
            gr.populate(
                creator_id=self.group_creator(),
                visibility=const.group_visibility_internal,
                name=self.name(),
                description=self.description(),
                group_type=const.group_type_lms,
            )
            set_default_expire_date(fs_group_categorizer,
                                    gr,
                                    self.name(),
                                    today=today)
            gr.write_db()
            logger.debug("Created group %s", self.name())
        else:
            grace = get_grace(fs_group_categorizer, self.name())
            if should_postpone_expire_date(gr, grace):
                gr.expire_date = (today +
                                  datetime.timedelta(days=grace['high_limit']))
                logger.debug('Postponing expire_date of group %s to %s',
                             self.name(),
                             gr.expire_date)
                gr.write_db()
        return gr

    def group_creator(self):
        acc = get_account(cereconf.INITIAL_ACCOUNTNAME)
        return acc.entity_id

    def __eq__(self, other):
        if type(other) is type(self):
            return (self.name() == other.name())
        return False

    def __ne__(self, other):
        return (not self.__eq__(other))

    def __hash__(self):
        return hash(self.name())


class FsSupergroup(_GroupTree):
    """ Supergroup for all group trees. """

    max_recurse = None

    def __init__(self):
        super(FsSupergroup, self).__init__()
        self._prefix = ('internal', cereconf.INSTITUTION_DOMAIN_NAME_LMS, 'fs')
        self._name = ('{supergroup}',)

    def description(self):
        return "Supergruppe for alle FS-avledede grupper ved %s" % (
            cereconf.INSTITUTION_DOMAIN_NAME_LMS,)

    def add(self, gtype, attrs):
        if gtype == 'undenh':
            subg = FsUnitSubtree(self, attrs)
        elif gtype == 'studieprogram':
            subg = FsProgramSubtree(self, attrs)
        elif gtype == 'evu':
            subg = FsEvuSubtree(self, attrs)
        else:
            raise ValueError("Ukjent gruppe i hierarkiet: %r" % (gtype,))
        children = self.subnodes
        # TBD: Make fs_{undenh,stprog}_N into singleton classes?
        if subg in children:
            subg = children[subg]
        else:
            children[subg] = subg
        subg.add(attrs)


class _FsUnitTree(_GroupTree):
    """ Abstract group tree for FS undervisningsenhet. """

    def __init__(self, parent):
        super(_FsUnitTree, self).__init__()
        self.parent = parent
        self.child_class = None

    def add(self, ue):
        new_child = self.child_class(self, ue)
        children = self.subnodes
        if new_child in children:
            new_child = children[new_child]
        else:
            children[new_child] = new_child
        new_child.add(ue)


class FsUnitSubtree(_FsUnitTree):
    """ FS undervisningsenhet - supergroup """

    max_recurse = 3

    def __init__(self, parent, ue):
        super(FsUnitSubtree, self).__init__(parent)
        self._prefix = (ue['institusjonsnr'], 'undenh')
        self.child_class = FsUnitTerm

    def description(self):
        return ("Supergruppe for alle grupper avledet fra"
                " undervisningsenhetene i %s sin FS" %
                cereconf.INSTITUTION_DOMAIN_NAME_LMS)

    def list_matches(self, gtype, data, category):
        if gtype != 'undenh':
            return ()
        if access_FS.roles_xml_parser.target_key in data:
            target = data[access_FS.roles_xml_parser.target_key]
            if not (len(target) == 1 and target[0] == 'undenh'):
                return ()
        if data.get('institusjonsnr', self._prefix[0]) != self._prefix[0]:
            return ()
        return super(FsUnitSubtree, self).list_matches(gtype, data, category)


class FsUnitTerm(_FsUnitTree):
    """ FS undervisningsenhet - semester subgroup """

    max_recurse = 2

    def __init__(self, parent, ue):
        super(FsUnitTerm, self).__init__(parent)
        self._prefix = (ue['arstall'], ue['terminkode'])
        self.child_class = FsUnitSubject

    def description(self):
        return ("Supergruppe for alle %s sine FS-undervisningsenhet-grupper"
                " %s %s" % (cereconf.INSTITUTION_DOMAIN_NAME_LMS,
                            self._prefix[1], self._prefix[0]))

    def list_matches(self, gtype, data, category):
        if data.get('arstall', self._prefix[0]) != self._prefix[0]:
            return ()
        if data.get('terminkode', self._prefix[1]) != self._prefix[1]:
            return ()
        return super(FsUnitTerm, self).list_matches(gtype, data, category)


class FsUnitSubject(_FsUnitTree):
    """ FS undervisningsenhet - subject sub-subgroup. """

    ue_versjon = {}
    ue_termin = {}
    max_recurse = 1

    def __init__(self, parent, ue):
        super(FsUnitSubject, self).__init__(parent)
        self._prefix = (ue['emnekode'], ue['versjonskode'], ue['terminnr'])
        multi_id = ":".join((
            six.text_type(x)
            for x in (ue['institusjonsnr'], ue['emnekode'],
                      ue['arstall'], ue['terminkode'])))
        self.ue_versjon.setdefault(multi_id, {})[ue['versjonskode']] = 1
        self.ue_termin.setdefault(multi_id, {})[ue['terminnr']] = 1
        self._multi_id = multi_id
        self.spreads = (const.spread_hia_fronter,)

    def multi_suffix(self):
        multi_suffix = []
        multi_id = self._multi_id
        if len(self.ue_versjon.get(multi_id, {})) > 1:
            multi_suffix.append("v%s" % (self._prefix[1],))
        if len(self.ue_termin.get(multi_id, {})) > 1:
            multi_suffix.append("%s. termin" % (self._prefix[2],))
        if multi_suffix:
            return (" " + " ".join(multi_suffix))
        return ""

    def description(self):
        return ("Supergruppe for grupper tilknyttet undervisningsenhet"
                " %s%s" % (self._multi_id, self.multi_suffix()))

    def list_matches(self, gtype, data, category):
        if data.get('emnekode', self._prefix[0]) != self._prefix[0]:
            return ()
        if data.get('versjonskode', self._prefix[1]) != self._prefix[1]:
            return ()
        if data.get('terminnr', self._prefix[2]) != self._prefix[2]:
            return ()
        return super(FsUnitSubject, self).list_matches(gtype, data, category)

    def add(self, ue):
        children = self.subnodes
        for category in ('student', 'foreleser', 'studieleder'):
            gr = FsUnitUsers(self, ue, category)
            if gr in children:
                logger.warn('Undervisningsenhet %r forekommer flere ganger.',
                            ue)
                continue
            children[gr] = gr


class FsUnitUsers(_FsUnitTree):
    """ FS undervisningsenhet - users leaf group. """

    max_recurse = 0

    def __init__(self, parent, ue, category):
        super(FsUnitUsers, self).__init__(parent)
        self._name = (category,)
        self._emnekode = ue['emnekode']

    def description(self):
        ctg = self._name[0]
        emne = self._emnekode + self.parent.multi_suffix()
        if ctg == 'student':
            return "Studenter på %s" % (emne,)
        elif ctg == 'foreleser':
            return "Forelesere på %s" % (emne,)
        elif ctg == 'studieleder':
            return "Studieledere på %s" % (emne,)
        else:
            raise ValueError("Ukjent UE-bruker-gruppe: %r" % (ctg,))

    def list_matches(self, gtype, data, category):
        if category == self._name[0]:
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user['fodselsdato']), int(user['personnr']))
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.warn("Bruker %r forsøkt meldt inn i gruppe %r"
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return
        self.users[fnr] = user


class _FsProgramTree(_GroupTree):
    """ Abstract group tree for study programs. """

    def __init__(self, parent):
        super(_FsProgramTree, self).__init__()
        self.parent = parent
        self.child_class = None

    def add(self, stprog):
        new_child = self.child_class(self, stprog)
        children = self.subnodes
        if new_child in children:
            new_child = children[new_child]
        else:
            children[new_child] = new_child
        new_child.add(stprog)


class FsProgramSubtree(_FsProgramTree):
    """ FS studieprogram - supergroup. """

    max_recurse = 3

    def __init__(self, parent, stprog):
        super(FsProgramSubtree, self).__init__(parent)
        self._prefix = (stprog['institusjonsnr_studieansv'],
                        'studieprogram')
        self.child_class = FsProgram

    def description(self):
        return ("Supergruppe for alle grupper relatert til"
                " studieprogram i %s sin FS" %
                (cereconf.INSTITUTION_DOMAIN_NAME_LMS,))

    def list_matches(self, gtype, data, category):
        if gtype != 'studieprogram':
            return ()
        if access_FS.roles_xml_parser.target_key in data:
            target = data[access_FS.roles_xml_parser.target_key]
            if not (len(target) == 1 and target[0] == 'stprog'):
                return ()
        if data.get('institusjonsnr', self._prefix[0]) != self._prefix[0]:
            return ()
        return super(FsProgramSubtree, self).list_matches(gtype, data,
                                                          category)


class FsProgram(_FsProgramTree):
    """ FS studieprogram - subgroup. """

    max_recurse = 2

    def __init__(self, parent, stprog):
        super(FsProgram, self).__init__(parent)
        self._prefix = (stprog['studieprogramkode'],)
        # Denne klassen har mer enn en mulig barn-klasse.
        self.child_class = None

    def description(self):
        return ("Supergruppe for alle grupper knyttet til"
                " studieprogrammet %r" % (self._prefix[0],))

    def add(self, stprog):
        # Det skal lages to grener under hver gruppe på dette nivået.
        old = self.child_class
        try:
            for child_class in (FsProgramYear, FsProgramRole):
                self.child_class = child_class
                super(FsProgram, self).add(stprog)
        finally:
            self.child_class = old

    def list_matches(self, gtype, data, category):
        if data.get('studieprogramkode', self._prefix[0]) != self._prefix[0]:
            return ()
        return super(FsProgram, self).list_matches(gtype, data, category)


class FsProgramYear(_FsProgramTree):
    """ FS studieprogram - cohort/examination year sub-subgroup. """

    max_recurse = 1

    def __init__(self, parent, stprog):
        super(FsProgramYear, self).__init__(parent)
        self._prefix = ('studiekull',)
        self._studieprog = stprog['studieprogramkode']
        self.child_class = FsProgramYearUsers
        self.spreads = (const.spread_hia_fronter,)

    def description(self):
        return ("Supergruppe for studiekull-grupper knyttet til"
                " studieprogrammet %r" % (self._studieprog,))

    def list_matches(self, gtype, data, category):
        # Denne metoden er litt annerledes enn de andre
        # list_matches()-metodene, da den også gjør opprettelse av
        # kullkode-spesifikke subgrupper når det er nødvendig.
        ret = []
        for subg in self.subnodes.values():
            ret.extend([m for m in subg.list_matches(gtype, data, category)])
        if (not ret) and ('arstall_kull' in data
                          and 'terminkode_kull' in data):
            ret.extend(self.add(data))
        return ret

    def add(self, stprog):
        children = self.subnodes
        ret = []
        for category in ('student',):
            # Fila studieprog.xml inneholder ikke noen angivelse av
            # hvilke studiekull som finnes; den lister bare opp
            # studieprogrammene.
            #
            # Opprettelse av grupper for de enkelte studiekullene
            # utsettes derfor til senere (i.e. ved parsing av
            # person.xml); se metoden list_matches over.
            if ('arstall_kull' in stprog
                    and 'terminkode_kull' in stprog):
                gr = self.child_class(self, stprog, category)
                if gr in children:
                    logger.warn("Kull %r forekommer flere ganger.", stprog)
                    continue
                children[gr] = gr
                ret.append(gr)
        # TBD: Bør, bl.a. for konsistensens skyld, alle .add()-metoden
        # returnere noe?  Denne .add()-metodens returverdi brukes av
        # .list_matches()-metoden like over.
        return ret


class FsProgramYearUsers(_FsProgramTree):
    """ FS studieprogram - leaf group. """

    max_recurse = 0

    def __init__(self, parent, stprog, category):
        super(FsProgramYearUsers, self).__init__(parent)
        self._prefix = (stprog['arstall_kull'], stprog['terminkode_kull'])
        self._studieprog = stprog['studieprogramkode']
        self._name = (category,)

    def description(self):
        category = self._name[0]
        if category == 'student':
            return ("Studenter på kull %s %s i"
                    " studieprogrammet %r" % (self._prefix[1],
                                              self._prefix[0],
                                              self._studieprog))
        raise ValueError("Ugyldig kategori: %r" % category)

    def list_matches(self, gtype, data, category):
        if (data.get('arstall_kull', self._prefix[0]) == self._prefix[0]
                and data.get('terminkode_kull',
                             self._prefix[1]) == self._prefix[1]
                and category == self._name[0]):
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user['fodselsdato']), int(user['personnr']))
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.warn("Bruker %r forsøkt meldt inn i gruppe %r"
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return
        self.users[fnr] = user


class FsProgramRole(_FsProgramTree):
    """ FS studieprogram roles - role sub-subgroup. """

    max_recurse = 1

    def __init__(self, parent, stprog):
        super(FsProgramRole, self).__init__(parent)
        self._prefix = ('rolle',)
        self._studieprog = stprog['studieprogramkode']
        self.child_class = FsProgramRoleUsers
        self.spreads = (const.spread_hia_fronter,)

    def description(self):
        return ("Supergruppe for personrolle-grupper knyttet til"
                " studieprogrammet %r" % (self._studieprog,))

    def add(self, stprog):
        children = self.subnodes
        for category in ('studieleder',):
            gr = self.child_class(self, stprog, category)
            if gr in children:
                logger.warn('Studieprogram %r forekommer flere ganger.',
                            self._studieprog)
                continue
            children[gr] = gr


class FsProgramRoleUsers(_FsProgramTree):
    """ FS studieprogram roles - role leaf group. """

    max_recurse = 0

    def __init__(self, parent, stprog, category):
        super(FsProgramRoleUsers, self).__init__(parent)
        self._studieprog = stprog['studieprogramkode']
        self._name = (category,)

    def description(self):
        category = self._name[0]
        if category == 'studieleder':
            return ("Studieledere på studieprogrammet %r" % self._studieprog)
        raise ValueError("Ugyldig kategori: %r" % category)

    def list_matches(self, gtype, data, category):
        if category == self._name[0]:
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user['fodselsdato']), int(user['personnr']))
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.warn("Bruker %r forsøkt meldt inn i gruppe %r"
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return
        self.users[fnr] = user


class FsEvuSubtree(_FsUnitTree):
    """ FS EVU - supergroup.  """

    max_recurse = 2

    def __init__(self, parent, evudata):
        super(FsEvuSubtree, self).__init__(parent)
        self._prefix = (evudata["institusjonsnr_adm_ansvar"], "evu")
        self.child_class = FsEvuCourse

    def description(self):
        return ("Supergruppe for alle grupper avledet fra"
                " EVU-kurs i %s sin FS" %
                cereconf.INSTITUTION_DOMAIN_NAME_LMS)

    def list_matches(self, gtype, data, category):
        if gtype != "evu":
            return ()

        if access_FS.roles_xml_parser.target_key in data:
            target = data[access_FS.roles_xml_parser.target_key]
            if not (len(target) == 1 and target[0] == "evu"):
                return ()

        if (data.get("institusjonsnr_adm_ansvar",
                     self._prefix[0]) != self._prefix[0]):
            return ()

        return super(FsEvuSubtree, self).list_matches(gtype, data, category)


class FsEvuCourse(_FsUnitTree):
    max_recurse = 1

    def __init__(self, parent, evudata):
        super(FsEvuCourse, self).__init__(parent)
        self._prefix = (evudata["etterutdkurskode"],
                        evudata["kurstidsangivelsekode"])
        self.spreads = (const.spread_hia_fronter,)

    def description(self):
        return ("Supergruppe for grupper tilknyttet EVU-kurs %s:%s" %
                (self._prefix[0], self._prefix[1]))

    def list_matches(self, gtype, data, category):
        if data.get("etterutdkurskode", self._prefix[0]) != self._prefix[0]:
            return ()
        if (data.get("kurstidsangivelsekode",
                     self._prefix[1]) != self._prefix[1]):
            return ()

        return super(FsEvuCourse, self).list_matches(gtype, data, category)

    def add(self, evudata):
        children = self.subnodes
        for category in ("kursdeltaker", "foreleser"):
            gr = FsEvuCourseUsers(self, evudata, category)
            if gr in children:
                logger.warn("EVU-kurs %r forekommer flere ganger.",
                            evudata)
                continue

            children[gr] = gr


class FsEvuCourseUsers(_FsUnitTree):

    max_recurse = 0

    def __init__(self, parent, evudata, category):
        super(FsEvuCourseUsers, self).__init__(parent)
        self._name = (category,)

    def description(self):
        category = self._name[0]
        if category == "kursdeltaker":
            return "Kursdeltakere på %s" % self.parent.name()
        elif category == "foreleser":
            return "Forelesere på %s" % self.parent.name()
        else:
            raise ValueError("Ukjent EVU-brukergrupper: %r" % (category,))

    def list_matches(self, gtype, data, category):
        if category == self._name[0]:
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user["fodselsdato"]), int(user["personnr"]))
        if fnr in self.users:
            logger.warn("Bruker %r forsøkt meldt inn i gruppe %r "
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return

        self.users[fnr] = user


def prefetch_primaryusers():
    logger.debug("Start: prefetch_primaryusers()")
    # TBD: This code is used to get account_id for both students and
    # fagansv.  Should we look at affiliation here?
    account = Factory.get('Account')(db)
    personid2accountid = {}
    for a in account.list_accounts_by_type():
        p_id = int(a['person_id'])
        a_id = int(a['account_id'])
        personid2accountid.setdefault(p_id, []).append(a_id)

    person = Factory.get('Person')(db)
    fnr_source = {}
    for row in person.search_external_ids(id_type=const.externalid_fodselsnr,
                                          fetchall=False):
        p_id = int(row['entity_id'])
        fnr = row['external_id']
        src_sys = int(row['source_system'])
        if fnr in fnr_source and fnr_source[fnr][0] != p_id:
            # Multiple person_info rows have the same fnr (presumably
            # the different fnrs come from different source systems).
            logger.error("Multiple persons share fnr %s: (%d, %d)",
                         fnr, fnr_source[fnr][0], p_id)
            # Determine which person's fnr registration to use.
            source_weight = {int(const.system_fs): 4,
                             int(const.system_manual): 3,
                             int(const.system_sap): 2,
                             int(const.system_migrate): 1}
            old_weight = source_weight.get(fnr_source[fnr][1], 0)
            if source_weight.get(src_sys, 0) <= old_weight:
                continue
            # The row we're currently processing should be preferred;
            # if the old row has an entry in fnr2account_id, delete
            # it.
            if fnr in fnr2account_id:
                del fnr2account_id[fnr]
        fnr_source[fnr] = (p_id, src_sys)
        if p_id in personid2accountid:
            account_ids = personid2accountid[p_id]
            fnr2account_id[fnr] = account_ids
    del fnr_source
    logger.debug("Ferdig: prefetch_primaryusers()")


def init_globals():
    global db, const, logger, fnr2account_id
    global dump_dir, dryrun, immediate_evu_expire
    global fs_group_categorizer

    logger = Factory.get_logger("cronjob")
    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    # locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    dump_dir = cereconf.FS_DATA_DIR
    dryrun = False
    immediate_evu_expire = False

    opts, rest = getopt.getopt(
        sys.argv[1:], "d:r",
        ["dump-dir=", "dryrun", "immediate-evu-expire"])
    for option, value in opts:
        if option in ("-d", "--dump-dir"):
            dump_dir = value
        elif option in ("-r", "--dryrun"):
            dryrun = True
        elif option in ("--immediate-evu-expire",):
            immediate_evu_expire = True

    db = Factory.get("Database")()
    db.cl_init(change_program='pop_extern_grps')
    const = Factory.get("Constants")(db)

    fnr2account_id = {}
    prefetch_primaryusers()
    fs_group_categorizer = FsGroupCategorizer()


def main():
    init_globals()

    # Opprett objekt for "internal:hia.no:fs:{supergroup}"
    fs_super = FsSupergroup()

    # Gå igjennom alle kjente undervisningsenheter; opprett
    # gruppe-objekter for disse.
    #
    # La fs-supergruppe-objektet ta seg av all logikk rundt hvor mange
    # nivåer gruppestrukturen skal ha for undervisningsenhet-grupper,
    # etc.
    def create_ue_helper(el_name, attrs):
        if el_name == 'undenhet':
            fs_super.add('undenh', attrs)

    logger.info("Leser XML-fil: underv_enhet.xml")
    access_FS.underv_enhet_xml_parser(
        os.path.join(dump_dir, 'underv_enhet.xml'),
        create_ue_helper)

    # Gå igjennom alle kjente EVU-kurs; opprett gruppeobjekter for disse.
    def create_evukurs_helper(el_name, attrs):
        if (el_name == "evukurs" and
                attrs.get("status_aktiv") == 'J' and
                attrs.get("status_nettbasert_und") == 'J'):

            if (immediate_evu_expire and
                    parse_date(attrs.get("dato_til")) < datetime.date.today()):
                logger.debug("Kurs %s-%s ekspirerte",
                             attrs["etterutdkurskode"],
                             attrs["kurstidsangivelsekode"])
            else:
                fs_super.add("evu", attrs)

    xmlfile = "evu_kursinfo.xml"
    logger.info("Leser XML-fil: %s", xmlfile)
    access_FS.evukurs_xml_parser(os.path.join(dump_dir, xmlfile),
                                 create_evukurs_helper)
    logger.info("Ferdig med %s", xmlfile)

    # Meld studenter inn i undervisningsenhet-gruppene
    def student_ue_helper(el_name, attrs):
        if el_name == 'student':
            for undenh in fs_super.list_matches_1('undenh', attrs,
                                                  'student'):
                undenh.add(attrs)

    logger.info("Leser XML-fil: student_undenh.xml")
    access_FS.student_undenh_xml_parser(
        os.path.join(dump_dir, 'student_undenh.xml'),
        student_ue_helper)

    # Meld EVU-kursdeltakere i de respektive EVU-kursgruppene.
    def evu_deltaker_helper(el_name, attrs):
        if el_name == "person" and len(attrs.get("evu")) > 0:
            # Dette blir ikke fult så pent -- i merged_persons plasserer man
            # informasjonen om EVU-tilknytning i form av underelementer av
            # <person>. Dermed må ethvert EVU-underelement (de er samlet i en
            # liste av dict'er under nøkkelen "evu" under) "suppleres" med
            # fdato/pnr på eieren til det EVU-underelementet.
            tmp = {
                "fodselsdato": attrs["fodselsdato"],
                "personnr": attrs["personnr"],
            }
            for evuattrs in attrs["evu"]:
                evuattrs.update(tmp)
                for evukurs in fs_super.list_matches_1("evu", evuattrs,
                                                       "kursdeltaker"):
                    evukurs.add(evuattrs)

    xmlfile = "merged_persons.xml"
    logger.info("Leser XML-fil: %s", xmlfile)
    access_FS.deltaker_xml_parser(os.path.join(dump_dir, xmlfile),
                                  evu_deltaker_helper)
    logger.info("Ferdig med %s", xmlfile)

    # Gå igjennom alle kjente studieprogrammer; opprett gruppeobjekter
    # for disse.
    def create_studieprog_helper(el_name, attrs):
        if el_name == 'studprog' and attrs.get('status_utgatt') != 'J':
            fs_super.add('studieprogram', attrs)
    logger.info("Leser XML-fil: studieprog.xml")
    access_FS.studieprog_xml_parser(
        os.path.join(dump_dir, 'studieprog.xml'),
        create_studieprog_helper)

    # Meld forelesere og studieledere inn i passende
    # undervisningsenhet/EVU-kurs -gruppene
    def rolle_helper(el_name, attrs):
        if el_name != 'rolle':
            return
        rolle = attrs['rollekode']
        target = attrs[access_FS.roles_xml_parser.target_key]
        if len(target) != 1:
            return
        target = target[0]
        if target in ('undenh', 'stprog'):
            if rolle == 'FORELESER':
                for ue_foreleser in fs_super.list_matches('undenh', attrs,
                                                          'foreleser'):
                    ue_foreleser.add(attrs)
            elif rolle in ('STUDILEDER', 'STUDKOORD'):
                for ue_studieleder in fs_super.list_matches('undenh', attrs,
                                                            'studieleder'):
                    ue_studieleder.add(attrs)
                for stpr_studieleder in fs_super.list_matches('studieprogram',
                                                              attrs,
                                                              'studieleder'):
                    stpr_studieleder.add(attrs)
            # fi
        elif target in ('evu',):
            if rolle == 'FORELESER':
                # Kan ett element tilhøre flere evukurs?
                for evu_foreleser in fs_super.list_matches('evu', attrs,
                                                           "foreleser"):
                    evu_foreleser.add(attrs)

    xmlfile = "roles.xml"
    logger.info("Leser XML-fil: %s", xmlfile)
    access_FS.roles_xml_parser(os.path.join(dump_dir, xmlfile),
                               rolle_helper)
    logger.info("Ferdig med %s", xmlfile)

    # Finn alle studenter
    def student_studieprog_helper(el_name, attrs):
        if el_name == 'aktiv':
            for stpr in fs_super.list_matches_1('studieprogram', attrs,
                                                'student'):
                stpr.add(attrs)

    logger.info("Leser XML-fil: person.xml")
    access_FS.person_xml_parser(
        os.path.join(dump_dir, 'person.xml'),
        student_studieprog_helper)
    logger.info("Ferdig med XML-fil: person.xml")

    # Write back all changes to the database
    fs_super.sync()

    if dryrun:
        logger.info("rolling back all changes")
        db.rollback()
    else:
        logger.info("committing all changes")
        db.commit()


def walk_hierarchy(root, indent=0, print_users=False):
    """
    Display the data structure (tree) from a given node. Useful to get an
    overview over how various nodes are structured/populated. This is used for
    debugging only.
    """
    logger.debug("%snode: %r (%d subnode(s), %d user(s))",
                 ' ' * indent, root.name(), len(root.subnodes),
                 len(root.users))
    if print_users and root.users:
        import pprint
        logger.debug("%susers: %s", ' ' * indent, pprint.pformat(root.users))

    for n in root.subnodes:
        walk_hierarchy(n, indent + 2)


if __name__ == '__main__':
    main()
