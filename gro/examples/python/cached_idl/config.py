import ConfigParser

conf = ConfigParser.ConfigParser()
conf.read('client.conf.template')
conf.read('client.conf')
