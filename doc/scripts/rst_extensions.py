#!/usr/bin/python2.2
from docutils.parsers.rst import directives
import re
import os
from docutils import io, nodes, statemachine

known_vars = {}

def namespace(name, arguments, options, content, lineno,
              content_offset, block_text, state, state_machine):
    """Define the namespace of this reST file."""
    state.document.set_namespace(arguments[0])
    return None

namespace.arguments = (1, 0, 1)

def sysinclude(name, arguments, options, content, lineno,
            content_offset, block_text, state, state_machine):
    """Insert the stdout of a command as part of the content of this
    reST file."""
    if options.has_key('vardef'):
        tmp = options['vardef'].split(" ", 1)
        known_vars[tmp[0]] = tmp[1]
    if not arguments:
        return None

    encoding = options.get('encoding', state.document.settings.input_encoding) # TODO: verdi?

    cmd = arguments[0] % known_vars
    def repl_var(matchobj):
        return os.environ[matchobj.group(1)]
    cmd = re.sub(r'\$ENV\[([^\]]+)\]', repl_var, cmd)
    p = os.popen(cmd, "r")
    include_file = io.StringInput(
        source=p.read(), source_path=cmd, encoding=encoding,
        error_handler=state.document.settings.input_encoding_error_handler
        )
    include_text = include_file.read()
    tmp = p.close()
    if tmp:
        severe = state_machine.reporter.severe(
              'Problems with "%s" directive cmd:\n%s: exit-value: %i.'
              % (name, cmd, divmod(tmp, 256)[0]),
              nodes.literal_block(block_text, block_text), line=lineno)
        return [severe]
        
    path=cmd

    if options.has_key('literal'):
        literal_block = nodes.literal_block(include_text, include_text,
                                            source=path)
        literal_block.line = 1
        return literal_block
    else:
        include_lines = statemachine.string2lines(include_text,
                                                  convert_whitespace=1)
        state_machine.insert_input(include_lines, path)
        return []

sysinclude.arguments = (0, 1, 1)
sysinclude.options = {'literal': directives.flag,
                      'vardef': directives.unchanged}

# arch-tag: c2dc2937-492d-4066-bdf4-2569685e9413
