#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2012 University of Oslo, Norway
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

import sys, getopt
from datetime import datetime

import cerebrum_path
import cereconf

from Cerebrum import OU
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email

db = Factory.get("Database")()
co = Factory.get("Constants")(db)
ou = Factory.get("OU")(db)
ac = Factory.get("Account")(db)

email = Email.EmailDomain(db)
eed = Email.EntityEmailDomain(db)


def usage(exitcode=0):
	"""Prints a usage string."""

	print """Usage: generate_ous_without_email_domain_report.py --output <file>

	Generates a HTML formatted report of OUs/stedkoder without an associated email domain

	-o, --output <file>		The file to print the report to. Defaults to stdout.
	-e, --exclude-empty		Exclude OUs with no affiliated users. Defaults to false if not present.
	"""
	sys.exit(exitcode)


def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], 'ho:e', ['output=', 'exclude-empty'])
	except getopt.GetoptError, e:
		print e
		usage(1)

	output = sys.stdout
	exclude_empty = False

	for opt, val in opts:
		if opt in ('-h', '--help'):
			usage()
		elif opt in ('-o', '--output'):
			output = open(val, 'w')
		elif opt in ('-e', '--exclude-empty'):
			exclude_empty = True

	print_report(output, get_report(exclude_empty))

	if not output is sys.stdout:
		output.close()


def get_report(exclude_empty):
	"""Returns a list of OUs with no email domain"""

	# Count the number of accounts in each OU
	ou_to_num_accounts = {}
	for acc in ac.list_accounts_by_type():
		ou_id = acc['ou_id']

		if ou_to_num_accounts.has_key(ou_id):
			ou_to_num_accounts[ou_id] += 1
		else:
			ou_to_num_accounts[ou_id] = 1

	# Map OU ids to email domain
	ou_to_domain = {}
	for dom in email.list_email_domains():
		for affs in eed.list_affiliations(domain_id=dom['domain_id']):
			ou_to_domain[affs[0]] = dom['domain_id']

	# Iterate through OUs
	report = []
	for sko in ou.get_stedkoder():
		ou_id = sko['ou_id']

		if exclude_empty and not ou_to_num_accounts.has_key(ou_id):
			continue
		if not ou_to_domain.has_key(ou_id):
			ou.clear()
			ou.find(ou_id)

			ou_quarantine = ou.get_entity_quarantine()

			# Skip if OU is in quarantine
			if len(ou_quarantine) is 0:
				if not ou_to_num_accounts.has_key(ou_id):
					ou_num_accounts = 0
				else:
					ou_num_accounts = ou_to_num_accounts[ou_id]

				ou_name = ou.get_name_with_language(name_variant=co.ou_name, name_language=co.language_nb, default="")

				report.append({
					'stedkode': '%02d%02d%02d' % (sko['fakultet'], sko['institutt'], sko['avdeling']),
					'ou_id': ou_id,
					'ou_num_accounts': ou_num_accounts,
					'ou_name': ou_name
				})

	return sorted(report, key=lambda k: k['stedkode'])


def print_report(output, report):
	"""Turns a list of OUs into a formatted HTML report"""

	output.write("""<html>
	<head>
		<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
		<title>Stedkoder uten e-postdomene</title>
		<style type="text/css">
		h1 { font-size: 1.4em; margin: 1em .8em 1em .8em; }
		table { border-collapse: collapse; width: 100%; text-align: left; }
		table thead { border-bottom: solid gray 1px; }
		table th, table td { padding: .5em 1em; }
		.meta { color: gray; text-align: right; }
		</style>
	</head>
	<body>
		<p class="meta">Generert """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
		<h1>Stedkoder uten e-postdomene</h1>
		<table>
			<thead>
				<tr>
					<th>Stedkode</th>
					<th>OU Entity ID</th>
					<th>Antall brukere</th>
					<th>Navn</th>
				</tr>
			</thead>
			<tbody>""")

	for item in report:
		output.write("\n<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (item['stedkode'], item['ou_id'], item['ou_num_accounts'], item['ou_name']))

	output.write("\n\t\t\t</tbody>\n\t\t</table>\n\t</body>\n</html>")


if __name__ == '__main__':
	main()
