
from Cerebrum import Disk
from Cerebrum import Errors
import re


host_name_regex=re.compile("^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+$")


class HostNoturMixin(Disk.Host):
    def illegal_name(self, name):
        if not re.match(host_name_regex, name):
            return "misformed (%s)" % name
        return self.__super.illegal_name(name)


# arch-tag: b45a0f12-d609-11da-8b66-63efeac51fdb
