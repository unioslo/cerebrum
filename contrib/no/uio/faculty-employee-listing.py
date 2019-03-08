#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

""" This script exports extracts of employee data.

Specifically, Per Grøttum made a request to have access to some of the employee
data for a script that populates mailing lists at MEDFAK.

Essentially, we want to have an extract of HR-originated data from Cerebrum
'associated' with a given faculty.

Fields that have been requested
-------------------------------

- uname (key, they don't get fnr)
- sko for employment/association
- name
- employment category (tekadm/vit/emeritus/ef-stip/etc.)
- stillingskode
- e-mail address

History
-------
This file has been copied from cerebrum_config, to see its history, look at the
last edit of bin/uio/employee-listing.py:

    commit 5939f46826a3ad40b431d7969d71c5752183cc8a
    Tue Sep 20 08:52:07 2011 +0000

"""
import getopt
import sys
import io

from six import text_type

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.funcwrap import memoize
from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.xmlutils.xml2object import DataOU

logger = Factory.get_logger("cronjob")
database = Factory.get('Database')()
constants = Factory.get('Constants')(database)

DEFAULT_OUTPUT_ENCODING = 'utf-8'


@memoize
def sko2ou_info(sko):
    """Map a sko from HR source data to OU info from Cerebrum.

    Given a sko, we try to locate all the interesting OU information from
    Cerebrum.

    @rtype: dict
    @return:
      A dict with the relevant entries, or an empty dict when no relevant
      information in Cerebrum could be found.
    """

    ou = Factory.get("OU")(database)
    try:
        ou.find_stedkode(sko[0],
                         sko[1],
                         sko[2],
                         cereconf.DEFAULT_INSTITUSJONSNR)
    except Errors.NotFoundError:
        logger.debug("OU sko=%s is not available in Cerebrum")
        return dict()

    return {"sko": "%02d%02d%02d" % sko,
            "name": ou.get_name_with_language(
                name_variant=constants.ou_name,
                name_language=constants.language_nb), }


def slurp_name(person, name_variant):
    """Fetch L{person}'s name of the specified type.

    @type person: Factory.get('Person') instance
    @param person:
      Person proxy associated with the database information.

    @type name_variant: PersonName constant
    @param name_variant:
      Specific name to fetch.

    @rtype: basestring
    @return:
      Name of the specified type for L{person} or None
    """

    # We respect SLO here, but this code should ideally be replaced with
    # SSLO
    for sname in cereconf.SYSTEM_LOOKUP_ORDER:
        try:
            return person.get_name(getattr(constants, sname), name_variant)
        except Errors.NotFoundError:
            pass

    return None


def xml2person(xmlperson, source_system):
    """Locate the relevant Cerebrum info for a person.

    Given XML information from an HR system, we try to locate all the
    interesting person information from Cerebrum.
    """

    # Ugh... more ugly duplication
    idxml2db = {xmlperson.NO_SSN: constants.externalid_fodselsnr,
                xmlperson.SAP_NR: constants.externalid_sap_ansattnr, }

    db_ids = set()
    person = Factory.get("Person")(database)
    for kind, id_on_file in xmlperson.iterids():
        if kind not in idxml2db:
            logger.debug("Unknown external ID %s for person id=%s is ignored",
                         kind, list(xmlperson.iterids()))
            continue

        try:
            person.clear()
            person.find_by_external_id(idxml2db[kind], id_on_file)
            db_ids.add(person.entity_id)
        except Errors.NotFoundError:
            pass
        except Errors.TooManyRowsError:
            person.find_by_external_id(idxml2db[kind], id_on_file,
                                       source_system)
            db_ids.add(person.entity_id)

    # We should see exactly 1 id
    if len(db_ids) == 0:
        logger.debug("Person ids=%s does not exist in Cerebrum",
                     list(xmlperson.iterids()))
        return {}
    elif len(db_ids) > 1:
        logger.debug("Multiple persons entity_ids=%s match XML ids=%s",
                     db_ids, list(xmlperson.iterids()))
        return {}

    # Let's grab all we can
    person.clear()
    person.find(db_ids.pop())
    account_id = person.get_primary_account()
    if account_id is None:
        logger.debug("Person cerebrum id=%s, XML ids=%s has no uname",
                     person.entity_id, list(xmlperson.iterids()))
        return {}
    account = Factory.get("Account")(database)
    account.find(account_id)

    gender2printable = {int(constants.gender_male): "M",
                        int(constants.gender_female): "F", }

    try:
        # If someone has a personal title, use that
        title = person.get_name_with_language(constants.personal_title,
                                              constants.language_nb)
    except Errors.NotFoundError:
        try:
            # ... if not, use worktitle
            title = person.get_name_with_language(constants.work_title,
                                                  constants.language_nb)
        except Errors.NotFoundError:
            # And here I thought everyone had titles?
            title = ""
            logger.debug("No title for person id=%s (account=%s)",
                         person.entity_id, account.account_name)
    try:
        email = account.get_primary_mailaddress()
    except Errors.NotFoundError:
        email = ""
        # if the user is active (has >= 1 spread and no expire), this should
        # not happen, and we should warn about such erroneous accounts.
        if account.get_spread() and not account.is_expired():
            logger.warn("No email for person id=%s (account=%s)",
                        person.entity_id, account.account_name)
        else:
            logger.info("Person id=%s (account=%s) has no e-mail",
                        person.entity_id, account.account_name)
    return {"first_name": slurp_name(person, constants.name_first),
            "last_name": slurp_name(person, constants.name_last),
            "title": title,
            "uname": account.get_account_name(),
            "email": email,
            "gender": gender2printable.get(int(person.gender), "X")}


