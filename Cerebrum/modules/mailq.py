# -*- coding: utf-8 -*-
#
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
"""
Implementation of mod_mailq.

This module implements a notification system with:

- An email notification queue.
- A dispatcher that processes the queue and sends out emails.

The mail queue is implemented through a table with the following values:

entity_id
    Reference to an entity to notify using the given template.

    When issuing email notifications, the recipient address will be fetched
    from this entity.

template
    A template to use for notification.

    This is a reference to a set of template files on disk (one per supported
    language) to use for this notification.

parameters
    A serialized dict of extra substitution arguments for the template.

scheduled
    When the notification should be sent out.

    When processing the queue, we'll look at all entries where the scheduled
    date is in the past.

status
    Status of this notification. ``1`` means the notification has failed, ``0``
    means that the notification has not been processed yet. Notifications that
    are successfully processed are deleted.

status_time
    When the status flag was last updated.
"""
from __future__ import unicode_literals

import itertools
import io
import logging
import os
import pickle

import mx.DateTime
import six

import cereconf

from Cerebrum import Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory, NotSet, argument_to_sql
from Cerebrum.utils import email

logger = logging.getLogger(__name__)


# Columns and column order when selecting from the mailq table
SELECT_COLUMNS = (
    'entity_id',
    'template',
    'parameters',
    'scheduled',
    'status',
    'status_time',
)

# Values of the 'status' column
STATUS_PENDING = 0
STATUS_ERROR = 1


def sql_insert(db, entity_id, template, parameters, scheduled, status,
               status_time):
    """
    Insert a new row into mailq.
    """
    # All cols are manatory
    binds = {
        'entity_id': int(entity_id),
        'template': six.text_type(template),
        'parameters': parameters,
        'scheduled': scheduled,
        'status': status,
        'status_time': status_time,
    }

    stmt = """
      INSERT INTO [:table schema=cerebrum name=mailq]
      ({cols}) VALUES ({params})
    """.format(
        cols=', '.join(sorted(binds)),
        params=', '.join(':' + k for k in sorted(binds)))
    logger.debug('Inserting mailq entity_id=%r template=%r',
                 entity_id, template)
    db.execute(stmt, binds)


def sql_update(db, entity_id, template, parameters=NotSet, scheduled=NotSet,
               status=NotSet, status_time=NotSet):
    """
    Update an existing row in mailq.
    """
    binds = {
        'entity_id': int(entity_id),
        'template': six.text_type(template),
    }
    changes = {}
    if parameters is not NotSet:
        changes['parameters'] = parameters
    if scheduled is not NotSet:
        changes['scheduled'] = scheduled
    if status is not NotSet:
        changes['status'] = status
    if status_time is not NotSet:
        changes['status_time'] = status_time
    binds.update(changes)

    stmt = """
      UPDATE [:table schema=cerebrum name=mailq]
      SET {assign}
      WHERE entity_id = :entity_id AND
            template = :template
    """.format(assign=', '.join(k + ' = :' + k for k in sorted(changes)))
    logger.debug('Updating mailq entity_id=%r template=%r columns=%r',
                 entity_id, template, tuple(changes.keys()))
    db.execute(stmt, binds)


def sql_exists(db, entity_id, template):
    """ Check if this primary key exists in mailq. """
    if not entity_id or not template:
        raise ValueError("Missing args")
    binds = {
        'entity_id': int(entity_id),
        'template': six.text_type(template),
    }
    stmt = """
      SELECT EXISTS (
        SELECT 1
        FROM [:table schema=cerebrum name=mailq]
        WHERE entity_id = :entity_id AND
              template = :template
      )
    """
    return db.query_1(stmt, binds)


