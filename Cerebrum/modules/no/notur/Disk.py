
from Cerebrum.modules import Host
from Cerebrum import Errors
import re


host_name_regex=re.compile("^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+$")


class HostNoturMixin(Disk.Host):
    def illegal_name(self, name):
        if not re.match(host_name_regex, name):
            return "misformed (%s)" % name
        return self.__super.illegal_name(name)


