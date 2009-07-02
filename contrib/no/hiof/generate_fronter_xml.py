#!/usr/bin/env python
# -*- encoding: iso-8859-1 -*-

"""This file contains the code to generate an XML file for import into
Fronter, HiØf's LMS.

It works in conjunction with populate_fronter_groups.py and is meant to
complement it -- p_f_g generates the necessary groups whereas g_f_x generates
an XML file from these groups.

All groups making the basis for XML output are tagged with a special trait,
and they have a highly structured name. Additionally, each trait links a group
with an ou (== avdeling) where such a group should be placed.

FIXME: Write a few words about how the script is organised.

FIXME: Flersemesteremnre are placed under the wrong node. The title is
correct, though, albeit somewhat hackish.

FIXME: 
"""

import getopt
import locale
import mx.DateTime
import sys


import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.Utils import simple_memoize
from Cerebrum.Utils import SimilarSizeWriter
from Cerebrum.extlib import xmlprinter



logger = None
STATUS_ADD = "1"
STATUS_UPDATE = "2"
STATUS_DELETE = "3"



class cf_permission(object):

    ROLE_READ = '01'
    ROLE_WRITE = '02'
    ROLE_DELETE = '03'
    ROLE_CHANGE = '07'

    access2symbol = {
        ROLE_READ: "READ",
        ROLE_WRITE: "WRITE",
        ROLE_DELETE: "DELETE",
        ROLE_CHANGE: "CHANGE",
    }

    def __init__(self, access_type, recursive, holder, target):
        # Does the permission apply recursively?
        self._recursive = recursive
        # read/write/delete/change
        self._access = access_type
        # the group that has the permissions on target
        self._holder = holder
        # the 'victim' of the permission assignment
        self._target = target
        assert self._access in self.access2symbol
    # end __init__


    def access_type(self):
        return self._access

    def is_recursive(self):
        return self._recursive

    def target(self):
        return self._target

    def holder(self):
        return self._holder

    def __str__(self):
        return "cf_perm %s (%s) for %s on %s" % (
            self.access2symbol[self.access_type()],
            self.is_recursive() and "recursive" or "non-recursive",
            self.holder(),
            self.target())
    # end __str__
# end cf_permission



class cf_tree(object):
    def __init__(self, db):
        self._root = None
        self._cf_id2node = dict()
        self._db = db

        self._build_static_nodes()
    # end __init__


    def _build_static_nodes(self):
        """Build the static part of OA/hiof's CF tree"""

        self._root = cf_structure_group("Oslofjordalliansen", "root", None)
        self.register_structure_group(self._root)

        hiof = cf_structure_group("HiØ", "STRUCTURE:hiof.no", self._root)
        self.register_structure_group(hiof)

        tmp = cf_structure_group("Automatisk",
                                 "STRUCTURE:hiof.no:automatisk", hiof)
        self.register_structure_group(tmp)
        tmp = cf_structure_group("Manuell",
                                 "STRUCTURE:hiof.no:manuell", hiof)
        self.register_structure_group(tmp)
    # end _build_static


    def get_cf_group(self, cf_id, default=None):
        return self._cf_id2node.get(cf_id, default)
    # end get_cf_group
        

    def register_member_group(self, cfmg):
        assert isinstance(cfmg, cf_member_group)
        cf_group_id = cfmg.cf_id()
        self._cf_id2node[cf_group_id] = cfmg


    def register_structure_group(self, cfsg):
        assert isinstance(cfsg, cf_structure_group)
        cf_group_id = cfsg.cf_id()
        self._cf_id2node[cf_group_id] = cfsg
    # end register_structure_group


    def create_associated_structures(self, cf_group):
        """Given a cf_member/structure_group, create *ALL* the necessary
        associated groups upwards in the structure tree.

        cf_group may be either a cf_structure_group or a cf_member_group.

        For cf_structure_group we figure out which group is the parent. If it
        does not exist, it's created (recursively).

        For cf_member_group we figure out which structure group it corresponds
        to. If it does not exist, it's created (recursively).

        @return:
          This returns a group that cf_group should be associated
          with. I.e. cf_group's 'closest' node in the structure hierarchy
        """

        structure_id = cf_group.cf_parent_id()
        if structure_id is None:
            logger.debug("No structure created for cf_group=%s", str(cf_group))
            return None
        if self.get_cf_group(structure_id):
            self.get_cf_group(structure_id).add_child(cf_group)
            return self.get_cf_group(structure_id)

        # No parent -> create new one
        # Regardless of cf_group's type, we create cf_structure_groups only.
        logger.debug("Creating new node id=%s (parent for %s)",
                     structure_id, cf_group.cf_id())
        new_node = cf_structure_group(cf_group.cf_parent_title(),
                                      structure_id,
                                      # None, since we don't know what the
                                      # parent is at this point.
                                      None)
        self.register_structure_group(new_node)
        new_node.add_child(cf_group)
        # This will eventually stop at a node that already exist, since we
        # have several static nodes in the tree.
        grandparent_node = self.create_associated_structures(new_node)
        # This will fix new_node's parent link as well.
        grandparent_node.add_child(new_node)
        return new_node
    # end create_associated_structures


    def iterate_groups(self, group_type=None):
        """Create an iterator for the specific group type in the CF-tree.
        """

        for group in self._cf_id2node.itervalues():
            if group.cf_group_type() == "emne":
                logger.debug("Ignoring 'emne' CF group: %s", str(group))
                continue
            
            if (group_type is None or
                isinstance(group, group_type)):
                yield group
    # end iterate_groups


    def get_root(self):
        return self._root
    # end get_root