def sql_delete(db, entity_id=None, template=None):
    """
    Delete rows from mailq.

    Optionally limited by entity_id and/or template.
    """
    binds = {}

    conditions = []
    if entity_id is not None:
        conditions.append(
            argument_to_sql(entity_id, 'entity_id', binds, int))
    if template is not None:
        conditions.append(
            argument_to_sql(template, 'template', binds, six.text_type))

    stmt = """
      DELETE FROM [:table schema=cerebrum name=mailq]
      {limit}
    """.format(
        limit=(('WHERE ' + ' AND '.join(conditions))
               if conditions else ''))
    logger.debug('Deleting mailq entity_id=%r template=%r',
                 entity_id, template)
    db.execute(stmt, binds)


def sql_get(db, entity_id, template):
    """ Get row identified by primary key. """
    if not entity_id or not template:
        raise ValueError("Missing args")
    binds = {
        'entity_id': int(entity_id),
        'template': six.text_type(template),
    }
    stmt = """
      SELECT {columns}
      FROM [:table schema=cerebrum name=mailq]
      WHERE entity_id = :entity_id AND
            template = :template
    """.format(columns=', '.join(SELECT_COLUMNS))
    return db.query_1(stmt, binds)


def sql_search(db, entity_id=None, template=None, scheduled=None, status=None,
               status_time=None, fetchall=False):
    """
    Find rows in mailq.

    Returns all rows, or optionally filters by the following keyword arguments:

    :type entity_id: int
    :param entity_id: One or more entity_ids

    :type template: str
    :param template: One or more template names.

    :type scheduled: mx.DateTime
    :param scheduled: Only entries with a scheduled date before this date.

    :type status: int
    :param status: Filter by status

    :type status_time: mx.DateTime
    :param status_time: Only entries with a status_time before this date.
    """
    binds = {}
    conditions = []

    if entity_id is not None:
        conditions.append(
            argument_to_sql(entity_id, 'entity_id', binds, int))
    if template is not None:
        conditions.append(
            argument_to_sql(template, 'template', binds, six.text_type))
    if scheduled is not None:
        binds['scheduled'] = _to_date(scheduled)
        conditions.append('scheduled <= :scheduled')
    if status is not None:
        conditions.append(
            argument_to_sql(status, 'status', binds, int))
    if status_time is not None:
        binds['status_time'] = _to_date(status_time)
        conditions.append('status_time <= :status_time')

    stmt = """
      SELECT {columns}
      FROM [:table schema=cerebrum name=mailq]
      {where}
    """.format(
        columns=', '.join(SELECT_COLUMNS),
        where=(('WHERE ' + ' AND '.join(conditions))
               if conditions else ''))
    return db.query(stmt, binds, fetchall=fetchall)


# TODO: Change serialization to JSON?

def serialize_params(obj):
    return pickle.dumps(obj)


def deserialize_params(data):
    return pickle.loads(data)


def _to_date(obj):
    return mx.DateTime.DateFrom(obj)


def _conv(fn, obj, default=None):
    if obj is None:
        return default
    else:
        return fn(obj)


class MailQueueEntry(object):
    """
    Object representing a notification in the mail queue.
    """

    def __init__(self, entity_id, template, parameters=None, scheduled=None,
                 status=None, status_time=None):
        self.entity_id = int(entity_id)
        self.template = six.text_type(template)
        self.parameters = dict(parameters or ())
        self.scheduled = _conv(_to_date, scheduled, mx.DateTime.now())
        self.status = int(status or 0)
        self.status_time = _conv(_to_date, status_time, mx.DateTime.now())

    def __repr__(self):
        # TODO: make the _ChangeTypeCode repr better?
        return ('<{cls.__name__} entity_id={obj.entity_id!r}'
                ' template={obj.template!r}>').format(
                    cls=type(self),
                    obj=self)

    def to_dict(self):
        return {
            'entity_id': self.entity_id,
            'template': self.template,
            'parameters': serialize_params(self.parameters),
            'scheduled': self.scheduled,
            'status': self.status,
            'status_time': self.status_time,
        }

    @classmethod
    def from_dict(cls, d):
        args = {k: d[k] for k in ('entity_id', 'template', 'scheduled',
                                  'parameters', 'status', 'status_time')}
        if not isinstance(args['parameters'], dict):
            args['parameters'] = deserialize_params(args['parameters'])
        return cls(**args)


