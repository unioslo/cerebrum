========================
Configuration framework
========================
Cerebrum implements its own configuration framework in ``Cerebrum.config``.  The
framework consists of pre-defined ``Configuration`` classes, and each setting is
a ``ConfigDescriptor``.


File formats
=============
Config can be written in YAML or JSON.

More formats can be added by implementing a parser class and registering a file
extension for it in the ``Cerebrum.config.parsers`` module.


Loading config
===============
To read a simple config from a single file:
::

    values = Cerebrum.config.loader.read_config(filename)
    config = MyConfigClass(values)
    config.validate()


Or, if you have a custom set of defaults to load, and want to read a file:
::

    # prepare a config with defaults
    defaults = {…}
    config = MyConfigClass(defaults)

    # replace config values from another source, e.g. a file:
    values = Cerebrum.config.loader.read_config(filename)
    config.load_dict(values)

    config.validate()


Autoloading
------------
Configs can be auto-loaded from the ``CEREBRUM_CONFIG_ROOT`` directory:
::

    namespace = "foo"
    config = FooConfig()
    loader.read(config, namespace)
    config.validate()

This will automatically look for a ``foo.json`` or ``foo.yaml`` in
``CEREBRUM_CONFIG_ROOT``, and populate the config object.

By autoloading a "namespace", sub-namespaces may be split into separate config
files.  As an example, let's say ``FooConfig`` has a ``bar`` setting that is its
own ``Configuration`` object.  The ``bar`` setting could then remain empty in
the ``foo.yaml`` config file, and be split into its own ``bar.yaml`` config
file.

See the ``Cerebrum.config.loader`` module for more details.


The Configuration
==================
A config is implemented by subclassing and creating a ``Configuration`` object.

Each setting in the ``Configuration`` object, is a ``Setting`` object.  The
Setting objects implement validation rules, as well as value
serialization/deserialization.

Settings are bound to a configuration object by assigning them to a class
attribute, wrapped in a ``ConfigDescriptor`` descriptor.  The descriptor
*attaches* the Setting to the Configuration object.


Nested configuration
---------------------
One ``Configuration`` object can contain other, nested ``Configuration`` objects
by nesting them in a ``Namespace`` setting.


Example:
::

    from Cerebrum.config import configuration
    from Cerebrum.config import secrets
    from Cerebrum.config import settings

    class OrgregClientConfig(configuration.Configuration):
        """ Orgreg API client config. """

        url = configuration.ConfigDescriptor(
            settings.String,
            default="http://localhost",
            doc="URL to an Orgreg API",
        )

        auth = configuration.ConfigDescriptor(
            secrets.Secret,
            doc="Auth token for the Orgreg API",
        )


    class OrgregImportConfig(configuration.Configuration):
        """ Orgreg import config. """

        client = configuration.ConfigDescriptor(
            configuration.Namespace,
            config=OrgregClientConfig,
        )

        perspective = configuration.ConfigDescriptor(
            settings.String,
            doc="Perspective / org tree to update",
        )


In the example above, the ``OrgregImportConfig`` describes a config that would
load a YAML snippet that looks like:
::

    client:
        url: "https://orgreg.example.org"
        auth: "plaintext:my-secret-api-key"

    perspective: "orgreg-tree"

Note that the input config structure can be "flattened".  I.e. the following
YAML snippet below would load the exact same values as the snippet above:
::

    "client.url": "https://orgreg.example.org"
    "client.auth": "plaintext:my-secret-api-key"
    perspective: "orgreg-tree"


Extending configuration
------------------------
Existing configuration classes can be extended with more settings by subclassing
an existing Configuration.

Example:
::

    from Cerebrum.config import configuration
    from Cerebrum.config import secrets
    from Cerebrum.config import settings


    class _HttpClientConfig(configuration.Configuration):

        url = configuration.ConfigDescriptor(
            settings.String,
            default="http://localhost",
            doc="URL to an HTTP service",
        )


    class _BearerTokenMixin(_HttpClientConfig):

        bearer_token = configuration.ConfigDescriptor(
            secrets.Secret,
            doc="A bearer token for the HTTP service",
        )


    class _TimeoutMixin(_HttpClientConfig):

        timeout_connect = configuration.ConfigDescriptor(
            settings.Numeric,
            default=3.1,
            doc="Connect timeout when using the HTTP service (in seconds)",
        )

        timeout_request = configuration.ConfigDescriptor(
            settings.Numeric,
            default=5.0,
            doc="Read timeout when using the HTTP service (in seconds)",
        )


    class MyHttpClientConfig(_TimeoutMixin, _BearerTokenMixin, _HttpClientConfig):
        pass


Documentation
--------------
Settings include descriptions, which can be formatted into a set of
documentation.

To show the documentation from the example in the `nested configuration`_
section:
::

    print(OrgregImportConfig.documentation())

Would show as:
::

    <class '__main__.OrgregImportConfig'>
    client: <class 'Cerebrum.config.configuration.Namespace'>
        auth: <class 'Cerebrum.config.secrets.Secret'>
            description: Auth token for the Orgreg API
            types: (<class 'str'>,)
        url: <class 'Cerebrum.config.settings.String'>
            description: URL to an Orgreg API
            default: 'http://localhost'
            types: (<class 'str'>,)
    perspective: <class 'Cerebrum.config.settings.String'>
        description: Perspective / org tree to update
        default: 'orgreg-tree'
        types: (<class 'str'>,)


Errors
-------
Invalid or missing settings will raise a
``Cerebrum.config.errors.ConfigurationError``.

Values may be checked at three different points:

1. When assigning to an individual setting (e.g. ``my_config.foo.bar = "baz"``)
2. When loading a config dict (e.g. ``my_config.load_dict({"foo.bar": "baz"})``)
3. When calling ``Configuration.validate()``.  This is the only point that will
   catch missing, required settings.

A ``ConfigurationError`` may include *multiple* rule violations.
