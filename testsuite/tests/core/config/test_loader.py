#!/usr/bin/env python
# encoding: utf-8
""" Unit tests for Cerebrum.config.loader. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import os
import stat

import pytest


@pytest.fixture
def loader(monkeypatch, config_dir, tmpdir):
    mod = pytest.importorskip("Cerebrum.config.loader")
    # Set the default config dir to our test configs
    monkeypatch.setattr(mod, 'DEFAULT_DIR', config_dir)
    # set user_dir to an empty directory
    monkeypatch.setattr(mod, 'USER_DIR', str(tmpdir))
    return mod


@pytest.fixture
def config_cls():
    mod = pytest.importorskip("example")
    return mod.Config


@pytest.fixture
def no_r(tmpdir):
    old_stat = os.stat(str(tmpdir))
    # chmod a-r
    os.chmod(str(tmpdir), old_stat.st_mode & (stat.S_IRWXU & ~stat.S_IRUSR |
                                              stat.S_IRWXG & ~stat.S_IRGRP |
                                              stat.S_IRWXO & ~stat.S_IROTH))
    yield tmpdir
    # Reset mode, so that we don't affect cleanup of tmpdir
    os.chmod(str(tmpdir), old_stat.st_mode)


@pytest.fixture
def no_x(tmpdir):
    old_stat = os.stat(str(tmpdir))
    # chmod a-x
    os.chmod(str(tmpdir), old_stat.st_mode & (stat.S_IRWXU & ~stat.S_IXUSR |
                                              stat.S_IRWXG & ~stat.S_IXGRP |
                                              stat.S_IRWXO & ~stat.S_IXOTH))
    yield tmpdir
    # Reset mode, so that we don't affect cleanup of tmpdir
    os.chmod(str(tmpdir), old_stat.st_mode)


def test_lookup_dirs(loader, config_dir, tmpdir):

    dirs = loader.lookup_dirs()
    assert len(dirs) == 2
    assert dirs[0] == config_dir
    assert dirs[1] == tmpdir

    dirs = loader.lookup_dirs(additional_dirs=['~', '/tmp', ])
    assert len(dirs) == 4
    assert dirs[0] == config_dir
    assert dirs[1] == tmpdir
    assert dirs[2] == os.path.abspath(os.path.expanduser('~'))
    assert dirs[3] == '/tmp'


def test_is_readable_dir_ok(loader, tmpdir):
    assert loader.is_readable_dir(str(tmpdir))
    assert loader.is_readable_dir('/tmp')


def test_is_readable_dir_no_r(loader, no_r):
    assert not loader.is_readable_dir(str(no_r))


def test_is_readable_dir_no_x(loader, no_x):
    assert not loader.is_readable_dir(str(no_x))


def test_is_readable_dir_file(loader):
    assert not loader.is_readable_dir(os.path.abspath(__file__))


def test_read_config_json(loader, config_dir):
    pytest.importorskip("json")
    data = loader.read_config(os.path.join(config_dir, 'sms.json'))
    assert data['user'] == 'sms-user'
    assert data['system'] == 'sms-system'
    assert data['url'] == 'https://example.org/sms'


def test_read_config_yaml(loader, config_dir):
    pytest.importorskip("yaml")
    data = loader.read_config(os.path.join(config_dir, 'root.yml'))
    assert 'job_runner' in data
    assert 'socket' in data['job_runner']
    assert 'db.user' in data
    assert data['db.db'] == 'bar'
    assert data['job_runner']['max_jobs'] == 1


def test_read(loader, config_cls):
    pytest.importorskip("json")
    pytest.importorskip("yaml")
    config = config_cls()
    # Default value
    assert config.job_runner.max_jobs == 3
    loader.read(config, 'root')
    assert config.job_runner.max_jobs == 1
    assert config.db.user == 'foo'
    assert config.bofhd.timeout == 60
    assert config.sms.user == 'sms-user'
