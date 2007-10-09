
import cerebrum_path
import cereconf
import MySQLdb
from Cerebrum.Utils import read_password


class Gruppesenter(object):
    def __init__(self):
        self.connection = MySQLdb.Connection(user = cereconf.GRUPPESENTER_USER,
            passwd = read_password(cereconf.GRUPPESENTER_USER, "Gruppesenter"),
            db = cereconf.GRUPPESENTER_DB,
            host = cereconf.GRUPPESENTER_HOST)
        
        self.cursor=self.connection.cursor()

    def get_groups(self):
        groups = {}

        self.cursor.execute("""SELECT group_name, unix_gid, description,
        relation, closed
        FROM groups WHERE closed = 0""")
        group_result = self.cursor.fetchall()

        for g in group_result:
            group = {}
            group['name'] = g[0]
            group['unix_gid'] = g[1]
            group['description'] = g[2]
            group['relation'] = g[3]
            group['members'] = []
            group['group_members'] = []
            groups[group['name']] = group

        self.cursor.execute("""SELECT m.group_name, m.member, m.flags
        FROM members m, groups g
        WHERE g.group_name = m.group_name AND g.closed = 0""")
        member_result = self.cursor.fetchall()

        for m in member_result:
            name = m[0]
            member = m[1]
            flags = m[2]
            group = groups[name]
            if flags & 1:
                group['group_members'].append(member)
            else:
                group['members'].append(member)

        return groups.values()
