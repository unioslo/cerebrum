# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
from Cerebrum.modules.bofhd.errors import PermissionDenied

Database = Utils.Factory.get("Database")
OU_class = Utils.Factory.get("OU")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.QuarantineDAO import QuarantineDAO
from lib.data.NoteDAO import NoteDAO
from lib.data.TraitDAO import TraitDAO

class OuDAO(EntityDAO):
    EntityType = OU_class

    def _get_type(self):
        return self.constants.entity_ou

    def _get_name(self, entity):
        return entity.name

    def get(self, entity_id):
        ou = self._find(entity_id)
        return self._create_dto(ou)

    def _create_dto(self, ou):
        dto = DTO()
        dto.id = ou.entity_id
        dto.name = self._get_name(ou)
        dto.type_name = self._get_type_name()
        dto.type_id = self._get_type_id()
        dto.acronym = ou.acronym
        dto.short_name = ou.short_name
        dto.display_name = ou.display_name
        dto.sort_name = ou.sort_name
        dto.quarantines = QuarantineDAO(self.db).create_from_entity(ou)
        dto.notes = NoteDAO(self.db).create_from_entity(ou)
        dto.traits = TraitDAO(self.db).create_from_entity(ou)
        dto.external_ids = self._get_external_ids(ou)
        dto.stedkode = ''
        dto.landkode = dto.institusjon = dto.fakultet \
                = dto.institutt = dto.avdeling = '0'
        for ext_id in dto.external_ids:
            if ext_id.variant.name == 'STEDKODE':
                dto.stedkode = ext_id.value
                dto.landkode = ext_id.value[0:2]
                dto.institusjon = ext_id.value[2:5]
                dto.fakultet = ext_id.value[5:7]
                dto.institutt = ext_id.value[7:9]
                dto.avdeling = ext_id.value[9:]
        dto.contacts = self._get_contacts(ou)
        dto.addresses = self._get_addresses(ou)
        dto.spreads = self._get_spreads(ou)
        return dto

    def _get_families(self, ou):
        s = OuDAO(self.db)

        families = {}
        for perspective in ConstantsDAO(self.db).get_ou_perspective_types():
            families[perspective] = family = DTO()

            try:
                ou.structure_path(perspective.id)
                family.in_perspective = True
            except NotFoundError, e:
                family.in_perspective = False
                family.parent = None
                family.is_root = False
                family.children = []
                continue

            try:
                parent_id = ou.get_parent(perspective.id)
                family.parent = s.get_entity(parent_id)
            except NotFoundError, e:
                family.parent = None

            family.is_root = family.parent is None

            child_ids = ou.list_children(perspective.id, ou.entity_id)
            family.children = [self._create_dto(self._find(c['ou_id'])) for c in child_ids]
            
        return families

    def get_entities(self):
        entity = self._get_cerebrum_obj()

        dtos = []
        for entity in entity.list_all():
            dto = DTO()
            dto.name = entity['name']
            dto.id = entity['ou_id']
            dtos.append(dto)
        return dtos

    def get_tree(self, perspective):
        """Get a tree structure containing all organizations within the given
        perspective."""
        entity = self._get_cerebrum_obj()
        if isinstance(perspective, (str, int)):
            perspective = ConstantsDAO(self.db).get_ou_perspective_type(perspective)
        # get pairs of organization id's, in the format:
        # {child_id: parent_id,....}
        structure_mappings = entity.get_structure_mappings(perspective.id)
        roots = {}
        cached_nodes = {}
        for child_id, parent_id in structure_mappings:
            # cache the node
            node = cached_nodes.setdefault(child_id, self._create_node(child_id))
            # organization node has a parent?
            if parent_id:
                # cache the parent
                if not parent_id in cached_nodes:
                    cached_nodes[parent_id] = self._create_node(parent_id)
                parent = cached_nodes[parent_id]
                
                # add child to the parent's children
                parent.children.append(node)
            else:
                # it's a root node
                roots[child_id] = node

        return roots.values()

    def get_trees(self):
        perspectives = ConstantsDAO(self.db).get_ou_perspective_types()
        roots = {}
        for perspective in perspectives:
            roots[perspective.id] = self.get_tree(perspective)
        return roots

    def get_parent(self, child_id, perspective):
        if isinstance(perspective, str):
            perspective = ConstantsDAO(self.db).get_ou_perspective_type(perspective)
        child = self._find(child_id)
        parent_id = child.get_parent(perspective.id)
        if parent_id is None:
            return None

        return self._create_node(parent_id)

    def create(self,
            name, fakultet, institutt, avdeling, institusjon, landkode,
            acronym, short_name, display_name, sort_name):

        if not self.auth.can_create_ou(self.db.change_by):
            raise PermissionDenied("Not authorized to create ou")

        ou = OU_class(self.db)
        ou.populate(
            name, fakultet, institutt, avdeling, institusjon, landkode,
            acronym = acronym,
            short_name = short_name,
            display_name = display_name,
            sort_name = sort_name)
        ou.write_db()

        return ou.entity_id

    def save(self, dto):
        ou = self._find(dto.id)
        if not self.auth.can_edit_ou(self.db.change_by, ou):
            raise PermissionDenied("Not authorized to edit ou")

        ou.name = dto.name
        ou.acronym = dto.acronym
        ou.short_name = dto.short_name
        ou.display_name = dto.display_name
        ou.sort_name = dto.sort_name
        ou.landkode = dto.landkode
        ou.institusjon = dto.institusjon
        ou.fakultet = dto.fakultet
        ou.institutt = dto.institutt
        ou.avdeling = dto.avdeling
        ou.write_db()

    def delete(self, entity_id):
        ou = self._find(entity_id)
        if not self.auth.can_delete_ou(self.db.change_by, ou):
            raise PermissionDenied("Not authorized to delete ou")

        ou.delete()

    def set_parent(self, entity_id, perspective, parent):
        ou = self._find(entity_id)
        if not self.auth.can_edit_ou(self.db.change_by, ou):
            raise PermissionDenied("Not authorized to edit ou")

        perspective = int(self.constants.OUPerspective(perspective))
        ou.set_parent(perspective, parent)

    def unset_parent(self, entity_id, perspective):
        ou = self._find(entity_id)
        if not self.auth.can_edit_ou(self.db.change_by, ou):
            raise PermissionDenied("Not authorized to edit ou")
        
        perspective = int(self.constants.OUPerspective(perspective))
        ou.unset_parent(perspective)

    def _create_node(self, ou_id):
        """Get an organization with no children, given an id."""
        ou = self._find(ou_id)
        node = self._create_dto(ou)
        node.children = []
        return node

