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
            for spread in disk.keys():
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

    def _solve_disk_match(self, disk_spread):
        potential_disks = []
        tmp_nivaakode = None

        # Determine all disks at the highest nivaakode, and make a list
        # with (setting, [all profilenames with this setting])
        for d, n, profile_names in self.matcher.get_raw_match('disk'):
            if disk_spread not in d.keys():
                continue            # Incorrect spread for this disk
            if not tmp_nivaakode:
                tmp_nivaakode = n
            if n != tmp_nivaakode:  # This disk is at a lower nivåkode
                break
            appended = False
            for tmp_d, tmp_pnames in potential_disks:
                if tmp_d == d[disk_spread]:
                    tmp_pnames.extend(profile_names)
                    appended = True
                    break
            if not appended:
                potential_disks.append((d[disk_spread], profile_names))
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
            if tmp_nivaakode < 300:
                # TODO: These cereconf variables should actually be
                # read from the xml file
                new_disk = cereconf.AUTOADMIN_DIV_LGRAD_DISK
            else:
                new_disk = cereconf.AUTOADMIN_DIV_HGRAD_DISK
        else:
            new_disk = potential_disks[0][0]
        self._logger.debug2("Result: %s" % repr(new_disk))
        return new_disk
    
    def get_disk(self, disk_spread, current_disk=None):
        """Return a disk_id matching the current profile.  If the
        account already exists, current_disk should be set to assert
        that the user is not moved to a new disk with the same
        prefix. (i.e from /foo/bar/u11 to /foo/bar/u12)"""

        # TBD: The above statement is incorrect; we will only move a
        # user if it no longer matches a profile with the users
        # current disk.  Is this the correct behaviour?

        # Detect conflicting disks at same 'nivåkode'
        disk_spread = int(disk_spread)

        new_disk = self._solve_disk_match(disk_spread)

        # Check if one of the matching disks matches the disk that the
        # user currently is on
        if current_disk is not None:
            if not self.pc.autostud.student_disk.has_key(int(current_disk)):
                return current_disk
            matches = self.matcher.get_match("disk")[:]
            if new_disk is not None:   # avoid moving users between div disks
                matches.append({disk_spread: new_disk})
            for d in matches:
                if disk_spread not in d.keys():
                    continue            # Incorrect spread for this disk
                d = d[disk_spread]
                if d.has_key('path'):
                    if d['path'] == current_disk:
                        return current_disk
                else:
                    disk_path = self.pc.autostud.disks[int(current_disk)][0]
                    if d['prefix'] == disk_path[0:len(d['prefix'])]:
                        return current_disk

        if new_disk.has_key('pool'):
            tmp = self.pc.disk_pools[new_disk['pool']]
        else:
            tmp = [new_disk]
        for new_disk in tmp:
            if new_disk.has_key('path'):
                # TBD: Should we ignore max_on_disk when path is explisitly set?
                return new_disk['path']

            dest_pfix = new_disk['prefix']
            max_on_disk = int(self.pc.disk_defs['prefix'][dest_pfix]['max'])
            if max_on_disk == -1:
                max_on_disk = 999999
            for d in self.pc.autostud.disks_order:
                tmp_path, tmp_count = self.pc.autostud.disks[d]
                if (dest_pfix == tmp_path[0:len(dest_pfix)]
                    and tmp_count < max_on_disk):
                     return d
        raise NoAvailableDisk, "No disks with free space matches %s" % new_disk

    def get_disk_kvote(self, disk_id):
        self._logger.debug2("Determine disk_quota (disk_id=%i)" % disk_id)
        # Look for profile match
        for m in self.matcher.get_match("disk_kvote"):
            self._logger.debug2("get_disk_kvote <tag>: %s" % m)
            return int(m['value'])
        # Look for match by diskdef
        quota = self.pc.disk_defs['path'].get(disk_id, {}).get('disk_kvote', None)
        if quota is not None:
            return quota
        disk = Disk.Disk(self.pc.autostud.db)
        disk.find(disk_id)
        for prefix, settings in self.pc.disk_defs['prefix'].items():
            if prefix == disk.path[:len(prefix)]:
                quota = self.pc.disk_defs['prefix'][prefix]['disk_kvote']
                self._logger.debug2("Match: %s - %s: %s" % (prefix, disk.path, quota))
                return int(quota)
        if self.pc.default_values.has_key('disk_kvote_value'):
            return int(self.pc.default_values['disk_kvote_value'])
        raise AutostudError("No defined disk_kvote")

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self.pc.autostud.disks[int(old)][1] -= 1
        if new is not None:
            self.pc.autostud.disks[new][1] += 1

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