# end cf_tree



class cf_group_interface(object):

    _acronym2avdeling = None

    def __init__(self):
        self._parent = None
    # end __init__


    @staticmethod
    def load_acronyms(db):
        result = dict()
        ou = Factory.get("OU")(db)
        for row in ou.list_all():
            ou.clear()
            ou.find(row["ou_id"])
            key = "%02d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling)
            result[key] = row["acronym"]
        cf_group_interface._acronym2avdeling = result
    # end load_acronyms


    def cf_group_type(self):
        raise NotImplementedError("N/A")

    def cf_id(self):
        raise NotImplementedError("N/A")        

    def cf_title(self):
        raise NotImplementedError("N/A")

    def cf_parent_id(self):
        raise NotImplementedError("N/A")

    def cf_parent_title(self):
        # If the parent link already exists, we are done
        if self._parent:
            return self._parent.cf_title()

        # If not, let's guess
        parent_id = self.cf_parent_id()
        parent_components = parent_id.split(":")

        if "klasse" in parent_components:
            return "Rom for kull %s %s, klasse %s" % (
                    parent_components[-3],
                    parent_components[-4],
                    parent_components[-1])
        elif "kull" in parent_components:
            idx = parent_components.index("kull")
            return "Kull %s %s" % (parent_components[idx+2],
                                   parent_components[idx+1])
        elif "studieprogram" in parent_components:
            idx = parent_components.index("studieprogram")
            return "Studieprogram %s" % parent_components[idx+1].upper()
        elif ("undenh" in parent_components) or ("undakt" in parent_components):
            # group's description (cf_title()) has the right semester number
            # even for multisemester undenh/undakt, this structure will have
            # the right title.
            title_components = self.cf_title().split(" ")
            return "Rom for " + " ".join(title_components[2:])
        elif "emner" in parent_components:
            idx = parent_components.index("emner")
            return "Emnerom %s %s" % (parent_components[idx+2],
                                      parent_components[idx+1])
        # avdeling
        elif len(parent_components) == 5 and parent_components[-1].isdigit():
            return "%s" % self._acronym2avdeling[parent_components[-1]]
        elif "automatisk" in parent_components:
            return "Automatisk"
        # for the sake of completeness
        elif "manuell" in parent_components:
            return "Manuell"
        elif parent_id == "root":
            return "Oslofjordalliansen"

        assert False, "This cannot happen: parent_id=%s" % parent_id
    # end cf_parent_id
