import cerebrum_path
from mx import DateTime
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")

from lib.data.ConstantsDTO import ConstantsDTO
from lib.data.ConstantsDAO import ConstantsDAO
from lib.data.DTO import DTO
from lib.data.OuDAO import OuDAO

class AffiliationDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        self.db = db
        self.constants = Constants(self.db)

    def create_from_account_types(self, account_types):
        affiliations = []
        for account_type in account_types:
            affiliations.append(self.create_from_account_type(account_type))
        return affiliations

    def create_from_account_type(self, account_type):
        affiliation = self.get_affiliation_constant(account_type)
        affiliation.type_id = affiliation.id
        affiliation.type_name = affiliation.name
        affiliation.priority = account_type.priority
        affiliation.ou = OuDAO(self.db).get_entity(account_type.ou_id)
        return affiliation

    def create_from_person_affiliations(self, person_affiliations):
        affiliations = []
        for affiliation in person_affiliations:
            affiliations.append(self.create_from_person_affiliation(affiliation))
        return affiliations

    def create_from_person_affiliation(self, paff):
        affiliation = self.get_status(paff)
        affiliation.ou = OuDAO(self.db).get_entity(paff.ou_id)
        affiliation.source_system = self.get_authorative_system(paff)
        affiliation.is_deleted = self.is_deleted(paff)
        return affiliation

    def get_affiliation_constant(self, paff):
        q = self.constants.PersonAffiliation(paff.affiliation)
        return ConstantsDTO(q)

    def get_authorative_system(self, paff):
        return ConstantsDAO(self.db).get_source_system(paff.source_system)

    def get_status(self, paff):
        q = self.constants.PersonAffStatus(paff.status)
        status = ConstantsDTO(q)
        status.affiliation = ConstantsDTO(q.affiliation)
        return status

    def is_deleted(self, paff):
        if not paff.deleted_date: return False
        return paff.deleted_date < DateTime.now()
