# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import pprint

import cereconf
from Cerebrum.modules.no import fodselsnr
from Cerebrum import Disk
from Cerebrum.modules.no.uio.AutoStud.ProfileConfig import StudconfigParser
from Cerebrum.modules.no.uio.AutoStud.Util import AutostudError
from Cerebrum.modules.no.uio.AutoStud.DiskTool import DiskDef

pp = pprint.PrettyPrinter(indent=4)

class NoMatchingQuotaSettings(AutostudError): pass
class NoMatchingProfiles(AutostudError): pass
class NoAvailableDisk(AutostudError): pass
class NoDefaultGroup(AutostudError): pass

class Profile(object):
    """Profile implements the logic that maps a persons student_info
    (and optionaly groups) to the apropriate home, default group etc
    using rules read by the StudconfigParser."""

    def __init__(self, student_info, logger, pc, member_groups=None,
                 person_affs=None):
        """The logic for resolving conflicts and enumerating settings
        is similar for most attributes, thus we resolve the settings
        applicatble for this profile in the constructor
        """

        # topics may contain data from get_studieprog_list
        self._logger = logger
        self.pc = pc
        
        reserve = 0
        mail_user = 0
        full_account = 0
        
        self.matcher = ProfileMatcher(pc, student_info, logger,
                                      member_groups=member_groups,
                                      person_affs=None)

    def get_disk_spreads(self):
        tmp = {}
        for disk in self.matcher.get_match("disk"):
            for spread in disk.spreads:
                tmp[int(spread)] = 1
        return tmp.keys()

    # remove any disks where its matching profile is the child of
    # another profile that has a matching disk
    def _check_elimination(self, candidate, original):
        """Check if candidate can be completly eliminated by
        looking in the profiles in original and their parents.
        Will remove the entries in 'candidate' that matches.
        """
        self._logger.debug2("_check_elimination: %s, %s" % (candidate, original))
        
        n = len(candidate) - 1
        while n >= 0:
            for o in original:
                self._logger.debug2("supr-check: %s in %s" % (
                    candidate[n], self.pc.profilename2profile[o].super_names))
                if (candidate[n] == o or
                    candidate[n] in self.pc.profilename2profile[o].super_names):
                    del(candidate[n])
                    break
            n -= 1
        if candidate:
            return False
        return True

    def _get_potential_disks(self, disk_spread, only_to=False):
        """Determine all disks at the highest nivaakode, and make a
        list with (setting, [all profilenames with this setting]).
        Will expand disk-pools"""
        
        potential_disks = []
        tmp_nivaakode = None

        def _do_append(disk_def):
            if only_to:
                if disk_def.auto not in ('auto', 'to'):
                    self._logger.debug2("Not to %s" % repr(tmp))
                    return

            appended = False
            for tmp_d, tmp_pnames in potential_disks:
                if tmp_d == disk_def:
                    tmp_pnames.extend(profile_names)
                    appended = True
                    break
            if not appended:
                potential_disks.append((disk_def, profile_names))

        for d, n, profile_names in self.matcher.get_raw_match('disk'):
            if disk_spread not in d.spreads:
                continue            # Incorrect spread for this disk
            if not tmp_nivaakode:
                tmp_nivaakode = n
            if n != tmp_nivaakode:  # This disk is at a lower nivåkode
                break
            if isinstance(d, DiskDef):
                _do_append(d)
            else:               # disk pool
                for d2 in d:
                    _do_append({disk_spread: d2})
        return tmp_nivaakode, potential_disks

    def _solve_disk_match(self, disk_spread):
        tmp_nivaakode, potential_disks = self._get_potential_disks(
            disk_spread, only_to=True)
        if not potential_disks:
            raise NoAvailableDisk, "No disk matches profiles"
        self._logger.debug2("Resolve %s" % potential_disks)

        # Iterate over all potential disks
        i1 = len(potential_disks) - 1
        while i1 >= 0:
            original = potential_disks[i1]
            i2 = len(potential_disks) - 1
            did_del = False
            # Then call check_elimination for all the other disks, and
            # remove those that may be omitted.  Everytime we remove
            # something, we restart the outer loop
            
            while i2 >= 0:
                if i1 != i2:
                    self._logger.debug2("i1 = %i, i2 = %i" % (i1, i2))
                    candidate = potential_disks[i2]
                    if self._check_elimination(candidate[1], original[1]):
                        did_del = True
                        del(potential_disks[i2])
                i2 -= 1
            i1 -= 1
            if did_del:
                i1 = len(potential_disks) - 1
        if len(potential_disks) > 1:
            if tmp_nivaakode < 500:
                # TODO: These cereconf variables should actually be
                # read from the xml file
                new_disk = self.pc.autostud.disk_tool.get_diskdef_by_select(
                    cereconf.AUTOADMIN_DIV_LGRAD_DISK)
            else:
                new_disk = self.pc.autostud.disk_tool.get_diskdef_by_select(
                    cereconf.AUTOADMIN_DIV_HGRAD_DISK)
        else:
            new_disk = potential_disks[0][0]
        self._logger.debug2("Result: %s" % repr(new_disk))
        return new_disk

    def _check_move_ok(self, current_disk, extra_match, disk_spread):
        """We only move the user if:
        * it is OK to move the user from the disk it resides on
        * the user currently does not reside on a disk that matches"""

        disk_def = self.pc.autostud.disk_tool.get_diskdef_by_diskid(current_disk)
        if not disk_def or disk_def.auto not in ('auto', 'from'):
            return False   # Won't move users from this disk

        matches = [p[0] for p in self._get_potential_disks(
            disk_spread, only_to=True)[1]]

        if extra_match:
            matches.append(extra_match)  # in case we also match a div-disk

        # Check if user already is on a matching disk
        for d in matches:
            if d.path:
                if d.path == current_disk:
                    return False
            else:
                disk_path = self.pc.autostud.disks[int(current_disk)][0]
                if d.prefix == disk_path[0:len(d.prefix)]:
                    return False
        return True

    def get_disk(self, disk_spread, current_disk=None):
        """Return a disk_id matching the current profile.  If the
        account already exists, current_disk should be set to assert
        that the user is not moved to a new disk with the same
        prefix. (i.e from /foo/bar/u11 to /foo/bar/u12)"""

        # Detect conflicting disks at same 'nivåkode'
        disk_spread = int(disk_spread)

        new_disk = self._solve_disk_match(disk_spread)
        if current_disk and not self._check_move_ok(
            current_disk, new_disk, disk_spread):
            self._logger.debug2("_check_move_ok not ok %s" % repr((current_disk, new_disk)))
            return current_disk

        return self.pc.autostud.disk_tool.get_cerebrum_disk_from_diskdef(new_disk)

    def get_disk_kvote(self, disk_id):
        self._logger.debug2("Determine disk_quota (disk_id=%i)" % disk_id)
        # Look for profile match
        max_quota = 0
        for m in self.matcher.get_match("disk_kvote"):
            self._logger.debug2("get_disk_kvote <tag>: %s" % m)
            if int(m['value']) > max_quota:
                max_quota = int(m['value'])
        if max_quota > 0:
            return max_quota
        # Look for match by diskdef
        disk_def = self.pc.autostud.disk_tool.get_diskdef_by_diskid(disk_id)
        if disk_def.disk_kvote:
            return disk_def.disk_kvote
        if self.pc.default_values.has_key('disk_kvote_value'):
            return int(self.pc.default_values['disk_kvote_value'])
        raise AutostudError("No defined disk_kvote")

    def get_brev(self):
        for b in self.matcher.get_match("brev"):
            return b
        return None  # TBD: Raise error?
        
    def get_printer_kvote_fritak(self):
        return self.matcher.get_match("print_kvote_fritak") and 1 or 0

    def get_printer_betaling_fritak(self):
        return self.matcher.get_match("print_betaling_fritak") and 1 or 0

    def get_build(self):
        home = False
        action = False
        for build in self.matcher.get_match("build"):
            if build.get('action', '') == 'true':
                action = True
            if build.get('home', '') == 'true':
                home = True
        return {'home': home, 'action': action}

    def get_stedkoder(self):
        return self.matcher.get_match("stedkode")

    def get_dfg(self):
        for t in self.matcher.get_match('primarygroup'):
            if self.pc.group_defs[t]['is_posix']:
                return t
        for t in self.matcher.get_match('gruppe'):
            if self.pc.group_defs[t]['is_posix']:
                return t
        raise NoDefaultGroup, "No dfg is a PosixGroup"

    def get_grupper(self):
        return self.matcher.get_match('gruppe')

    def get_spreads(self):
        return self.matcher.get_match('spread')

    def get_quarantines(self):
        """Returns [{'quarantine': QuarantineCode, 'start_at': seconds}]"""
        return self.matcher.get_match("quarantine")

    def get_pquota(self, as_list=False):
        """Return information about printerquota.  Throws a
        NoMatchingQuotaSettings if profile has no quota information

        as_list=False is for the old quota system"""
        if as_list:
            return self.matcher.get_match('printer_kvote')
        ret = {}
        if not self.matcher.get_match('printer_kvote'):
            raise NoMatchingQuotaSettings, "No matching quota settings"
        for m in self.matcher.get_match('printer_kvote'):
            for k in ('start', 'uke', 'max_akk', 'max_sem'):
                if ret.get(k, '') == 'UL':
                    continue
                if m[k] == 'UL':
                    ret[k] = m[k]
                else:
                    try:
                        ret[k] = int(ret.get(k, 0)) + int(m[k])
                    except ValueError:
                        self._logger.warn("Bad value: %s / %s" % (ret.get(k, 0), m[k]))
        return {
            'initial_quota': ret['start'],
            'weekly_quota': ret['uke'],
            'max_quota': ret['max_akk'],
            'termin_quota': ret['max_sem']
            }

class ProfileMatcher(object):
    """Methods for determining which profiles matches a given
    person."""

    def __init__(self, pc, student_info, logger, member_groups=None,
                 person_affs=None):
        self.pc = pc
        self.logger = logger
        self._matches, self._matched_settings = pc.select_tool.get_person_match(
            student_info, member_groups=member_groups, person_affs=person_affs)
        if not self._matched_settings:
            raise NoMatchingProfiles, "No matching profiles"

    def get_match(self, match_type):
        return [x[0] for x in self._matched_settings.get(match_type, [])]

    def get_raw_match(self, match_type):
        return self._matched_settings.get(match_type, [])

    def debug_dump(self):
        ret = "Dumping %i match entries\n" % len(self._matches)
        ret += pp.pformat(self._matches)
        ret += "\nSettings: "
        ret += pp.pformat(self._matched_settings)
        return ret


# arch-tag: 729aa779-5820-442a-aad6-31e56666d9ae
