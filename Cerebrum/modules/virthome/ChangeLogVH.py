#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""This implements VirtHome extensions to the ChangeLog framework.

The primary purpose of the extensions is to be able to track state change
requests for the database, without immediately executing them. E.g. we may
want to delay changing an e-mail address until a user actually confirms
receiving a message sent to the new address.

Each request is tracked with a unique key (they should not be
change_log.change_id, since the latter are too easily guessed) -- think of
them as a one-time password to acknowledge a certain state change. The
change_log framework in itself is sufficient for the task, except for the
tidbit where unique keys are linked to the change_log events; such a linkage
is the main task of this modules.

"""
from Cerebrum.modules.ChangeLog import ChangeLog, _params_to_db
from Cerebrum.Utils import argument_to_sql


class ChangeLogVH(ChangeLog):

    """Extension of ChangeLog to accomodate OTP tracking for change log
    events.

    Essentially, we override just the methods that need be tweeked to
    accomodate access to mod_virthome.sql:pending_change_log. This class
    should be usable for general changelogging, so it's important to keep
    compatible with ChangeLog's interface.

    """

    def remove_log_event(self, change_id):
        """Remove a specific entry from (pending)_change_log."""

        # Drop entries, if any, from pcl BEFORE deleting the referenced row in
        # the superclass.
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=pending_change_log]
        WHERE change_id=:change_id""", {'change_id': int(change_id)})

        super(ChangeLogVH, self).remove_log_event(change_id)

    def __create_unique_request_id(self):
        """Return a unique request id.

        Some of the actions in virthome require a form of confirmation. E.g.
        creating a VirtAccount requires us to check the validity of the
        associated e-mail address. When such an action is required, we create
        a changelog event that binds entities that the change concerns. Such
        an event has a confirmation key associated with it. This method
        creates such a key. This key can be thought of as a one-time password
        tied up to a very particular action bound to a specific account.

        The easiest choice is probably uuid (although reading /dev/urandom
        will probably work just as well).

        :return basestring:
          A unique ID (or, at least an id unique for as long as the request is
          potentially to remain pending/valid).

        """
        import uuid
        # <http://en.wikipedia.org/wiki/Uuid>
        return str(uuid.uuid4())

    def log_pending_change(self, subject_entity,
                           change_type_id, destination_entity,
                           change_params=None, change_by=None,
                           change_program=None):
        """Log a new pending change.

        This is a copy of ChangeLog.log_change(), with the additional
        'confirmation_key' magic.

        :return basestring:
          Return the magic_key associated with this request.

        """
        confirmation_key = self.__create_unique_request_id()
        if change_by is None and self.change_by is not None:
            change_by = self.change_by
        elif change_program is None and self.change_program is not None:
            change_program = self.change_program
        if change_by is None and change_program is None:
            raise RuntimeError("must set change_by or change_program")
        change_type_id = int(change_type_id)
        if change_params is not None:
            change_params = _params_to_db(change_params)
        self.messages.append(locals())

        return confirmation_key

    def write_log(self):
        """Commit the accumulated in-memory events to (pending_)change_log.

        The requests/events are accumulated in-memory until write_log() is
        issued. Here we actually write the requests to the db. This method
        looks a lot like superclass' equivalent.

        """
        for message in self.messages:
            message["change_id"] = int(self.nextval("change_log_seq"))

            self.execute("""
            INSERT INTO [:table schema=cerebrum name=change_log]
               (change_id, subject_entity, change_type_id, dest_entity,
                change_params, change_by, change_program)
            VALUES (:change_id, :subject_entity, :change_type_id,
                    :destination_entity, :change_params, :change_by,
                    :change_program)""", message)

            # This is actually a 'pending' request.
            if "confirmation_key" in message:
                self.execute("""
                INSERT INTO [:table schema=cerebrum name=pending_change_log]
                VALUES (:confirmation_key, :change_id)
                """, message)
        self.messages = list()

    def get_pending_event(self, confirmation_key):
        """ Fetch ChangeLog information for a given confirmation key. """
        result = dict(self.query_1("""
        SELECT cl.*, pcl.confirmation_key
        FROM [:table schema=cerebrum name=change_log] cl,
             [:table schema=cerebrum name=pending_change_log] pcl
        WHERE pcl.confirmation_key = :confirmation_key AND
              pcl.change_id = cl.change_id""",
                                   {"confirmation_key": confirmation_key}))
        return result

    def get_pending_events(self, types=None,
                           subject_entity=None,
                           confirmation_key=None):
        """Short version of get_log_events that carries the information about
        the pending requests as well as the change_log entries.
        """

        where = list()
        binds = dict()
        if types is not None:
            where.append(argument_to_sql(types, "cl.change_type_id", binds, int))
        if subject_entity is not None:
            where.append(argument_to_sql(subject_entity,
                                         "cl.subject_entity",
                                         binds, int))
        if confirmation_key is not None:
            where.append(argument_to_sql(confirmation_key,
                                         "pcl.confirmation_key",
                                         binds))
        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        return self.query("""
        SELECT cl.*, pcl.confirmation_key
        FROM [:table schema=cerebrum name=change_log] cl
        JOIN [:table schema=cerebrum name=pending_change_log] pcl
          ON cl.change_id = pcl.change_id
        %s
        """ % where_str, binds)

    def remove_pending_log_event(self, confirmation_key):
        change_id = int(self.query_1("""
        SELECT change_id
        FROM [:table schema=cerebrum name=pending_change_log]
        WHERE confirmation_key=:confirmation_key""",
                                     {"confirmation_key": confirmation_key}))
        return self.remove_log_event(change_id)
