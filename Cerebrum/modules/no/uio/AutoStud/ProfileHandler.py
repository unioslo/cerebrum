# -*- coding: iso-8859-1 -*-
from Cerebrum.modules.no.uio.AutoStud.ProfileConfig import StudconfigParser

class Profile(object):
    """Profile implements the logic that maps a persons student_info
    (and optionaly groups) to the apropriate home, default group etc
    using rules read by the StudconfigParser."""

    def __init__(self, autostud, student_info, logger, groups=None):
        """The logic for resolving conflicts and enumerating settings
        is similar for most attributes, thus we resolve the settings
        applicatble for this profile in the constructor
        """

        # topics may contain data from get_studieprog_list
        self._groups = groups
        self._autostud = autostud
        self._logger = logger
        
        reserve = 0
        mail_user = 0
        full_account = 0

        self.matches = []
        self.settings = {}
        self.toplevel_settings = {}
        self._get_profile_matches(student_info)
        self._resolve_matches()

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
                    self._unique_extend(self.toplevel_settings.setdefault(k, []),
                                        profile.settings[k])

    def _unique_extend(self, list, values):
        for item in values:
            if item not in list:
                list.append(item)

    def debug_dump(self):
        ret = "Dumping %i match entries\n" % len(self.matches)
        ret += self._logger.pformat(self.matches)
        ret += "Settings: "
        ret += self._logger.pformat(self.settings)
        ret += "Toplevel: "
        ret += self._logger.pformat(self.toplevel_settings)
        return ret
    
    def _get_profile_matches(self, student_info):
        """Check if student_info contains data of the type identified
        by StudconfigParser.select_elements.  If yes, check if the
        corresponding value matches a profile."""

        for select_type in student_info.keys():
            ids = StudconfigParser.select_elements.get(select_type, None)
            if ids is None:
                continue
            for use_id in ids:
                for entry in student_info[select_type]:
                    value = StudconfigParser.get_value_for_select_id(
                        entry, use_id)
                    if value is None:
                        continue
                    self._append_match(select_type, use_id, value,
                                       self._autostud.pc.get_matching_profiles(
                        select_type, use_id, value))
                # Also check for wildcard match for this id type:
                self._append_match(select_type, use_id, '*',
                                   self._autostud.pc.get_matching_profiles(
                    select_type, use_id, '*'))
                
    def _append_match(self, select_type, use_id, value, matches):
        """Calculate the significance of this match, and append to
        to the list of matches"""
        if matches is None:
            return
        nivakode = 0
        if use_id == 'studieprogram':
            nivakode = self._autostud.studieprogramkode2info.get(
                value, {}).get('studienivakode', 0)
        for match in matches:
            self.matches.append((match, nivakode))

    def _normalize_nivakode(self, niva):
        niva = int(niva)
        if niva >= 100 and niva < 300:
            niva = 100
        elif niva >= 300 and niva < 400:
            niva = 300
        return niva

    def get_disk(self, current_disk=None):
        """Return a disk_id matching the current profile.  If the
        account already exists, current_disk should be set to assert
        that the user is not moved to a new disk with the same
        prefix. (i.e from /foo/bar/u11 to /foo/bar/u12)"""

        disks = self.toplevel_settings.get("disk", [])
        if len(disks) == 0:
            raise ValueError, "No disk matches profiles"
        if current_disk is not None:
            for d in disks:
                if d.has_key('path'):
                    if d['path'] == current_disk:
                        return current_disk
                else:
                    disk_path = self._autostud._disks[int(current_disk)][0]
                    if d['prefix'] == disk_path[0:len(d['prefix'])]:
                        return current_disk
        disk = disks[0]
        if disk.has_key('path'):
            # TBD: Should we ignore max_on_disk when path is explisitly set?
            return disk['path']

        dest_pfix = disk['prefix']
        max_on_disk = self._autostud.pc.disk_defs['prefix'][dest_pfix]['max']
        if max_on_disk == -1:
            max_on_disk = 999999
        for d in self._autostud.disks_order:
            tmp_path, tmp_count = self._autostud.disks[d]
            if (dest_pfix == tmp_path[0:len(dest_pfix)]
                and tmp_count < max_on_disk):
                return d
        raise ValueError, "Bad disk %s" % disk

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self._autostud.disks[int(old)][1] -= 1
        if new is not None:
            self._autostud.disks[new][1] += 1

    def get_brev(self):
        return self.settings.get("brev", [None])[0]
        
    def get_stedkoder(self):
        return self.settings.get("stedkode", [])

    def get_dfg(self):
        if len(self.toplevel_settings.get('primarygroup', [])) > 0:
            return self.toplevel_settings['primarygroup'][0]
        return self.toplevel_settings['gruppe'][0]

    def get_grupper(self):
        return self.settings.get('gruppe', [])

    def get_spreads(self):
        return self.settings.get('spread', [])

    def get_pquota(self):
        assert self._groups is not None
        for m in self.settings.get('printer_kvote', []):
            pass # TODO
        raise NotImplementedError, "TODO"
        
