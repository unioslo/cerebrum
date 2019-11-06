# -*- coding: utf-8 -*-

# Copyright 2019 University of Oslo, Norway
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

"""How this stuff works:

SelectTool.select_map_defs defines a mapping of studconfig.xml
select-tags to the corresponding matching class.

While parsing the studconfig.xml file,
ProfileDefinition.add_selection_criteria is called for each
select-criteria that points to that profile (selection_criterias).

Once parsing is complete, SelectTool iterates over all
ProfileDefinitions and calls SelectMap*.set_select_map where
apropriate, making SelectMap*._select_map look like:
  { <studieprogram="TVIJF">: <profile> }

"""
from __future__ import unicode_literals
import pprint

from six import python_2_unicode_compatible

pp = pprint.PrettyPrinter(indent=4)


@python_2_unicode_compatible
class SelectMapSuper(object):
    """SelectMap* provides the rules to match a <select> line in
    studconfig.xml with a line from merged_persons.xml.
    """

    def __init__(self):
        self._select_map = {}

    def __str__(self):
        return "c={}, select_map: {}".format(
            self.__class__.__name__, pp.pformat(self._select_map))

    def _append_match(self, lst, profiles, nivakode=0):
        if isinstance(profiles, (list, tuple)):
            for p in profiles:
                lst.append((p, nivakode))
        else:
            lst.append((profiles, nivakode))

    def _normalize_nivakode(self, niva):
        niva = int(niva)
        if niva < 100:  # Forkurs ol.
            niva = 50
        elif niva >= 100 and niva < 500:  # Laveregrad, Cand.Mag, Bachelor
            niva = 100
        elif niva >= 500 and niva < 900:  # Høyeregrad, Profesjon, hovedfag, master
            niva = 500
        elif niva >= 900:  # PHD
            niva = 900
        return niva


@python_2_unicode_compatible
class SelectMapTag(SelectMapSuper):
    """Map studconfig.xml:
      <select><aktiv studieprogram="JFM5-RV"/></select>
    To:
      <person><aktiv studieprogramkode="JFM5-RV"
                     studieretningkode="LATAM"/></person>
    """

    def __init__(self, config_attr, match_tag, match_attr):
        super(SelectMapTag, self).__init__()
        if not isinstance(config_attr, (list, tuple)):
            config_attr = [config_attr]
        if not isinstance(match_attr, (list, tuple)):
            match_attr = [match_attr]
        assert len(config_attr) == len(match_attr)
        self._config_attr = config_attr
        self._match_tag = match_tag
        self._match_attr = match_attr

    def _append_match(self, lst, profiles, pdta):
        nivakode = 0
        if self._match_attr[0] == 'studieprogramkode':
            nivakode = self._normalize_nivakode(
                self._pc.autostud.studieprogramkode2info.get(
                    pdta['studieprogramkode'], {}).get('studienivakode', 0))
        super(SelectMapTag, self)._append_match(lst, profiles,
                                                nivakode=nivakode)

    def set_select_map(self, select_attrs, profile):
        # Build mapping: _select_map[key] = profile where key is
        # the attribute-name used in the merged_persons file and value
        # is fetched from the corresponding attr from the
        # studconfig.xml file.  This way we won't need to know the
        # config_attr any more.  A resulting key may look like:
        #
        #  (('studieprogramkode', 'MNM2-ANMAT'), ('studieretningskode', 'CSC'))

        for s_attr in select_attrs:
            key = tuple([(self._match_attr[n], s_attr[self._config_attr[n]])
                         for n in range(len(self._config_attr))
                         if s_attr.has_key(self._config_attr[n])])
            self._select_map[key] = profile

    def get_matches(self, person_info, member_groups=None, person_affs=None):
        matches = []
        # Iterate over all person-info of this _match_tag, and find
        # corresponding entries from _select_map.
        #
        # To have a match, all entries in a _select_map key must match.
        # If the person_info entry does not have an entry of the
        # corresponding type, a '*' in _select_map is required for match.

        for pdta in person_info.get(self._match_tag, []):
            for select_attrs, profile in self._select_map.items():
                n_matches = 0
                for s_attr, s_val in select_attrs:
                    if s_val == '*' or pdta.get(s_attr, None) == s_val:
                        n_matches += 1
                    else:
                        # not match
                        break

                if n_matches == len(select_attrs):
                    self._logger.debug("OK: %s -> %s", select_attrs, profile)
                    self._append_match(matches, profile, pdta)
        return matches

    def __str__(self):
        return "config_attr: {}, match_tag: {}, match_attr: {}, {}".format(
            self._config_attr, self._match_tag, self._match_attr,
            super(SelectMapTag, self).__str__())


