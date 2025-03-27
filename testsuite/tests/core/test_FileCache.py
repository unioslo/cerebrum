# encoding: utf-8
"""
Unit tests for :mod:`Cerebrum.FileCache`.

Note that these tests are a bit convoluted, as the cache implementation is a
bit convoluted.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import datetime
import logging
import os

import pytest

from Cerebrum import FileCache
from Cerebrum.utils import date as date_utils
from Cerebrum.testutils import file_utils
from Cerebrum.testutils.log_utils import StrictNullHandler


@pytest.fixture(scope="module", autouse=True)
def logger():
    return logging.getLogger(__name__)


@pytest.fixture(scope="module", autouse=True)
def _patch_logging(logger):
    """ catch badly formatted log records in FileCache module log messages. """
    logger.addHandler(StrictNullHandler())
    logger.setLevel(-100)
    FileCache.logger = logger


@pytest.fixture(scope='module')
def cache_dir():
    with file_utils.tempdir_ctx(prefix="test-filecache") as path:
        yield path


@pytest.fixture(autouse=True)
def _patch_cereconf(cereconf, cache_dir):
    cereconf.CACHE_DIR = cache_dir


def test_init_without_name(database):
    """ test init without subclassing (no name set). """
    with pytest.raises(NotImplementedError):
        FileCache.FileCache(database)


class DefaultFileCache(FileCache.FileCache):
    """ FileCache without a build_callback. """

    name = "test-default"


def test_default_build_callback(database):
    """ test build with no build callback. """
    obj = DefaultFileCache(database)
    with pytest.raises(NotImplementedError):
        obj.build()


#
# Tests for basic cache behaviour
#
# These tests mocks/stubs out the load/save functions to prevent file io
#


STATIC_DATA = {
    'foo': 1,
    'bar': "baz",
}


def basic_callback(db):
    return STATIC_DATA


dt_aware_utc = datetime.datetime(1998, 6, 28, 23, 30, 11, 987654,
                                 tzinfo=date_utils.UTC)
dt_timestamp = 899076611


class BasicFileCache(FileCache.FileCache):
    """ FileCache with all required attrs. """

    name = "test"
    build_callback = staticmethod(basic_callback)
    did_load = False
    did_save = False

    def dumper(self, data):
        self.did_save = True

    def loader(self):
        self.did_load = True
        return {
            'timestamp': dt_timestamp,
            'data': STATIC_DATA,
        }


@pytest.fixture
def basic_cache(database):
    return BasicFileCache(database)


def test_dump_dir(database, cache_dir):
    dump_dir = os.path.join(cache_dir, "test")
    obj = BasicFileCache(database, dump_dir=dump_dir)
    assert obj.dump_dir == dump_dir


def test_filecache_filename(basic_cache, cache_dir):
    expected = os.path.join(cache_dir, "cache-test.tmp")
    assert basic_cache.filename == expected


def test_filecache_init(basic_cache, cache_dir):
    assert basic_cache.max_age is None
    assert basic_cache.timestamp == 0
    assert basic_cache.dump_dir == cache_dir


def test_filecache_max_age_from_delta(basic_cache):
    delta = datetime.timedelta(hours=12)
    basic_cache.max_age = delta
    assert basic_cache.max_age == delta


def test_filecache_max_age_negative_delta(basic_cache):
    with pytest.raises(ValueError):
        basic_cache.max_age = datetime.timedelta(hours=-12)


def test_filecache_max_age_from_dict(basic_cache):
    kwargs = {'hours': 12}
    delta = datetime.timedelta(**kwargs)
    basic_cache.max_age = kwargs
    assert basic_cache.max_age == delta


def test_filecache_max_age_from_none(basic_cache):
    basic_cache.max_age = None
    assert basic_cache.max_age is None


def test_mock_save(database):
    obj = BasicFileCache(database)
    assert not obj.did_save
    assert not obj.saved
    obj.save()
    assert obj.did_save
    assert obj.saved


def test_mock_load(database):
    obj = BasicFileCache(database)
    assert not obj.did_load
    assert not obj.saved
    obj.load()
    assert obj.did_load
    assert obj.saved
    assert obj.timestamp == dt_timestamp


def test_build_callback(database):
    obj = BasicFileCache(database)
    before = date_utils.now()
    obj.build()
    after = date_utils.now()
    assert obj.saved
    assert obj.timestamp >= int(date_utils.to_timestamp(before))
    assert obj.timestamp <= int(date_utils.to_timestamp(after))


def test_data_autoload(database):
    obj = BasicFileCache(database)
    data = obj.data
    assert obj.did_load
    assert obj.saved
    assert data == STATIC_DATA


def test_data_setter(database):
    obj = BasicFileCache(database)
    obj.load()
    assert obj.saved

    obj.data = {'new': "data"}
    assert not obj.saved


#
# Tests for file io behaviour
#


class BasicJsonCache(FileCache.JsonCache):
    name = "tj"


class BasicPickleCache(FileCache.PickleCache):
    name = "tp"


@pytest.mark.parametrize(
    "cls, filename",
    [
        pytest.param(BasicJsonCache, "cache-tj.json", id="json"),
        pytest.param(BasicPickleCache, "cache-tp.pickle", id="pickle"),
    ],
)
def test_format_mixin_filename(database, cache_dir, cls, filename):
    obj = cls(database)
    expected = os.path.join(cache_dir, filename)
    assert obj.filename == expected


@pytest.mark.parametrize(
    "cls",
    [
        pytest.param(BasicJsonCache, id="json"),
        pytest.param(BasicPickleCache, id="pickle"),
    ],
)
def test_format_mixin_cycle(database, cls):
    ts = date_utils.now()
    data = {'vare': "blåbær", 'antall': 3}
    delta = datetime.timedelta(days=7)  # prevent rebuild

    # init with some data to save():
    obj = cls(database)
    obj.data = data
    obj._when = ts
    # save
    obj.save()
    assert os.path.exists(obj.filename)

    # init a new cache with different content to check if load() actually
    # loads our data:
    obj = cls(database, max_age=delta)
    obj.data = STATIC_DATA
    # load
    obj.load()
    assert obj.data == data
    assert obj.timestamp == int(date_utils.to_timestamp(ts))
