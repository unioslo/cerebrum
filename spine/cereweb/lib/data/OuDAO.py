import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
OU_class = Utils.Factory.get("OU")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.QuarantineDAO import QuarantineDAO
from lib.data.NoteDAO import NoteDAO
from lib.data.TraitDAO import TraitDAO

class OuDAO(EntityDAO):
    def __init__(self, db=None):
        super(OuDAO, self).__init__(db, OU_class)

    def _get_type_name(self):
        return self.constants.entity_ou.str

    def _get_type_id(self):
        return int(self.constants.entity_ou)

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
        dto.landkode = ou.landkode
        dto.institusjon = ou.institusjon
        dto.fakultet = ou.fakultet
        dto.institutt = ou.institutt
        dto.avdeling = ou.avdeling
        dto.stedkode = "%03d%05d%02d%02d%02d"  % (ou.landkode, ou.institusjon, ou.fakultet, ou.institutt, ou.avdeling)
        dto.families = self._get_families(ou)
        dto.quarantines = QuarantineDAO(self.db).create_from_entity(ou)
        dto.notes = NoteDAO(self.db).create_from_entity(ou)
        dto.traits = TraitDAO(self.db).create_from_entity(ou)
        dto.external_ids = self._get_external_ids(ou)
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
            family.children = [s.get_entity(c.ou_id) for c in child_ids]

        return families

    def get_entities(self):
        dtos = []
        for entity in self.entity.list_all():
            dto = DTO()
            dto.name = entity.name
            dto.id = entity.ou_id
            dtos.append(dto)
        return dtos

    def get_tree(self, perspective):
        if isinstance(perspective, (str, int)):
            perspective = ConstantsDAO(self.db).get_ou_perspective_type(perspective)
        structure_mappings = self.entity.get_structure_mappings(perspective.id)
        roots = {}
        data = {}
        for node_id, parent_id in structure_mappings:
            node = data.setdefault(node_id, self._create_node(node_id))

            if not parent_id: 
                roots[node_id] = node
            else:
                if not parent_id in data:
                    data[parent_id] = self._create_node(parent_id)
                parent = data[parent_id]
                parent.children.append(node)

        return [root for root in roots.values()]

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
            name, institution, faculty, institute, department,
            acronym, short_name, display_name, sort_name):
        ou = OU_class(self.db)
        ou.populate(
            name, faculty, institute, department, institution,
            acronym = acronym,
            short_name = short_name,
            display_name = display_name,
            sort_name = sort_name)
        ou.write_db()

        return ou.entity_id

    def save(self, dto):
        ou = self._find(dto.id)
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
        ou.delete()

    def set_parent(self, entity_id, perspective, parent):
        ou = self._find(entity_id)
        perspective = self.constants.OUPerspective(perspective)
        ou.set_parent(perspective, parent)

    def unset_parent(self, entity_id, perspective):
        ou = self._find(entity_id)
        perspective = self.constants.OUPerspective(perspective)
        ou.unset_parent(perspective)

    def _create_node(self, node_id):
        node = self.get_entity(node_id)
        node.children = []
        return node

