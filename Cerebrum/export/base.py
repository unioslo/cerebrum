"""
Common template classes for export utils.

This module provides abstractions for fetching, selecting and formatting entity
data.

The general flow for exports should look something like:

1. Fetch and validate configuration
2. Build cache of all relevant authentication types and data
3. Fetch and format authentication data as needed.
"""

MISSING = object()


class EntityFetcher(object):
    """
    Abstract database accessor for exportable data.

    Fetches data on either a single entity or all entities, according to a
    pre-determined set of parameters.
    """

    def get_one(self, entity_id):
        """
        :rtype: object
        :returns:
            Returns a single object (or the MISSING object if the entity
            doesn't exist)
        """
        raise NotImplementedError("%r does not implement get_one()" %
                                  repr(type(self)))

    def get_all(self):
        """
        :rtype: dict
        :returns:
            Returns a dictionary that maps entity_ids to objects. Each object
            should be identical to the object retured by get_one(entity_id).
        """
        raise NotImplementedError("%r does not implement get_all()" %
                                  repr(type(self)))


class EntityCache(object):
    """
    Fetch and cache data on entities.

    You'd typically implement a subclass along with a fetcher class.
    """
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.found = {}
        self.missing = set()
        self.cached_all = False

    def update_all(self):
        self.missing = set()
        self.found = self.fetcher.get_all()
        self.cached_all = True

    def update_one(self, entity_id):
        result = self.fetcher.get_one(entity_id)
        if result is MISSING:
            self.missing.add(entity_id)
            self.found.pop(entity_id, None)
        else:
            self.missing.discard(entity_id)
            self.found[entity_id] = result

    def __getitem__(self, entity_id):
        if entity_id in self.found:
            return self.found[entity_id]
        if self.cached_all or entity_id in self.missing:
            raise KeyError(repr(entity_id))

        self.update_one(entity_id)

        if entity_id in self.found:
            return self.found[entity_id]
        else:
            raise KeyError(repr(entity_id))

    def get(self, entity_id, default=None):
        try:
            return self[entity_id]
        except KeyError:
            return default