class SelectMapAktivtSted(SelectMapSuper):
    def __init__(self):
        super(SelectMapAktivtSted, self).__init__()

    def _append_match(self, lst, profiles, fs_info):
        nivakode = self._normalize_nivakode(fs_info.get('studienivakode', 0))
        super(SelectMapAktivtSted, self)._append_match(lst, profiles,
                                                       nivakode=nivakode)

    def _get_steder(self, institusjon, stedkode, scope):
        ret = []
        sko = self._pc.lookup_helper.get_stedkode(stedkode, institusjon)
        if scope == 'sub':
            ret.extend(self._pc.lookup_helper.get_all_child_sko(sko))
        else:
            ret.append(stedkode)
        return ret

    def set_select_map(self, select_attrs, profile):
        """build a mapping:
             '150000:185:sub:100:499': {
                'nivaa_max': '499',
                'nivaa_min': '100',
                'profiles': [   Profile object(MNF_Laveregrad)],
                'steder': [   '150000', .... ]
              }"""

        for s_criteria in select_attrs:
            tmp = ":".join((s_criteria['stedkode'],
                            s_criteria['institusjon'],
                            s_criteria['scope'],
                            s_criteria.get('nivaa_min', ''),
                            s_criteria.get('nivaa_max', '')))
            tmp = self._select_map.setdefault(tmp, {})
            tmp.setdefault('profiles', []).append(profile)
            if not tmp.has_key('steder'):
                tmp['steder'] = self._get_steder(
                    s_criteria['institusjon'],
                    s_criteria['stedkode'],
                    s_criteria['scope'])
            tmp['nivaa_min'] = s_criteria.get('nivaa_min', None)
            tmp['nivaa_max'] = s_criteria.get('nivaa_max', None)

    def get_matches(self, person_info, member_groups=None, person_affs=None):
        matches = []
        for fs_infodict, match_tag, col_postfix in (
                (self._pc.autostud.studieprogramkode2info,
                 'studieprogramkode', '_studieansv'),
                (self._pc.autostud.emnekode2info,
                 'emnekode', '_reglement')):
            # self._logger.debug("Check with %s" % match_tag)
            for pdta in person_info.get('aktiv', []):
                if not pdta.has_key(match_tag):
                    continue  # emnekode not set for some aktiv tags.
                try:
                    fs_info = fs_infodict[pdta[match_tag]]
                except KeyError:
                    self._logger.error("Ukjent: %s in %s" % (
                        match_tag, pdta))
                    continue
                sko = "%02i%02i%02i" % (int(fs_info['faknr%s' % col_postfix]),
                                        int(fs_info[
                                                'instituttnr%s' % col_postfix]),
                                        int(fs_info[
                                                'gruppenr%s' % col_postfix]))
                # self._logger.debug("Is %s in %s?" % (sko, self._select_map.values()))
                for select_attrs in self._select_map.values():
                    if not sko in select_attrs['steder']:
                        continue
                    if ((select_attrs['nivaa_min'] and
                         int(fs_info['studienivakode']) < int(
                                select_attrs['nivaa_min'])) or
                            (select_attrs['nivaa_max'] and
                             int(fs_info['studienivakode']) > int(
                                        select_attrs['nivaa_max']))):
                        continue
                    self._append_match(matches, select_attrs['profiles'],
                                       fs_info)
        return matches


class SelectMapEmnestudSted(SelectMapAktivtSted):
    def get_matches(self, person_info, member_groups=None, person_affs=None):
        # print "SelectMapEmnestudSted.get_matches"
        matches = []
        for fs_infodict, match_tag, col_postfix in (
                (self._pc.autostud.emnekode2info,
                 'emnekode', '_reglement'),):
            # print "***%s" % match_tag
            for pdta in person_info.get('emnestud', []):
                # print "***emnestud"
                if not pdta.has_key(match_tag):
                    continue  # emnekode not set for some aktiv tags.
                try:
                    fs_info = fs_infodict[pdta[match_tag]]
                except KeyError:
                    self._logger.error("Ukjent: %s in %s" % (
                        match_tag, pdta))
                    continue
                sko = "%02i%02i%02i" % (int(fs_info['faknr%s' % col_postfix]),
                                        int(fs_info[
                                                'instituttnr%s' % col_postfix]),
                                        int(fs_info[
                                                'gruppenr%s' % col_postfix]))
                # self._logger.debug("Is %s in %s?" % (sko, self._select_map.values()))
                for select_attrs in self._select_map.values():
                    if not sko in select_attrs['steder']:
                        continue
                    self._append_match(matches, select_attrs['profiles'],
                                       fs_info)
        return matches


