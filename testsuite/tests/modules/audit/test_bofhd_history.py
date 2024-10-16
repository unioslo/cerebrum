# -*- coding: utf-8 -*-
""" Tests for :mod:`Cerebrum.modules.audit.bofhd_history_cmds` """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import logging

import pytest
import six

from Cerebrum.group.template import GroupTemplate
from Cerebrum.modules.audit import auditdb
from Cerebrum.modules.audit import bofhd_history_cmds
from Cerebrum.modules.bofhd import errors
from Cerebrum.modules.bofhd import session


@pytest.fixture
def logger():
    return logging.getLogger("test")


@pytest.fixture
def commands(database, logger):
    return bofhd_history_cmds.BofhdHistoryCmds(database, logger)


@pytest.fixture
def superuser_group(database, cereconf):
    tpl = GroupTemplate(
        group_name=cereconf.BOFHD_SUPERUSER_GROUP,
        group_description="bofhd-superusers",
        group_type="internal-group",
        group_visibility="A",
        conflict=GroupTemplate.CONFLICT_IGNORE,
    )
    return tpl(database)


@pytest.fixture
def superuser(database, account_creator, superuser_group):
    owner = superuser_group
    account, _ = next(account_creator(owner, 1))
    superuser_group.add_member(account.entity_id)
    return account


@pytest.fixture
def superuser_session(database, superuser):
    operator = session.BofhdSession(database)
    operator.set_authenticated_entity(superuser.entity_id, "127.0.0.1")
    return operator


@pytest.fixture
def account(database, account_creator, superuser_group):
    owner = superuser_group
    account, _ = next(account_creator(owner, 1))
    return account


@pytest.fixture
def account_session(database, account):
    operator = session.BofhdSession(database)
    operator.set_authenticated_entity(account.entity_id, "127.0.0.1")
    return operator


@pytest.fixture
def group(database, group_creator):
    group, _ = next(group_creator(1))
    return group


#
# test help strings
#


@pytest.mark.parametrize("group_name", ["history"])
def test_help_strings_group(commands, group_name):
    group, _, _ = commands.get_help_strings()
    assert group_name in group


@pytest.mark.parametrize(
    "group_name, command_name",
    [
        ("history", "history_show"),
    ],
)
def test_help_strings_cmd(commands, group_name, command_name):
    _, cmds, _ = commands.get_help_strings()
    assert group_name in cmds
    cmd_group = cmds[group_name]
    assert command_name in cmd_group


@pytest.mark.parametrize(
    "arg_name",
    [
        "limit_number_of_results",
        "yes_no_all_changes",
    ],
)
def test_help_strings_args(commands, arg_name):
    _, _, args = commands.get_help_strings()
    assert arg_name in args
    # Command help args must have a short-name and prompt - and may have an
    # optional description
    assert len(args[arg_name]) in (2, 3)


#
# Basic authz tests
#


def test_is_superuser(commands, superuser_session):
    operator_id = superuser_session.get_entity_id()
    assert commands.ba.is_superuser(operator_id)


def test_is_not_superuser(commands, account_session):
    operator_id = account_session.get_entity_id()
    assert not commands.ba.is_superuser(operator_id)


def test_can_show_history_superuser(commands, superuser_session, account):
    operator_id = superuser_session.get_entity_id()
    assert commands.ba.can_show_history(operator_id, query_run_any=True)
    assert commands.ba.can_show_history(operator_id, entity=account)


def test_can_show_history_other(commands, account_session, group):
    operator_id = account_session.get_entity_id()
    assert not commands.ba.can_show_history(operator_id, query_run_any=True)
    with pytest.raises(errors.PermissionDenied):
        commands.ba.can_show_history(operator_id, entity=group)


#
# Basic command tests
#


@pytest.fixture
def records(database, const, clconst, superuser, group):
    """ a series of changes for *group* by *superuser*. """

    def add_record(change_type, meta=None, params=None, timestamp=None):
        metadata = {
            'change': six.text_type(change_type),
            'change_program': __name__,
            'entity_name': group.group_name,
            'entity_type': six.text_type(const.entity_group),
            'operator_name': superuser.account_name,
            'operator_type': six.text_type(const.entity_account),
            'target_name': None,
            'target_type': None,
        }
        if meta:
            metadata.update(meta)

        return auditdb.sql_insert(
            database,
            change_type=change_type,
            operator_id=superuser.entity_id,
            entity_id=group.entity_id,
            metadata=metadata,
            params=params,
            timestamp=timestamp,
        )

    records = []

    # entity:add
    records.append(
        add_record(
            clconst.entity_add,
            meta={'entity_name': None},  # name doesn't exist yet
        )
    )
    # group:create
    records.append(
        add_record(
            clconst.group_create,
            meta={'entity_name': None},  # name doesn't exist yet
        )
    )
    # entity_name:add
    records.append(
        add_record(
            clconst.entity_name_add,
            params={
                'domain': int(const.group_namespace),
                'domain_str': six.text_type(const.group_namespace),
                'name': group.group_name,
            },
        )
    )
    return records


def test_history_show(commands, records, superuser_session, group):
    results = commands.history_show(
        operator=superuser_session,
        entity="id:{}".format(group.entity_id),
        any_entity="yes",
        limit_number_of_results="0",
    )
    assert len(results) == len(records)
