#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-

"""This file contains the code to generate all relevant Cerebrum groups for
hiof's Fronter.

We update and create a number of groups in Cerebrum that are used to create a
Fronter-structure. This file is the first half of the process -- mapping data
from FS to groups in Cerebrum and assigning traits. The next step is the XML
file generation, done by generate_fronter_file.py.

The details for group building are outlined in fronter-hiof-spesifikasjon.rst

Since hiof's CF-tree is not time-based (but rather department/avdeling-based),
multi-semester undenh/undakt are easier to deal with: we 'unroll time
backwards' to calculate the group id. The group **description** would have to
be changed as well. As far as XML generation goes, though, there is no
difference between the undenh.

This script needs a considerable deal of data from FS and is therefore highly
dependent on import_from_FS.py's output.

FIXME: A FAQ entry for all the warn()/error() statements.
"""



import getopt
import locale
import os
import sys



import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import access_FS
from Cerebrum.Utils import simple_memoize
from Cerebrum.modules.xmlutils.fsxml2object import EduGenericIterator
from Cerebrum.modules.xmlutils.fsxml2object import EduDataGetter



logger = None



class FSAttributeHandler(object):
    """A class that deals with FS attributes.

    We need to operate on a number of IDs/attributes stemming from FS
    data. This class captures the functionality for doing just that. All group
    name/id/description manipulation happens within this class. The crux of
    the solution is the fact that CF-groups are of 9 different kinds
    (group_kind) and the (unique) name for each kind has an internal
    structure.
    """

    # List of required attributes for each kind. I.e. for a set of attributes
    # describing a studieprogram, we want to have at least these 4 keys
    # present in attributes. There may be other keys, but AT LEAST the ones
    # listed below must be present.
    group_kind2required_keys = {
        "stprog": ("institusjonsnr",
                   "studieprogramkode", "avdeling", "rollekode",),
        "kull": ("institusjonsnr",
                 "studieprogramkode", "avdeling", "rollekode",
                 "terminkode", "arstall",),
        "kullklasse": ("institusjonsnr",
                       "studieprogramkode", "avdeling", "rollekode",
                       "terminkode", "arstall", "klassekode",),
        "emne": ("institusjonsnr", "avdeling", "emnekode", "rollekode"),
        "undenh": ("institusjonsnr",
                   "emnekode", "versjonskode", "terminkode", "arstall",
                   "terminnr", "avdeling", "rollekode",),
        "undakt": ("institusjonsnr",
                   "emnekode", "versjonskode", "terminkode", "arstall",
                   "terminnr", "aktivitetkode", "avdeling", "rollekode",),
        "student-undenh": ("institusjonsnr",
                           "emnekode", "versjonskode", "terminkode", "arstall",
                           "terminnr", "avdeling",),
        "student-undakt": ("institusjonsnr",
                           "emnekode", "versjonskode", "terminkode", "arstall",
                           "terminnr", "aktivitetkode", "avdeling",),
        "student-kullklasse": ("institusjonsnr",
                               "studieprogramkode", "avdeling",
                               "terminkode", "arstall", "klassekode",),
    }
    

    # Mapping of attribute kinds to group name templates that they
    # create. I.e. an stprog role results in a group with the id as specified
    # below. The interpolated names are taken from L{attributes}.
    group_kind2name_template = {
        "stprog": "hiof.no:fs:"
                  "%(institusjonsnr)s:%(avdeling)s:"
                  "studieprogram:%(studieprogramkode)s:rolle:%(rollekode)s",
        "kull": "hiof.no:fs:"
                "%(institusjonsnr)s:%(avdeling)s:"
                "studieprogram:%(studieprogramkode)s:"
                "kull:%(arstall)s:%(terminkode)s:rolle:%(rollekode)s",
        "kullklasse": "hiof.no:fs:"
                      "%(institusjonsnr)s:%(avdeling)s:"
                      "studieprogram:%(studieprogramkode)s:"
                      "kull:%(arstall)s:%(terminkode)s:"
                      "klasse:%(klassekode)s:rolle:%(rollekode)s",
        "emne": "hiof.no:fs:"
                "%(institusjonsnr)s:%(avdeling)s:"
                "emner:%(emnekode)s:rolle:%(rollekode)s",
        "undenh": "hiof.no:fs:"
                  "%(institusjonsnr)s:%(avdeling)s:"
                  "emner:%(arstall)s:%(terminkode)s:"
                  "undenh:%(emnekode)s:%(versjonskode)s:%(terminnr)s:"
                  "rolle:%(rollekode)s",
        "undakt": "hiof.no:fs:"
                  "%(institusjonsnr)s:%(avdeling)s:"
                  "emner:%(arstall)s:%(terminkode)s:"
                  "undakt:%(emnekode)s:%(versjonskode)s:%(terminnr)s:"
                  "%(aktivitetkode)s:"
                  "rolle:%(rollekode)s",
        "student-undenh": "hiof.no:fs:"
                          "%(institusjonsnr)s:%(avdeling)s:"
                          "emner:%(arstall)s:%(terminkode)s:"
                          "undenh:%(emnekode)s:%(versjonskode)s:%(terminnr)s:"
                          "student",
        "student-undakt": "hiof.no:fs:"
                          "%(institusjonsnr)s:%(avdeling)s:"
                          "emner:%(arstall)s:%(terminkode)s:"
                          "undakt:%(emnekode)s:%(versjonskode)s:%(terminnr)s:"
                          "%(aktivitetkode)s:"
                          "student",
        "student-kullklasse": "hiof.no:fs:"
                              "%(institusjonsnr)s:%(avdeling)s:"
                              "studieprogram:%(studieprogramkode)s:"
                              "kull:%(arstall)s:%(terminkode)s:"
                              "klasse:%(klassekode)s:"
                              "student",
    }


    # A mapping for creating a group description based on the group
    # name/key. Since both names and descriptions are pretty regular, we can
    # use a template for each kind.
    #
    # The integers are the indices from the key/group name that are
    # interpolated into the description.
    group_kind2description = {
        "student-undakt": ("Studenter ved %s (versjon %s, %s. termin), aktivitet %s",
                           ("emnekode", "versjonskode", "terminnr", "aktivitetkode")),
        "student-undenh": ("Studenter ved %s (versjon %s, %s. termin)",
                           ("emnekode", "versjonskode", "terminnr",)),
        "student-kullklasse": ("Studenter på %s %s %s, klasse %s",
                               ("studieprogramkode", "terminkode", "arstall", "klassekode")),

        "undakt": ("%s for %s (versjon %s, %s. termin), aktivitet %s",
                   ("rollekode", "emnekode", "versjonskode", "terminnr", "aktivitetkode")),
        "undenh": ("%s for %s (versjon %s, %s. termin)",
                   ("rollekode", "emnekode", "versjonskode", "terminnr")),
        "emne": ("%s ved %s", ("rollekode", "emnekode")),
        "kullklasse": ("%s for %s %s %s, klasse %s",
                       ("rollekode", "studieprogramkode", "terminkode",
                        "arstall", "klassekode")),
        "kull": ("%s for %s %s %s",
                 ("rollekode", "studieprogramkode", "terminkode", "arstall")),
        "stprog": ("%s for %s",
                   ("rollekode", "studieprogramkode",)),
    }



    # Interesting roles from FS. We ignore the rest
    valid_roles = ('undakt', 'undenh', 'stprog', 'kull', 'kullklasse', 'emne')

    # Interesting role codes from FS. We ignore the rest
    valid_role_codes = ("assistent", "hovedlærer", "kursansv", "lærer",
                        "kontakt", "veileder",)

       
    def __init__(self, db, stprog_file, emne_file, undenh_file, undakt_file):

        logger.debug("FSAttributes from files: stprog=%s, emne=%s, "
                     "undenh=%s, undakt=%s",
                     stprog_file, emne_file, undenh_file, undakt_file)
        # stprog -> avdeling mapping
        self.stprog2avdeling = self._stprog2avdeling(stprog_file)
        # emne(kode) -> avdeling mapping
        self.emne2avdeling = self._emne2avdeling(emne_file)
        self._db = db

        self._exportable_keys = self._load_exportable_keys(stprog_file,
                                                           undenh_file,
                                                           undakt_file)
        self._group_name2description = dict()
    # end __init__



    def role_is_exportable(self, role_kind, role_attrs):
        """Decide whether a role with a given set of attributes should
        extually be exported to LMS. Some entities (stprog, undenh and undakt)
        are not pushed to LMS unless explicitely marked so.
        """

        assert role_kind in self.valid_roles

        # is stprog exportable?
        if role_kind in ("stprog", "kull", "kullklasse", "undakt", "undenh"):
            key = self._attributes2exportable_key(role_kind, role_attrs)
        elif role_kind in ("emne",):
            # emne-roles are always exportable
            return True 

        return key in self._exportable_keys
    # end role_is_exportable



    def edu_entry_is_exportable(self, edu_entry_kind, attrs):
        """Much like L{role_is_exportable}, except this works for student info
        entries. 

        Student info exists for undenh, undakt and kullklasse only. We don't
        care about the rest (these are the student info tidbits that result in
        room creation in CF).
        """

        assert edu_entry_kind in ("undenh", "undakt", "kullklasse")
        key = self._attributes2exportable_key(edu_entry_kind, attrs)
        return key in self._exportable_keys
    # end edu_entry_is_exportable



    def _load_exportable_keys(self, stprog_file, undenh_file, undakt_file):
        """Build a set of FS 'entity' keys that are exportable to LMS.

        There is a constraint placed by hiof on stprog, undenh and undakt. If
        status_eksport_lms = 'J', then the entity in question is exportable to
        CF. If it is NOT, then it should be interpreted as if the entity did
        not exist.

        This means, e.g., that any group related to, say, a non-exportable
        stprog is skipped as well (*ALL* kull/kullklasse/roles associated with
        that stprog).
        """

        result = set()

        for (source, 
             entry_kind) in ((EduDataGetter(stprog_file, logger).iter_stprog,
                              "stprog",),
                             (EduDataGetter(undenh_file, logger).iter_undenh,
                              "undenh",),
                             (EduDataGetter(undakt_file, logger).iter_undakt,
                              "undakt",)):
            logger.debug("Loading exportable %s", entry_kind)
            for entry in source():
                attrs = self.lower(entry)
                key = self._attributes2exportable_key(entry_kind, attrs)
                if attrs["status_eksport_lms"] == 'j':
                    result.add(key)
                logger.debug("%s=%s is%sexportable",
                             entry_kind, key,
                             key in result and " " or " not ")
        return result
    # end _stprog2avdeling



    def _attributes2exportable_key(self, attr_kind, attributes):
        """A help method to create an internal lookup key.

        This is for internal usage only.
        """
        key = None

        attrs = self.lower(attributes)
        
        if attr_kind == "undenh":
            attrs = self._count_back_semesters(attrs)
            key = ":".join((attrs[x] for x in
                            ("arstall", "terminkode",
                             "emnekode", "versjonskode", "terminnr")))
        elif attr_kind == "undakt":
            attrs = self._count_back_semesters(attrs)
            key = ":".join((attrs[x] for x in
                            ("arstall", "terminkode",
                             "emnekode", "versjonskode", "terminnr",
                             "aktivitetkode")))
        elif attr_kind in ("stprog", "kull", "kullklasse"):
            key = attributes["studieprogramkode"]
        else:
            assert False, "NOTREACHED"
            
        return key
    # end _attributes2exportable_key



    def attributes2key(self, group_kind, attributes):
        """Construct a Cerebrum/CF group ID, given a bunch of attributes.

        This function is useful to map various information tidbits on groups,
        roles, etc to a unique ID in Cerebrum for that particular kind of
        attributes. Each L{group_kind} results in a group in Cerebrum and this
        function calculates that group's id (not entity_id, but the id used in
        CF).

        @type group_kind: basestring
        @param group_kind:
          A tag that describes what kind of information is to be expected in
          L{attributes}. The ONLY legal values are:

            - 'stprog', 'kull', 'kullklasse', 'undenh', 'undakt', 'emne'
            - 'student-undenh', 'student-undakt', 'student-kullklasse'

          Each kind has a different set of keys in attributes that MUST be
          present.

        @type attributes: dict (of basestring -> basestring)
        @param attributes:
          A collection of attributes. This collection may contain more than what
          is required by L{group_kind}.

        @rtype: basestring or None
        @return:
          None if an id could not be constructed. The id itself otherwise.
        """

        # easiest way to copy, since we modify these destructively
        attrs = self.lower(attributes)
        
        if group_kind not in self.group_kind2required_keys:
            logger.warn("Don't know how to process attributes "
                        "belonging to '%s' (%s)",
                        group_kind, repr(attrs))
            return None

        keys = self.group_kind2required_keys[group_kind]
        if not all(x in attrs for x in keys):
            logger.warn("Missing essential keys for kind=%s. "
                        "Required=%s, available=%s",
                        group_kind, sorted(keys), sorted(attrs))
            return None

        # Now, those that have "terminnr" > 1 MUST be remapped.
        if "terminnr" in keys:
            attrs = self._count_back_semesters(attrs)

        result_id = self.group_kind2name_template[group_kind]
        result_id = result_id % attrs
        return result_id
    # attributes2key



    def _count_back_semesters(self, attributes):
        """Given a bunch of attributes for an FS entity with terminnr, figure
        out the year and starting semester for that FS entity (i.e. the one
        with terminnr=1).

        This method assumes that there are spring and fall semesters only (it
        is not true for all FS entities), but it's the best guess we can make!

        L{attributes} is modified destructively!
        """

        terminnr = int(attributes["terminnr"])
        terminkode = attributes["terminkode"]
        year = int(attributes["arstall"])
        # counting backwards
        while terminnr > 1:
            terminnr -= 1
            if terminkode == "høst":
                terminkode = "vår"
            else:
                year -= 1
                terminkode = "høst"

        attributes["terminnr"] = '1'
        attributes["terminkode"] = terminkode
        attributes["arstall"] = str(year)

        return attributes
    # end _count_back_semesters



    def register_description(self, group_key, attrs):
        """Register group description associated with group_key.

        Note that group_key and attrs may have different content, because of
        undenh/undakt spanning multiple semesters.
        """

        # TBD: clean up this mess!
        fields = group_key.split(":")
        description = None
        # student group
        if "student" == fields[-1]:
            if "undakt" in fields:
                description = self._calculate_description("student-undakt", attrs)
            elif "undenh" in fields:
                description = self._calculate_description("student-undenh", attrs)
            elif "klasse" in fields:
                description = self._calculate_description("student-kullklasse", attrs)
            else:
                assert False, "This cannot happen: %s" % group_key
        # role group
        # NB! DO NOT RESHUFFLE THE TESTS!
        elif "rolle" == fields[-2]:
            if "undakt" in fields:
                description = self._calculate_description("undakt", attrs)
            elif "undenh" in fields:
                description = self._calculate_description("undenh", attrs)
            # Must be tested for AFTER undakt/undenh
            elif "emner" in fields:
                description = self._calculate_description("emne", attrs)
            elif "klasse" in fields:
                description = self._calculate_description("kullklasse", attrs)
            # Must be tested for AFTER 'klasse'
            elif "kull" in fields:
                description = self._calculate_description("kull", attrs)
            # Must be tested for AFTER 'kull'
            elif "studieprogram" in fields:
                description = self._calculate_description("stprog", attrs)
            else:
                assert False, "This cannot happen: %s" % group_key
        else:
            assert False, "This cannot happen: %s" % group_key

        self._group_name2description[group_key] = description
        return description
    # end register_description



    def _calculate_description(self, group_kind, attrs):
        """Calculate group name from attrs"""
        
        template, keys = self.group_kind2description[group_kind]
        description = template % tuple(attrs[x].upper() for x in keys)
        return description
    # end _calculate_description



    def get_description(self, group_name):
        if group_name not in self._group_name2description:
            assert False, "No description for group_key %" % group_name

        return self._group_name2description[group_name]
    # end get_description



    def lower(self, obj):
        """Do a safe lowering on obj, whatever that may be.

        The idea is to force certain string values (on their own, or parts of
        a more complex data structure) to lowercase, so that we won't have to
        deal with case sensitive keys/identifiers.

        @type obj: a str, unicode, tuple, list, set, dict
        @param obj:
          The object to lowercase. str are lowercased directly, unicode
          objects are encoded to latin-1 first, then
          lowercased. tuple/list/set/dict are processed recursively with
          lower() called on each member. All other types are returned as they
          are.

        @rtype: type of L{obj}
        @return:
          Lowercased version of obj, if possible, or obj itself.
        """

        if isinstance(obj, (tuple, list, set)):
            return type(obj)([self.lower(x) for x in obj])
        elif isinstance(obj, dict):
            return dict((self.lower(x), self.lower(y)) for (x, y) in obj.iteritems())
        elif isinstance(obj, str):
            return obj.lower()
        elif isinstance(obj, unicode):
            return obj.encode("iso-8859-1").lower()
        else:
            return obj
    # end lower



    def group_name2ou_id(self, group_name):
        """Figure out which department (avdeling) a group should be associated
        with.
        
        All hiof's Fronter-groups are associated with a department (it's part of
        their name, in fact).
        """

        keys = group_name.split(":")
        sko = keys[3]
        assert sko.isdigit() and len(sko) == 6
        fak, inst, avd = int(sko[:2]), int(sko[2:4]), int(sko[4:])
        ou = Factory.get("OU")(self._db)
        return ou.find_stedkode(fak, inst, avd, cereconf.DEFAULT_INSTITUSJONSNR)
    # end group_name2ou_id



    def fixup_attributes(self, attributes):
        """Convert attributes to standard form and amend with extra keys.

        This is a convenience/external method.
        """

        # Force lowercase, so we won't have to bother about this later.
        attrs = self.lower(attributes)
        # Force-insert a few required attributes
        attrs = self._extend_attributes(attrs)
        return attrs
    # end fixup_attributes

    

    def _extend_attributes(self, attrs):
        """Extend L{attributes} to include some generic values.
    
        All of the groups generated from attributes must have 'avdeling' and
        'institusjonsnr' keys. This function makes sure it is the case.
    
        @type attrs: dict (of basestring to whatever)
        @param attrs:
          Dictionary with values generated from elements in an XML file. These are
          the values we are supplementing.
    
        @param stprog2avd:
          A dictionary mapping stprog codes to the corresponding departments
          (avdeling).
    
        @param emne2avd:
          A dictionary mapping emner (emnekoder) to the corresponding departments
          (avdeling).
    
        @return:
          Modified L{attributes} with a few additional keys. attributes is
          modified in place (and returned as welle.)
        """
    
        # If there is a studieprogram key, we amend attrs with the faculty
        # (avdeling) with which this stprog is associated.
        if "studieprogramkode" in attrs:
            avdeling = self.stprog2avdeling.get(attrs["studieprogramkode"])
            if not avdeling:
                logger.warn("Do not know how to map stprog=%s to avdeling",
                            attrs["studieprogramkode"])
            else:
                attrs["avdeling"] = avdeling

        # Same as with stprog above.
        if "emnekode" in attrs:
            avdeling = self.emne2avdeling.get(attrs["emnekode"])
            if not avdeling:
                logger.warn("Do not know how to map emne=%s to avdeling",
                            attrs["emnekode"])
            else:
                attrs["avdeling"] = avdeling
    
        # Everything gets institusjonsnr, since it's needed for all keys.
        attrs["institusjonsnr"] = cereconf.DEFAULT_INSTITUSJONSNR
    
        return attrs
    # end _extend_attributes



    def _stprog2avdeling(self, stprog_file):
        """Create a dictionary mapping stprog to avdeling (department).
        
        fs.studieprogram.faknr_studieansv is the value we want.
        """

        result = dict()
        for entry in EduDataGetter(stprog_file, logger).iter_stprog():
            attrs = self.lower(entry)
            stprog = attrs["studieprogramkode"]
            result[stprog] = "%02d0000" % int(attrs["faknr_studieansv"])

        logger.debug("Collected %d stprog->avdeling mappings from %s",
                     len(result), stprog_file)
        return result
    # end _stprog2avdeling



    def _emne2avdeling(self, emne_file):
        """Create a dictionary mapping emnekode to avdeling (department).
        
        fs.undervisningsemne.faknr_reglement is the value we want.
        """

        result = dict()
        def slurp_emne(element, attributes):
            if element == "emne":
                emne = self.lower(attributes["emnekode"])
                result[emne] = "%02d0000" % int(attributes["faknr_reglement"])

        access_FS.emne_xml_parser(emne_file, slurp_emne)
        logger.debug("Collected %d emne->avdeling mappings from %s",
                     len(result), emne_file)
        return result
    # end _emne2avdeling