# end cf_node_interface



class cf_structure_group(cf_group_interface):
    """A group representing a structure (a room or a corridor) in CF.

    This class deals with intergroup relations in CF (permissions,
    parent-child relations, etc.). Some cf_structure_groups would have
    cf_member_group(s) associated with them (typically student / FS role
    holder groups). That association is used to grant access permissions in
    CF.
    """

    valid_types = ("STRUCTURE", "ROOM")

    def __init__(self, description, cf_id, parent):
        super(cf_structure_group, self).__init__()
        self._cf_id = cf_id
        self._title = description
        self._parent = parent
        if self._parent:
            self._parent.add_child(self)
        self._structure_children = dict()
        self._permissions = dict()
        self._group_type = self._calculate_group_type()
    # end __init__


    def cf_id(self):
        return self._cf_id


    def cf_title(self):
        return self._title


    def cf_group_type(self):
        return self._group_type


    def cf_parent_id(self):
        """Calculate which *structure* group is the parent of this group.

        If the _parent link has already been established

        Until the _parent link is set, we don't have the actual parent node
        and have to calculate the id itself.

        The idea is to figure out which parent structure group a given
        structure group should be associated with. This happens during the
        creation of the cf structure tree.
        """

        # If the parent link already exists, we are done.
        if self._parent:
            return self._parent.cf_id()

        # Now, which structure node is this?
        components = self.cf_id().split(":")
        result = None
        if self.cf_group_type() == "ROOM":
            # kullklasse
            if "klasse" in components:
                result = ["STRUCTURE",] + components[1:-2]
            elif "undenh" in components:
                # FIXME: flersemesteremner. The id refers to terminnnr=1. We
                # need to count forward in time to calculate the proper
                # structure node id.
                result = ["STRUCTURE",] + components[1:-4]
            elif "undakt" in components:
                # FIXME: flersemesteremner. Same as undenh
                result = ["STRUCTURE",] + components[1:-5]
            else:
                assert False, "This cannot happen: self.id=%s" % self.cf_id()
            return ":".join(result)
        else:
            # kull -> stprog
            if "kull" in components:
                result = components[:-3]
            # stprog -> avdeling
            elif "studieprogram" in components:
                result = components[:-2]
            # emnerom -> avdeling
            elif "emner" in components:
                result = components[:-3]
            # avdeling -> automatisk
            elif len(components) == 5 and components[-1].isdigit():
                return "STRUCTURE:hiof.no:automatisk"
            # root is special
            elif self.cf_id() == "root":
                return self.cf_id()
            else:
                assert False, "This cannot happen: self.id=%s" % self.cf_id()
            return ":".join(result)
    # end cf_parent_id
        

    def _calculate_group_type(self):
        """Figure out what kind of structure group this is -- STRUCTURE
        (corridor) or ROOM"""

        # root is special. UNFORTUNATELY
        if self.cf_id() == "root":
            return "STRUCTURE"
        
        components = self.cf_id().split(":")
        assert components[0] in self.valid_types
        return components[0]
    # end _calculate_group_type


    def add_child(self, child):
        self._structure_children[child.cf_id()] = child
        # this will allow us to create parentless nodes, and have them fixed
        # up later on. _parent slot is initialised to None.
        if child._parent != self:
            child._parent = self
    # end add_child


    def iterate_children(self, child_type=None):
        for child in self._structure_children.itervalues():
            if (child_type is None or
                isinstance(child, child_type)):
                yield child
    # end iterate_children


    def iterate_permissions(self):
        return self._permissions.itervalues()
    # end iterate_permissions

    def register_permissions(self, cf_group):
        assert isinstance(cf_group, cf_member_group)
        permission = cf_group.get_cf_permission(self)
        if permission is not None:
            self._permissions[cf_group.cf_id()] = permission

        logger.debug("Registered permission %s", str(permission))
    # end register_permissions


    def __str__(self):
        return "CFSG id=%s (parent=%s), %d structure members, %d perm groups" % (
            self.cf_id(), self._parent.cf_id(), len(self._structure_children),
            len(self._permissions))
    # end __str__
