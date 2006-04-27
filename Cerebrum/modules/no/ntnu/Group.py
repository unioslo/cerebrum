
from Cerebrum import Group
from Cerebrum import Errors
import re

group_name_regex=re.compile("^[a-z][a-z0-9_]*$")

class GroupNTNUMixin(Group.Group):
    def illegal_name(self, name):
        if len(name) > 16:
            return "too long (%s)" % name
        if not re.match(group_name_regex, name):
            return "misformed (%s)" % name
        return self.__super.illegal_name(name)


# arch-tag: 11c6f04e-d604-11da-957b-a2951bfbed57