class MailQueueDb(DatabaseAccessor):
    """
    Access to the mail queue using MailQueueEntry objects.
    """

    def in_db(self, entry):
        """ Check if a template is queued for a given entity. """
        return sql_exists(self._db, entry.entity_id, entry.template)

    def get(self, entity_id, template):
        return MailQueueEntry.from_dict(
            sql_get(self._db, entity_id, template))

    def __insert(self, entry):
        binds = entry.to_dict()
        return sql_insert(self._db, **binds)

    def __update(self, entry):
        old = sql_get(self._db, entry.entity_id, entry.template)
        new = entry.to_dict()
        changes = {}
        for k in ('parameters', 'scheduled', 'status'):
            if old[k] != new[k]:
                changes[k] = new[k]

        if 'status' in changes:
            changes['status_time'] = '[:now]'

        if not changes:
            logger.debug('No change in mail queue entry %r', entry)
            return
        return sql_update(self._db, entry.entity_id, entry.template, **changes)

    def store(self, entry):
        if self.in_db(entry):
            self.__update(entry)
        else:
            self.__insert(entry)

    def remove(self, entry):
        """
        Delete a single mail entry.
        """
        if not self.in_db(entry):
            raise Errors.NotFoundError("no %r in db" % (entry, ))
        sql_delete(self._db, entity_id=entry.entity_id,
                   template=entry.template)

    def search(self, **kwargs):
        kwargs['fetchall'] = False
        for row in sql_search(self._db, **kwargs):
            yield MailQueueEntry.from_dict(row)


class EntityCache(DatabaseAccessor):
    """
    Entity metadata cache for the MailProcessor
    """

    def __init__(self, db):
        self.db = db
        self._co = Factory.get('Constants')(db)
        self._en = Factory.get('Entity')(db)
        self._cache = dict()
        self._errors = dict()

    def get_entity(self, entity_id, entity_type):
        if entity_type == self._co.entity_account:
            obj = Factory.get('Account')(self.db)
            obj.find(entity_id)
            return obj
        raise NotImplementedError("Unsupported entity_type=%r" % entity_type)

    def get_metadata(self, entity_id):
        self._en.clear()
        self._en.find(entity_id)
        entity_type = self._co.EntityType(self._en.entity_type)
        entity = self.get_entity(entity_id, entity_type)
        return {
            'epost': entity.get_primary_mailaddress(),
            'brukernavn': entity.account_name,
            'entity_id': entity.entity_id,
        }

    def __getitem__(self, entity_id):
        if entity_id in self._errors:
            raise self._errors[entity_id]
        if entity_id in self._cache:
            return self._cache[entity_id]

        logger.debug("caching metadata for entity_id=%r", entity_id)
        try:
            self._cache[entity_id] = data = self.get_metadata(entity_id)
            return data
        except Exception as e:
            self._errors = e
            raise


