# -*- coding: iso-8859-1 -*-
import re

import cereconf
from Cerebrum.Utils import Factory

class DiskDef(object):
    def __init__(self, prefix=None, path=None, spreads=None, max=None,
                 disk_kvote=None, auto=None):
        self.prefix = prefix
        self.path = path
        self.spreads = spreads
        self.max = max
        self.disk_kvote = disk_kvote
        self.auto = auto
        self._cerebrum_disk = None

    def __repr__(self):
        return ("DiskDef(prefix=%s, path=%s, spreads=%s, max=%s, disk_kvote="
                "%s, auto=%s)") % (self.prefix, self.path, self.spreads,
                                   self.max, self.disk_kvote, self.auto)

class CerebrumDisk(object):
    def __init__(self, disk_id, path, count):
        self.disk_id = disk_id
        self.path = path
        self.count = count

    def alter_count(self, n):
        self.count += n

    def get_disk_def(self):
        pass

class DiskTool(object):
    def __init__(self, db, const):
        self._db = db
        self._const = const
        self._disk_spreads = {}
        self._cerebrum_disks = {}
        self._cerebrum_disks_order = []
        self.using_disk_kvote = False
        self._disk_def_by = {'path': {}, 'prefix': {}}
        self._disk_pools = {}
        self._disk_id2disk_def = {}

    def post_process(self):
        disk = Factory.get('Disk')(self._db)
        for d in disk.list(filter_expired=True,
                           spread=getattr(self._const, cereconf.HOME_SPREADS[0])):
            cd = CerebrumDisk(int(d['disk_id']), d['path'], int(d['count']))
            self._cerebrum_disks[int(d['disk_id'])] = cd
            tmp = self._disk_def_by['path'].get(d['path'])
            if tmp:
                tmp._cerebrum_disk = cd
            else:
                for tk, tv in self._disk_def_by['prefix'].items():
                    if d['path'].startswith(tk):
                        tmp = tv
                        break
            if tmp:
                self._disk_id2disk_def[int(d['disk_id'])] = tmp
                
        self._cerebrum_disks_order = self._cerebrum_disks.keys()
        self._cerebrum_disks_order.sort(self._disk_sort)

    def _disk_sort(self, x, y):
        regexp = re.compile(r"^(\D+)(\d*)")
        m_x = regexp.match(self._cerebrum_disks[x].path)
        m_y = regexp.match(self._cerebrum_disks[y].path)
        pre_x, num_x = m_x.group(1), m_x.group(2)
        pre_y, num_y = m_y.group(1), m_y.group(2)
        if pre_x <> pre_y:
            return cmp(pre_x, pre_y)
        try:
            return cmp(int(num_x), int(num_y))
        except ValueError:
            self._logger.warn("Unexpected disk name %s or %s" % (
                              self._cerebrum_disks[x].path, self._cerebrum_disks[y].path))
            return cmp(pre_x, pre_y)

    def append_to_pool(self, name, prefix=None, path=None):
        tmp = self.get_diskdef_by_select(prefix=prefix, path=path)
        self._disk_pools.setdefault(name, []).append(tmp)

    def add_disk_def(self, prefix=None, path=None, spreads=None, max=None,
                     disk_kvote=None, auto=None):
        disk = DiskDef(prefix, path, spreads, max, disk_kvote, auto)
        if prefix:
            self._disk_def_by['prefix'][prefix] = disk
        else:
            self._disk_def_by['path'][path] = disk

    def add_known_spread(self, spread_code):
        self._disk_spreads[spread_code] = True

    def get_known_spreads(self):
        return self._disk_spreads.keys()

    def get_diskdef_by_select(self, prefix=None, path=None, pool=None):
        if prefix:
            return self._disk_def_by['prefix'][prefix]
        elif path:
            return self._disk_def_by['path'][path]
        else:
            return self._disk_pools[pool]

    def get_diskdef_by_diskid(self, disk_id):
        return self._disk_id2disk_def.get(int(disk_id), None)

    def get_cerebrum_disk_from_diskdef(self, new_disk):
        if new_disk.path:
            # TBD: Should we ignore max_on_disk when path is explisitly set?
            return new_disk._cerebrum_disk

        dest_pfix = new_disk.prefix
        max_on_disk = new_disk.max
        if max_on_disk == -1:
            max_on_disk = 999999
        for d in self._cerebrum_disks_order:
            tmp_disk = self._cerebrum_disks[d]
            if (dest_pfix == tmp_disk.path[0:len(dest_pfix)]
                and tmp_disk.count < max_on_disk):
                 return d
        raise ProfileHandler.NoAvailableDisk,\
              "No disks with free space matches %s" % new_disk

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self._cerebrum_disks[int(old)].alter_count(-1)
        if new is not None:
            self._cerebrum_disks[int(new)].alter_count(+1)
    
