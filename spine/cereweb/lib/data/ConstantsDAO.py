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

    def get_user_spreads(self):
        dtos = []
        names = self._get_names("spread_")
        for c in self._get_constants(names, Constants.Spread):
            if c.entity_type == self.constants.entity_account:
                dto = ConstantsDTO(c)
                dtos.append(dto)
        return dtos

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

    def get_shell(self, id):
        q = self.constants.PosixShell(id)
        return ConstantsDTO(q)

    def get_shells(self):
        names = self._get_names("posix_shell_")
        return self._get_constant_dtos(names, Constants.PosixShell)

    def get_quarantine(self, id):
        q = self.constants.Quarantine(id)
        return ConstantsDTO(q)

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
