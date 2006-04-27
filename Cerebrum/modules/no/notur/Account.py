
from Cerebrum import Account
from Cerebrum import Errors
import re

account_name_regex=re.compile("^[a-z][a-z0-9]*$")

class AccountNoturMixin(Account.Account):
    def illegal_name(self, name):
        if len(name) > 8:
            return "too long (%s)" % name
        if not re.match(account_name_regex, name):
            return "misformed (%s)" % name
        return self.__super.illegal_name(name)


# arch-tag: e686edd2-d606-11da-94e0-9b20a5786e63
