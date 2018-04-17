#!/usr/bin/env python
# *-* coding: utf-8 *-*
"""
Helper tool for developing Cerebrum template-files.
Launches a web-server that serves the template-file with live reloading.
"""

import json
import os
import formic
from livereload import Server, shell
from flask import Flask, render_template, request
from distutils.dir_util import copy_tree
from subprocess import Popen
from env import create_environment

render_pdf_cmd = 'google-chrome --no-sandbox --headless --no-margins --disable-gpu --print-to-pdf=/static/output.pdf file:///static/pdf_tmp.html'

jinja_config = {
    'template_folders': [
        os.path.join(os.getcwd(), 'templates'),
        os.path.join(os.getcwd(), 'synced-templates'),
    ],
    'static_prefix': '/static/'
}

usage = """
<h1>You have now entered the realm of The Epic Cerebrum Template Dev-server!</h1>
<h2>Usage:</h2>
<p>http://localhost:5500/?template=my-template.html&vars=my-vars.json.</p>
<p>The template file (and static files) must be present either inside 
   ./templates or ./synced-templates.</p>
<p>The vars file must be present in ./template-vars.</p>
<p>.scss-files found in the ./scss-folder will be automatically compiled and
   placed inside the ./templates-folder as .css-files. 
</p>
<p>In order to render a template into a PDF-file, add pdf=1
 as a query parameter in the URL, like this:</p>
<p>http://localhost:5500/?template=my-template.html&vars=my-vars.json&pdf=1</p>
<p>The PDF can the be viewed at http://localhost:5500/static/output.pdf</p>
<p>Happy templating!</p>
"""


def start(host, port):
    app = Flask(
        __name__,
        static_folder='/static'
    )

    app.config['DEBUG'] = True

    @app.route('/')
    def index():
        template_name = request.args.get('template')
        vars_file = request.args.get('vars')
        make_pdf = request.args.get('pdf')

        if template_name is None:
            return usage

        if vars_file is not None:
            with open(os.path.join('template-vars', vars_file), 'r') as f:
                template_vars = json.load(f)
        else:
            template_vars = {}

        for folder in jinja_config['template_folders']:
            copy_tree(folder, '/static', update=1)
        env = create_environment(jinja_config)
        template = env.get_template(template_name)
        rendered = template.render(**template_vars).encode('utf-8')
        if make_pdf:
            print('MAKING PDF!')
            with open('/static/pdf_tmp.html', 'wb') as pdf:
                pdf.write(rendered)
            Popen(render_pdf_cmd, shell=True).wait()
        return rendered

    server = Server(app.wsgi_app)
    watched_files = formic.FileSet(include='**/*',
                                   exclude=['templates/**/*.css',
                                            'templates/pdf_tmp.html',
                                            '**/*.pdf'])
    for file_name in watched_files:
        server.watch(file_name, shell(
            'node-sass-chokidar scss -o templates'
        ))
    server.serve(host=host, port=port, liveport=35729)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '-i',
        help='ip/hostname to start the server on.',
        type=str,
        default='0.0.0.0')
    parser.add_argument(
        '-p',
        help='port to start the server on.',
        type=str,
        default='5500')

    args = parser.parse_args()

    start(args.i, args.p)


if __name__ == '__main__':
    main()