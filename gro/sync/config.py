import ConfigParser

conf = ConfigParser.ConfigParser()
conf.read('client.conf.template')
conf.read('client.conf')

sync = ConfigParser.ConfigParser()
sync.read('sync.conf.template')
sync.read('sync.conf')

# arch-tag: 822897c4-fded-4788-9d1a-fbe22b2f7219
