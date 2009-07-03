import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError

Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")

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
        affiliation = DTO()
        affiliation.priority = account_type.priority
        affiliation.type_name = self.constants.PersonAffiliation(account_type.affiliation).str
        affiliation.type_id = account_type.affiliation

        affiliation.ou = OuDAO(self.db).get_entity(account_type.ou_id)
        return affiliation

    def create_from_person_affiliations(self, person_affiliations):
        affiliations = []
        for affiliation in person_affiliations:
            affiliations.append(self.create_from_person_affiliation(affiliation))
        return affiliations

    def create_from_person_affiliation(self, person_affiliation):
        affiliation = DTO()
        affiliation.priority = -1
        affiliation.type_name = self.constants.PersonAffiliation(person_affiliation.affiliation).str
        affiliation.type_id = person_affiliation.affiliation
        affiliation.ou = OuDAO(self.db).get_entity(person_affiliation.ou_id)
        return affiliation
