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
#               internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                 STUDIEPROGRAMKODE:studiekull:KULLKODE:student
#               Eks "internal:hia.no:fs:201:studieprogram:tekn.eksp:studiekull:
#                    04v:student"

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
##     import traceback
##     traceback.print_stack()
    print ".",
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
        logger.info("removing %s from group %s" % (gr.group_name,
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
        return safe_join(name_elements, ':')

    def description(self):
        pass

    def list_matches(self, gtype, data, category):
        pass

    def list_matches_1(self, *args, **kws):
        ret = self.list_matches(*args, **kws)
        if len(ret) == 1:
            return ret
        logger.error("Matchet for mange: self=%r, args=%r, kws=%r, ret=%r",
                     self, args, kws, ret)
        return ()

    def sync(self):
        db_group = self.maybe_create()
        sub_ids = {}
        if self.users:
            for fnr in self.users.iterkeys():
                a_ids = fnr2account_id.get(fnr)
                if a_ids is not None:
                    primary_account_id = int(a_ids[0])
                    sub_ids[primary_account_id] = const.entity_account
                else:
                    logger.warn("Fant ingen bruker for fnr=%r", fnr)
        else:
            # Sørg for at alle subgrupper er synkronisert, og samle
            # samtidig inn entity_id'ene deres.
            for subg in self.subnodes:
                sub_ids[int(subg.sync())] = const.entity_group
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

    def list_matches(self, gtype, data, category):
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, data, category):
                yield match


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
            return
        if data.get('institusjonsnr', self._prefix[0]) <> self._prefix[0]:
            return
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, data, category):
                yield match


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
            return
        if data.get('terminkode', self._prefix[1]) <> self._prefix[1]:
            return
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, data, category):
                yield match


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
            return
        if data.get('versjonskode', self._prefix[1]) <> self._prefix[1]:
            return
        if data.get('terminnr', self._prefix[2]) <> self._prefix[2]:
            return
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, data, category):
                yield match

    def add(self, ue):
        children = self.subnodes
        for category in ('student', 'foreleser', 'studieleder'):
            gr = fs_undenh_users(self, ue, category)
            if gr in children:
                logger.error('Undervisningsenhet %r forekommer flere ganger.',
                             ue)
                return
            children[gr] = gr


class fs_undenh_users(fs_undenh_group):

    max_recurse = 0

    def __init__(self, parent, ue, category):
        super(fs_undenh_users, self).__init__(parent)
        self._name = (category,)
        self._emnekode = ue['emnekode']

    def description(self):
        ctg = self._name[0]
        emne = self._emnekode + self.parent.multi_suffix()
        if ctg == 'student':
            return "Studenter på %s" % (emne,)
        elif ctg == 'foreleser':
            return "Forelesere på %s" % (emne,)
        elif ctg == 'studieledere':
            return "Studieledere på %s" % (emne,)
        else:
            raise ValueError, "Ukjent UE-bruker-gruppe: %r" % (ctg,)

    def list_matches(self, gtype, data, category):
        if category == self._name[0]:
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (user['fodselsdato'], user['personnr'])
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.error("Bruker %r forsøkt meldt inn i gruppe flere ganger.",
                         user)
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
        self._prefix = (stprog['institusjonsnr'], 'studieprogram')
        self.child_class = fs_stprog_2

    def list_matches(self, gtype, data, category):
        if gtype <> 'undenh':
            return
        if data.get('institusjonsnr', self._prefix[0]) <> self._prefix[0]:
            return
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, data, category):
                yield match


class fs_stprog_2(fs_stprog_group):

    max_recurse = 2

    def __init__(self, parent, stprog):
        super(fs_stprog_2, self).__init__(parent)
        self._prefix = (stprog['studieprogramkode'],)
        self.child_class = fs_stprog_3

    def list_matches(self, gtype, data, category):
        if data.get('studieprogramkode', self._prefix[0]) <> self._prefix[0]:
            return
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, data, category):
                yield match


class fs_stprog_3(fs_stprog_group):

    max_recurse = 1

    def __init__(self, parent, stprog):
        super(fs_stprog_3, self).__init__(parent)
        self._prefix = ('studiekull',)
        self.child_class = fs_stprog_users

    def list_matches(self, gtype, data, category):
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, data, category):
                yield match

    def add(self, stprog):
        children = self.subnodes
        for category in ('student',):
            gr = fs_stprog_users(self, stprog, category)
            if gr in children:
                logger.error("Kull %r forekommer flere ganger.", stprog)
                return
            children[gr] = gr


class fs_stprog_users(fs_stprog_group):

    max_recurse = 0

    def __init__(self, parent, stprog, category):
        super(fs_stprog_users, self).__init__(parent)
        self._prefix = (stprog['kullkode'],)
        self._name = (category,)

    def list_matches(self, gtype, data, category):
        if (data.get('kullkode', self._prefix[0]) == self._prefix[0]
            and category == self._name[0]):
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (user['fodselsdato'], user['personnr'])
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.error("Bruker %r forsøkt meldt inn i gruppe flere ganger.",
                         user)
            return
        self.users[fnr] = user


def prefetch_primaryusers():
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

def init_globals():
    global db, const, logger, fnr2account_id
    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)
    logger = Factory.get_logger("console")

    fnr2account_id = {}
    prefetch_primaryusers()

def main():
    init_globals()
    dump_dir = '/cerebrum/dumps/FS'

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

    access_FS.underv_enhet_xml_parser(
        os.path.join(dump_dir, 'underv_enhet.xml'),
        create_UE_helper)

    # Meld studenter inn i undervisningsenhet-gruppene
    def student_UE_helper(el_name, attrs):
        if el_name == 'student':
            for undenh in fs_super.list_matches_1('undenh', attrs,
                                                  'student'):
                undenh.add(attrs)

    access_FS.person_xml_parser(
        os.path.join(dump_dir, 'student_undenh.xml'),
        student_UE_helper)

    # Meld forelesere og studieledere inn i undervisningsenhet-gruppene
    def rolle_UE_helper(el_name, attrs):
        if el_name <> 'role':
            return
        rolle = attrs['rollekode']
        if rolle == 'FORELESER':
            for ue_foreleser in fs_super.list_matches('undenh', attrs,
                                                      'foreleser'):
                ue_foreleser.add(attrs)
        elif rolle == 'STUDIELEDER':
            for ue_studieleder in fs_super.list_matches('undenh', attrs,
                                                        'studieleder'):
                ue_studieleder.add(attrs)

    access_FS.roles_xml_parser(
        os.path.join(dump_dir, 'roles.xml'),
        rolle_UE_helper)

    # Her kan i prinsippet alle undervisningsenhet-relaterte
    # gruppeobjekter synkroniseres med tilsvarende grupper i
    # databasen.

    # Gå igjennom alle kjente studieprogrammer; opprett gruppeobjekter
    # for disse.
    def create_studieprog_helper(el_name, attrs):
        if el_name == 'studprog':
            fs_super.add('studieprogram', attrs)

    access_FS.studieprog_xml_parser(
        os.path.join(dump_dir, 'studieprog.xml'),
        create_studieprog_helper)

    # Finn alle studenter 
    def student_studieprog_helper(el_name, attrs):
        if el_name == 'aktiv':
            for stpr in fs_super.list_matches_1('studieprogram', attrs,
                                                'student'):
                stpr.add(attrs)

    access_FS.person_xml_parser(
        os.path.join(dump_dir, 'person.xml'),
        student_studieprog_helper)

    fs_super.sync(db)

if __name__ == '__main__':
    main()