# end FSAttributeHandler




def collect_roles(role_file, fs_handler):
    """Read role data and build a suitable data structure.

    Extract all the interesting roles from role_file, and return a suitable
    representation of the roles for group building.

    @type role_file: basestring
    @param role_file:
      File with FS role data. Not all roles are of interest!
    """

    logger.debug("Extracting roles from %s", role_file)
    role_parser = access_FS.roles_xml_parser
    
    result = dict()

    def slurp_role(element_name, attributes):
        """Look at a specific <role>-element"""

        if element_name != "rolle":
            return

        # what *kind* of role is this?
        role_kind = attributes[role_parser.target_key]
        if len(role_kind) != 1:
            # A warning about this has has already been issued
            return 
        role_kind = role_kind[0]

        if role_kind not in fs_handler.valid_roles:
            logger.debug("Ignoring '%s' role for: %s",
                         role_kind, repr(attributes))
            return

        attrs = fs_handler.fixup_attributes(attributes)
        if attrs["rollekode"] not in fs_handler.valid_role_codes:
            logger.debug("Ignoring '%s' role, role code %s: attrs=%s",
                         role_kind, attrs["rollekode"], attrs)
            return 

        logger.debug("Collecting role '%s' with %s",
                     role_kind, repr(attributes))

        group_key = fs_handler.attributes2key(role_kind, attrs)
        if group_key is None:
            return
        fs_handler.register_description(group_key, attrs)
        if group_key is None:
            logger.warn("Failed to create group key for role=%s/attrs=%s",
                        role_kind, attrs)
            return

        if not fs_handler.role_is_exportable(role_kind, attrs):
            logger.debug("Ignoring role=%s/attrs=%s (not exportable to LMS)",
                         role_kind, attrs)
            return

        fnr = "%06d%05d" % (int(attrs["fodselsdato"]),
                            int(attrs["personnr"]))
        result.setdefault(group_key, set()).add(fnr)
    # end slurp_role

    access_FS.roles_xml_parser(role_file, slurp_role)
    logger.debug("Roles from %s result in %d groups", role_file, len(result))
    return result