def output_fields(stream, **rest):
    """Output a bunch of fields to an output sink.

    @type stream: file-like object
    @param stream:
      An open output sink for our fields.
    """

    eol = "\n"
    separator = "\t"
    field_order = ("uname", "stedkode", "first_name", "last_name", "gender",
                   "ou_name", "category", "stillingskode", "title",
                   "date_start", "date_end", "email", "stillingsandel")
    if "uname" not in field_order:
        logger.warn("uname is missing from %s. Record is skipped", rest)
        return

    to_go = list()
    for key in field_order:
        if key not in rest:
            continue

        if rest[key] is not None:
            to_go.append(text_type(rest[key]))
        else:
            to_go.append("")

    stream.write(separator.join(to_go))
    stream.write(eol)


def category2printable(emp):
    primary2print = {emp.KATEGORI_VITENSKAPLIG: "VIT",
                     emp.KATEGORI_OEVRIG: "TEKADM", }

    # True employments are classified into VIT/TEKADM
    if emp.kind in (emp.HOVEDSTILLING, emp.BISTILLING):
        return primary2print.get(emp.category, "")

    # Bilagslønnede remain just that
    if emp.kind == emp.BILAG:
        return "BILAG"

    # The rest are guests and can have an exact status specified
    if emp.kind == emp.GJEST:
        return emp.category

    logger.debug("Employment of weird kind=%s", emp.kind)
    return ""


def fetch_data(parser, source_system, faculty, stream):
    """Extract the relevant employment data for faculty.

    @type parser: XMLDataGetter or its subclass
    @param parser:
      Suitable parser for the specified XML data source.

    @type source_system: AuthoritativeSystem constant (or int)
    @param source_system:
      Source system for the incoming data.

    @type faculty: int
    @param faculty:
      The faculty about which we export the data.

    @type stream: file-like object
    @param stream:
      An open (for writing) file-like object which is the output sink for this
      job.
    """

    # Fuck this code duplication. *UGLY*. (check import_HR_person.py)
    for xmlperson in parser.iter_person():
        person_info = None
        count = 0

        for t in xmlperson.iteremployment():
            if t.kind not in (t.HOVEDSTILLING, t.BISTILLING, t.BILAG, t.GJEST):
                logger.debug("Irrelevant emp kind=%s for person ids=%s",
                             t.kind, list(xmlperson.iterids()))
                continue

            if not t.is_active():
                logger.debug("Non-active employment record for person ids=%s.",
                             list(xmlperson.iterids()))
                continue

            if not (t.place and t.place[0] == DataOU.NO_SKO and
                    t.place[1][0] == faculty and sko2ou_info(t.place[1])):
                logger.debug("Irrelevant OU id=%s for person ids=%s",
                             t.place, list(xmlperson.iterids()))
                continue

            if person_info is None:
                person_info = xml2person(xmlperson, source_system)

            if not person_info.get("uname"):
                logger.debug("Cannot find uname for person ids=%s",
                             list(xmlperson.iterids()))
                break

            count += 1
            ou_info = sko2ou_info(t.place[1])
            # NB! Use keyword arguments. The specific field order will be
            # enforced by output_fields itself.
            output_fields(stream,
                          uname=person_info["uname"],
                          stedkode=ou_info["sko"],
                          ou_name=ou_info["name"],
                          first_name=person_info.get("first_name"),
                          last_name=person_info.get("last_name"),
                          category=category2printable(t),
                          stillingskode=t.code,
                          email=person_info.get("email"),
                          date_start=t.start.strftime("%Y-%m-%d"),
                          date_end=t.end.strftime("%Y-%m-%d"),
                          title=person_info.get("title"),
                          gender=person_info["gender"],
                          stillingsandel=t.percentage)

        logger.debug("Done with person ids=%s (%d entries)",
                     list(xmlperson.iterids()), count)


def main():
    opts, args = getopt.getopt(sys.argv[1:], "s:o:f:",
                               ["source-spec=",
                                "output-file=",
                                "faculty="])

    filename = None
    sources = list()
    faculty = None
    output_encoding = None
    for option, value in opts:
        if option in ("-s", "--source-spec",):
            sysname, personfile = value.split(":")
            sources.append((sysname, personfile))
        elif option in ("-o", "--output-file",):
            filename = value
        elif option in ("-f", "--faculty",):
            faculty = int(value)
            assert 0 < faculty < 100, "Faculty is a 2-digit number"
        elif option in ("-e", "--encoding"):
            output_encoding = value

    assert filename, "Need an output file name"
    assert faculty, "Need a faculty to operate on"
    logger.debug("sources is %s", sources)

    # TODO: Ask per if we can use UTF-8
    stream = io.open(filename, "w", encoding=(output_encoding or
                                              DEFAULT_OUTPUT_ENCODING))
    for system_name, filename in sources:
        # Locate the appropriate Cerebrum constant
        source_system = getattr(constants, system_name)
        parser = system2parser(system_name)

        fetch_data(parser(filename, logger, False),
                   source_system,
                   faculty,
                   stream)

    stream.close()


if __name__ == "__main__":
    main()
