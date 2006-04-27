
from Cerebrum import Account
from Cerebrum import Errors
import re


account_name_regex=re.compile("^[a-z][a-z0-9]*$")

class AccountNTNUMixin(Account.Account):
    def illegal_name(self, name):
        if len(name) > 8:
            return "too long (%s)" % name
        if not re.match(account_name_regex, name):
            return "misformed (%s)" % name
        return self.__super.illegal_name(name)


# arch-tag: 115d851e-d604-11da-80dd-29649c6d89a0