# end cf_structure_group
    


class cf_member_group(cf_group_interface):
    """A group holding members of a Cerebrum group for CF.

    This class deals with member management and storing member attributes to
    export to CF (unames, e-mails, etc)
    """
                   # FS role groups
    valid_types = ("stprog", "kull", "kullklasse", "emne", "undenh", "undakt",
                   # FS student groups
                   "student-undenh", "student-undakt", "student-kullklasse",)

    def __init__(self, group):
        super(cf_member_group, self).__init__()
        self._cf_id = group.group_name
        self._title = group.description
        self._account_ids = [x["member_id"]
                             for x in group.search_members(group_id=group.entity_id)]
        self._group_type = self._calculate_group_type()
        self._parent = None
        assert self._group_type in self.valid_types, \
               "Cannot deduce type for group id=%s/name=%s: type=%s" % (group.entity_id,
                                                                        group.group_name,
                                                                        self._group_type)
    # end __init__


    def cf_id(self):
        return self._cf_id


    def cf_title(self):
        return self._title


    def cf_group_type(self):
        return self._group_type


    def cf_parent_id(self):
        """Calculate which *structure* group this member group corresponds to.

        The idea is to figure out which structure group a given member group
        should be associated with. Member groups are 'extracted' directly from
        Cerebrum, whereas structure groups will have to be deduced.
        """

        if self._parent is not None:
            return self._parent.cf_id()

        group_type2cf_structure_fixup = {
            "student-undenh":     ("ROOM", -1), 
            "student-undakt":     ("ROOM", -1),
            "student-kullklasse": ("ROOM", -1),
            "emne":               (None, None),
            "undenh":             ("ROOM", -2),
            "undakt":             ("ROOM", -2),
            "kullklasse":         ("ROOM", -2),
            "kull":               ("STRUCTURE", -2),
            "stprog":             ("STRUCTURE", -2),
        }

        member_group_type = self.cf_group_type()
        if member_group_type == "emne":
            logger.debug("No cf structure group for cf_member group %s "
                         "(type=%s is ignored)",
                         self.cf_id(), member_group_type)
            return None
        elif member_group_type in group_type2cf_structure_fixup:
            prefix, last = group_type2cf_structure_fixup[member_group_type]
            components = self.cf_id().split(":")
            return ":".join([prefix,] + components[:last])
        else:
            assert False, "This cannot happen: cf_member id=%s/type=%s" % (
                self.cf_id(), member_group_type)

        assert False, "NOTREACHED"
    # end parent_cf_structure_id



    def _role_code(self):
        """What kind of role code does self correspond to?
        
        This makes sense for role groups only (i.e. NOT student-groups)
        """

        components = self.cf_id().split(":")
        assert "rolle" in components
        for marker in ("assistent", "hovedlærer", "kursansv", "lærer",
                       "kontakt", "veileder", "admin",):
            if marker in components:
                return marker

        assert (False,
                "This cannot happen: unknown role code for cd id=%s" %
                self.cf_id())
    # end _role_code
        

    def get_cf_permission(self, structure_group):
        """Calculate permission for self on L{structure_group}.

        The calculations are a bit involved, since the permission in question
        depends on both self AND structure_group. 'emne' groups do not result
        in any permission assignment, since 'emne' groups have no associated
        structure node.
        """

        all_read = {
            "stprog": cf_permission.ROLE_READ,
            "kull": cf_permission.ROLE_READ,
            "kullklasse": cf_permission.ROLE_READ,
            "undenh": cf_permission.ROLE_READ,
            "undakt": cf_permission.ROLE_READ,
        }

        all_write = {
            "stprog": cf_permission.ROLE_WRITE,
            "kull": cf_permission.ROLE_WRITE,
            "kullklasse": cf_permission.ROLE_WRITE,
            "undenh": cf_permission.ROLE_WRITE,
            "undakt": cf_permission.ROLE_WRITE,
        }

        all_delete = {
            "stprog": cf_permission.ROLE_DELETE,
            "kull": cf_permission.ROLE_DELETE,
            "kullklasse": cf_permission.ROLE_DELETE,
            "undenh": cf_permission.ROLE_DELETE,
            "undakt": cf_permission.ROLE_DELETE,
        }

        role_code2permission = {
            "assistent":   all_read,
            "hovedlærer":  all_write,
            "kursansv":    all_write,
            "lærer":       all_write,
            "kontakt":     all_read,
            "veileder":    { "stprog": cf_permission.ROLE_READ,
                             "kull": cf_permission.ROLE_READ,
                             "kullklasse": cf_permission.ROLE_READ,
                             "undenh": cf_permission.ROLE_WRITE,
                             "undakt": cf_permission.ROLE_WRITE,},
            "admin":       all_delete,
        }

        # emne roles are useless (there are no cf structures associated with
        # them).
        if self.cf_group_type() == "emne":
            return None

        access_type = None
        recursive = False
        if self.cf_group_type() in ("stprog", "kull"):
            recursive = True

        if self.cf_group_type() in ("student-undenh", "student-undakt",
                                    "student-kullklasse",):
            # students have WRITE
            access_type = cf_permission.ROLE_WRITE
        elif self.cf_group_type() in ("undenh", "undakt", "kullklasse",
                                      "kull", "stprog"):
            # These are the perms stemming from FS roles. We have to look at
            # the specific role
            role_code = self._role_code()
            access_type = role_code2permission[role_code][self.cf_group_type()]
        else:
            logger.debug("Weird group type for %s", str(self))
            assert False, "This cannot happen"

        perm_object = cf_permission(access_type, recursive,
                                    holder=self,
                                    target=structure_group)
        return perm_object
    # end get_cf_permission
    

    def _calculate_group_type(self):
        """Figure out what kind of group this is."""

        suffix_map = {"undenh": "undenh",
                      "undakt": "undakt",
                      "klasse": "kullklasse",
                      "emner": "emne",
                      "studieprogram": "stprog",
                      "kull": "kull",}

        components = self.cf_id().split(":")
        if "student" in components:
            for marker in ("undenh", "undakt", "klasse",):
                if marker in components:
                    return "student-" + suffix_map[marker]
            assert False, "This is impossible - no type for %s" % self.cf_id()
        elif "rolle" in components:
            for marker in ("undakt", "undenh", "emner",
                           "klasse", "kull", "studieprogram"):
                if marker in components:
                    return suffix_map[marker]
    # end _calculate_group_type


    def __str__(self):
        return "CFMG type=%s id=%s %d members" % (self.cf_group_type(),
                                                  self.cf_id(),
                                                  len(self._account_ids))
    # end __str__


    def iterate_members(self):
        return iter(self._account_ids)
    # end iterate_members
