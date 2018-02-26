#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2009 University of Oslo, Norway
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

# $Id$

import sys
import getopt

import cerebrum_path

from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.modules.dns import IPNumber, IPv6Number


del cerebrum_path

progname = __file__.split("/")[-1]

__doc__ = """
Usage: %s [options]
   --file, -f   File to be generated

'--file' must be specified

Retrieves all MAC-addressesknown in Cerebrum and dumps them to the
given output-file along with the IP-addresses associated with each
MAC-address.

FORMAT OF DATAFILE

* One MAC-address per line
* Comma-seperated list of all IP-addresses associated with said MAC.

The list of IP-addresses starts at the 20th character on the line; the
space between the MAC-address and the list of IP-addresses is padded
with <space>-characters.

""" % progname


logger = Factory.get_logger("cronjob")

db = Factory.get('Database')()
db.cl_init(change_program=progname[:16])


def get_data_from_DB():
    """Retrieves all relevant data needed from database

    @rtype: dict
    @return: A dictionary where the keys are MAC-addresses and the
             values are lists of IP-addresses associated with each
             MAC-address.
    """
    ips_by_mac = {}

    ipnumber = IPNumber.IPNumber(db)
    all_ips = ipnumber.list()
    mac_ips = 0

    for ip in all_ips:
        if ip['mac_adr'] is None:
            continue
        current = ips_by_mac.get(ip['mac_adr'], [])
        current.append(ip['a_ip'])
        ips_by_mac[ip['mac_adr']] = current
        mac_ips += 1
    ipnumber = IPv6Number.IPv6Number(db)
    all_ips = ipnumber.list()

    for ip in all_ips:
        if ip['mac_adr'] is None:
            continue
        current = ips_by_mac.get(ip['mac_adr'], [])
        current.append(ip['aaaa_ip'])
        ips_by_mac[ip['mac_adr']] = current
        mac_ips += 1

    logger.info("Found a total of %s MAC-addesses in DB",
                len(ips_by_mac.keys()))
    logger.info("Found a total of %s associated IP-addesses in DB", mac_ips)
    return ips_by_mac


def write_to_file(ips_by_mac, file):
    """Writes all relevant data to selected output file.

    @type ips_by_mac: dict
    @param ips_by_mac: A dictionary where the keys are MAC-addresses
                       and the values are lists of IP-addresses
                       associated with each MAC-address.

    @type file: string
    @param file: Path/name of the file where the data should be
                 written to
    """
    all_macs = ips_by_mac.keys()
    all_macs.sort()
    logger.info("Writing to export-file: '%s'" % file)

    output_stream = SimilarSizeWriter(file, "w")
    output_stream.max_pct_change = 10
    for mac in all_macs:
        output_stream.write("%-18s %s\n" % (mac, ",".join(ips_by_mac[mac])))
    logger.info("Done writing to export-file")
    output_stream.close()


def usage(message=None):
    """Gives user info on how to use the program and its options.

    @type message: string
    @param message: Additional message to give to user, e.g. error
                    explanation

    """
    if message is not None:
        print >>sys.stderr, "\n%s" % message

    print >>sys.stderr, __doc__


def main(argv=None):
    """Main processing hub for program.

    @type argv: list
    @param argv: List of arguments, usually from commmandline

    @rtype: int
    @return: Exit value
    """
    if argv is None:
        argv = sys.argv

    # Default values for command-line options
    options = {"file": None}

    ######################################################################
    # Option-gathering
    try:
        opts, args = getopt.getopt(argv[1:],
                                   "hf:",
                                   ["help", "file="])
    except getopt.GetoptError as error:
        usage(message=error.msg)
        return 1

    for opt, val in opts:
        if opt in ('-h', '--help',):
            usage()
            return 0
        if opt in ('-f', '--file',):
            options["file"] = val

    if not options["file"]:
        usage("Error: need to specify exportfile.")
        return 2

    ######################################################################
    # Data-processing

    ips_by_mac = get_data_from_DB()
    write_to_file(ips_by_mac, options["file"])
    return 0


if __name__ == "__main__":
    logger.info("Starting program '%s'" % progname)
    return_value = main()
    logger.info("Program '%s' finished" % progname)
    sys.exit(return_value)
