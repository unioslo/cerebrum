import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
OU = Utils.Factory.get("OU")

from lib.data.DTO import DTO
from lib.data.EntityDAO import EntityDAO
from lib.data.ConstantsDAO import ConstantsDAO

class OuDAO(EntityDAO):
    def __init__(self, db=None):
        super(OuDAO, self).__init__(db, OU)

    def _get_type_name(self):
        return self.constants.entity_ou.str

    def _get_type_id(self):
        return int(self.constants.entity_ou)

    def _get_name(self, entity):
        return entity.name

    def get_entities(self):
        dtos = []
        for entity in self.entity.list_all():
            dto = DTO()
            dto.name = entity.name
            dto.id = entity.ou_id
            dtos.append(dto)
        return dtos

    def get_tree(self, perspective):
        if isinstance(perspective, str):
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

        return [root for root in roots.values() if root.children]

    def get_parent(self, child_id, perspective):
        if isinstance(perspective, str):
            perspective = ConstantsDAO(self.db).get_ou_perspective_type(perspective)
        child = self._find(child_id)
        parent_id = child.get_parent(perspective.id)

        return self._create_node(parent_id)
        
    def _create_node(self, node_id):
        node = self.get_entity(node_id)
        node.children = []
        return node