# end cf_member_group



class cf_members(object):
    """A class to keep track of person information in CF.

    Technically, this class is superfluous. However, we can cache a lot of
    information about people in order to speed up the output. All that caching
    is contained within this class. The only interface available is
    L{member_info}, which looks up all the necessary info by account_id.
    """

    def __init__(self, db):
        self.db = db
        self.const = Factory.get("Constants")(db)
    # end __init__


    def account2uname(self):
        """Construct a mapping from account_id to account_name.
        """

        account = Factory.get("Account")(self.db)
        result = dict()
        for row in account.list_names(self.const.account_namespace):
            result[row["entity_id"]] = row["entity_name"] + "@hiof.no"
        return result
    # end account_mapping


    def member_info(self):
        """Slurp i info about all members.

        @return:
          A dictionary from account_ids to dicts with the corresponding
          information. 
        """

        # For each person we need:
        #
        # [ok] uname
        # [ok] name
        # [ok] first name
        # [ok] e-mail address
        # imap-server
        # address (?)
        # phone number (?)
        # affiliation (?)
        account = Factory.get("Account")(self.db)
        person = Factory.get("Person")(self.db)
        const = self.const
        result = dict()

        logger.debug("Caching e-mail addresses")
        uname2mail = account.getdict_uname2mailaddr()

        logger.debug("Caching member names")
        person_id2name = person.getdict_persons_names(
            source_system=const.system_cached,
            name_types=[const.name_first, const.name_full])

        logger.debug("Caching primary accounts")
        fnr2uname = person.getdict_external_id2primary_account(
                        const.externalid_fodselsnr)

        logger.debug("Caching complete user records")
        for row in person.list_persons_atype_extid(idtype=const.externalid_fodselsnr):
            person_id = row["person_id"]
            fnr = row["external_id"]
            account_id = row["account_id"]

            if fnr not in fnr2uname:
                logger.debug("Ignoring person id=%s (no primary account)",
                             person_id)
                continue
            uname = fnr2uname[fnr]

            if uname not in uname2mail:
                logger.debug("Ignoring person id=%s (account %s has no e-mail)",
                             person_id, uname)
                continue
            email_address = uname2mail[uname]

            if person_id not in person_id2name:
                logger.debug("Ignoring person id=%s (person has no name)",
                             person_id)
                continue
            first_name = person_id2name[person_id].get(const.name_first, "")
            name = person_id2name[person_id].get(const.name_full, "")
            result[account_id] = {"name": name,
                                  "first": first_name,
                                  "email": email_address,
                                  "user": uname + "@hiof.no",}

        return result
    # end member_info
