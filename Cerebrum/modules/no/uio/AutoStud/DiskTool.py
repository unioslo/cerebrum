# -*- coding: utf-8 -*-
import re

from six import python_2_unicode_compatible

import cereconf
from Cerebrum.Utils import Factory


_disk_sort_regex = re.compile(r"^(\D+)(\d*)")


class DiskSorters(object):
    """Mix-in for DiskDef/DiskPool"""

    def _disk_sort_by_count_key(self, name):
        return self._disks[name].count

    def _disk_sort_by_name_key(self, name):
        """
        Key function to sort cached disk name/identifier by disk path.
        """
        # Sort by disk prefix and then numerator
        matchres = _disk_sort_regex.match(self._disks[name].path)
        disk_prefix, raw_idx = matchres.group(1), matchres.group(2)
        try:
            disk_idx = int(raw_idx)
        except ValueError:
            disk_idx = 0
        return (disk_prefix, disk_idx)

    def _resort_disk_count(self):
        self._disk_count_order.sort(key=self._disk_sort_by_count_key)

    def post_filter_search_res(self, order, orderby, max=999999):
        """Do not allow results with more than max users on disk.  Try
        to avoid using disks with 0 users when ordering by count."""

        for allow_count0 in (False, True):
            for disk_id in order:
                cd = self._disks[disk_id]
                if cd.count >= max:
                    continue
                if orderby == 'name':
                    return cd
                if not allow_count0 and cd.count == 0:
                    continue
                return cd


@python_2_unicode_compatible
class DiskDef(DiskSorters):

    def __init__(self, disk_tool, prefix=None, path=None, spreads=None,
                 max=None, disk_kvote=None, auto=None, orderby=None):
        self._disk_tool = disk_tool
        self.prefix = prefix
        self.path = path
        self.spreads = spreads
        self.max = int(max)
        if orderby is None:
            self.orderby = 'name'
        else:
            self.orderby = orderby
        if self.max == -1:  # inifinive
            self.max = 999999
        if disk_kvote is not None:
            disk_kvote = int(disk_kvote)
        self.disk_kvote = disk_kvote
        self.auto = auto
        self._disks = self._find_cerebrum_disks()
        self._disk_name_order = list(self._disks)
        self._disk_name_order.sort(key=self._disk_sort_by_name_key)
        self._disk_count_order = list(self._disks)
        self._resort_disk_count()

    def __str__(self):
        return ("DiskDef(prefix={}, path={}, spreads={}, max={}, disk_kvote="
                "{}, auto={}, orderby={})").format(
            self.prefix, self.path, self.spreads, self.max,
            self.disk_kvote, self.auto, self.orderby)

    def _find_cerebrum_disks(self):
        ret = {}
        for cd in self._disk_tool._cerebrum_disks.values():
            if self.path and cd.path == self.path:
                return {cd.disk_id: cd}
            elif self.prefix and cd.path.startswith(self.prefix):
                ret[cd.disk_id] = cd
        return ret

    def get_cerebrum_disk(self, check_ok_to=False, _orderby=None):
        if _orderby is None:  # Used when called from DiskPool
            _orderby = self.orderby
        if check_ok_to and self.auto not in ('auto', 'to'):
            return
        if self.path:
            # we ignore max_on_disk when path is explisitly set
            return list(self._disks.values())[0]
        if _orderby == 'name':
            order = self._disk_name_order
        elif _orderby == 'count':
            self._resort_disk_count()
            order = self._disk_count_order
        return self.post_filter_search_res(order, _orderby, max=self.max)


class DiskPool(DiskSorters):

    def __init__(self, disk_tool, name, orderby=None):
        self._disk_tool = disk_tool
        self.name = name
        self.disk_defs = []
        self.spreads = []
        self.auto = None  # contains "max" auto for all its disk_defs
        if orderby is None:
            self.orderby = 'name'
        else:
            self.orderby = orderby

    def post_process(self):
        """Call once you have finished calling add_disk_def"""
        self._disks = self._find_cerebrum_disks()
        self._disk_name_order = list(self._disks)
        self._disk_name_order.sort(key=self._disk_sort_by_name_key)
        self._disk_count_order = list(self._disks)
        self._resort_disk_count()

    def _find_cerebrum_disks(self):
        ret = {}
        for dt in self.disk_defs:
            ret.update(dt._find_cerebrum_disks())
        return ret

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

    def get_cerebrum_disk(self, check_ok_to=False):
        # Find best disk for all disk_defs
        tmp = []
        for dd in self.disk_defs:
            cd = dd.get_cerebrum_disk(check_ok_to=check_ok_to,
                                      _orderby=self.orderby)
            if cd is not None:
                tmp.append(cd.disk_id)
        # Resort results
        if self.orderby == 'name':
            tmp.sort(key=self._disk_sort_by_name_key)
        else:
            self._resort_disk_count()
            tmp.sort(self._disk_sort_by_count_key)
        return self.post_filter_search_res(tmp, self.orderby)

    def __repr__(self):
        return ("DiskPool(name=%s, spreads=%s, auto=%s, orderby=%s, "
                "disk_defs=%s)") % (self.name, self.spreads, self.auto,
                                    self.orderby, self.disk_defs)


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
        self.using_disk_kvote = False
        self._disk_def_by = {'path': {}, 'prefix': {}}
        self._disk_pools = {}
        self._disk_id2disk_def = {}

        self._cerebrum_disks = {}
        disk = Factory.get('Disk')(self._db)
        for d in disk.list(
                filter_expired=True,
                spread=getattr(self._const, cereconf.HOME_SPREADS[0])):
            cd = CerebrumDisk(int(d['disk_id']), d['path'], int(d['count']))
            self._cerebrum_disks[int(d['disk_id'])] = cd

    def post_process(self):
        for cd in self._cerebrum_disks.values():
            tmp = self._disk_def_by['path'].get(cd.path)
            if tmp is None:
                for tk, tv in self._disk_def_by['prefix'].items():
                    if cd.path.startswith(tk):
                        tmp = tv
                        break
            if tmp:
                self._disk_id2disk_def[cd.disk_id] = tmp
        for dp in self._disk_pools.values():
            dp.post_process()

    def append_to_pool(self, name, orderby=None, prefix=None, path=None):
        tmp = self.get_diskdef_by_select(prefix=prefix, path=path)
        dp = self._disk_pools.setdefault(name, DiskPool(self, name, orderby))
        dp.add_disk_def(tmp)

    def add_disk_def(self, prefix=None, path=None, spreads=None, max=None,
                     disk_kvote=None, auto=None, orderby=None):
        disk = DiskDef(self, prefix, path, spreads, max, disk_kvote, auto,
                       orderby)
        if prefix:
            self._disk_def_by['prefix'][prefix] = disk
        else:
            self._disk_def_by['path'][path] = disk

    def add_known_spread(self, spread_code):
        self._disk_spreads[spread_code] = True

    def get_known_spreads(self):
        return list(self._disk_spreads)

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

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self._cerebrum_disks[int(old)].alter_count(-1)
        if new is not None:
            self._cerebrum_disks[int(new)].alter_count(+1)
