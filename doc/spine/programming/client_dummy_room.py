import sys

# replace this with import cerebrum_path or something
sys.path.append('/home/erikgors/install/etc/cerebrum')
sys.path.append('/home/erikgors/install/lib/python2.3/site-packages')

import SpineClient
spine = SpineClient.SpineClient('http://pointy.itea.ntnu.no/~erikgors/spine.ior', idl_path='/tmp/erikgors').connect()

session = spine.login('bootstrap_account', 'blapp')
tr = session.new_transaction()

cmd = tr.get_dummy_commands()

building = cmd.create_building('RA3', 'realfagsbygget')
room = cmd.create_room('A3-111 B', building, 'prosjektrom')

for room in tr.get_dummy_room_searcher().search():
    print room.get_id(), room.get_name(), room.get_description(), 'building:', room.get_building().get_name()

# tr.commit()

# arch-tag: c7e8b83c-cb49-11da-83cd-13e9296b50e4
