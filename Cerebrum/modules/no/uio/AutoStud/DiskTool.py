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
        if max is not None:
            self.max = int(max)
        if disk_kvote is not None:
            disk_kvote = int(disk_kvote)
        self.disk_kvote = disk_kvote
        self.auto = auto
        self._cerebrum_disk = None

    def __repr__(self):
        return ("DiskDef(prefix=%s, path=%s, spreads=%s, max=%s, disk_kvote="
                "%s, auto=%s)") % (self.prefix, self.path, self.spreads,
                                   self.max, self.disk_kvote, self.auto)

class DiskPool(object):
    def __init__(self, name):
        self.name = name
        self.disk_defs = []
        self.spreads = []
        self.auto = None # contains "max" auto for all its disk_defs

    def add_disk_def(self, ddef):
        self.disk_defs.append(ddef)
        self.spreads.extend(
            [x for x in ddef.spreads if x not in self.spreads])
        tmp = [d.auto for d in self.disk_defs]
        if 'auto' in tmp:
            self.auto = 'auto'
        elif 'to' in tmp:
            self.auto = 'to'
        else:
            # 'from' has no meaining in a disk_pool as
            # get_diskdef_by_diskid won't return a pool
            self.auto = None

    def __repr__(self):
        return "DiskPool(name=%s, spreads=%s, auto=%s, disk_defs=%s)" % (
            self.name, self.spreads, self.auto, self.disk_defs)

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
        dp = self._disk_pools.setdefault(name, DiskPool(name))
        dp.add_disk_def(tmp)

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

    def get_cerebrum_disk_by_diskid(self, disk_id):
        return self._cerebrum_disks[disk_id]
    
    def get_cerebrum_disk_from_diskdef(self, new_disk, check_ok_to=False):
        # avoid circular dependency while allowing use of
        # ProfileHandler.NoAvailableDisk
        from Cerebrum.modules.no.uio.AutoStud import ProfileHandler
        def _find_free_disk(new_disk):
            if new_disk.path:
                # TBD: Should we ignore max_on_disk when path is explisitly set?
                return new_disk._cerebrum_disk.disk_id

            dest_pfix = new_disk.prefix
            max_on_disk = new_disk.max
            if max_on_disk == -1:
                max_on_disk = 999999
            for d in self._cerebrum_disks_order:
                tmp_disk = self._cerebrum_disks[d]
                if (dest_pfix == tmp_disk.path[0:len(dest_pfix)]
                    and tmp_disk.count < max_on_disk):
                    return d
            return None

        if isinstance(new_disk, DiskDef):
            new_disk = [new_disk]
        elif isinstance(new_disk, DiskPool):
            new_disk = new_disk.disk_defs
        for d in new_disk:
            ret = _find_free_disk(d)
            if ret is not None:
                return ret
        raise ProfileHandler.NoAvailableDisk,\
              "No disks with free space matches %s" % new_disk

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self._cerebrum_disks[int(old)].alter_count(-1)
        if new is not None:
            self._cerebrum_disks[int(new)].alter_count(+1)
    
# arch-tag: 4ca25096-b693-11d9-9ffc-7680148697de
