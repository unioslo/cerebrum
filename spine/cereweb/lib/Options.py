# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

import os
import ConfigParser
from gettext import gettext as _

path = os.path.dirname(__file__) or '.'
template = os.path.join(path, 'options.conf.template')
config = os.path.join(path, 'options.conf')

default_options = ConfigParser.ConfigParser()
default_options.read(template)
default_options.read(config)

class Options(ConfigParser.ConfigParser):
    """User-specific options for cereweb.
    
    Reads the options from file, and stores options which differ
    from the default-values in the database.

    Adds type and help-text to the classic ConfigParser, which is
    used when displaying the options form for the user. To add
    help-text to an section or an option add it as an option with
    the key <name>_help. Type is handled the same way and available
    types are, but not limited to, checkbox, int, boolean.
    """
    
    def __init__(self, session, user):
        ConfigParser.ConfigParser.__init__(self)
        self.session = session
        self.user = user
        self.load()
    
    def _get_user(self, tr):
        """Finds the user by the name."""
        return tr.get_commands().get_account_by_name(self.user)
    
    def _read_from_db(self, tr):
        """Returns structs with options set in the db."""
        searcher = tr.get_cereweb_option_searcher()
        searcher.set_entity(self._get_user(tr))
        return searcher.dump()
    
    def _get_changes_from_default(self):
        """Returns options which have changed from the default options."""
        changes = []
        for s in self.sections():
            changes.extend([(s, k, v) for k, v in self.items(s)
                            if default_options.get(s, k) != v])
        return changes
    
    def save(self):
        """Save changes to the database.
        
        Write options which differ from the default config to the database.
        """
        tr = self.session.new_transaction()
        commands = tr.get_commands()
        user = self._get_user(tr)
        
        changes = self._get_changes_from_default()
        structs = self._read_from_db(tr)

        # update changes not already in db
        for s, k, v in changes:
            tmp = [i for i in structs if i.section == s and i.key == k]
            if not tmp:
                commands.create_cereweb_option(user, s, k, v)
            elif tmp[0].value != v:
                option = tr.get_cereweb_option(int(tmp[0].id))
                option.set_value(v)

        # remove changes from db which equals default-values
        for s in structs:
            tmp = [i for i in changes if i[0] == s.section and i[1] == s.key]
            if not tmp:
                option = tr.get_cereweb_option(int(s.id))
                option.delete()
        
        tr.commit()

    def load(self):
        """Read options from file and database.

        Default options are stored on file, and options which differ from
        them are stored in the database.
        """
        ConfigParser.ConfigParser.read(self, template)
        ConfigParser.ConfigParser.read(self, config)
        
        tr = self.session.new_transaction()
        result = self._read_from_db(tr)
        for struct in result:
            self.set(struct.section, struct.key, struct.value)
        tr.rollback()

    def read():
        raise Exception('Use load to read from file and db.')
        
    def write():
        raise Exception('Default-values are readonly, use save to write to db.')


def restore_to_default(transaction, entity):
    """Deletes all options for entity in the database."""
    search = transaction.get_cereweb_option_searcher()
    search.set_entity(entity)
    for option in search.search():
        option.delete()

# arch-tag: cd23c5b4-4f37-11da-8118-34958c2b9815
