import logging

import six

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (
    Command,
    FormatSuggestion,
    PersonId,
    SimpleString,
)
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.no.dfo.tasks import EmployeeTasks
from Cerebrum.modules.no.uio.bofhd_auth import UioAuth
from Cerebrum.modules.tasks.task_queue import TaskQueue, sql_search


logger = logging.getLogger(__name__)


class BofhdHrImportAuth(UioAuth):

    def can_run_program(self, operator, query_run_any=False):
        has_acess = self.is_superuser(operator)
        if query_run_any or has_acess:
            return has_acess
        raise PermissionDenied('Can not show user info')


class CsnExtension(BofhdCommonMethods):

    all_commands = {}
    authz = BofhdHrImportAuth

    all_commands['show_user'] = Command(
        ('show', 'user'),
        PersonId(help_ref="id:target:person"),
        fs=FormatSuggestion([
            ("Name:          %s\n"
             "Entity-id:     %i\n"
             "E-mail:       %s\n"
             "Affiliated accounts:  %s\n"
             "Quarantine: %s", ("name", "entity_id", "e_mail", 'other', 'quarantine'))
        ]),
        perm_filter='can_run_program')

    def show_user(self, operator, accountname):
        account = self._get_account(accountname)
        data = [{
            'name': account.get_fullname(),
            'entity_id': account.entity_id,
            'e_mail':account.get_primary_mailaddress(),
            'other': [i[0] for i in account.list_accounts_by_owner_id(account.owner_id)],
            'quarantine': 'No'
        }]
        if len(account.get_entity_quarantine()) >0:
            data[-1]['quarantine'] = 'Yes'

        return data
