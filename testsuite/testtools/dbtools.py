# -*- coding: utf-8 -*-
""" Database utils

This class contains database utils for Cerebrum tests.

This class helps with creating temporary objects in the database, for use in
tests. It's not as flexible as the API, but the idea is to generalize simple
tasks that needs to happen in the database before and after each test, in
different test cases.

"""
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Errors import NotFoundError

from Cerebrum.Account import Account
from Cerebrum.Person import Person
from Cerebrum.Group import Group
from Cerebrum.OU import OU
from Cerebrum.Constants import Constants


class DatabaseManager(object):
    """
    Tools for managing a database.

    This includes a 'python interface' for makedb, as well as methods for
    creating and dropping databases, running 'analyze' and 'vacuum' on
    postgres-databases, etc...
    """
    pass


class DatabaseTools(object):
    """
    Tools to read and write to and from a database transaction.
    """

    def __init__(self,
                 db_conn,
                 pe_cls=None,
                 ac_cls=None,
                 gr_cls=None,
                 co_cls=None,):
        """ Initialize with a Cerebrum.database. Database object."""
        self._db = db_conn
        self._db.commit = self._db.rollback

        if not isinstance(pe_cls, Person):
            pe_cls = Factory.get('Person')
        self._pe = pe_cls(self._db)

        if not isinstance(ac_cls, Account):
            ac_cls = Factory.get('Account')
        self._ac = ac_cls(self._db)

        if not isinstance(gr_cls, Group):
            gr_cls = Factory.get('Group')
        self._gr = gr_cls(self._db)

        if not isinstance(gr_cls, OU):
            ou_cls = Factory.get('OU')
        self._ou = ou_cls(self._db)

        if not isinstance(co_cls, Constants):
            co_cls = Factory.get('Constants')
        self._co = co_cls(self._db)

        self._init_account_id = None
        self._init_group_id = None

        self.constants = []
        self.account_ids = set()
        self.person_ids = set()
        self.group_ids = set()
        self.ou_ids = set()

    # Shared objects save time.
    # As long as we don't mind the objects being cleared by this objects,
    # we can save some time by fetching and sharing initialized
    # Cerebrum objects.

    def get_database_object(self):
        """Return a initialized, dynamic Cerebrum.database.Database object."""
        return self._db

    def get_person_object(self):
        """ Return a initialized, dynamic Cerebrum.Account object. """
        return self._pe

    def get_account_object(self):
        """ Return a initialized, dynamic Cerebrum.Account object. """
        return self._ac

    def get_group_object(self):
        """ Return a initialized, dynamic Cerebrum.Group object. """
        return self._gr

    def get_constants_object(self):
        """ Return a initialized, dynamic Cerebrum.Constants object. """
        return self._co

    def get_initial_account_id(self):
        """ Fetch and cache the entity_id of INITIAL_ACCOUNTNAME. """
        if not self._init_account_id:
            self._ac.clear()
            self._ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
            self._init_account_id = self._ac.entity_id
        return self._init_account_id

    def get_initial_group_id(self):
        """ Fetch and cache the entity_id of INITIAL_GROUPNAME. """
        if not self._init_group_id:
            self._gr.clear()
            self._gr.find_by_name(cereconf.INITIAL_GROUPNAME)
            self._init_group_id = self._gr.entity_id
        return self._init_group_id

    def insert_constant(self, code_cls, *args, **kwargs):
        """ Create, insert, and return a constant in the database. """
        if not issubclass(code_cls, _CerebrumCode):
            raise ValueError("Code class must be subclass of %s" %
                             str(_CerebrumCode))

        constant = code_cls(*args, **kwargs)
        constant.set_sql(self._db)
        constant.insert()
        self.constants.append(constant)
        return constant

    def delete_constant(self, constant):
        """ Delete a given constant created by this class. """
        if not isinstance(constant, _CerebrumCode):
            raise ValueError("Code class must be instance of %s" %
                             str(_CerebrumCode))

        self.constants.remove(constant)
        constant.delete()

    def clear_constants(self):
        """ Delete all constants created by this class. """
        for constant in self.constants[:]:
            self.delete_constant(constant)

        for constant in self.constants:
            assert False, "All constants should be gone by now"

    # Helpers to create and remove accounts

    def create_account(self, account_dict, person_owner_id=None):
        """ Create an acocunt based on dict values.

        @type account_dict: dict
        @param account_dict: A dictionary with values for:
             - account_name: str (mandatory)
             - password: str or None (optional)
             - expire_date: mx.DateTime.DateTime or None (optional)

        @type person_owner_id: int, NoneType
        @param person_owner_id: The entity_id of person to set as account
            owner. If no owner is given, the INITIAL_GROUPNAME is set as owner,
            and the account type is set to 'programvare'.

        @rtype: int
        @return: The entity_id of the newly created account.

        """
        creator_id = self.get_initial_account_id()

        if person_owner_id is not None:
            owner_id = person_owner_id
            owner_type = self._co.entity_person
            account_type = None
        else:
            owner_id = self.get_initial_group_id()
            owner_type = self._co.entity_group
            account_type = self._co.account_program

        self._ac.clear()
        self._ac.populate(account_dict['account_name'], owner_type, owner_id,
                          account_type, creator_id,
                          account_dict.get('expire_date'))
        self._ac.write_db()
        if account_dict.get('password'):
            self._ac.set_password(account_dict.get('password'))
            self._ac.write_db()
        entity_id = self._ac.entity_id
        self.account_ids.add(entity_id)
        return entity_id

    def delete_account_id(self, entity_id):
        """ Delete account with given entity_id. """
        self._ac.clear()
        try:
            self._ac.find(entity_id)
        except NotFoundError:
            pass
        else:
            self._ac.delete()
        finally:
            if entity_id in self.account_ids:
                self.account_ids.remove(entity_id)

    def clear_accounts(self):
        """ Clear accounts created by this class. """
        for entity_id in self.account_ids.copy():
            self.delete_account_id(entity_id)

        for entity_id in self.account_ids:
            assert False, "All accounts should be deleted"

    # Helpers to create and remove persons

    def create_person(self, person_dict):
        """ Create a person based on dict values.

        @type person_dict: dict
        @param person_dict: A dictionary with values for:
             - birth_date: mx.DateTime.DateTime (mandatory)
             - gender: Cerebrum.Constants.GenderCode, str, NoneType (optional)

        @rtype: int
        @return: The entity_id of the newly created person.

        """
        gender = person_dict.get('gender')
        if not gender:
            gender = self._co.gender_unknown
        elif not isinstance(gender, _CerebrumCode):
            gender = self._co.human2constant(
                gender, type(self._co.gender_unknown))

        self._pe.clear()
        self._pe.populate(person_dict['birth_date'], gender,
                          person_dict.get('description'))

        self._pe.write_db()
        entity_id = self._pe.entity_id
        self.person_ids.add(entity_id)
        return entity_id

    def delete_person_id(self, entity_id):
        """ Delete account with given entity_id. """
        self._pe.clear()
        try:
            self._pe.find(entity_id)
        except NotFoundError:
            pass
        else:
            self._pe.delete()
        finally:
            if entity_id in self.person_ids:
                self.person_ids.remove(entity_id)

    def clear_persons(self):
        """ Clear accounts created by this class. """
        for entity_id in self.person_ids.copy():
            self.delete_person_id(entity_id)

        for entity_id in self.person_ids:
            assert False, "All persons should be deleted"

    # Helpers to create and remove groups

    def create_group(self, group_dict):
        """ Create a group based on dict values.

        @type group_dict: dict
        @param group_dict: A dictionary with values for:
             - group_name: str (mandatory)
             - description: str (optional)

        @rtype: int
        @return: The entity_id of the newly created group.

        """
        creator_id = self.get_initial_account_id()
        self._gr.clear()
        self._gr.populate(creator_id, self._co.group_visibility_all,
                          group_dict['group_name'], group_dict['description'])
        self._gr.expire_date = group_dict.get('expire_date')
        self._gr.write_db()
        entity_id = self._gr.entity_id
        self.group_ids.add(entity_id)
        return entity_id

    def delete_group_id(self, entity_id):
        """ Delete group with given entity_id. """
        self._gr.clear()
        try:
            self._gr.find(entity_id)
        except NotFoundError:
            pass
        else:
            self._gr.delete()
        finally:
            if entity_id in self.group_ids:
                self.group_ids.remove(entity_id)

    def clear_groups(self):
        """ Delete all groups created by a DatabaseTools object. """
        for entity_id in self.group_ids.copy():
            self.delete_group_id(entity_id)

        for entity_id in self.group_ids:
            assert False, "All groups should be deleted"

    # Helpers to create and remove OUs

    def create_ou(self, ou_dict):
        """ Create an OU based on dict values.

        :type dict ou_dict:
            Given values to set for the OU that should get created. Values that
            are used:

            - name
            - acronym
            - short_name
            - display_name

        :rtype: int
        :return: The entity_id for the new OU

        """
        creator_id = self.get_initial_account_id()
        self._ou.clear()
        self._ou.populate()
        self._ou.write_db()
        for nametype in (self._co.ou_name, self._co.ou_name_acronym,
                         self._co.ou_name_short, self._co.ou_name_display):
            if str(nametype) in ou_dict:
                self._ou.add_name_with_language(
                                name_variant=nametype,
                                name_language=self._co.language_en,
                                name=ou_dict[str(nametype)])
                self._ou.write_db()
        self.ou_ids.add(self._ou.entity_id)
        return self._ou.entity_id

    def delete_ou_id(self, entity_id):
        """ Delete OU with given entity_id. """
        self._ou.clear()
        try:
            self._ou.find(entity_id)
        except NotFoundError:
            pass
        else:
            self._ou.delete()
        finally:
            if entity_id in self.ou_ids:
                self.ou_ids.remove(entity_id)

    def clear_ous(self):
        """ Delete all OUs created by a DatabaseTools object. """
        for entity_id in self.ou_ids.copy():
            self.delete_ou_id(entity_id)

        for entity_id in self.ou_ids:
            assert False, "All OUs should be deleted"