# end cf_members



def collect_cf_groups(db):
    """Collect all CF groups from Cerebrum."""

    group = Factory.get("Group")(db)
    const = Factory.get("Constants")()

    result = set(r["entity_id"] for r in
                 group.list_traits(code=const.trait_cf_group))
    logger.debug("Collected %d CF groups from Cerebrum", len(result))
    return result
# end collect_cf_groups



def locate_db_group(db, group_id):
    """Create a Group proxy for the specified group_id.
    """

    group = Factory.get("Group")(db)
    group.find(group_id)
    return group
# end locate_db_group



def build_cf_tree(db, db_groups):
    """Construct a complete CF tree with all groups and permissions.

    @param db:
      A database proxy.

    @param db_groups:
      Complete list of cerebrum group_ids which are the basis for CF
      population.
    """

    cf_group_interface.load_acronyms(db)
    tree = cf_tree(db)
    for group_id in db_groups:
        db_group = locate_db_group(db, group_id)
        cf_member = cf_member_group(db_group)
        tree.register_member_group(cf_member)
        logger.debug("Created CF group %s", str(cf_member))

        # Now that we have the group node, we create the corresponding
        # structure nodes (all of them).
        node = tree.create_associated_structures(cf_member)
        if node:
            logger.debug("Created assoc structures for cf_member id=%s. Parent "
                         "node is id=%s", cf_member.cf_id(), node.cf_id())
            node.register_permissions(cf_member)
        else:
            logger.debug("No node created for cf_member id=%s",
                         cf_member.cf_id())

    # FIXME: debug output a few more statistics
    logger.debug("Built a CF tree")
    return tree
# end build_cf_tree



def open_xml_stream(filename):
    """Open the xml file for writing.

    @return:
      Return an xmlprinter instance ready for output.
    """
    
    sink = SimilarSizeWriter(filename, "w")
    sink.set_size_change_limit(15)
    printer = xmlprinter.xmlprinter(sink,
                                    indent_level=2,
                                    data_mode=1,
                                    input_encoding="iso-8859-1")

    logger.debug("Opened %s for XML output", filename)
    return printer
# end open_xml_stream



def output_fixed_header(printer):

    printer.startElement("properties")
    printer.dataElement("datasource", "cerebrum@hiof.no")
    printer.dataElement("datetime", mx.DateTime.now().strftime("%Y-%M-%d"))
    printer.endElement("properties")
# end output_fixed_header



def output_source_element(printer):
    printer.dataElement("source", "cerebrum@hiof.no")
# end output_source_element



