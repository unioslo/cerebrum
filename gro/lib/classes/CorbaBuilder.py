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

__all__ = ['CorbaBuilder']

from Cerebrum.extlib import sets

class CorbaBuilder:
    def create_idl_interface(cls, exceptions=()):
        txt = 'interface Spine%s' % cls.__name__

        parent_slots = sets.Set()
        if cls.builder_parents:
            txt += ': ' + ', '.join(['Spine' + i.__name__ for i in sets.Set(cls.builder_parents)])
            for i in cls.builder_parents:
                parent_slots.update(i.slots)
                parent_slots.update(i.method_slots)

        txt += ' {\n'

        def get_exceptions(exceptions):
            # FIXME: hente ut navnerom fra cereconf? err.. stygt :/
            if not exceptions:
                return ''
            else:
                return '\n\t\traises(%s)' % ', '.join(['Cerebrum_core::Errors::' + i for i in exceptions])

        from Dumpable import Struct
        headers = []
        def add_header(header):
            if header not in headers:
                headers.append(header)
        def get_type(data_type):
            if type(data_type) == list:
                blipp = get_type(data_type[0])
                name = blipp + 'Seq'
                add_header('typedef sequence<%s> %s;' % (blipp, name))

            elif data_type == str:
                name = 'string'

            elif data_type == int:
                name = 'long'

            elif data_type == None:
                name = 'void'

            elif data_type == bool:
                name = 'boolean'

            elif isinstance(data_type, Struct):
                cls = data_type.data_type
                name = cls.__name__ + 'Struct'

                header = 'struct %s {\n' % name
                header += '\t%s reference;\n' % get_type(cls)
                for attr in cls.slots + [i for i in cls.method_slots if not i.write]:
                    header += '\t%s %s;\n' % (get_type(attr.data_type), attr.name)

                header += '};'

                add_header(header)

            else:
                name = 'Spine' + data_type.__name__
                add_header('interface %s;' % name)

            return name
                

        txt += '\n\t//get and set methods for attributes\n'
        for attr in cls.slots:
            if attr in parent_slots:
                continue
            exception = get_exceptions(tuple(attr.exceptions) + tuple(exceptions))
            data_type = get_type(attr.data_type)
            txt += '\t%s get_%s()%s;\n' % (data_type, attr.name, exception)
            if attr.write:
                txt += '\tvoid set_%s(in %s new_%s)%s;\n' % (attr.name, data_type, attr.name, exception)
            txt += '\n'

        if cls.method_slots:
            txt += '\n\t//other methods\n'
        for method in cls.method_slots:
            if method in parent_slots:
                continue
            exception = get_exceptions(tuple(method.exceptions) + tuple(exceptions))

            args = []
            for name, data_type in method.args:
                args.append('in %s in_%s' % (get_type(data_type), name))

            data_type = get_type(method.data_type)
            txt += '\t%s %s(%s)%s;\n' % (data_type, method.name, ', '.join(args), exception)

        txt += '};\n'

        return headers, txt
    create_idl_interface = classmethod(create_idl_interface)

def create_idl_source(classes, module_name='Generated'):
    include = '#include "errors.idl"\n'
    headers = []
    lines = []

    exceptions = ('TransactionError', 'AlreadyLockedError')

    defined = []
    for cls in classes:
        cls_headers, cls_txt = cls.create_idl_interface(exceptions=exceptions)
        for i in cls_headers:
            if i not in headers:
                headers.append(i)
        lines.append('\t' + cls_txt.replace('\n', '\n\t'))

    return '%s\nmodule %s {\n%s\n%s\n};\n' % (include,
                                              module_name,
                                              '\n'.join(headers),
                                              '\n'.join(lines))
# arch-tag: bddbc6e7-fa76-4a6e-a7be-c890c537b54c
