import ConfigParser

conf = ConfigParser.ConfigParser()
conf.read('client.conf.template')
conf.read('client.conf')

sync = ConfigParser.ConfigParser()
sync.read('sync.conf.template')
sync.read('sync.conf')