# end collect_roles



def collect_student_info(edu_info_file, fs_handler):
    """Read student data and build a suitable data structure.

    Since we have student rooms for undenh, undakt and kullklasse, these are
    the XML tags we are interested in. The rest is of no consequence.
    """

    result = dict()
    
    # FIXME: it's silly to iterate the same file thrice.
    #
    for (xml_tag, edu_info_type) in (("undenh", "student-undenh"),
                                     ("undakt", "student-undakt"),
                                     ("kullklasse", "student-kullklasse"),):
        logger.debug("Processing <%s> elements", xml_tag)
        for entry in EduGenericIterator(edu_info_file, xml_tag):
            attrs = fs_handler.fixup_attributes(entry)
            key = fs_handler.attributes2key(edu_info_type, attrs)
            if key is None:
                continue
            fs_handler.register_description(key, attrs)
            if key is None:
                logger.warn("Failed to create group key for entry=%s/attrs=%s",
                            xml_tag, attrs)
                continue
            
            if not fs_handler.edu_entry_is_exportable(xml_tag, attrs):
                logger.debug("Ignoring %s/attrs=%s (not exportable to LMS)",
                             xml_tag, attrs)
                continue

            fnr = "%06d%05d" % (int(attrs["fodselsdato"]),
                                int(attrs["personnr"]))
            result.setdefault(key, set()).add(fnr)

    logger.debug("%s student groups (%s individual memberships) arose from %s",
                 len(result),
                 sum(len(y) for y in result.itervalues()),
                 edu_info_file)
    return result
