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

import sys
import os

from __future__ import generators

if False:
    import cerebrum_path
    import cereconf
    from Cerebrum.Utils import Factory
    from Cerebrum.modules.no.hia import access_FS
else:
    class liksom_module(object): pass
    cereconf = liksom_module()
    cereconf.INSTITUTION_DOMAIN_NAME = 'hia.no'

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


class group_tree(object):

    def __init__(self):
        self.subnodes = {}

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

    def __hash__(self):
        return hash(self.name())


class fs_supergroup(group_tree):

    def __init__(self):
        super(fs_supergroup, self).__init__()
        self._prefix = ('internal', cereconf.INSTITUTION_DOMAIN_NAME, 'fs')
        self._name = ('{supergroup}',)

    def add_undenh(self, ue):
        subg = fs_undenh_1(self, ue)
        children = self.subnodes
        # TBD: Make fs_undenh_1 a singleton class?
        if children.has_key(subg):
            subg = children[subg]
        else:
            children[subg] = subg
        subg.add(ue)

    def list_matches(self, gtype, ue, category):
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, ue, category):
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

    def get(self, ue, category):
        subg = self.child_class(self, ue)
        subg = self.subnodes[subg]
        return subg.get(ue, category)


class fs_undenh_1(fs_undenh_group):

    def __init__(self, parent, ue):
        super(fs_undenh_1, self).__init__(parent)
        self._prefix = (ue['institusjonsnr'], 'undenh')
        self.child_class = fs_undenh_2

    def list_matches(self, gtype, ue, category):
        if gtype <> 'undenh':
            return
        if ue.get('institusjonsnr', self._prefix[0]) <> self._prefix[0]:
            return
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, ue, category):
                yield match


class fs_undenh_2(fs_undenh_group):

    def __init__(self, parent, ue):
        super(fs_undenh_2, self).__init__(parent)
        self._prefix = (ue['arstall'], ue['terminkode'])
        self.child_class = fs_undenh_3

    def list_matches(self, gtype, ue, category):
        if ue.get('arstall', self._prefix[0]) <> self._prefix[0]:
            return
        if ue.get('terminkode', self._prefix[1]) <> self._prefix[1]:
            return
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, ue, category):
                yield match


class fs_undenh_3(fs_undenh_group):

    def __init__(self, parent, ue):
        super(fs_undenh_3, self).__init__(parent)
        self._prefix = (ue['emnekode'], ue['versjonskode'], ue['terminnr'])

    def list_matches(self, gtype, ue, category):
        if ue.get('emnekode', self._prefix[0]) <> self._prefix[0]:
            return
        if ue.get('versjonskode', self._prefix[1]) <> self._prefix[1]:
            return
        if ue.get('terminnr', self._prefix[2]) <> self._prefix[2]:
            return
        for subg in self.subnodes.itervalues():
            for match in subg.list_matches(gtype, ue, category):
                yield match

    def add(self, ue):
        children = self.subnodes
        for category in ('student', 'foreleser', 'studieleder'):
            gr = fs_undenh_users(self, ue, category)
            if gr in children:
                raise RuntimeError, \
                      'Undervisningsenhet %r forekommer flere ganger.' % (ue,)
            children[gr] = gr


class fs_undenh_users(fs_undenh_group):

    def __init__(self, parent, ue, category):
        super(fs_undenh_users, self).__init__(parent)
        self._name = (category,)
        self.users = {}

    def list_matches(self, gtype, ue, category):
        if category == self._name[0]:
            yield self

    def add(self, user):
        if user in self.users:
            raise RuntimeError, \
                  "Bruker %r forsøkt meldt inn i gruppe flere ganger." % \
                  (user,)
        self.users[user] = user

    def get(self, ue, category):
        return self


def main():
    db = Factory.get("Database")()
    logger = Factory.get_logger("console")

    dumpdir = '/cerebrum/dumps/FS'

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
            fs_super.add_undenh(attrs)

    access_FS.underv_enhet_xml_parser(
        os.path.join(dumpdir, 'underv_enhet.xml'),
        create_UE_helper)

    # Meld studenter inn i undervisningsenhet-gruppene
    def student_UE_helper(el_name, attrs):
        if el_name == 'aktiv':
            # TBD: Det ser ikke ut til at det finnes XML-fil som
            # inneholder informasjon om hvilke studenter som er meldt
            # på hvilke undervisningsenheter.  Det finnes dog en
            # metode HiAFS.GetStudenterUndervEnhet() som gir liste
            # over studenter på en bestemt UE.
            #
            # Er det en forglemmelse at disse dataene ikke er dumpet
            # som XML?
            undenh = tryll_tryll()
            ue_student = [x for x in fs_super.list_matches('undenh', undenh,
                                                           'student')]
            if len(ue_student) == 1:
                ue_student[0].add(attrs)
            else:
                logger.warn("Utilstrekkelig spesifisert UE; traff %d (%r).",
                            len(ue_student),
                            [ue.name() for ue in ue_student])

    access_FS.person_xml_parser(
        os.path.join(dumpdir, 'person.xml'),
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
        os.path.join(dumpdir, 'roles.xml'),
        rolle_UE_helper)

    # Her kan i prinsippet alle undervisningsenhet-relaterte
    # gruppeobjekter synkroniseres med tilsvarende grupper i
    # databasen.

    # Gå igjennom alle kjente studieprogrammer; opprett gruppeobjekter
    # for disse.
    def create_studieprog_helper(el_name, attrs):
        if el_name == 'studprog':
            fs_super.add_studieprog(attrs)

    access_FS.studieprog_xml_parser(
        os.path.join(dumpdir, 'studieprog.xml'),
        create_studieprog_helper)

    # Finn alle studenter 
    def student_studieprog_helper(el_name, attrs):
        if el_name == 'aktiv':
            studieprog_student = fs_super.get_studieprog(attrs, 'student')
            studieprog_student.add(attrs)

    access_FS.person_xml_parser(
        os.path.join(dumpdir, 'person.xml'),
        student_studieprog_helper)

    fs_super.sync(db)

if __name__ == '__main__':
    main()
