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

from Cerebrum.modules.no.uio.AutoStud.ProfileConfig import StudconfigParser

class Profile(object):
    """Profile implements the logic that maps a persons student_info
    (and optionaly groups) to the apropriate home, default group etc
    using rules read by the StudconfigParser."""

    def __init__(self, student_info, logger, pc, member_groups=None):
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
                                      member_groups=member_groups)


    def debug_dump(self):
        ret = "Dumping %i match entries\n" % len(self.matcher.matches)
        ret += self._logger.pformat(self.matcher.matches)
        ret += "\nSettings: "
        ret += self._logger.pformat(self.matcher.settings)
        ret += "\nToplevel: "
        ret += self._logger.pformat(self.matcher.toplevel_settings)
        return ret
    
    def get_disk(self, current_disk=None):
        """Return a disk_id matching the current profile.  If the
        account already exists, current_disk should be set to assert
        that the user is not moved to a new disk with the same
        prefix. (i.e from /foo/bar/u11 to /foo/bar/u12)"""

        disks = self.matcher.toplevel_settings.get("disk", [])
        if len(disks) == 0:
            raise ValueError, "No disk matches profiles"
        # Detect conflicting disks at same 'nivåkode'
        tmp = disks[0]
        for d in disks:
            if d != tmp:
                for tmp in self.matcher.matches:
                    profile, nivaakode = tmp
                    if profile.settings.has_key("disk"):
                        if nivaakode < 300:  # TODO: don't hardcode these
                            disks = [{'prefix': '/uio/kant/div-l'}]
                        else:
                            disks = [{'prefix': '/uio/kant/div-h'}]
                break
        if current_disk is not None:
            if not self.pc.autostud.student_disk.has_key(int(current_disk)):
                return current_disk
            for d in disks:
                if d.has_key('path'):
                    if d['path'] == current_disk:
                        return current_disk
                else:
                    disk_path = self.pc.autostud.disks[int(current_disk)][0]
                    if d['prefix'] == disk_path[0:len(d['prefix'])]:
                        return current_disk
        disk = disks[0]
        if disk.has_key('path'):
            # TBD: Should we ignore max_on_disk when path is explisitly set?
            return disk['path']

        dest_pfix = disk['prefix']
        max_on_disk = int(self.pc.disk_defs['prefix'][dest_pfix]['max'])
        if max_on_disk == -1:
            max_on_disk = 999999
        for d in self.pc.autostud.disks_order:
            tmp_path, tmp_count = self.pc.autostud.disks[d]
            if (dest_pfix == tmp_path[0:len(dest_pfix)]
                and tmp_count < max_on_disk):
                 return d
        raise ValueError, "Bad disk %s" % disk

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self.pc.autostud.disks[int(old)][1] -= 1
        if new is not None:
            self.pc.autostud.disks[new][1] += 1

    def get_brev(self):
        return self.matcher.settings.get("brev", [None])[0]
        
    def get_stedkoder(self):
        return self.matcher.settings.get("stedkode", [])

    def get_dfg(self):
        for t in self.matcher.toplevel_settings.get('primarygroup', []):
            if self.pc.group_defs[t]['is_posix']:
                return t
        for t in self.matcher.toplevel_settings['gruppe']:
            if self.pc.group_defs[t]['is_posix']:
                return t
        for t in self.matcher.settings.get('gruppe', []):
            if self.pc.group_defs[t]['is_posix']:
                return t
        raise ValueError, "No dfg is a PosixGroup"

    def get_grupper(self):
        return self.matcher.settings.get('gruppe', [])

    def get_spreads(self):
        return self.matcher.settings.get('spread', [])

    def get_pquota(self):
        """Return information about printerquota.  Throws a ValueError
        if profile has no quota information"""
        ret = {}
        if not self.matcher.settings.has_key('printer_kvote'):
            raise ValueError, "No matching quota settings"
        for m in self.matcher.settings.get('printer_kvote', []):
            for k in ('start', 'uke', 'max_akk', 'max_sem'):
                if m[k] == 'UL':
                    ret[k] = m[k]
                else:
                    ret[k] = ret.get(k, 0) + int(m[k])
        return {
            'initial_quota': ret['start'],
            'weekly_quota': ret['uke'],
            'max_quota': ret['max_akk'],
            'termin_quota': ret['max_sem']
            }