class MailProcessor(object):
    """
    Process and send out notifications from the mail queue.
    """

    languages = ('no', 'en')
    template_path = os.path.join(cereconf.TEMPLATE_DIR, 'MailQ')

    encoding = 'utf-8'
    master_template = 'Master_Default'
    sender = getattr(cereconf, 'USER_NOTIFICATION_SENDER', None)

    def __init__(self,
                 db,
                 dryrun=True,
                 encoding=encoding,
                 master_template=master_template,
                 sender=sender):
        self.db = db
        self.mq = MailQueueDb(db)
        self.cache = EntityCache(db)
        self.dryrun = dryrun
        self.encoding = encoding
        self.master_template = master_template
        self.sender = sender

    def format_template(self, lang, entry):
        """
        Format a single template.

        :param lang:
            Language (this selects the template named (entry.template + lang)
        :param entry:
            The MailQueueEntry object to render a template for.

        :returns: A message formatted from the entry.template.
        """
        substitute = {}
        substitute.update(self.cache[entry.entity_id])
        substitute.update(entry.parameters)
        filename = os.path.join(self.template_path,
                                ".".join((entry.template, lang)))

        logger.info("Preparing template %s.%s for user %s (%s)",
                    entry.template, lang, substitute['brukernavn'],
                    substitute['entity_id'])
        with io.open(filename, encoding=self.encoding, mode='r') as f:
            message = "".join(f.readlines())
            for key, value in substitute.items():
                if not isinstance(value, six.text_type):
                    value = six.text_type(value)
                message = message.replace("${%s}" % key, value)
            return message

    def prepare_email_substitutions(self, entity_id, entries):
        """
        Prepare substitutions for the master template.

        :param metadata:
            A dict with keys 'username', 'recipient' and 'entity_id'.

        :param entries:
            An iterable with MailQueueEntry objects to prepare.

        :returns:
            A dict that can be used with the master template. The dict contains
            the mentioned fields from *metadata*, and a 'body_<lang>' key for
            each <lang> in ``self.langauges``.

        """
        msg_body = dict()
        for lang in self.languages:
            out = io.StringIO()
            for e in entries:
                out.write(self.format_template(lang, e))
                out.write("\n")
            msg_body[lang] = out.getvalue()

        substitute = {}
        substitute.update(self.cache[entity_id])
        for lang in self.languages:
            substitute['body_'+lang] = msg_body[lang]
        return substitute

    def send_mail(self, email_data):
        """
        Format template and send email.

        :param email_data:
            A dict with substitutions from `prepare_email_substitutions`.
        """
        tpl = self.master_template
        rcp = email_data['epost']
        filename = os.path.join(self.template_path, tpl)

        logger.info("Sending template %s to user %s (%s)",
                    tpl, email_data['brukernavn'], email_data['entity_id'])

        output = email.mail_template(
            rcp,
            filename,
            sender=self.sender,
            cc=None,
            substitute=email_data,
            charset='ascii',
            debug=self.dryrun)

        if self.dryrun:
            logger.info(
                "Debug enabled, would have sent message of size %s to %s",
                len(output), rcp)
            logger.debug("Content:\n%s", output)

    def process_entity(self, entity_id, entries):
        """
        Prepare and send mail for a given entity.

        :param entity_id:
            The entity to send email to
        :param entries:
            A sequence of MailQueueEntry objects to send.
        """
        entries = list(entries)
        if {entity_id, } != {e.entity_id for e in entries}:
            raise ValueError(
                "process_entity got entries for multiple entity_ids")
        try:
            tpl_sub = self.prepare_email_substitutions(entity_id, entries)
            self.send_mail(tpl_sub)
        except Exception:
            logger.error("Unable to process entries: %r", entries,
                         exc_info=True)
            for e in entries:
                e.status = STATUS_ERROR
                self.mq.store(e)
        else:
            for e in entries:
                self.mq.remove(e)

    def process(self, **terms):
        """
        Find and process entries matching *terms*
        """
        for entity_id, entries in itertools.groupby(
                sorted(self.mq.search(**terms),
                       key=lambda e: (e.entity_id, e.scheduled)),
                lambda e: e.entity_id):

            entries = list(entries)
            templates = {e.template for e in entries}

            try:
                self.cache[entity_id]
            except NotImplementedError as e:
                logger.error(
                    "Invalid entity_type (id=%r, templates=%r, error=%s)",
                    entity_id, templates, e)
                continue
            except Exception:
                logger.error(
                    "Error retrieving metadata for for entity_id=%r,"
                    " removing templates=%r from queue!",
                    entity_id, templates, exc_info=True)
                for e in entries:
                    self.mq.remove(e)
                continue

            self.process_entity(entity_id, entries)