class SelectMapTilbudSted(SelectMapAktivtSted):
    def set_select_map(self, select_attrs, profile):
        """build a mapping:
             '150000:185:sub:100:499': {
                'profiles': [   Profile object(MNF_Laveregrad)],
                'steder': [   '150000', .... ]
              }"""

        for s_criteria in select_attrs:
            tmp = ":".join((s_criteria['stedkode'],
                            s_criteria['institusjon'],
                            s_criteria['scope']))
            tmp = self._select_map.setdefault(tmp, {})
            tmp.setdefault('profiles', []).append(profile)
            if not tmp.has_key('steder'):
                tmp['steder'] = self._get_steder(
                    s_criteria['institusjon'],
                    s_criteria['stedkode'],
                    s_criteria['scope'])

    def get_matches(self, person_info, member_groups=None, person_affs=None):
        matches = []
        for fs_infodict, match_tag, col_postfix in (
                (self._pc.autostud.studieprogramkode2info,
                 'studieprogramkode', '_studieansv'),):
            for pdta in person_info.get('tilbud', []):
                if not pdta.has_key(match_tag):
                    continue  # emnekode not set for some aktiv tags.
                try:
                    fs_info = fs_infodict[pdta[match_tag]]
                except KeyError:
                    self._logger.error("Ukjent: %s in %s" % (
                        match_tag, pdta))
                    continue
                sko = "%02i%02i%02i" % (int(fs_info['faknr%s' % col_postfix]),
                                        int(fs_info[
                                                'instituttnr%s' % col_postfix]),
                                        int(fs_info[
                                                'gruppenr%s' % col_postfix]))
                # self._logger.debug("Is %s in %s?" % (sko, self._select_map.values()))
                for select_attrs in self._select_map.values():
                    if not sko in select_attrs['steder']:
                        continue
                    self._append_match(matches, select_attrs['profiles'],
                                       fs_info)
        return matches


class SelectMapEvuSted(SelectMapAktivtSted):
    def set_select_map(self, select_attrs, profile):
        self._logger.debug("EVU Map: %s -> %s", select_attrs, profile)
        super(SelectMapEvuSted, self).set_select_map(select_attrs, profile)

    def get_matches(self, person_info, member_groups=None, person_affs=None):
        matches = []
        for entry in person_info.get('evu', []):
            sko = "%02i%02i%02i" % (int(entry['faknr_adm_ansvar']),
                                    int(entry['instituttnr_adm_ansvar']),
                                    int(entry['gruppenr_adm_ansvar']))
            for select_attrs in self._select_map.values():
                if sko in select_attrs['steder']:
                    # TBD: finnes det noen nivåkode vi kan bruke?
                    super(SelectMapAktivtSted, self)._append_match(
                        matches, select_attrs['profiles'])
        return matches


class SelectMapAny(SelectMapSuper):
    def set_select_map(self, select_attrs, profile):
        if len(select_attrs) > 0:
            self._select_map.setdefault('ALL', []).append(profile)

    def get_matches(self, person_info, member_groups=None, person_affs=None):
        matches = []
        for p in self._select_map.get('ALL', []):
            self._append_match(matches, p)
        return matches


class SelectMapGroupMember(SelectMapSuper):
    def set_select_map(self, select_attrs, profile):
        for s_attr in select_attrs:
            group_id = self._pc.lookup_helper.get_group(s_attr['navn'])
            self._select_map.setdefault(group_id, []).append(profile)

    def get_matches(self, person_info, member_groups=None, person_affs=None):
        matches = []
        if not member_groups:
            return matches
        for g in member_groups:
            if self._select_map.has_key(g):
                self._append_match(matches, self._select_map[g])
        return matches


class SelectMapPersonAffiliation(SelectMapSuper):
    def set_select_map(self, select_attrs, profile):
        self._logger.debug("Paff Map: %s -> %s" % (select_attrs, profile))
        for s_attr in select_attrs:
            affiliation = self._pc.autostud.co.PersonAffiliation(
                s_attr['affiliation'])
            if 'status' not in s_attr:
                key = int(affiliation)
                self._select_map.setdefault(key, []).append(profile)
            else:
                aff_status = self._pc.autostud.co.PersonAffStatus(
                    affiliation, s_attr['status'])
                key = (int(affiliation), int(aff_status))
                self._select_map.setdefault(key, []).append(profile)

    def get_matches(self, person_info, member_groups=None, person_affs=None):
        # person_affs are tuples from
        # process_students/ExistingPerson.get_affiliations()
        matches = []
        if not person_affs:
            return matches

        # try keys `(aff, status)` and `aff`
        for p_aff in ([(x[0], x[2]) for x in person_affs] +
                      [x[0] for x in person_affs]):
            if self._select_map.has_key(p_aff):
                self._append_match(matches, self._select_map[p_aff])
        return matches