# end collect_student_info



def person_id2account_id(db):
    """Build a dict mapping person_id to primary account_id."""

    account = Factory.get("Account")(db)
    result = dict()
    
    logger.debug("Loading all person_id -> primary account_id")
    for row in account.list_accounts_by_type(primary_only=True):
        person_id = row["person_id"]
        account_id = row["account_id"]
        result[person_id] = account_id

    logger.debug("%d person_id -> primary account_id mappings",
                 len(result))
    return result
# end person_id2account_id



def fnr2person_id(db):
    """Build a dict mapping fnrs to person_ids in Cerebrum.
    """

    person = Factory.get("Person")(db)
    const = Factory.get("Constants")()
    result = dict()
    
    logger.debug("Loading all fnr -> person_id")
    for row in person.list_external_ids(id_type=const.externalid_fodselsnr):
        person_id = row["entity_id"]
        fnr = row["external_id"]
        result[fnr] = person_id

    logger.debug("%d fnr -> person_id mappings", len(result))
    return result
# end fnr2person_id
    


def fnr2account_id(db):
    """Build a dictionary mapping FNRs to account_ids.
    """

    # FIXME: there is quite a bit of copying around here. Can any of it be
    # avoided?
    p2a = person_id2account_id(db)
    f2p = fnr2person_id(db)
    result = dict()
    for fnr in f2p:
        person_id = f2p[fnr]
        if person_id not in p2a:
            logger.debug2("Cannot map fnr=%s/person_id=%s to primary account",
                          fnr, person_id)
            continue

        account_id = p2a[person_id]
        result[fnr] = account_id

    logger.debug("%d fnr -> primary account_id mappings", len(result))
    return result