class ProfileMatcher(object):
    """Methods for determining which profiles matches a given
    person."""

    def __init__(self, pc, student_info, logger, member_groups=None):
        self.pc = pc
        self.matches = []
        self.logger = logger
        self.matching_selectors = {}
        self._process_person_info(student_info, member_groups=member_groups)
        self.logger.debug("Matching profiles: %s" % self.matches)
        if len(self.matches) == 0:
            raise ValueError, "No matching profiles"
        self.settings = {}
        self.toplevel_settings = {}
        self._resolve_matches()

    def _process_person_info(self, student_info, member_groups=[]):
        """Check if student_info contains data of the type identified
        by StudconfigParser.select_elements.  If yes, check if the
        corresponding value matches a profile."""

        # Find the select_map_defs that map to data in student_info
        for select_type in StudconfigParser.select_map_defs.keys():
            map_data = StudconfigParser.select_map_defs[select_type]
            if map_data[0] == StudconfigParser.NORMAL_MAPPING:
                for entry in student_info.get(map_data[2], []):
                    value = entry[map_data[3]]
                    self._check_match(select_type, value)
            else:
                if select_type == 'aktivt_sted':
                    self._check_aktivt_sted(student_info)
                elif select_type == 'evu_sted':
                    self._check_evu_sted(student_info)
                elif select_type == 'medlem_av_gruppe':
                    self._check_group_membership(member_groups)

    def _check_aktivt_sted(self, student_info):
        """Resolve all aktivt_sted criterias for this student."""

        as_dict = self.pc.select_mapping['aktivt_sted']
        for k in as_dict.keys():
            v = as_dict[k]
            had_eksamen = False
            # Does this aktivt_sted criteria match an 'eksamen'?
            for entry in student_info.get('eksamen', []):
                d = self.pc.autostud.emnekode2info[
                    entry['emnekode']]
                if ((v['nivaa_min'] and
                     int(v['nivaa_min']) <= int(d['studienivakode'])) or
                    (v['nivaa_max'] and
                     int(d['studienivakode']) > int(v['nivaa_max']))):
                    continue
                sko = "%02i%02i%02i" % (int(d['faknr_reglement']),
                                        int(d['instituttnr_reglement']),
                                        int(d['gruppenr_reglement']))
                if sko in v['steder']:
                    self._append_match(
                        'aktivt_sted', 'emnekode',
                        entry['emnekode'], v['profiles'])
                    had_eksamen = True
            if had_eksamen:
                continue
            # Does this aktivt_sted criteria match a 'studieprogram'?
            for entry in student_info.get('aktiv', []):
                d = self.pc.autostud.studieprogramkode2info[
                    entry['studieprogramkode']]
                if ((v['nivaa_min'] and
                     int(v['nivaa_min']) <= int(d['studienivakode'])) or
                    (v['nivaa_max'] and
                     int(d['studienivakode']) > int(v['nivaa_max']))):
                    continue
                sko = "%02i%02i%02i" % (int(d['faknr_studieansv']),
                                        int(d['instituttnr_studieansv']),
                                        int(d['gruppenr_studieansv']))
                if sko in v['steder']:
                    self._append_match(
                        'aktivt_sted', 'studieproram',
                        entry['studieprogramkode'], v['profiles'])

    def _check_evu_sted(self, student_info):
        """Resolve all evu_sted criterias for this student."""

        as_dict = self.pc.select_mapping.get('evu_sted', {})
        for k in as_dict.keys():
            v = as_dict[k]
            # Does this aktivt_sted criteria match a 'evu' entry?
            for entry in student_info.get('evu', []):
                sko = "%02i%02i%02i" % (int(entry['faknr_adm_ansvar']),
                                        int(entry['instituttnr_adm_ansvar']),
                                        int(entry['gruppenr_adm_ansvar']))
                if sko in v['steder']:
                    self._append_match(
                        'evu_sted', 'sted', sko, v['profiles'])

    def _check_group_membership(self, groups):
        if not groups:
            return
        for g in self.pc.select_mapping['medlem_av_gruppe'].keys():
            if g in groups:
                self._append_match(
                    'medlem_av_gruppe', 'gruppe',
                    g, self.pc.select_mapping['medlem_av_gruppe'][g])

    def _check_match(self, select_type, value):
        # If studconfig.xml don't use this mapping: return
        if not self.pc.select_mapping.has_key(select_type):
            return

        # Check if this value matches any <select> criterias
        map_data = StudconfigParser.select_map_defs[select_type]
        if map_data[0] == StudconfigParser.NORMAL_MAPPING:
            tmp_map = self.pc.select_mapping[select_type][map_data[1]]
            matches = tmp_map.get(value, None)
            if matches:
                self._append_match(select_type, map_data[1], value, matches)
            else:
                matches = tmp_map.get('*', None)
                self._append_match(select_type, map_data[1], value, matches)

    def _append_match(self, select_type, sx_match_attr, value, matches):
        """Calculate the significance of this match, and append to
        to the list of matches"""
        if matches is None:
            return
        nivakode = 0
        if sx_match_attr == 'studieprogram':
            nivakode = self._normalize_nivakode(
                self.pc.autostud.studieprogramkode2info.get(
                value, {}).get('studienivakode', 0))
        self.matching_selectors.setdefault(sx_match_attr, {})[value] = 1
        for match in matches:
            self.matches.append((match, nivakode))

    def _normalize_nivakode(self, niva):
        niva = int(niva)
        if niva >= 100 and niva < 300:
            niva = 100
        elif niva >= 300 and niva < 400:
            niva = 300
        return niva

    def _matches_sort(self, x, y):
        """Sort by nivaakode, then by profile"""
        if(x[1] == y[1]):
            return cmp(x[0], y[0])
        return cmp(y[1], x[1])

    def _resolve_matches(self):
        """Determine most significant value for singular values, and
        fetch all other settings."""
        self.matches.sort(self._matches_sort)
        set_at = {}
        for match in self.matches:
            profile, nivaakode = match
            for k in profile.settings.keys():
                self._unique_extend(self.settings.setdefault(k, []),
                                    profile.settings[k])
                if set_at.get(k, nivaakode) == nivaakode:
                    set_at[k] = nivaakode
                    # NOTE: By using :1 we assert that disks inherited
                    # from a parent profile won't move us to a
                    # div-disk.  However, this also means that we
                    # won't be member of all default_groups
                    self._unique_extend(self.toplevel_settings.setdefault(
                        k, []), profile.settings[k][:1])

        # Automatically add the stedkode from the studieprogram that matched
        for p in self.matching_selectors.get('studieprogram', {}).keys():
            if not self.pc.autostud.studieprogramkode2info.has_key(p):
                continue
            d = self.pc.autostud.studieprogramkode2info[p]
            sko = self.pc.lookup_helper.get_stedkode(
                "%02i%02i%02i" % (int(d['faknr_studieansv']),
                                  int(d['instituttnr_studieansv']),
                                  int(d['gruppenr_studieansv'])),
                                  int(d['institusjonsnr_studieansv']))
            self._unique_extend(self.settings.setdefault("stedkode", []), [sko])

    def _unique_extend(self, list, values):
        for item in values:
            if item not in list:
                list.append(item)

