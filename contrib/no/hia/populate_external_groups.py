#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

"""<Documentation goes here.>"""

from __future__ import generators

import sys
import os
import locale

if True:
    import cerebrum_path
    import cereconf
    from Cerebrum import Errors
    from Cerebrum.Utils import Factory
    from Cerebrum.modules import Email
    from Cerebrum.modules.no.hia import access_FS
else:
    class liksom_module(object): pass
    cereconf = liksom_module()
    cereconf.INSTITUTION_DOMAIN_NAME = 'hia.no'

# Define all global variables, to avoid pychecker warnings.
db = logger = fnr2account_id = const = None


###
### Struktur FS-grupper i Cerebrum
###
#
# 0  Supergruppe for alle grupper automatisk avledet fra FS
#      internal:DOMAIN:fs:{supergroup}
#      Eks "internal:hia.no:fs:{supergroup}"
#    1  Gruppering av alle undervisningsenhet-relaterte grupper ved en
#       institusjon
#         internal:DOMAIN:fs:INSTITUSJONSNR:undenh
#         Eks "internal:hia.no:fs:201:undenh"
#       2  Gruppering av alle undervisningsenhet-grupper i et semester
#            internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:TERMINKODE
#            Eks "internal:hia.no:fs:201:undenh:2004:vår"
#          3  Gruppering av alle grupper knyttet til en bestemt und.enhet
#               internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
#                 TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR
#               Eks "internal:hia.no:fs:201:undenh:2004:vår:be-102:g:1"
#             4  Gruppe med studenter som tar und.enhet
#                  Eks "internal:hia.no:fs:201:undenh:2004:vår:be-102:g:1:
#                       student"
#             4  Gruppe med forelesere som gir und.enhet
#                  Eks "internal:hia.no:fs:201:undenh:2004:vår:be-102:g:1:
#                       foreleser"
#             4  Gruppe med studieledere knyttet til en und.enhet
#                  Eks "internal:hia.no:fs:201:undenh:2004:vår:be-102:g:1:
#                       studieleder"
#    1  Gruppering av alle grupper relatert til studieprogram ved en
#       institusjon
#         internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram
#         Eks "internal:hia.no:fs:201:studieprogram"
#       2  Gruppering av alle grupper knyttet til et bestemt studieprogram
#            internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:STUDIEPROGRAMKODE
#            Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp"
#          3  Gruppering av alle studiekull-grupper for et studieprogram
#               internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                 STUDIEPROGRAMKODE:studiekull
#               Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:studiekull"
#             4  Gruppe med alle studenter i et kull
#                  internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                    STUDIEPROGRAMKODE:studiekull:KULLKODE:student
#                  Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:
#                       studiekull:04v:student"
#          3  Gruppering av alle personrolle-grupper for et studieprogram
#               internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                 STUDIEPROGRAMKODE:rolle
#               Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:rolle"
#             4  Gruppe med alle studieledere knyttet til et studieprogram
#                  internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                    STUDIEPROGRAMKODE:rolle:studieleder
#                  Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:
#                       rolle:studieleder"

###
### Struktur SAP-grupper i Cerebrum
###
#
# 0  Supergruppe for alle grupper automatisk avledet fra SAP
#      internal:DOMAIN:sap:{supergroup}
#      Eks "internal:hia.no:sap:{supergroup}"
#    1  Gruppering av alle fakultets-baserte grupper
#         internal:DOMAIN:sap:fakultet
#         Eks "internal:hia.no:sap:fakultet"
#       2  Gruppering av alle grupper knyttet til et bestemt fakultet
#            internal:DOMAIN:sap:fakultet:INSTITUSJONSNR:STEDKODE
#            Eks "internal:hia.no:sap:fakultet:201:010000"
#          3  Gruppe med alle ansatte på fakultet
#            internal:DOMAIN:sap:fakultet:INSTITUSJONSNR:STEDKODE:ansatt
#            Eks "internal:hia.no:sap:fakultet:201:010000:ansatt"

