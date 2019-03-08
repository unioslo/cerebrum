# -*- coding: utf-8 -*-

# Copyright 2002-2018 University of Oslo, Norway
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

import time
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Errors
from mx import DateTime


class BofhdRequests(object):
    def __init__(self, db, const, id=None):
        self._db = db
        self.co = const

        midnight = DateTime.today()
        now = DateTime.now()
        # if we are past 22:00 this day, schedule for tomorrow evening
        if (now - midnight) > DateTime.TimeDeltaFrom(hours=22):
            self.batch_time = midnight + DateTime.TimeDeltaFrom(days=1,
                                                                hours=22)
        # ... otherwise, schedule for this day
        else:
            self.batch_time = midnight + DateTime.TimeDeltaFrom(hours=22)

        self.now = now

        # "None" means _no_ conflicts, there can even be several of
        # that op pending.  All other ops implicitly conflict with
        # themselves, so there can only be one of each op.
        self.conflicts = {
            int(const.bofh_move_user): [const.bofh_move_student,
                                        const.bofh_move_user_now,
                                        const.bofh_move_request,
                                        const.bofh_delete_user],
            int(const.bofh_move_student): [const.bofh_move_user,
                                           const.bofh_move_user_now,
                                           const.bofh_move_request,
                                           const.bofh_delete_user],
            int(const.bofh_move_user_now): [const.bofh_move_student,
                                            const.bofh_move_user,
                                            const.bofh_move_request,
                                            const.bofh_delete_user],
            int(const.bofh_move_request): [const.bofh_move_user,
                                           const.bofh_move_user_now,
                                           const.bofh_move_student,
                                           const.bofh_delete_user],
            int(const.bofh_move_give): None,
            int(const.bofh_archive_user): [const.bofh_move_user,
                                           const.bofh_move_user_now,
                                           const.bofh_move_student,
                                           const.bofh_delete_user],
            int(const.bofh_delete_user): [const.bofh_move_user,
                                          const.bofh_move_user_now,
                                          const.bofh_move_student,
                                          const.bofh_email_create],
            int(const.bofh_email_create): [const.bofh_email_delete,
                                           const.bofh_delete_user],
            int(const.bofh_email_delete): [const.bofh_email_create],
            int(const.bofh_email_convert): [const.bofh_email_delete],
            int(const.bofh_sympa_create): [const.bofh_sympa_remove],
            int(const.bofh_sympa_remove): [const.bofh_sympa_create],
            int(const.bofh_quarantine_refresh): None,
            int(const.bofh_email_restore): [const.bofh_email_create],
            int(const.bofh_homedir_restore): [const.bofh_move_user,
                                              const.bofh_move_user_now,
                                              const.bofh_move_student,
                                              const.bofh_delete_user]
            }

    def get_conflicts(self, op):
        """Returns a list of conflicting operation types.  op can be
        an integer or a constant."""

        conflicts = self.conflicts[int(op)]

        if conflicts is None:
            conflicts = []
        else:
            conflicts.append(op)
        # Make sure all elements in the returned list are integers
        return [int(c) for c in conflicts]

    def add_request(self, operator, when, op_code, entity_id,
                    destination_id, state_data=None):

        conflicts = self.get_conflicts(op_code)

        if entity_id is not None:
            # No need to check for conflicts when no entity is given
            for r in self.get_requests(entity_id=entity_id):
                if int(r['operation']) in conflicts:
                    raise CerebrumError("Conflicting request exists (%s)" %
                                        self.co.BofhdRequestOp(r['operation']).
                                        description)

        reqid = int(self._db.nextval('request_id_seq'))
        cols = {
            'requestee_id': operator,
            'run_at': when,
            'operation': int(op_code),
            'entity_id': entity_id,
            'destination_id': destination_id,
            'state_data': state_data,
            'request_id': reqid
            }

        self._db.execute("""
        INSERT INTO [:table schema=cerebrum name=bofhd_request] (%(tcols)s)
        VALUES (%(binds)s)""" % {
            'tcols': ", ".join(cols.keys()),
            'binds': ", ".join([":%s" % t for t in cols.keys()])},
                         cols)
        return reqid

    def delay_request(self, request_id, minutes=10):
        for r in self.get_requests(request_id):
            # Note: the semantics of time objects is DB driver
            # dependent, and not standardised in PEP 249.
            # PgSQL will convert to ticks when forced into int().
            t = int(r['run_at'])
            # don't use self.now, it's a DateTime object.
            now = time.time()
            if t < now:
                t = now
            when = self._db.TimestampFromTicks(int(t + minutes*60))
            self._db.execute("""
                UPDATE [:table schema=cerebrum name=bofhd_request]
                SET run_at=:when WHERE request_id=:id""",
                             {'when': when, 'id': request_id})
            return
        raise Errors.NotFoundError("No such request %d" % request_id)

    def delete_request(self, entity_id=None, request_id=None,
                       operator_id=None, operation=None):
        cols = {}
        if entity_id is not None:
            cols['entity_id'] = entity_id
        if request_id is not None:
            cols['request_id'] = request_id
        if operator_id is not None:
            cols['requestee_id'] = operator_id
        if operation is not None:
            cols['operation'] = int(operation)
        self._db.execute("""DELETE FROM [:table schema=cerebrum name=bofhd_request]
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x) for x in cols.keys()]),
                         cols)

    def get_requests(self, request_id=None, operator_id=None, entity_id=None,
                     operation=None, destination_id=None, given=False,
                     only_runnable=False):
        cols = {}
        if request_id is not None:
            cols['request_id'] = request_id
        if entity_id is not None:
            cols['entity_id'] = entity_id
        if operator_id is not None:
            cols['requestee_id'] = operator_id
        if operation is not None:
            cols['operation'] = int(operation)
        if destination_id is not None:
            cols['destination_id'] = int(destination_id)
        where = ["%s = :%s" % (x, x) for x in cols.keys()]
        if only_runnable:
            cols['now'] = DateTime.now()
            where.append("run_at <= :now")
        qry = """
        SELECT request_id, requestee_id, run_at, operation, entity_id,
               destination_id, state_data
        FROM [:table schema=cerebrum name=bofhd_request]
        WHERE """
        ret = self._db.query(qry + " AND ".join(where), cols)
        if given:
            group = Factory.get('Group')(self._db)
            tmp = [str(x["group_id"])
                   for x in group.search(member_id=operator_id,
                                         indirect_members=True)]
            extra_where = ""
            if len(tmp) > 0:
                extra_where = "AND destination_id IN (%s)" % ", ".join(tmp)
            ret.extend(self._db.query(qry + "operation=:op %s" % extra_where,
                                      {'op': int(self.co.bofh_move_give)}))
        return ret

    def get_operations(self):
        """Retrieves the various types/operations that it is possible
        to generate bofhd-requests for.

        """
        qry = """
        SELECT code, code_str, description
        FROM [:table schema=cerebrum name=bofhd_request_code]
        ORDER BY code_str
        """
        return self._db.query(qry)


class BofhdUtils(object):
    """Utility functions for bofhd."""

    def __init__(self, db):
        self.db = db
        self.co = Factory.get("Constants")(db)

    # TBD: The helper functions inside get_target() might be useful
    # outside.
    #
    # TODO: Lookup by e-mail address -- but how to do that without
    # requiring mod_email?
    def get_target(self, name, default_lookup="account", restrict_to=None):
        """The user input should be a name on the form
            [LOOKUP ':'] IDENTIFIER
        The name of the lookup type can be abbreviated by the user.
        If the user doesn't include a lookup type, default_lookup
        will be used.

        Valid lookup types are
             'account' (name of user => Account or PosixUser)
             'person' (name of user => Person)
             'fnr' (external ID, Norwegian SSN => Person)
             'group' (name of group => Group or PosixGroup)
             'host' (name of host => Host)
             'id' (entity ID => any)
             'external_id' (i.e. employee or studentnr)
             'stedkode' (stedkode => OU)

        If name is actually an integer, 'id' lookup is always chosen.

        If restrict_to isn't set, it will be initialised according to
        default_lookup.  It should be a list containing the names of
        acceptable classes, and a CerebrumError will be raised if the
        resulting entity isn't among them.  The class names must be
        known to Factory.  To accept all kinds of objects, pass
        restrict_to=[].

        restrict_to can lead to a cast operation.  E.g., if Person is
        acceptable, but the user specified an account, the account's
        owner will be returned.

        The return value is an instantiated object of the appropriate
        class.  If no entity is found, CerebrumError is raised.

        """

        # This mapping restricts the possible values get_target returns.
        entity_lookup_types = {"account": ("Account",),
                               "fnr": ("Person",),
                               "group": ("Group",),
                               "host": ("Host",),
                               "disk": ("Disk",),
                               "stedkode": ("OU",),
                               "person": ("Person",),
                               "entity_id": None,
                               "id": None,
                               "external_id": None,
                               }

        def get_target_find_lookup(name, default_lookup):
            if isinstance(name, int):
                # We ignore default_lookup in this case, even if it
                # could conceivably have been a "fnr" on systems where
                # int is 64-bit.
                ltype = "id"
            elif name.count(":") == 0:
                if name.isdigit() and len(name) == 11:
                    ltype = "fnr"
                else:
                    ltype = default_lookup
            else:
                ltype, name = name.split(":", 1)
                ltype = self.get_abbr_type(ltype, entity_lookup_types.keys())
            return ltype, name

        def get_target_lookup(ltype, name):
            if ltype == 'id' or ltype == 'entity_id':
                return get_target_entity(name)
            elif ltype == 'account' or ltype == 'group':
                return get_target_posix_by_name(name, clstype=ltype)
            elif ltype == 'fnr':
                return get_target_person_fnr(name)
            elif ltype == 'host':
                return get_target_host(name)
            elif ltype == 'disk':
                return get_target_disk(name)
            elif ltype == 'external_id':
                return get_target_by_external_id(name)
            elif ltype == 'stedkode':
                return get_target_ou_by_stedkode(name)
            elif ltype == 'person':
                return get_target_person_by_account_name(name)
            else:
                raise CerebrumError("Lookup type %s not implemented yet" %
                                    ltype)

        def get_target_by_external_id(ext_id):
            # This does not have to be person, but cereconf.CLASS_ENTITY is
            # insufficient. We need EntityExternalId here.
            en = Factory.get("Person")(self.db)
            # first, locate the entity_id
            candidates = en.search_external_ids(external_id=ext_id,
                                                fetchall=False)
            only_ids = set([int(x["entity_id"]) for x in candidates])
            if len(only_ids) < 1:
                raise CerebrumError("No entity with external id=%s" % ext_id)
            if len(only_ids) > 1:
                raise CerebrumError("Too many targets with external id=%s"
                                    "[entity_ids=%s]" % (ext_id, only_ids))
            return get_target_entity(only_ids.pop())
        # end get_target_by_external_id

        def get_target_person_by_account_name(name):
            account = get_target_posix_by_name(name)
            if isinstance(account, Factory.get("Account")):
                if account.owner_type == self.co.entity_person:
                    return get_target_entity(account.owner_id)
                else:
                    raise CerebrumError("Account %s is not owned by a person" %
                                        name)

        def get_target_entity(ety_id):
            try:
                ety_id = int(ety_id)
            except ValueError:
                # TBD: This triggers if the numeric value can't fit in
                # 32 bits, too.  Should we use a regexp instead?
                raise CerebrumError("Non-numeric id lookup (%s)" % ety_id)
            en = Factory.get("Entity")(self.db)
            try:
                en = en.get_subclassed_object(ety_id)
            except Errors.NotFoundError:
                raise CerebrumError("No such entity (%d)" % ety_id)
            except ValueError as e:
                raise CerebrumError("Can't handle entity (%s)" % e)
            if en.entity_type == self.co.entity_account:
                return get_target_posix_by_object(en)
            elif en.entity_type == self.co.entity_group:
                return get_target_posix_by_object(en, clstype="group")
            return en

        def get_target_posix_by_object(obj, clstype="account"):
            """Takes an Account or Group object, and returns a
            PosixUser or PosixGroup object if the entity is also a
            POSIX object.

            """
            # FIXME: due to constants being defined in this file, we
            # can't import these at the top level.

            if clstype == "account":
                promoted = Factory.get('PosixUser')(self.db)
            elif clstype == "group":
                promoted = Factory.get('PosixGroup')(self.db)
            try:
                promoted.find(int(obj.entity_id))
                return promoted
            except Errors.NotFoundError:
                return obj

        def get_target_posix_by_name(name, clstype="account"):
            """Returns either a Posix or a Cerebrum core version of
            Account or Group.

            """
            # We could use get_target_posix_by_object, but then the
            # common case of a PosixUser would lead to a wasted
            # instantiation of a plain Account object first.
            if clstype == "account":
                plain_cls = Factory.get("Account")
                posix_cls = Factory.get("PosixUser")
            elif clstype == "group":
                plain_cls = Factory.get("Group")
                posix_cls = Factory.get("PosixGroup")
            try:
                obj = posix_cls(self.db)
                obj.find_by_name(name)
            except Errors.NotFoundError:
                try:
                    obj = plain_cls(self.db)
                    obj.find_by_name(name)
                except Errors.NotFoundError:
                    raise CerebrumError("Unknown %s %s" % (clstype, name))
            return obj

        def get_target_person_fnr(id):
            person = Factory.get("Person")(self.db)
            found = {}
            for name in cereconf.SYSTEM_LOOKUP_ORDER:
                ss = getattr(self.co, name)
                try:
                    person.clear()
                    person.find_by_external_id(self.co.externalid_fodselsnr,
                                               id, source_system=ss)
                    found[int(person.entity_id)] = person
                except Errors.NotFoundError:
                    pass
            found = found.keys()
            if len(found) == 0:
                raise CerebrumError("No person with fnr %s" % id)
            if len(found) > 1:
                raise CerebrumError("More than one person with fnr %s found "
                                    "(all ids: %s)" % (id, ", ".join(
                                                    str(x) for x in found)))
            person.clear()
            person.find(found[0])
            return person

        def get_target_host(hostname):
            host = Factory.get("Host")(self.db)
            try:
                host.find_by_name(hostname)
            except Errors.NotFoundError:
                raise CerebrumError("No such host: %s" % hostname)
            return host

        def get_target_disk(path):
            disk = Factory.get("Disk")(self.db)
            host_id = None
            if path.count(':'):
                hostname, path = path.split(':', 1)
                host_id = get_target_host(hostname).entity_id
            try:
                disk.find_by_path(path, host_id=host_id)
            except Errors.NotFoundError:
                raise CerebrumError("No such path: %s" % path)
            except Errors.TooManyRowsError:
                # This can't happen currently, disk_info.path has a
                # UNIQUE constraint.
                raise CerebrumError("%s is not unique, use 'host:path'" % path)
            return disk

        def get_target_ou_by_stedkode(stedkode):
            ou = Factory.get("OU")(self.db)

            if len(stedkode) != 6 or not stedkode.isdigit():
                raise CerebrumError("Expected a six-digit stedkode.")

            try:
                ou.find_stedkode(
                    stedkode[0:2],
                    stedkode[2:4],
                    stedkode[4:6],
                    cereconf.DEFAULT_INSTITUSJONSNR
                )
            except Errors.NotFoundError:
                raise CerebrumError("Stedkode %s was not found." % stedkode)

            return ou

        #
        # Finally, here is the start of the function itself
        #

        if name is None or name == "":
            raise CerebrumError("Empty value given")

        ltype, name = get_target_find_lookup(name, default_lookup)
        obj = get_target_lookup(ltype, name)

        if restrict_to is None:
            restrict_to = entity_lookup_types[ltype]
        if not restrict_to:
            # empty list means accept everything
            return obj
        if not isinstance(restrict_to, (list, tuple)):
            restrict_to = (restrict_to,)
        for clsname in restrict_to:
            if isinstance(obj, Factory.get(clsname)):
                return obj
        # The object isn't strictly acceptable according to
        # restrict_to, but let's be user-friendly and turn an account
        # into a person and a disk into a host.
        if ("Person" in restrict_to and
                isinstance(obj, Factory.get("Account")) and
                obj.owner_type == self.co.entity_person):
            return get_target_entity(obj.owner_id)
        if "Host" in restrict_to and isinstance(obj, Factory.get("Disk")):
            return get_target_entity(obj.host_id)

        raise CerebrumError("Wrong argument type '%s' returned by %s:%s" %
                            (self.co.EntityType(obj.entity_type), ltype, name))

    def get_abbr_type(self, type_name, valid_types):
        """Looks for type_name in valid_types, and returns the full
        type name if found.  Raises CerebrumError if not found, or if
        name is ambiguous.

        """
        found = None
        for v in valid_types:
            if v.startswith(type_name):
                if found:
                    raise CerebrumError("Ambiguous value '%s' (%s or %s?)" %
                                        (type_name, found, v))
                found = v
        if found is None:
            raise CerebrumError("Unknown value '%s'" % type_name)
        return found
