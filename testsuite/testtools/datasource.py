# -*- coding: utf-8 -*-
""" Default test data sources.

This class contains data source generators for our tests. The classes in this
file contains simple generators, which can be extended if need be.

These data sources use an int counter (ident) to:
 - Insert/append the ident to a string
 - Select from a preset list based on the ident (cyclic)

We can easily extend these classes to provide random data, or to calculate
data from other types of idents.

The ident is mostly internal (not treated as int outside of the class) - it is
only used by teste to relocate/re-create data (e.g. what is the name of an item
with ident x).

Example usage and extension:

    This is an example setup, where we've extended AccountTestData to include a
    set of different passwords.


    In test_SomeClass.py:
    ---------------------
    from <module> import BaseDataSource, SomeMixin

    class _MyDataSource(BaseDataSource, SomeMixin):
        some_mixin_setting = 'setting'

    datasource = _MyDataSource()
    items = [d for d in datasource(limit=10)]

    infinite_source = datasource()
    another_item = infinite_source.next()

    <do things with items, like create them in the database>
"""
from mx.DateTime import DateTimeDelta
from mx.DateTime import now


# When used with filter(expired_filter, items), will return expired items
expired_filter = lambda x: ((x.get('expire_date') is not None) and
                            (x.get('expire_date') < now()))
""" A filter to identify expired items (according to the key 'expire_date') in
a dict or dict-like object. """

# When used with filter(nonexpired_filter, items), will return non-expired
# items
nonexpired_filter = lambda x: ((x.get('expire_date') is None) or
                               (x.get('expire_date') >= now()))
""" A filter to identify non-expired items (according to the key 'expire_date')
in a dict or dict-like object. """


class BaseDataSource(object):

    """ The basic data source.

    Each item that the data source creates, consists of a dict and an ident.
    The ident is an internal id of the item, and the dict contains all the
    generated data.

    """

    def __init__(self):
        # A list of attrributes and calls to get a value for the attribute
        self.attr_cb = {}   # Callbacks for each attr that a mixin provides
        self.num_items = 0  # Number of generated items in this data source
        self.items = {}     # The items this data source have created

        parent = super(BaseDataSource, self)
        if hasattr(parent, '__init__'):
            getattr(parent, '__init__')()

        self.register_attr('ident', lambda id: id)

    def __call__(self, limit=None):
        """ See L{_get_item_generator}. """
        return self._get_item_generator(limit=limit)

    def _get_item_generator(self, limit=None):
        """ Create a new data source item generator.

        The generator will produce up to C{limit} number of items. If C{limit}
        is C{None}, the generator will keep producing items unbounded.

        @type limit: int, long, NoneType
        @param limit: The maximum number of items to generate (default: None)

        @rtype: generator
        @return: A data source item generator

        """
        iterations = 0
        while (limit is None) or (iterations < int(limit)):
            iterations += 1
            yield self.get_next_item()

    def _get_next_ident(self):
        """ Create a unique string that identifies this item. 

        @rtype: str
        @return: An item id

        """
        next = str(self.num_items)
        self.num_items += 1
        return next

    def _get_cyclic_value(self, ident, values):
        """ Choose a given value from a list of values, based on the ident.

        @type ident: str
        @param ident: The 'ident' or 'id' of this item

        @type values: list, tuple
        @param values: An indexable sequence of values to choose from

        @return: A given value from the list.

        """
        try:
            ident = int(ident)
        except ValueError:
            ident = 0
            for c in ident:
                ident = (ident + ord(c))
        return values[ident % len(values)]

    def register_attr(self, attr, func):
        """ Register a new attribute and callback to generate its value.

        @type attr: str
        @param attr: The attribute name. If multiple mixins provide the same
            attribute, then the last mixin in the call chain will have its
            attribute generated.

        @type func: function
        @param func: A function to call, in order to generate the value of
            C{attr}. The function is called with one argument, the 'ident' or
            'id' (str) of the item to generate the attribute for.

        """
        self.attr_cb[attr] = func

    def get_next_item(self):
        """ Create a new item. """
        next_ident = self._get_next_ident()
        return self.get_item_for_ident(next_ident)

    def get_item_for_ident(self, ident):
        """ Generate a given item for a given ident.

        @type ident: str
        @param ident: The 'ident' or 'id' of the item to create.

        @rtype: dict
        @return: A new item, with attributes that are registered with this data
            source.

        """
        if ident in self.items:
            return self.items[ident]

        item = dict(((key, func(ident)) for key, func in self.attr_cb.items()))
        self.items[ident] = item
        return item