def output_id(id_data, printer):
    printer.startElement("sourcedid")
    output_source_element(printer)
    printer.dataElement("id", id_data)
    printer.endElement("sourcedid")
# end output_person_id


def output_person_names(data, printer):
    printer.startElement("name")
    printer.dataElement("fn", data["name"])
    printer.startElement("n")
    printer.dataElement("given", data["first"])
    printer.endElement("n")
    printer.endElement("name")
# end output_person_names


def output_person_element(data, printer):
    """Output all relevant data for a <person> element.
    """

    printer.startElement("person", {"recstatus": STATUS_ADD,})
    output_id(data["user"], printer)
    printer.dataElement("email", data["email"])
    output_person_names(data, printer)
    printer.endElement("person")
# end output_person_element    



def output_people(db, tree, printer):
    """Output information about all people mentioned in at least one group in
    tree.

    The information has already been prepared by the corresponding nodes. The
    only thing we need is to make sure that the same person is not output
    twice.
    """

    logger.debug("Outputting all people register in CF-tree (in-memory)")
    member_info = cf_members(db).member_info()
    processed = set()
    for group in tree.iterate_groups(cf_member_group):
        for member_id in group.iterate_members():
            if member_id in processed:
                continue

            xml_data = member_info.get(member_id)
            if xml_data is None:
                logger.warn("No data about account_id=%s", member_id)
                continue

            output_person_element(xml_data, printer)
# end output_people



def output_group_element(cf_group, printer):
    """Output all info pertaining to the specific cf_group"""

    printer.startElement("group", {"recstatus": STATUS_ADD,})
    output_id(cf_group.cf_id(), printer)

    # FIXME: <typevalue> here

    printer.startElement("description")
    if len(cf_group.cf_title()) > 60:
        printer.emptyTag("short")
        printer.dataElement("long", cf_group.cf_title())
    else:
        printer.dataElement("short", cf_group.cf_title())
    printer.endElement("description")

    printer.startElement("relationship", {"relation": "1"})
    output_id(cf_group.cf_parent_id(), printer)
    printer.emptyElement("label")
    printer.endElement("relationship")
    printer.endElement("group")
# end output_group_element
    


def output_member_groups(db, tree, printer):
    """Output all group information about the structures we are building in
    CF.

    db is passed along for completeness. It's unused here.
    """

    for cf_group in tree.iterate_groups():
        output_group_element(cf_group, printer)
# end output_member_groups



def output_membership(group, members, printer):
    """Output XML subtree for the specific membership."""

    printer.startElement("membership")
    output_id(group.cf_id(), printer)
    for member in members:
        printer.startElement("member")
        output_id(member, printer)
        # 1 = person, 2 = group
        printer.dataElement("idtype", "1")
        printer.startElement("role", {"restatus": STATUS_UPDATE,
                                      # FIXME: This should be expressed via cf_permission
                                      "roletype": cf_permission.ROLE_WRITE})
        # 0 = inactive member, 1 = active member
        printer.dataElement("status", "1")
        # FIXME: What does this junk mean? Alle person members seem to have
        # this memberof extension with type=2. This is a blind copy from
        # UiO/UiA.
        printer.startElement("extension")
        printer.emptyElement("memberof", {"type": "2"})
        printer.endElement("extension")
        printer.endElement("role")
        printer.endElement("member")
        
    printer.endElement("membership")
# end output_membership



def output_memberships(db, tree, printer):
    """Output all user membership information."""

    account2uname = cf_members(db).account2uname()
    for group in tree.iterate_groups(cf_member_group):
        members = [account2uname[x] for x in group.iterate_members()]
        if not members:
            continue

        output_membership(group, members, printer)
# end output_memberships
    


