"""This is the only class that should be directly accessed within
this package"""
TOPICS_FILE="/cerebrum/dumps/FS/topics.xml"   # TODO: cereconf
STUDIEPROGS_FILE="/cerebrum/dumps/FS/studieprogrammer.xml"   # TODO: cereconf
STUDCONFIG_FILE="/cerebrum/uiocerebrum/etc/config/studconfig.xml"

from Cerebrum.modules.no.uio.AutoStud import ProfileConfig
from Cerebrum.modules.no.uio.AutoStud import ProfileHandler
from Cerebrum.modules.no.uio.AutoStud import StudentInfo

class AutoStud(object):
    def __init__(self, db, cfg_file=STUDCONFIG_FILE, debug=0,
                 studieprogs_file=STUDIEPROGS_FILE):
        self.debug = debug
        self._disks = {}
        if False:
            disk = Disk.Disk(db)
            for d in disk.list():
                self._disks[int(d['disk_id'])] = [d['path'], int(d['count'])]
            self._disks_order = self._disks.keys()
            self._disks_order.sort(self._disk_sort)
        self.pc = ProfileConfig.Config(db, debug=debug, cfg_file=cfg_file)

        self.studieprogramkode2info = {}
        for sp in StudentInfo.StudieprogDefParser(studieprogs_file=studieprogs_file):
            self.studieprogramkode2info[sp['studieprogramkode']] = sp

    def _disk_sort(self, x, y):
        regexp = re.compile(r"^(\D+)(\d*)")
        m_x = regexp.match(self._disks[x][0])
        m_y = regexp.match(self._disks[y][0])
        pre_x, num_x = m_x.group(1), m_x.group(2)
        pre_y, num_y = m_y.group(1), m_y.group(2)
        if pre_x <> pre_y:
            return cmp(pre_x, pre_y)
        return cmp(int(num_x), int(num_y))

    def start_student_callbacks(self, student_file, callback_func):
        StudentInfo.StudentInfoParser(student_file, callback_func)

    def get_profile(self, student_info, groups=None):
        """Returns a Profile object matching the topics, to check
        quotas, groups must also be set."""
        return ProfileHandler.Profile(self, student_info, groups)