class NameMixin(object):

    """ Mixin for providing a item name. """

    name_attr = 'name'
    name_prefix = ''
    name_ident_fmt = '%02d'

    def __init__(self):
        parent = super(NameMixin, self)
        if hasattr(parent, '__init__'):
            getattr(parent, '__init__')()

        self.register_attr(self.name_attr, self.get_name)

    def get_name(self, ident):
        """ Get the name for a given ident.

        @type ident: str
        @param ident: The 'ident' or 'id of an item

        @rtype: str
        @return: A string name for an item

        """
        if ident in getattr(self, 'items'):
            return getattr(self, 'items')[ident][self.name_attr]
        try:
            return self.name_prefix + '%02d' % int(ident)
        except ValueError:
            return self.name_prefix + ident

    def get_name_prefix(self):
        """ Get the common prefix that all generated names share.

        Note: The common prefix might be str('')

        @rtype: str
        @return: The common prefix for all generated names

        """
        return self.name_prefix

    def list_names(self):
        """ List all generated names.

        @return: A list of attr_name values in generated items.

        """
        return [item[self.name_attr] for item in self.items.values()]


class DescriptionMixin(object):

    """ Mixin for providing a item name. """

    desc_attr = 'description'
    desc_prefix = ''

    def __init__(self):
        parent = super(DescriptionMixin, self)
        if hasattr(parent, '__init__'):
            getattr(parent, '__init__')()

        self.register_attr(self.desc_attr, self.get_description)

    def get_description(self, ident):
        """ Get the description for a given ident.

        @type ident: str
        @param ident: The 'ident' or 'id of an item

        @rtype: str
        @return: A string description for an item

        """
        if ident in getattr(self, 'items'):
            return getattr(self, 'items')[ident][self.desc_attr]

        try:
            return self.desc_prefix + '%d' % int(ident)
        except ValueError:
            return self.desc_prefix + ident

    def get_description_prefix(self):
        """ Get the common prefix that all generated descriptions share.

        Note: The common prefix might be str('')

        @rtype: str
        @return: The common prefix for all generated descriptions

        """
        return self.desc_prefix


class ExpireDateMixin(object):

    """ A mixin for providing expire dates. """

    expire_attr = 'expire_date'
    expire_dates = [None, now() - DateTimeDelta(10),
                    now() + DateTimeDelta(10)]

    def __init__(self):
        parent = super(ExpireDateMixin, self)
        if hasattr(parent, '__init__'):
            getattr(parent, '__init__')()

        self.register_attr(self.expire_attr, self.get_expire_date)

    def get_expire_date(self, ident):
        """ Get the expire_date for a given ident.

        @type ident: str
        @param ident: The 'ident' or 'id of an item

        @rtype: mx.DateTime.DateTime or NoneType
        @return: An expire date or None

        """
        if ident in getattr(self, 'items'):
            return getattr(self, 'items')[ident][self.expire_attr]

        return self._get_cyclic_value(ident, self.expire_dates)


class EntityMixin(object):

    """ A mixin for providing empty entity_id keys. """

    id_attr = 'entity_id'

    def __init__(self):
        parent = super(EntityMixin, self)
        if hasattr(parent, '__init__'):
            getattr(parent, '__init__')()

        self.register_attr(self.id_attr, lambda id: None)


class BasicPersonSource(BaseDataSource):

    birth_dates = [now(), now() - DateTimeDelta(365*100),
                   now() - DateTimeDelta(356 * 20)]

    genders = ['M', 'F', None]

    birth_date_attr = 'birth_date'
    gender_attr = 'gender'

    def __init__(self):
        parent = super(BasicPersonSource, self)
        if hasattr(parent, '__init__'):
            getattr(parent, '__init__')()

        self.register_attr(self.birth_date_attr, self.get_birth_date)
        self.register_attr(self.gender_attr, self.get_gender)

    def get_gender(self, ident):
        """ Get the gender for a given ident.

        @type ident: str
        @param ident: The 'ident' or 'id of an item

        @rtype: str or NoneType
        @return: One of the values in self.genders

        """
        if ident in getattr(self, 'items'):
            return getattr(self, 'items')[ident][self.expire_attr]

        return self._get_cyclic_value(ident, self.genders)

    def get_birth_date(self, ident):
        """ Get the expire_date for a given ident.

        @type ident: str
        @param ident: The 'ident' or 'id of an item

        @rtype: mx.DateTime.DateTime or NoneType
        @return: One of the values in self.birth_dates

        """
        if ident in getattr(self, 'items'):
            return getattr(self, 'items')[ident][self.expire_attr]

        return self._get_cyclic_value(ident, self.birth_dates)


class BasicAccountSource(BaseDataSource, NameMixin, ExpireDateMixin,
                         EntityMixin):

    """ A simple data source that can generate sets of account data. """

    name_attr = 'account_name'
    name_prefix = 'aq3zcx'

    passwd_attr = 'password'
    passwd_val = 'adobe123'

    def __init__(self):
        parent = super(BasicAccountSource, self)
        if hasattr(parent, '__init__'):
            getattr(parent, '__init__')()

        self.register_attr(self.passwd_attr, lambda x: self.passwd_val)


class BasicGroupSource(BaseDataSource, NameMixin, DescriptionMixin,
                       ExpireDateMixin, EntityMixin):

    """ A simple data source that can generate setx of group data. """

    name_attr = 'group_name'
    name_prefix = 'kruadw'
    desc_attr = 'description'
    desc_prefix = '5gzklxdsabrucz8r Test group '


class BasicOUSource(BaseDataSource, EntityMixin):
    pass
