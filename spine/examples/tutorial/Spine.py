import os
import SpineClient

ior_url = 'http://pointy.itea.ntnu.no/~erikgors/spine.ior'
use_ssl = False
idl_path = '/tmp/erikgors'

username = 'bootstrap_account'
password = 'blapp'

def connect():
 spine = SpineClient.SpineClient(ior_url, use_ssl, idl_path=idl_path)
 return spine.connect()

def login():
    return connect().login(username, password)

if __name__ == '__main__':
    version = connect().get_version()
    print 'Spine v%s.%s' % (version.major, version.minor)

# arch-tag: e0e532e4-56ae-11da-8677-5089de056b48
