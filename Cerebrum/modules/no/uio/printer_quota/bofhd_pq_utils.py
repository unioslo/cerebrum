# -*- coding: iso-8859-1 -*-

from Cerebrum import Account
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas

class UserHasNoQuota(CerebrumError):
    pass

class NotFound(CerebrumError):
    pass

class BadQuotaValue(CerebrumError):
    pass

class BofhdUtils(object):
    def __init__(self, server):
        self.server = server
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.uname_cache = {}

    def get_pquota_status(self, person_id):
        ppq = PaidPrinterQuotas.PaidPrinterQuotas(self.db)
        try:
            row = ppq.find(person_id)
        except Errors.NotFoundError:
            raise UserHasNoQuota("User has no quota")
        return row
        
    def find_pq_person(self, fnr):
        """Returns person_id by doing fnr lookup in the order
        specified by 'betaling for utskrift': spesifikasjon.txt"""
        person = Person.Person(self.db)
        person.clear()
        for ss in (self.const.system_fs, self.const.system_lt,
                   self.const.system_manual):
            try:
                person.find_by_external_id(
                    self.const.externalid_fodselsnr, fnr, source_system=ss)
                return person.entity_id
            except Errors.NotFoundError:
                pass
        raise NotFound("No person with fnr=%s" % fnr)

    def _map_person_id(self, id_data):
        """Map <id_type:id> to const.<id_type>, id.  Recognizes
        fødselsnummer without <id_type>.  Also recognizes entity_id"""
        if id_data.isdigit() and len(id_data) >= 10:
            return self.const.externalid_fodselsnr, id_data
        if id_data.find(":") == -1:     # Assume it is an account
            return "account_name", id_data

        id_type, id_data = id_data.split(":", 1)
        if id_type != 'entity_id':
            id_type = self.const.PersonExternalId(id_type)
        if id_type is not None:
            return id_type, id_data
        raise CerebrumError, "Unknown person_id type"

    def find_person(self, id_data, id_type=None):
        """Return person_id matching id_data.  id_data can be an
        account name or an id_type:id string as well as an 11 digit
        fødselsnummer."""

        if not id_type:
            id_type, id_data = self._map_person_id(id_data)

        person = Person.Person(self.db)
        person.clear()
        try:
            if str(id_type) == 'account_name':
                ac = self.get_account(id_data)
                person.find(ac.owner_id)
            elif isinstance(id_type, Constants._CerebrumCode):
                if int(id_type) == int(self.const.externalid_fodselsnr):
                    return self.find_pq_person(id_data)
                person.find_by_external_id(id_type, id_data)
            elif id_type == 'entity_id':
                person.find(id_data)
            else:
                raise NotFound, "Unknown id_type"
        except Errors.NotFoundError:
            raise NotFound, "Could not find person with %s=%s" % (
                id_type, id_data)
        except Errors.TooManyRowsError:
            raise CerebrumError, "ID not unique %s=%s" % (id_type, id_data)
        return person.entity_id

    def get_uname(self, entity_id):
        if not self.uname_cache.has_key(entity_id):
            ac = self.get_account(entity_id, id_type='id')
            self.uname_cache[entity_id] = ac.account_name
        return self.uname_cache[entity_id]

    def get_account(self, id_data, id_type=None):
        account = Account.Account(self.db)
        account.clear()
        try:
            if id_type is None:
                if id_data.find(":") != -1:
                    id_type, id_data = id_data.split(":", 1)
                else:
                    id_type = 'name'
            if id_type == 'name':
                account.find_by_name(id_data, self.const.account_namespace)
            elif id_type == 'id':
                account.find(id_data)
            else:
                raise NotImplementedError, "unknown id_type: '%s'" % id_type
        except Errors.NotFoundError:
            raise CerebrumError(
                "Could not find Account with %s=%s" % (id_type, id_data))
        return account
