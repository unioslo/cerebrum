from Cerebrum.modules.no.uio.AutoStud.ProfileConfig import StudconfigParser
import pprint
pp = pprint.PrettyPrinter(indent=4)

class Profile(object):
    """Profile implements the logic that maps a persons student_info
    (and optionaly groups) to the apropriate home, default group etc
    using rules read by the StudconfigParser."""

    def __init__(self, autostud, student_info, groups=None):
        """The logic for resolving conflicts and enumerating settings
        is similar for most attributes, thus we resolve the settings
        applicatble for this profile in the constructor
        """

        # topics may contain data from get_studieprog_list
        self._groups = groups
        self._autostud = autostud

        reserve = 0
        mail_user = 0
        full_account = 0

        self.matches = []
        self._get_profile_matches(student_info)

        # TODO: Sort matches and resolve singular attributes etc.

    def debug_dump(self):
        print "Dumping %i match entries" % len(self.matches)
        pp.pprint(self.matches)

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

    def _topics_sort(self, x, y):
        x = self._normalize_nivakode(x['studienivakode'])
        y = self._normalize_nivakode(y['studienivakode'])
        return cmp(y, x)
        
    def get_disk(self, current_disk=None):
        """Return a disk_id matching the current profile.  If the
        account already exists, current_disk should be set to assert
        that the user is not moved to a new disk with the same
        prefix. (i.e from /foo/bar/u11 to /foo/bar/u12)"""

        if current_disk is not None:
            if self._disk.has_key('path'):
                if self._disk['path'] == current_disk:
                    return current_disk
            else:
                disk_path = self._autostud._disks[int(current_disk)][0]
                if self._disk['prefix'] == disk_path[0:len(self._disk['prefix'])]:
                    return current_disk
        
        if self._disk.has_key('path'):
            # TBD: Should we ignore max_on_disk when path is explisitly set?
            return self._disk['path']

        dest_pfix = self._disk['prefix']
        max_on_disk = self._autostud.sp.disk_defs['prefix'][dest_pfix]['max']
        if max_on_disk == -1:
            max_on_disk = 999999
        for d in self._autostud._disks_order:
            tmp_path, tmp_count = self._autostud._disks[d]
            if (dest_pfix == tmp_path[0:len(dest_pfix)]
                and tmp_count < max_on_disk):
                return d
        raise ValueError, "Bad disk %s" % self._disk

    def notify_used_disk(self, old=None, new=None):
        if old is not None:
            self._autostud._disks[int(old)][1] -= 1
        if new is not None:
            self._autostud._disks[new][1] += 1

    def get_stedkoder(self):
        return self._flat_settings['stedkode']

    def get_dfg(self):
        return self._dfg

    def get_email_sko(self):
        return self._email_sko
    
    def get_grupper(self):
        return self._flat_settings['gruppe']


    def get_pquota(self):
        assert self._groups is not None
        for m in self._flat_settings.get('printer_kvote', []):
            pass # TODO
        raise NotImplementedError, "TODO"
        
