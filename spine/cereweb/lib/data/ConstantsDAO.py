from lib.data.ConstantsDTO import ConstantsDTO
import cerebrum_path
from Cerebrum import Utils
from Cerebrum.Errors import NotFoundError
Database = Utils.Factory.get("Database")
Constants = Utils.Factory.get("Constants")
Person = Utils.Factory.get("Person")

class ConstantsDAO(object):
    def __init__(self, db=None):
        if db is None:
            db = Database()
        self.constants = Constants(db)

    def get_group_visibilities(self):
        names = self._get_names("group_visibility_")
        return self._get_constant_dtos(names, Constants.GroupVisibility)

    def get_ou_spreads(self):
        dtos = []
        names = self._get_names("spread_")
        for c in self._get_constants(names, Constants.Spread):
            if c.entity_type == self.constants.entity_ou:
                dto = ConstantsDTO(c)
                dtos.append(dto)
        return dtos

    def get_user_spreads(self):
        dtos = []
        names = self._get_names("spread_")
        for c in self._get_constants(names, Constants.Spread):
            if c.entity_type == self.constants.entity_account:
                dto = ConstantsDTO(c)
                dtos.append(dto)
        return dtos

    def get_spread(self, spread_id):
        c = self.constants.Spread(spread_id)
        return ConstantsDTO(c)

    def get_authentication_method(self, method_id):
        c = self.constants.Authentication(method_id)
        return ConstantsDTO(c)

    def get_group_spreads(self):
        dtos = []
        names = self._get_names("spread_")
        for c in self._get_constants(names, Constants.Spread):
            if c.entity_type == self.constants.entity_group:
                dto = ConstantsDTO(c)
                dtos.append(dto)
        return dtos

    def get_email_target_types(self):
        names = self._get_names("email_target_")
        return self._get_constant_dtos(names, Constants.EmailTarget)

    def get_account_types(self):
        names = self._get_names("account_")
        return self._get_constant_dtos(names, Constants.Account)

    def get_name_types(self):
        names = self._get_names("name_")
        return self._get_constant_dtos(names, Constants.PersonName)

    def get_name_type(self, type_id):
        return ConstantsDTO(Constants.PersonName(type_id))    

    def get_external_id_type(self, type_id):
        return ConstantsDTO(Constants.EntityExternalId(type_id))

    def get_address_type(self, type_id):
        return ConstantsDTO(Constants.Address(type_id))

    def get_contact_type(self, type_id):
        return ConstantsDTO(Constants.ContactInfo(type_id))

    def get_source_system(self, system_id):
        q = self.constants.AuthoritativeSystem(system_id)
        return ConstantsDTO(q)

    def get_affiliation_types(self):
        names = self._get_names("affiliation_")
        return self._get_constant_dtos(names, Constants.PersonAffiliation)

    def get_affiliation_statuses(self):
        names = self._get_names("affiliation_status_")
        dtos = {}
        for c in self._get_constants(names, Constants.PersonAffStatus):
            if c in dtos: continue

            dto = ConstantsDTO(c)
            dto.affiliation = ConstantsDTO(c.affiliation)
            dtos[c] = dto
        statuses = dtos.values()
        statuses.sort(lambda x, y: cmp(
            x.affiliation.name + x.name,
            y.affiliation.name + y.name))
        return statuses

    def get_ou_perspective_type(self, type_id):
        q = self.constants.OUPerspective(type_id)
        return ConstantsDTO(q)

    def get_ou_perspective_types(self):
        names = self._get_names("perspective_")
        return self._get_constant_dtos(names, Constants.OUPerspective)

    def get_shell(self, id):
        q = self.constants.PosixShell(id)
        return ConstantsDTO(q)

    def get_shells(self):
        names = self._get_names("posix_shell_")
        return self._get_constant_dtos(names, Constants.PosixShell)

    def get_quarantine(self, id):
        q = self.constants.Quarantine(id)
        return ConstantsDTO(q)

    def get_gender_types(self):
        names = self._get_names("gender_")
        return self._get_constant_dtos(names, Constants.Gender)

    def get_gender(self, id):
        q = self.constants.Gender(id)
        return ConstantsDTO(q)

    def get_id_types(self):
        names = self._get_names("externalid_")
        return self._get_constant_dtos(names, Constants.EntityExternalId)

    def _get_constant_dtos(self, names, filter_type=None):
        dtos = []
        for c in self._get_constants(names, filter_type):
            dto = ConstantsDTO(c)
            dtos.append(dto)
        return dtos

    def _get_constants(self, names, filter_type=None):
        constants = []
        for c in [getattr(self.constants, n) for n in names]:
            if filter_type is None or isinstance(c, filter_type):
                constants.append(c)
        return constants

    def _get_names(self, str):
        return [n for n in dir(self.constants) if n.startswith(str)]
