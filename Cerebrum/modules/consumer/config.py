
""" basic consumer settings. """
import ssl

import pika

from Cerebrum.config.configuration import (
    Configuration,
    ConfigDescriptor,
    Namespace,
)
from Cerebrum.config.settings import (
    Boolean,
    FilePath,
    Iterable,
    Numeric,
    String,
)


_notset = object()


class Exchange(Configuration):
    """Configuration of a broker exchange."""

    name = ConfigDescriptor(
        String,
        minlen=1,
        doc='Exchange name',
    )
    # TODO: Choice?
    exchange_type = ConfigDescriptor(
        String,
        minlen=1,
        default='topic',
        doc='Exchange type',
    )
    durable = ConfigDescriptor(
        Boolean,
        default=True,
        doc='Set exchange to be durable',
    )


class Queue(Configuration):
    """Configuration of a broker queue."""

    name = ConfigDescriptor(
        String,
        minlen=1,
        doc='Queue name',
    )
    durable = ConfigDescriptor(
        Boolean,
        default=True,
        doc='Set queue to be durable',
    )
    exclusive = ConfigDescriptor(
        Boolean,
        default=False,
        doc='Set queue to be exclusive',
    )
    auto_delete = ConfigDescriptor(
        Boolean,
        default=False,
        doc='Set queue to be deleted',
    )


class Binding(Configuration):
    """Configuration of an exchange/queue binding."""

    exchange = ConfigDescriptor(
        String,
        minlen=1,
        doc='Exchange to bind from',
    )
    queue = ConfigDescriptor(
        String,
        minlen=1,
        doc='Queue to bind to',
    )
    routing_keys = ConfigDescriptor(
        Iterable,
        template=String(minlen=1, doc='Routing key'),
        doc='A list of routing keys to bind',
    )


class Connection(Configuration):
    """Connection params for a message broker."""

    username = ConfigDescriptor(
        String,
        default='guest',
        doc='Username for plain authentication',
    )

    password = ConfigDescriptor(
        String,
        default='guest',
        doc='Password for plain authentication',
    )

    host = ConfigDescriptor(
        String,
        default='localhost',
        doc='Hostname or IP',
    )

    port = ConfigDescriptor(
        Numeric,
        minval=0,
        maxval=0xFFFF,
        default=5672,
        doc='Port number at host',
    )

    ssl_enable = ConfigDescriptor(
        Boolean,
        default=False,
        doc='Connection/port uses ssl',
    )

    ca_file = ConfigDescriptor(
        FilePath,
        doc='Path to a ca-file in PEM format',
    )

    client_cert_file = ConfigDescriptor(
        FilePath,
        doc='Path to a client certificate in PEM format',
    )

    client_key_file = ConfigDescriptor(
        FilePath,
        doc='Path to a client key in PEM format',
    )

    virtual_host = ConfigDescriptor(
        String,
        default='/',
        doc='RabbitMQ virtual host (namespace) to use',
    )


class ConsumerConfig(Configuration):
    """MQ consumer/manager config."""

    connection = ConfigDescriptor(
        Namespace,
        config=Connection,
        doc=Connection.__doc__.strip(),
    )

    consumer_tag = ConfigDescriptor(
        String,
        default=None,
        doc='A consumer tag',
    )

    exchanges = ConfigDescriptor(
        Iterable,
        template=Namespace(config=Exchange),
        default=(),
        doc='A list of exchanges',
    )

    queues = ConfigDescriptor(
        Iterable,
        template=Namespace(config=Queue),
        default=(),
        doc='A list of queues',
    )

    bindings = ConfigDescriptor(
        Iterable,
        template=Namespace(config=Binding),
        default=(),
        doc='A list of bindings',
    )


def get_credentials(config):
    """ Get credentials from Connection object. """
    if config.username or config.password:
        return pika.PlainCredentials(config.username, config.password)
    return None


def get_ssl_options(config):
    """ Get ssl options from Connection object. """
    if config.ssl_enable:
        ssl_context = ssl.create_default_context(cafile=config.ca_file)
        # load_cert_chain requires first param (certfile) to be a valid file
        # system path. keyfile is optional tough, so we do not need to check if
        # it is defined:
        if config.client_cert_file:
            ssl_context.load_cert_chain(config.client_cert_file,
                                        config.client_key_file)

        return pika.SSLOptions(ssl_context, config.host)
    return None


def get_connection_params(config, credentials=_notset, ssl_options=_notset):
    """ Get pika connection from Connection object. """
    if credentials is _notset:
        credentials = get_credentials(config)

    if ssl_options is _notset:
        ssl_options = get_ssl_options(config)

    return pika.ConnectionParameters(
        config.host,
        config.port,
        virtual_host=config.virtual_host,
        ssl_options=ssl_options,
        credentials=credentials,
    )


if __name__ == '__main__':
    print(ConsumerConfig.documentation())