# end fnr2account_id
        


def remap_fnr_to_account_id(db, *groups_from_fs):
    """Replace all FNRs with account_ids (for primary account) everywhere in
    groups_from_fs.

    FS uses fnrs for identification. We, however, need accounts as members of
    CF-groups for later processing. The easiest is probably to remap fnrs to
    account_ids before we start syncing FS with Cerebrum.

    @param groups_in_fs:
      A sequence of dicts, where each dict is a mapping from group names to
      sets of fnrs. We want to remap the fnrs to the corresponding (primary
      account) account_ids.

    @return:
      One dictionary with all group_names and the corresponding member
      account_ids. Should two entries in groups_from_fs have overlapping
      group_names, the latter overwrites the former.
    """

    # it's too time consuming to use person.find() + fetch external_id. It
    # makes more sense to cache all id mappings in one db query.
    cache = fnr2account_id(db)

    def remapper_helper(fnr):
        if fnr not in cache:
            logger.debug2("Cannot map fnr=%s to account_id", fnr)
            return None
        return cache[fnr]
    # end remapper_helper

    logger.debug("Remapping FS fnrs to Cerebrum primary account_ids")
    result = dict()
    for group_dict in groups_from_fs:
        for group_name in group_dict:
            logger.debug("Remapping fnrs to account_ids for group name=%s",
                         group_name)
            result[group_name] = set(remapper_helper(x)
                                     for x in group_dict[group_name]
                                     if remapper_helper(x))
    return result