def output_node_permissions(cf_group, local_permissions,
                            inherited_permissions, printer):
    """Generate XML for representing permissions on cf_group.

    permissions is a sequence of cf_permission instances that list permissions
    (direct or indirect) on cf_group. I.e. there may be entries in permissions
    that have target != cf_group.
    """

    permissions = local_permissions + inherited_permissions
    
    # No permissions -> nothing to do
    if len(permissions) == 0:
        logger.debug("No permissions output for group id=%s",
                     cf_group.cf_id())
        return

    logger.debug("cf_group id=%s has %d local and %d inherited permissions",
                 cf_group.cf_id(), len(local_permissions),
                 len(inherited_permissions))

    printer.startElement("membership")
    output_id(cf_group.cf_id(), printer)
    for permission in permissions:
        printer.startElement("member")
        output_id(permission.holder().cf_id(), printer)
        # 1 = person, 2 = group
        printer.dataElement("idtype", "2")
        printer.startElement("role", {"recstatus": STATUS_UPDATE,
                                      "roletype": permission.access_type(),})
        # FIXME: what about <extension><memberof type="??"></extension> ?
        # FIXME: what about
        # <extension><groupaccess roomAccess="0" contactAccess="100"/></extension>
        # 0 = inactive, 1 = active member
        printer.dataElement("status", "1")
        printer.endElement("role")
        printer.endElement("member")

    # FIXME: what about viewContacts for inherited_permissions.holder() on
    # local_permissions().holder()? I.e. admin-group should be able to see the
    # student group, no?
    printer.endElement("membership")
# end output_node_permissions    
    


def process_node_permissions(node, inherited_permissions, printer):
    """Output permissions for the CF subtree with root at node.

    Permissions are generated in depth-first order down the tree.

    @type node: cf_structure_group instance
    @param node:
      Subtree root for which we generate permission data. I.e. other
      structures have permissions on L{node}.

    @type inherited_permissions: sequence of cf_permission instances.
    @param inherited_permissions:
      Sequence of permissions inherited by this node from its parents. Some
      groups result in recursive permissions. E.g. an 'admin' role given for a
      'stprog' is *inherited* for all structures associated with that 'stprog'
      (kull and kullklasse). Should node have its own recursive permissions,
      they are added to inherited_permissions.
    """

    #
    # There is a bit of tuple copying here; hopefully this won't be a
    # performance issue.
    #
    children = node.iterate_children(cf_structure_group)
    local_permissions = tuple(node.iterate_permissions())
    output_node_permissions(node, local_permissions, inherited_permissions,
                            printer)
    node_recursive_permissions = tuple(x for x in local_permissions
                                       if x.is_recursive())

    children_permissions = inherited_permissions + node_recursive_permissions
    for child in children:
        process_node_permissions(child, children_permissions, printer)
# end output_node_permissions



def output_permissions(db, tree, printer):
    """Output all permissions.

    Permissions are expressed in IMS enterprise through memberships, much like
    output_membership. However, in this case groups are members of other
    groups (groups-with-user-members are members of STRUCTURE/ROOM groups).
    """

    root = tree.get_root()
    process_node_permissions(root, tuple(), printer)
# end output_permissions


def generate_xml_file(filename, db, tree):
    """'Flatten' cf_tree to L{filename}.

    'Flattening' is accomplished in several steps:

      * output people
      * output all groups
      * output all memberships
      * output all permissions
    """

    printer = open_xml_stream(filename)
    printer.startDocument("utf-8")
    output_fixed_header(printer)
    output_people(db, tree, printer)
    output_member_groups(db, tree, printer)
    output_memberships(db, tree, printer)
    output_permissions(db, tree, printer)
    printer.endDocument()
    printer.fp.close()
# end generate_xml_file
    


def main(argv):

    # Upper/lowercasing of Norwegian letters.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    global logger
    logger = Factory.get_logger("cronjob")


    options, junk = getopt.getopt(argv[1:],
                                  "f:",
                                  ("file=",))

    filename = None
    for option, value in options:
        if option in ("-f", "--file",):
            filename = value

    db = Factory.get("Database")()
    groups = collect_cf_groups(db)
    tree = build_cf_tree(db, groups)
    generate_xml_file(filename, db, tree)
# end main



if __name__ == "__main__":
    main(sys.argv)
