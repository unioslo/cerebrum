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

from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio.AutoStud.ProfileConfig import StudconfigParser

class NoMatchingQuotaSettings(Exception): pass
class NoMatchingProfiles(Exception): pass

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
        ret += self._logger.pformat(self.matcher.matched_settings)
        return ret

    def get_disk_spreads(self):
        tmp = {}
        for disk in self.matcher.get_match("disk"):
            for spread in disk['spreads']:
                tmp[int(spread)] = 1
        return tmp.keys()
    
    def get_disk(self, disk_spread, current_disk=None):
        """Return a disk_id matching the current profile.  If the
        account already exists, current_disk should be set to assert
        that the user is not moved to a new disk with the same
        prefix. (i.e from /foo/bar/u11 to /foo/bar/u12)"""

        # TBD: The above statement is incorrect; we will only move a
        # user if it no longer matches a profile with the users
        # current disk.  Is this the correct behaviour?

        # Detect conflicting disks at same 'nivåkode'
        new_disk, tmp_nivaakode = None, None
        for d, n in self.matcher.matched_settings.get("disk", []):
            if int(disk_spread) not in d['spreads']:
                continue            # Incorrect spread for this disk
            if not new_disk:
                new_disk, tmp_nivaakode = d, n
            if n != tmp_nivaakode:  # This disk is at a lower nivåkode
                break
            if d != new_disk:
                if n < 300:  # TODO: don't hardcode these
                    new_disk = {'prefix': '/uio/kant/div-l'}
                else:
                    new_disk = {'prefix': '/uio/kant/div-h'}
                break
        if not new_disk:
            raise ValueError, "No disk matches profiles"

        # Check if one of the matching disks matches the disk that the
        # user currently is on
        if current_disk is not None:
            if not self.pc.autostud.student_disk.has_key(int(current_disk)):
                return current_disk
            for d in self.matcher.get_match("disk"):
                if int(disk_spread) not in d['spreads']:
                    continue            # Incorrect spread for this disk
                if d.has_key('path'):
                    if d['path'] == current_disk:
                        return current_disk
                else:
                    disk_path = self.pc.autostud.disks[int(current_disk)][0]
                    if d['prefix'] == disk_path[0:len(d['prefix'])]:
                        return current_disk

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
        raise ValueError, "No disks with free space matches %s" % new_disk

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self.pc.autostud.disks[int(old)][1] -= 1
        if new is not None:
            self.pc.autostud.disks[new][1] += 1

    def get_brev(self):
        return self.matcher.get_match("brev") or None  # TBD: Raise error?
        
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
        raise ValueError, "No dfg is a PosixGroup"

    def get_grupper(self):
        return self.matcher.get_match('gruppe')

    def get_spreads(self):
        return self.matcher.get_match('spread')

    def get_pquota(self):
        """Return information about printerquota.  Throws a
        NoMatchingQuotaSettings if profile has no quota information"""
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

    def __init__(self, pc, student_info, logger, member_groups=None):
        self.pc = pc
        self.matches = []
        self.logger = logger
        self.matching_selectors = {}
        self._process_person_info(student_info, member_groups=member_groups)
        self.logger.debug("Matching profiles: %s" % self.matches)
        if len(self.matches) == 0:
            raise NoMatchingProfiles, "No matching profiles"
        self.matched_settings = {}
        # type: [(value_from_profile, nivaakode_where_first_set)]
        self._resolve_matches()

    def get_match(self, match_type):
        return [x[0] for x in self.matched_settings.get(match_type, [])]

    def _process_person_info(self, student_info, member_groups=[]):
        """Check if student_info contains data of the type identified
        by StudconfigParser.select_elements.  If yes, check if the
        corresponding value matches a profile."""

        # Find the select_map_defs that map to data in student_info
        for select_type in StudconfigParser.select_map_defs.keys():
            map_data = StudconfigParser.select_map_defs[select_type]
            if map_data[0] == StudconfigParser.NORMAL_MAPPING:
                for entry in student_info.get(map_data[2], []):
                    for match_attr in map_data[3]:
                        value = entry.get(match_attr, None)
                        if not value:
                            continue
                        if self._check_match(select_type, value):
                            continue  # No point in matching twice to same profile
            else:
                if select_type == 'aktivt_sted':
                    self._check_aktivt_sted(student_info)
                elif select_type == 'evu_sted':
                    self._check_evu_sted(student_info)
                elif select_type == 'medlem_av_gruppe':
                    self._check_group_membership(member_groups)
                elif select_type == 'person_affiliation':
                    fnr = fodselsnr.personnr_ok(
                        "%06d%05d" % (int(student_info['fodselsdato']),
                                      int(student_info['personnr'])))
                    self._check_person_affiliation(
                        self.pc.lookup_helper.get_person_affiliations(fnr))

    def _check_aktivt_sted(self, student_info):
        """Resolve all aktivt_sted criterias for this student."""

        as_dict = self.pc.select_mapping.get('aktivt_sted', {})
        for k in as_dict.keys():
            v = as_dict[k]
            had_eksamen = False
            if had_eksamen:
                continue
            # Does this aktivt_sted criteria match a 'studieprogram'?
            for entry in student_info.get('aktiv', []):
                d = self.pc.autostud.studieprogramkode2info[
                    entry['studieprogramkode']]
                if ((v['nivaa_min'] and
                     int(d['studienivakode']) < int(v['nivaa_min'])) or
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

    def _check_person_affiliation(self, persons_affiliations):
        if not persons_affiliations:
            return
        persons_affiliations = [(x['affiliation'], x['status']) for x in persons_affiliations]
        for p_aff in self.pc.select_mapping['person_affiliation'].keys():
            if p_aff in persons_affiliations:
                self._append_match(
                    'person_affiliation', 'affiliation',
                    p_aff, self.pc.select_mapping['person_affiliation'][p_aff])

    def _check_match(self, select_type, value):
        # If studconfig.xml don't use this mapping: return
        if not self.pc.select_mapping.has_key(select_type):
            return False

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
            if matches:
                return True
        return False

    def _append_match(self, select_type, sx_match_attr, value, matches):
        """Calculate the significance of this match, and append to
        to the list of matches"""
        if matches is None:
            return
        self.logger.debug2("_append_match: "+self.logger.pformat((select_type, sx_match_attr, value, matches)))
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
        """Sort by nivaakode (highest first), then by profile"""
        if(x[1] == y[1]):
            return cmp(x[0], y[0])
        return cmp(y[1], x[1])

    def _resolve_matches(self):
        """Fill self.settings with settings from the matched profiles,
        highest nivaakode first."""
        self.matches.sort(self._matches_sort)
        for match in self.matches:
            profile, nivaakode = match
            for k in profile.settings.keys():
                if not profile.settings[k]:
                    continue      # This profile had no setting of this type
                self._unique_extend(self.matched_settings.setdefault(k, []),
                                    profile.settings[k])

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
            self._unique_extend(self.matched_settings.setdefault(
                "stedkode", []), [sko])

    def _unique_extend(self, list, values, nivaakode=0):
        for item in values:
            if item not in [x[0] for x in list]:
                list.append((item, nivaakode))