# end remap_fnr_to_account_id



def create_fs_groups(db, fs_handler, fs_groups):
    """Make sure that all groups listed in fs_groups exist in Cerebrum.

    Should a group be missing, it's created and populated with proper info and
    traits.
    """

    group = Factory.get("Group")(db)
    const = Factory.get("Constants")(db)
    # Locate the system account for group creation
    account = Factory.get("Account")(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    creator_id = account.entity_id

    for group_name in fs_groups:
        description = fs_handler.get_description(group_name)
        group.clear()
        try:
            group.find_by_name(group_name)
            # This is necessary to alter group names for multisemester
            # undenh/undakt. The description changes, the group id does not.
            if group.description != description:
                logger.debug("Changing description for existing group "
                             "id=%s/name=%s: %s -> %s",
                             group.entity_id, group.group_name,
                             group.description, description)
                group.description = description
                group.write_db()
                
            logger.debug("Found old CF group id=%s/name=%s, description=%s",
                         group.entity_id, group.group_name, group.description)
        except Errors.NotFoundError:
            group.populate(creator_id,
                           const.group_visibility_all,
                           group_name,
                           description)
            group.write_db()
            logger.debug("Created new CF group id=%s/name=%s, description=%s",
                         group.entity_id, group_name, description)

        # Tag the groups with the right trait
        if group.get_trait(const.trait_cf_group):
            continue

        ou_id = fs_handler.group_name2ou_id(group_name)
        group.populate_trait(const.trait_cf_group, target_id=ou_id)
        group.write_db()
# end create_fs_groups



def collect_existing_cf_groups(db):
    """Grab all groups in Cerebrum that exist for CF only.

    We tag every group with a special EntityTrait. Thus, collecting the groups
    is a matter of listing all Groups with that trait. 
    """

    result = dict()
    group = Factory.get("Group")(db)
    const = Factory.get("Constants")(db)
    logger.debug("Collecting all CF groups in Cerebrum")
    for row in group.list_traits(return_name=True,
                                 code=const.trait_cf_group):
        group_id = row["entity_id"]
        group_name = row["name"]
        result[group_name] = set(row["member_id"]
                                 for row in
                                 group.search_members(
                                     group_id=group_id,
                                     member_type=const.entity_account))

    logger.debug("%s CF groups (%s individual memberships) are in Cerebrum",
                 len(result),
                 sum(len(y) for y in result.itervalues()))
    return result
# end collect_existing_cf_groups



def synchronize_groups(db, fs_groups):
    """Synchronise the FS group picture with Cerebrum.

    @param role_groups:
      A dict from group ids (NOT entity_ids) to sequences of fnrs for the
      members of that particular group.
    """

    # groups currently in the db
    groups_in_cerebrum = collect_existing_cf_groups(db)

    # Good to go.
    sync_file_with_database(db, groups_in_cerebrum, fs_groups)
# end build_groups



def sync_file_with_database(db, groups_in_cerebrum, groups_in_fs):
    """Compare the data structures and write the differences to the database.

    What does it mean, exactly? FS data structure represents the image of what
    the database should look like when we are done. If it were not for time
    constraints and HUGE change_log deltas, we could just drop everything in
    groups_in_cerebrum and then write everything in groups_in_fs.

    Obviously we can't do that in practice. So, for each group, we'll sync the
    contents. A nice bonus is that group members are registered in sets, so we
    have intersection() available.
    """

    for group_name in groups_in_fs:
        current_fs_set = groups_in_fs[group_name]
        current_cerebrum_set = groups_in_cerebrum.get(group_name, set())

        sync_member_sets(db, group_name, current_cerebrum_set, current_fs_set)
        if group_name in groups_in_cerebrum:
            del groups_in_cerebrum[group_name]

    # Whatever remains in groups_in_cerebrum at *this* point has to be
    # removed, because there is no data basis in FS for these groups to exist.
    for group_name in groups_in_cerebrum:
        nuke_cf_group(db, group_name)
# end sync_file_with_database



def sync_member_sets(db, group_name, cerebrum_set, fs_set):
    """Make sure that the members associated with group_name are exactly those
    in fs_set.

    @param group_name: Name of the group we are processing (it's uniqued')

    @param cerebrum_set: Set of account_ids that are members in cerebrum.

    @param fs_set: Set of account_ids that are members in FS.
    """

    to_remove = cerebrum_set.difference(fs_set)
    to_add = fs_set.difference(cerebrum_set)
    group = Factory.get("Group")(db)
    group.find_by_name(group_name)

    if to_add or to_remove:
        logger.debug("Synching member sets for group id=%s/name=%s: "
                     "to add=%s, to remove=%s",
                     group.entity_id, group.group_name,
                     len(to_add), len(to_remove))
    else:
        logger.debug("No changes to group id=%s/name=%s",
                     group.entity_id, group.group_name)

    for account_id in to_remove:
        group.remove_member(account_id)

    for account_id in to_add:
        group.add_member(account_id)
# end sync_member_sets



def nuke_cf_group(db, group_name):
    """Make sure that subsequent CF exports do not see this group.

    The basis for p_f_g and XML-generation are groups built by *this*
    script. Essentially, there are two ways of identifying groups -- either by
    name (they are structured in a very specific way) OR by some attributes
    associated with the group.

    For hiof we'll use traits to mark the CF groups holding people that should
    be registered for export. As soon as such a trait is deleted, the group is
    exempt from all CF-relevant jobs. This gives us an easy way of disabling a
    group for CF without losing the information about the existence of a group
    and its members.

    Should we later opt for actual group deletion, it can (still) be done here.
    """

    const = Factory.get("Constants")()
    group = Factory.get("Group")(db)
    group.find_by_name(group_name)
    logger.debug("Nuking CF group id=%s/name=%s",
                 group.entity_id, group.group_name)
    if group.get_trait(const.trait_cf_group):
        group.delete_trait(const.trait_cf_group)
# end nuke_cf_group



def check_files_exist(*files):
    """Check that all files are readable by us"""

    for filename in files:
        if not os.access(filename, os.R_OK):
            logger.warn("%s is unreadable", filename)
            sys.exit(1)
# end check_files_exist



def main():
    global logger
    logger = Factory.get_logger("cronjob")

    # Upper/lowercasing of Norwegian letters.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    options, junk = getopt.getopt(sys.argv[1:],
                                  "d",
                                  ("role-file=",
                                   "stprog-file=",
                                   "emne-file=",
                                   "edu-file=",
                                   "undenh-file=",
                                   "undakt-file=",
                                   "dryrun",))

    dryrun = False
    role_file = stprog_file = emne_file = edu_file = ""
    undenh_file = undakt_file = ""
    for option, value in options:
        if option in ("-d", "--dryrun",):
            dryrun = True
        elif option in ("--role-file",):
            role_file = value
        elif option in ("--stprog-file",):
            stprog_file = value
        elif option in ("--emne-file",):
            emne_file = value
        elif option in ("--edu-file",):
            edu_file = value
        elif option in ("--undenh-file",):
            undenh_file = value
        elif option in ("--undakt-file",):
            undakt_file = value

    check_files_exist(role_file, stprog_file, emne_file, edu_file,
                      undenh_file, undakt_file)
    db = Factory.get("Database")()
    db.cl_init(change_program="pop-front-groups")
    fs_handler = FSAttributeHandler(db, stprog_file, emne_file,
                                    undenh_file, undakt_file)

    # get all the roles and assign them to group names
    roles = collect_roles(role_file, fs_handler)
    # get all the students and assign them to group names
    students = collect_student_info(edu_file, fs_handler)

    # force all FS members to Cerebrum person_ids
    fs_groups = remap_fnr_to_account_id(db, roles, students)

    # Make sure all CF groups exist
    create_fs_groups(db, fs_handler, fs_groups)

    # synchronise file information with cerebrum
    synchronize_groups(db, fs_groups)

    if dryrun:
        db.rollback()
        logger.debug("Rollback all changes")
    else:
        db.commit()
        logger.debug("Committed all changes")
# end main



if __name__ == "__main__":
    main()
    