def safe_join(elements, sep=' '):
    """As string.join(), but ensures `sep` isn't part of any element."""
    for i in range(len(elements)):
        if elements[i].find(sep) <> -1:
            raise ValueError, \
                  "Join separator %r found in element #%d (%r)" % (
                sep, i, elements[i])
    return sep.join(elements)

def get_account(name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(name)
    return ac

def get_group(id):
    gr = Factory.get('Group')(db)
    if isinstance(id, str):
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
    logger.debug("destroy_group(%s/%d, %d) [After get_group]"
                 % (gr.group_name, gr.entity_id, max_recurse))
    if max_recurse < 0:
        logger.fatal("destroy_group(%s): Recursion too deep" % gr.group_name)
        sys.exit(3)
        
    # If this group is a member of other groups, remove those
    # memberships.
    for r in gr.list_groups_with_entity(gr.entity_id):
        parent = get_group(r['group_id'])
        logger.debug("removing %s from group %s" % (gr.group_name,
                                                    parent.group_name))
        parent.remove_member(gr.entity_id, r['operation'])

    # If a e-mail target is of type multi and has this group as its
    # destination, delete the e-mail target and any associated
    # addresses.  There can only be one target per group.
    et = Email.EmailTarget(db)
    try:
        et.find_by_email_target_attrs(target_type = const.email_target_multi,
                                      entity_id = gr.entity_id)
    except Errors.NotFoundError:
        pass
    else:
        logger.debug("found email target referencing %s" % gr.group_name)
        ea = Email.EmailAddress(db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            logger.debug("deleting address %s@%s" %
                         (r['local_part'], r['domain']))
            ea.delete()
        et.delete()
    # Fetch group's members
    u, i, d = gr.list_members(member_type=const.entity_group)
    logger.debug("destroy_group() subgroups: %r" % (u,))
    # Remove any spreads the group has
    for row in gr.get_spread():
        gr.delete_spread(row['spread'])
    # Delete the parent group (which implicitly removes all membership
    # entries representing direct members of the parent group)
    gr.delete()
    # Destroy any subgroups (down to level max_recurse).  This needs
    # to be done after the parent group has been deleted, in order for
    # the subgroups not to be members of the parent anymore.
    for subg in u:
        destroy_group(subg[1], max_recurse - 1)


class group_tree(object):

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
            raise RuntimeError, \
                  "list_matches() not overriden for user-containing group."
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, data, category):
                yield match

    def list_matches_1(self, *args, **kws):
        ret = [x for x in self.list_matches(*args, **kws)]
        if len(ret) == 1:
            return ret
        logger.error("Matchet for mange: self=%r, args=%r, kws=%r, ret=%r",
                     self, args, kws, ret)
        return ()

    def sync(self):
        logger.debug("Start: group_tree.sync(), name = %s", self.name())
        db_group = self.maybe_create()
        sub_ids = {}
        if self.users:
            # Gruppa inneholder minst en person, og skal dermed
            # populeres med *kun* primærbrukermedlemmer.  Bygg opp
            # oversikt over primærkonto-id'er i 'sub_ids'.
            for fnr in self.users.iterkeys():
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
                sub_ids[int(subg.sync())] = const.entity_group
        # I 'sub_ids' har vi nå en oversikt over hvilke entity_id'er
        # som skal bli gruppens medlemmer.  Foreta nødvendige inn- og
        # utmeldinger.
        membership_ops = (const.group_memberop_union,
                          const.group_memberop_intersection,
                          const.group_memberop_difference)
        for members_with_op, op in zip(db_group.list_members(),
                                       membership_ops):
            for member_type, member_id in members_with_op:
                member_id = int(member_id)
                if member_id in sub_ids:
                    del sub_ids[member_id]
                else:
                    db_group.remove_member(member_id, op)
                    if member_type == const.entity_group:
                        destroy_group(member_id, self.max_recurse)
        for member_id in sub_ids.iterkeys():
            db_group.add_member(member_id, sub_ids[member_id],
                                const.group_memberop_union)
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
        for new_spread in want_spreads.iterkeys():
            db_group.add_spread(new_spread)
        logger.debug("Ferdig: group_tree.sync(), name = %s", self.name())
        return db_group.entity_id

    def maybe_create(self):
        try:
            return get_group(self.name())
        except Errors.NotFoundError:
            gr = Factory.get('Group')(db)
            gr.populate(self.group_creator(),
                        const.group_visibility_internal,
                        self.name(),
                        description=self.description())
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


class fs_supergroup(group_tree):

    max_recurse = None

    def __init__(self):
        super(fs_supergroup, self).__init__()
        self._prefix = ('internal', cereconf.INSTITUTION_DOMAIN_NAME, 'fs')
        self._name = ('{supergroup}',)

    def description(self):
        return "Supergruppe for alle FS-avledede grupper ved %s" % (
            cereconf.INSTITUTION_DOMAIN_NAME,)

    def add(self, gtype, attrs):
        if gtype == 'undenh':
            subg = fs_undenh_1(self, attrs)
        elif gtype == 'studieprogram':
            subg = fs_stprog_1(self, attrs)
        children = self.subnodes
        # TBD: Make fs_{undenh,stprog}_N into singleton classes?
        if children.has_key(subg):
            subg = children[subg]
        else:
            children[subg] = subg
        subg.add(attrs)


class fs_undenh_group(group_tree):

    def __init__(self, parent):
        super(fs_undenh_group, self).__init__()
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


class fs_undenh_1(fs_undenh_group):

    max_recurse = 3

    def __init__(self, parent, ue):
        super(fs_undenh_1, self).__init__(parent)
        self._prefix = (ue['institusjonsnr'], 'undenh')
        self.child_class = fs_undenh_2

    def description(self):
        return ("Supergruppe for alle grupper avledet fra"
                " undervisningsenhetene i %s sin FS" %
                cereconf.INSTITUTION_DOMAIN_NAME)

    def list_matches(self, gtype, data, category):
        if gtype <> 'undenh':
            return ()
        if '::rolletarget::' in data:
            target = data['::rolletarget::']
            if not (len(target) == 1 and target[0] == 'undenh'):
                return ()
        if data.get('institusjonsnr', self._prefix[0]) <> self._prefix[0]:
            return ()
        return super(fs_undenh_1, self).list_matches(gtype, data, category)


class fs_undenh_2(fs_undenh_group):

    max_recurse = 2

    def __init__(self, parent, ue):
        super(fs_undenh_2, self).__init__(parent)
        self._prefix = (ue['arstall'], ue['terminkode'])
        self.child_class = fs_undenh_3

    def description(self):
        return ("Supergruppe for alle %s sine FS-undervisningsenhet-grupper"
                " %s %s" % (cereconf.INSTITUTION_DOMAIN_NAME,
                            self._prefix[1], self._prefix[0]))

    def list_matches(self, gtype, data, category):
        if data.get('arstall', self._prefix[0]) <> self._prefix[0]:
            return ()
        if data.get('terminkode', self._prefix[1]) <> self._prefix[1]:
            return ()
        return super(fs_undenh_2, self).list_matches(gtype, data, category)


class fs_undenh_3(fs_undenh_group):

    ue_versjon = {}
    ue_termin = {}
    max_recurse = 1

    def __init__(self, parent, ue):
        super(fs_undenh_3, self).__init__(parent)
        self._prefix = (ue['emnekode'], ue['versjonskode'], ue['terminnr'])
        multi_id = ":".join([str(x)
                             for x in(ue['institusjonsnr'], ue['emnekode'],
                                      ue['terminkode'], ue['arstall'])])
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
        if data.get('emnekode', self._prefix[0]) <> self._prefix[0]:
            return ()
        if data.get('versjonskode', self._prefix[1]) <> self._prefix[1]:
            return ()
        if data.get('terminnr', self._prefix[2]) <> self._prefix[2]:
            return ()
        return super(fs_undenh_3, self).list_matches(gtype, data, category)

    def add(self, ue):
        children = self.subnodes
        for category in ('student', 'foreleser', 'studieleder'):
            gr = fs_undenh_users(self, ue, category)
            if gr in children:
                logger.warn('Undervisningsenhet %r forekommer flere ganger.',
                            ue)
                continue
            children[gr] = gr


class fs_undenh_users(fs_undenh_group):

    max_recurse = 0

    def __init__(self, parent, ue, category):
        super(fs_undenh_users, self).__init__(parent)
        self._name = (category,)
        self._emnekode = ue['emnekode']
        # Det viser seg at HiA ønsker seg grupper over studenter på
        # undervisningsenheter inn i AD.  Da det haster en del å få
        # dette på plass, gjøres dette med et hack her.
        #
        # TODO: Generalisere dette svært HiA-spesifikke hacket.
        if category == 'student':
            self.spreads = (const.spread_hia_ad_group,)

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
            raise ValueError, "Ukjent UE-bruker-gruppe: %r" % (ctg,)

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


class fs_stprog_group(group_tree):

    def __init__(self, parent):
        super(fs_stprog_group, self).__init__()
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


class fs_stprog_1(fs_stprog_group):

    max_recurse = 3

    def __init__(self, parent, stprog):
        super(fs_stprog_1, self).__init__(parent)
        self._prefix = (stprog['institusjonsnr_studieansv'],
                        'studieprogram')
        self.child_class = fs_stprog_2

    def description(self):
        return ("Supergruppe for alle grupper relatert til"
                " studieprogram i %s sin FS" %
                (cereconf.INSTITUTION_DOMAIN_NAME,))

    def list_matches(self, gtype, data, category):
        if gtype <> 'studieprogram':
            return ()
        if '::rolletarget::' in data:
            target = data['::rolletarget::']
            if not (len(target) == 1 and target[0] == 'stprog'):
                return ()
        if data.get('institusjonsnr', self._prefix[0]) <> self._prefix[0]:
            return ()
        return super(fs_stprog_1, self).list_matches(gtype, data, category)


class fs_stprog_2(fs_stprog_group):

    max_recurse = 2

    def __init__(self, parent, stprog):
        super(fs_stprog_2, self).__init__(parent)
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
            for child_class in (fs_stprog_3_kull, fs_stprog_3_rolle):
                self.child_class = child_class
                super(fs_stprog_2, self).add(stprog)
        finally:
            self.child_class = old

    def list_matches(self, gtype, data, category):
        if data.get('studieprogramkode', self._prefix[0]) <> self._prefix[0]:
            return ()
        return super(fs_stprog_2, self).list_matches(gtype, data, category)


class fs_stprog_3_kull(fs_stprog_group):

    max_recurse = 1

    def __init__(self, parent, stprog):
        super(fs_stprog_3_kull, self).__init__(parent)
        self._prefix = ('studiekull',)
        self._studieprog = stprog['studieprogramkode']
        self.child_class = fs_stprog_kull_users
        self.spreads = (const.spread_hia_fronter,)

    def description(self):
        return ("Supergruppe for studiekull-grupper knyttet til"
                " studieprogrammet %r" % (self._studieprog,))

    def list_matches(self, gtype, data, category):
        # Denne metoden er litt annerledes enn de andre
        # list_matches()-metodene, da den også gjør opprettelse av
        # kullkode-spesifikke subgrupper når det er nødvendig.
        ret = []
        for subg in self.subnodes.itervalues():
            ret.extend([m for m in subg.list_matches(gtype, data, category)])
        if (not ret) and data.has_key('kullkode'):
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
            if stprog.has_key('kullkode'):
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


class fs_stprog_kull_users(fs_stprog_group):

    max_recurse = 0

    def __init__(self, parent, stprog, category):
        super(fs_stprog_kull_users, self).__init__(parent)
        self._prefix = (stprog['kullkode'],)
        self._studieprog = stprog['studieprogramkode']
        self._name = (category,)

    def description(self):
        category = self._name[0]
        if category == 'student':
            return ("Studenter på studiekullet %r i"
                    " studieprogrammet %r" % (self._prefix[0],
                                              self._studieprog))
        raise ValueError("Ugyldig kategori: %r" % category)

    def list_matches(self, gtype, data, category):
        if (data.get('kullkode', self._prefix[0]) == self._prefix[0]
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


class fs_stprog_3_rolle(fs_stprog_group):

    max_recurse = 1

    def __init__(self, parent, stprog):
        super(fs_stprog_3_rolle, self).__init__(parent)
        self._prefix = ('rolle',)
        self._studieprog = stprog['studieprogramkode']
        self.child_class = fs_stprog_rolle_users
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


class fs_stprog_rolle_users(fs_stprog_group):

    max_recurse = 0

    def __init__(self, parent, stprog, category):
        super(fs_stprog_rolle_users, self).__init__(parent)
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
    for row in person.list_external_ids(id_type=const.externalid_fodselsnr):
        p_id = int(row['person_id'])
        fnr = row['external_id']
        src_sys = int(row['source_system'])
        if fnr_source.has_key(fnr) and fnr_source[fnr][0] <> p_id:
            # Multiple person_info rows have the same fnr (presumably
            # the different fnrs come from different source systems).
            logger.error("Multiple persons share fnr %s: (%d, %d)" % (
                fnr, fnr_source[fnr][0], p_id))
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
            if fnr2account_id.has_key(fnr):
                del fnr2account_id[fnr]
        fnr_source[fnr] = (p_id, src_sys)
        if personid2accountid.has_key(p_id):
            account_ids = personid2accountid[p_id]
##             for acc in account_ids:
##                 account_id2fnr[acc] = fnr
            fnr2account_id[fnr] = account_ids
    del fnr_source
    logger.debug("Ferdig: prefetch_primaryusers()")

def init_globals():
    global db, const, logger, fnr2account_id
    db = Factory.get("Database")()
    db.cl_init(change_program='pop_extern_grps')
    const = Factory.get("Constants")(db)
    logger = Factory.get_logger("console")

    fnr2account_id = {}
    prefetch_primaryusers()

def main():
    init_globals()
    dump_dir = '/cerebrum/dumps/FS'

    # Håndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    # Opprett objekt for "internal:hia.no:fs:{supergroup}"
    fs_super = fs_supergroup()

    # Gå igjennom alle kjente undervisningsenheter; opprett
    # gruppe-objekter for disse.
    #
    # La fs-supergruppe-objektet ta seg av all logikk rundt hvor mange
    # nivåer gruppestrukturen skal ha for undervisningsenhet-grupper,
    # etc.
    def create_UE_helper(el_name, attrs):
        if el_name == 'undenhet':
            fs_super.add('undenh', attrs)

    logger.info("Leser XML-fil: underv_enhet.xml")
    access_FS.underv_enhet_xml_parser(
        os.path.join(dump_dir, 'underv_enhet.xml'),
        create_UE_helper)

    # Meld studenter inn i undervisningsenhet-gruppene
    def student_UE_helper(el_name, attrs):
        if el_name == 'student':
            for undenh in fs_super.list_matches_1('undenh', attrs,
                                                  'student'):
                undenh.add(attrs)

    logger.info("Leser XML-fil: student_undenh.xml")
    access_FS.student_undenh_xml_parser(
        os.path.join(dump_dir, 'student_undenh.xml'),
        student_UE_helper)

    # Gå igjennom alle kjente studieprogrammer; opprett gruppeobjekter
    # for disse.
    def create_studieprog_helper(el_name, attrs):
        if el_name == 'studprog' and attrs.get('status_utgatt') <> 'J':
            fs_super.add('studieprogram', attrs)

    logger.info("Leser XML-fil: studieprog.xml")
    access_FS.studieprog_xml_parser(
        os.path.join(dump_dir, 'studieprog.xml'),
        create_studieprog_helper)

    # Meld forelesere og studieledere inn i undervisningsenhet-gruppene
    def rolle_helper(el_name, attrs):
        if el_name <> 'role':
            return
        rolle = attrs['rollekode']
        target = attrs['::rolletarget::']
        if len(target) <> 1:
            return
        target = target[0]
        if target not in ('undenh', 'stprog'):
            # Denne importen oppretter kun grupper basert på
            # undervisningsenhet- og studieprogram-roller.
            return
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

    logger.info("Leser XML-fil: roles.xml")
    access_FS.roles_xml_parser(
        os.path.join(dump_dir, 'roles.xml'),
        rolle_helper)

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

    fs_super.sync()
    db.commit()

if __name__ == '__main__':
    main()