class SelectTool(object):
    select_map_defs = {
        "aktiv": SelectMapTag(['studieprogram', 'studieretning'],
                              'aktiv',
                              ['studieprogramkode', 'studieretningkode']),
        "evu": SelectMapTag(['etterutdkurskode'],
                            'evu',
                            ['etterutdkurskode']),
        "fagperson": SelectMapTag(['instituttnr', 'gruppenr', 'faknr'],
                                  'fagperson',
                                  ['instituttnr', 'gruppenr', 'faknr']),
        "tilbud": SelectMapTag(['studieprogram', 'studieretning'],
                               'tilbud',
                               ['studieprogramkode', 'studieretningkode']),
        "studierett": SelectMapTag(
            ['studieprogram', 'studieretning', 'status'],
            'opptak',
            ['studieprogramkode', 'studieretningkode', 'status']),
        "privatist_studieprogram": SelectMapTag(
            ['studieprogram', 'studieretning'],
            'privatist_studieprogram',
            ['studieprogramkode', 'studieretningkode']),
        "drgrad": SelectMapTag(['studieprogram'],
                               'drgrad',
                               ['studieprogramkode']),
        "emne": SelectMapTag('emnekode', 'eksamen', 'emnekode'),
        "privatist_emne": SelectMapTag('emnekode', 'privatist_emne',
                                       'emnekode'),
        "aktivt_sted": SelectMapAktivtSted(),
        "tilbud_sted": SelectMapTilbudSted(),
        "emnestud_sted": SelectMapEmnestudSted(),
        "evu_sted": SelectMapEvuSted(),
        "medlem_av_gruppe": SelectMapGroupMember(),
        "person_affiliation": SelectMapPersonAffiliation(),
        "match_any": SelectMapAny()
    }

    def __init__(self, profiles, logger, profile_config):
        """Make all SelectMap* instances aware of the ProfileDefinition
        instances that points to them"""
        self._logger = logger
        self._pc = profile_config
        for smd in self.select_map_defs.values():
            smd._logger = logger
            smd._pc = profile_config
        for p in profiles:
            for select_name, select_attrs in p.selection_criterias.items():
                self._logger.debug(
                    "S: %s -> %s" % (select_name, select_attrs))
                sm_obj = self.select_map_defs[select_name]
                sm_obj.set_select_map(select_attrs, p)

    def _matches_sort(self, x, y):
        """Sort by nivaakode (highest first), then by profile"""
        if (x[1] == y[1]):
            return cmp(x[0], y[0])
        return cmp(y[1], x[1])

    def _unique_extend(self, tgt_list, values, profile_name, nivaakode=0):
        """Append all v in values to tgt_list iff they are not already
        there.  We also store the nivakode for the first time the
        value was seen.  We store the name of all profiles that has
        this value at this nivåkode
        """
        if not isinstance(values, (tuple, list)):
            values = (values,)
        for item in values:
            if item not in [x[0] for x in tgt_list]:
                tgt_list.append((item, nivaakode, [profile_name]))
            else:
                for tmp_item, tmp_nivaakode, tmp_profiles in tgt_list:
                    if (tmp_item == item and tmp_nivaakode == nivaakode and
                            profile_name not in tmp_profiles):
                        tmp_profiles.append(profile_name)

    def get_person_match(self, person_info, member_groups=None,
                         person_affs=None):
        """Returns a dict where each key is a configuration item, such
        as 'disk' for <disk>, and the value is a list of the relevant
        profiles for the specified person.  The profiles are sorted by
        nivaakode.
        """
        matches = []
        for mtype, sm in self.select_map_defs.items():
            tmp = sm.get_matches(person_info, member_groups=member_groups,
                                 person_affs=person_affs)
            self._logger.debug("check-type: %s -> %s", mtype, tmp)
            matches.extend(tmp)

        self._logger.debug("pre-priority filter: m= %s", matches)
        if self._pc.using_priority:
            # Only use matches at prioritylevel with lowest value
            tmp = []
            min_pri = None
            for m in matches:
                if min_pri is None or m[0].priority < min_pri:
                    min_pri = m[0].priority
            for m in matches:
                if m[0].priority == min_pri:
                    tmp.append(m)
            self._logger.debug("Priority filter gave %i -> %i entries" % (
                len(matches), len(tmp)))
            matches = tmp
        self._logger.debug("Matching settings: %s", matches)
        # Sort matches on nivåkode, and remove duplicates
        matches.sort(self._matches_sort)
        matched_settings = {}
        for match in matches:
            profile, nivaakode = match
            for k in profile._settings.keys():
                for settings, actual_profile in profile.get_settings(k):
                    self._unique_extend(matched_settings.setdefault(k, []),
                                        settings, actual_profile,
                                        nivaakode=nivaakode)
        return matches, matched_settings
