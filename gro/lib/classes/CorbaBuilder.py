# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

class CorbaBuilder:
    corba_parents = []

    def create_idl(cls, module_name=None, exceptions=()):
        txt = cls.create_idl_header()
        txt += cls.create_idl_interface(exceptions=exceptions)

        if module_name is not None:
            return 'module %s {\n\t%s\n};' % (module_name, txt.replace('\n', '\n\t'))
        else:
            return txt

    create_idl = classmethod(create_idl)

    def create_idl_header(cls, defined = None):
        if defined is None:
            defined = []

        txt = ''

        for slot in cls.slots + cls.method_slots:
            if slot.data_type in (str, int, None, bool):
                continue

            if slot.data_type in defined:
                continue
            else:
                defined.append(slot.data_type)

            name = slot.data_type.__name__

            txt += 'interface %s;\n' % name
            txt += 'typedef sequence<%s> %sSeq;\n' % (name, name)

        return txt

    create_idl_header = classmethod(create_idl_header)

    def create_idl_interface(cls, exceptions=()):
        txt = 'interface %s {\n' % cls.__name__

        txt = 'interface ' + cls.__name__
        if cls.corba_parents:
            txt += ': ' + ', '.join(cls.corba_parents)

        txt += ' {\n'

        txt += '\t//constructors\n'
        
        def get_exceptions(exceptions):
            # FIXME: hente ut navnerom fra cereconf? err.. stygt :/
            if not exceptions:
                return ''
            else:
                return '\n\t\traises(%s)' % ', '.join(['Cerebrum_core::Errors::' + i for i in exceptions])

        def get_type(data_type, sequence):
            if data_type == str:
                name = 'string'
            elif data_type == int:
                name = 'long'
            elif data_type == None:
                name = 'void'
            elif data_type == bool:
                name = 'boolean'
            else:
                name = data_type.__name__
            if sequence:
                name += 'Seq'
            return name
                

        txt += '\n\t//get and set methods for attributes\n'
        for attr in cls.slots:
            exception = get_exceptions(tuple(attr.exceptions) + tuple(exceptions))
            type = get_type(attr.data_type, attr.sequence)
            txt += '\t%s get_%s()%s;\n' % (type, attr.name, exception)
            if attr.write:
                txt += '\tvoid set_%s(in %s new_%s)%s;\n' % (attr.name, type, attr.name, exception)
            txt += '\n'

        txt += '\n\t//other methods\n'
        for method in cls.method_slots:
            exception = get_exceptions(tuple(method.exceptions) + tuple(exceptions))

            args = []
            for arg in method.args:
                if len(arg) == 2:
                    name, data_type = arg
                    sequence = False
                else:
                    name, data_type, sequence = arg
                
                args.append('in %s in_%s' % (get_type(data_type, sequence), name))

            type = get_type(method.data_type, method.sequence)
            txt += '\t%s %s(%s)%s;\n' % (type, method.name, ', '.join(args), exception)

        txt += '};\n'

        return txt

    create_idl_interface = classmethod(create_idl_interface)

def create_idl_source(classes, module_name = 'Generated'):
    include = '#include "errors.idl"\n'
    header = []
    lines = []
    header.append('typedef sequence<string> stringSeq;\n')
    header.append('typedef sequence<long> longSeq;\n')
    header.append('typedef sequence<float> floatSeq;\n')
    header.append('typedef sequence<boolean> booleanSeq;\n')

    exceptions = ('TransactionError', 'AlreadyLockedError')

    defined = []
    for cls in classes:
        header.append('\t' + cls.create_idl_header(defined).replace('\n', '\n\t'))
        lines.append('\t' + cls.create_idl_interface(exceptions=exceptions).replace('\n', '\n\t'))

    return '%s\nmodule %s {\n%s\n%s\n};\n' % (include,
                                              module_name,
                                              '\n'.join(header),
                                              '\n'.join(lines))
# arch-tag: bddbc6e7-fa76-4a6e-a7be-c890c537b54c
