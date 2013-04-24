#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""Job for importing XML files generated from Nettskjema surveys.

The data from Nettskjema is normally generated by researchers, asking for new
projects, registering themselves, adding changes to the project or asking about
new project resources. The person who has sent in the form has been
authenticated, e.g. by ID-porten, but no authorizations has been checked. All
requests from the XML files must therefore be approved before it could be e.g.
synced to AD, or do anything harmful, like changing a person's name. Projects
and accounts must for instance start with a quarantine, to be approved by
superusers.

The survey XML files have the format:

    <?xml version="1.0" encoding="UTF-8" standalone="yes">
    <submission>
        <answers>
            <answer>
                <textAnswer>TEXT INPUT</textAnswer>
                <answerOptions>
                    ...
                </answerOptions>
                <question inputType="SOME INPUT TYPE, LIKE TEXT">
                    <externalQuestionId>EXTERNAL ID, SET BY ADMIN</externalQuestionId>
                    ...
                    <questionId>XXX</questionId>
                </question>
            </answer>
            ...
        </answers>
        <respondentPersonIdNumber>FNR FOR THE AUTHENTICATED RESPONDENT</respondentPersonIdNumber>
    </submission>

Tags that are important to us:

 - respondentPersonIdNumber: The FNR for the respondent. We must just trust that
   this number is authenticated through ID-porten, as long as we get the XML
   files from TSD's closed environment.

 - externalQuestionId: An ID for the given answer that is manually set by the
   administrators of the survey. This is used to map answers into attributes in
   Cerebrum.

 - textAnswer: Used for questions that are just simple textfields. No filtering
   is done in Nettskjema, so we need to do all of that in here. Other question
   types have different tags that is used instead.

"""

import sys
import os
import getopt
from lxml import etree
from mx import DateTime

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr

logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
co = Factory.get('Constants')(db)
ou = Factory.get('OU')(db)
pe = Factory.get('Person')(db)
ac = Factory.get('Account')(db)

ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
systemaccount_id = ac.entity_id

def usage(exitcode=0):
    print """
    %(doc)s 
    
    Usage: %(file)s FILE_OR_DIR [FILE_OR_DIR...]

    Where FILE_OR_DIR is a specific XML file to import, or a directory where all
    the XML files should be imported from. You could specify several directories
    and/or files.

    TODO:
    --backup DIR        A directory to move successfully processed files. 

    -h --help           Show this and quit.
    """ % {'doc': __doc__,
           'file': os.path.basename(sys.argv[0])}
    sys.exit(exitcode)

def gateway(command, *args):
    """Send commands to the gateway
    
    The gateway needs to be informed about changes that are useful for it. This
    should only happen when not in dryrun.

    """
    logger.debug("Gateway call: %s(%s)", command, ', '.join(args))
    if dryrun:
        return True
    # TODO: not implemented yet
    return True

def remove_file(file, dryrun, archive_dir=None):
    """Remove a file by either moving it to a archive directory, or delete it.

    The given file should be successfully processed before moving it.

    """
    logger.warn('File deletion is not implemented yet')
    if dryrun:
        return True
    # TODO
    pass

def process_files(locations, dryrun):
    """Do the process thing."""
    for location in locations:
        # TODO: support directories
        try:
            if process_file(location, dryrun):
                if dryrun:
                    db.rollback()
                    logger.info("Dryrun, rolled back changes")
                else:
                    db.commit()
                    logger.info("Commited changes")
                remove_file(location, dryrun)
        except BadInputError, e:
            logger.warn("Bad input in file %s: %s", location, e)
            db.rollback()
        except Errors.CerebrumError, e:
            logger.warn("Failed processing %s: %s", location, e)
            db.rollback()

class BadInputError(Exception):
    """Exception for invalid input."""
    pass

class InputControl(object):
    """Class for validating and filtering the input.

    All control functions should return True if input is valid, or raise a
    BadInputError with a better explanation in case of errors. It could return
    just False, but no explanation would get logged about why the input was
    invalid.

    All the data given from the XML forms must not be trusted, as it could be
    given by anyone with an FNR. The only data we could trust, is the FNR
    itself, as that is authenticated by ID-porten.

    """
    def is_projectid(self, name):
        """Check that a given projectname validates."""
        return ou._validate_project_name(name)

    def is_valid_date(self, date):
        """Check that a date is parsable and valid."""
        DateTime.strptime(date, '%d.%m.%Y')
        return True

    def is_nonempty(self, txt):
        """Check that a string is not empty or only consists of whitespaces."""
        if bool(txt.strip()):
            return True
        raise BadInputError('Empty string')

    def is_username(self, name):
        """Check that a given username is a valid username."""
        self.is_nonempty(name)
        err = ac.illegal_name(name)
        if err:
            raise BadInputError('Illegal username: %s' % err)
        return True

    def is_phone(self, number):
        """Check if a phone number is valid."""
        self.is_nonempty(number)
        number = number.replace(' ', '')
        number = number.replace('-', '')
        if number.startswith('+'):
            number = number[1:]
        if number.isdigit():
            return True
        raise BadInputError('Invalid phone number: %s' % number)

    def is_email(self, adr):
        """Check if an e-mail address is valid."""
        self.is_nonempty(adr)
        # TODO: how much should we check here?
        if '@' not in adr:
            raise BadInputError('Invalid e-mail address: %s' % adr)
        return True

    def is_fnr(self, fnr):
        """Check if input is a valid, Norwegian fnr."""
        self.is_nonempty(fnr)
        # TODO: bogus fnr in test, add the check back when done testing:
        #fnr = fodselsnr.personnr_ok(fnr)
        return True

    def str(self, data):
        """Return the data as a string, stripped."""
        return str(data).strip()

    def filter_date(self, date):
        """Parse a date and return a DateTime object."""
        # TODO: What date format should we use? Isn't ISO the best option?
        return DateTime.strptime(date, '%d.%m.%Y')

input = InputControl()

# Settings for input data
#
# This dict contains the settings for the input control and filter. The keys are
# the tag names that should be found in the file.
#
# Tag found in submission, mapped to requirement func, filter func and name of
# variable.
input_values = {
        # Project ID
        'p_id': (input.is_projectid, input.str),
        # Project full name
        'p_name': (input.is_nonempty, input.str),
        # Project short name
        'p_shortname': (input.is_nonempty, input.str),
        # Project start date
        'p_start': (input.is_valid_date, input.filter_date),
        # Project end date
        'p_end': (input.is_valid_date, input.filter_date),
        # Project owner's FNR
        'p_responsible': (input.is_fnr, input.str),
        # Project's institution address
        'institution': (input.is_nonempty, input.str),
        # Project's REK approval number
        'rek_approval': (input.is_nonempty, input.str),
        # Project members, identified by FNR
        'p_persons': (lambda x: True, input.str),
        # PA's full name
        'pa_name': (input.is_nonempty, input.str),
        # PA's phone number
        'pa_phone': (input.is_phone, input.str),
        # PA's e-mail address
        'pa_email': (input.is_email, input.str),
        # PA's chosen username
        'pa_uiousername': (input.is_username, input.str),
        # The respondent's chosen username. Not necessarily mandatory.
        'uio_or_feide_username': (lambda x: True, input.str),
        # The respondent's full name
        'real_name': (input.is_nonempty, input.str),
        }

# A list of all the required input values for each defined survey type. This is
# used to identify the survey type.
survey_types = {
        'new_project': ('p_id', 'p_name', 'p_shortname', 'p_start', 'p_end',
                        'p_responsible', 'institution', 'rek_approval',
                        'p_persons', 'pa_name', 'pa_phone', 'pa_email',
                        'pa_uiousername'),
        'project_access': ('p_id', 'real_name', 'uio_or_feide_username'),
        'approve_person': ('p_id', 'TODO'),
        }

input_settings = {
    'new_project': {
        'p_id': (input.is_projectid, input.str),
        'p_name': (input.is_nonempty, input.str),
        'p_shortname': (input.is_nonempty, input.str),
        'p_start': (input.is_valid_date, input.filter_date),
        'p_end': (input.is_valid_date, input.filter_date),
        'p_responsible': (input.is_fnr, input.str),
        'institution': (input.is_nonempty, input.str),
        'rek_approval': (input.is_nonempty, input.str),
        'p_persons': (lambda x: True, input.str),

        # The PA:
        'pa_name': (input.is_nonempty, input.str),
        'pa_phone': (input.is_phone, input.str),
        'pa_email': (input.is_email, input.str),
        'pa_uiousername': (input.is_username, input.str),
        },
    'project_access': {
        'real_name': (input.is_nonempty, input.str),
        'p_id': (input.is_projectid, input.str),
        'uio_or_feide_username': (lambda x: True, input.str),
        # TODO: more data, like contact info?
        },
    'approve_person': {
        #TODO
        },
    }


def _xml2answersdict(xml):
    """Parse the XML and return a dict with all the answers.

    No input control or filtering is performed in this function, but only input
    values that are defined in L{input_values} by their external-ID gets
    returned.

    @type xml: etree.Element
    @param xml: The given submission, as an XML object.

    @rtype: dict
    @return: A mapping of the answers. Keys are the external-id of the answer,
        and the values are the answers, most often as strings.

    """
    ret = dict()
    for ans in xml.find('answers').iterfind('answer'):
        try:
            extid = ans.find('question').find('externalQuestionId').text
        except AttributeError:
            # Ignore questions without a set external ID
            continue
        if extid not in input_values:
            # Ignore undefined questions
            continue
        answer = ans.find('textAnswer')
        if answer is not None:
            answer = answer.text
        else:
            # TODO: should be able to parse answers that is not text, if needed
            logger.warn("For question %s, got unhandled answerOption: %s",
                        extid, etree.tostring(ans)[:200])
            continue
        ret[extid] = answer
    return ret

def xml2answers(xml):
    """Fetch and check answers from XML, and guess the submission type.

    The answers are processed through the input control and filter settings in
    L{input_values}.
    
    Since the XML does not have an identifier of what survey it is about, we
    need to guess it by finding the L{survey_type} that has all its questions
    answered in the XML. The external IDs are used for this.

    Note that you *could* get a file that matches more than one survey type,
    which is an error. You then either have to fix the config of L{input_values}
    and L{survey_types}, or you need to change the defined external IDs in the
    form at Nettskjema.

    @type xml: etree.Element
    @param xml:
        The parsed content of a file from Nettskjema.

    @rtype: (string, dict)
    @return: The first element contains the id of the submission type, defined
        in L{survey_types}, followed by a dict with the answers. The keys are
        from L{input_values} and the values are the filtered answers.

    """
    answers = _xml2answersdict(xml)
    # Find the correct survey type:
    stypes = []
    for stype, requireds in survey_types.iteritems():
        if all(req in answers for req in requireds):
            stypes.append(stype)
    if len(stypes) != 1:
        raise Exception('Could not uniquely identify submission type: %s' %
                        stypes)
    # Do the input control and filtering:
    ret = dict()
    for extid in survey_types[stypes[0]]:
        control, filter = input_values[extid]
        answer = answers[extid]
        try:
            control_ans = control(answer)
        except BadInputError, e:
            raise BadInputError('Answer "%s" invalid: %s. Answer: %s' % (extid, e,
                                                                         answer))
        if not control_ans:
            raise BadInputError('Answer "%s" invalid: %s' % (extid, answer))
        ret[extid] = filter(answer)
    return stypes.pop(), ret

def process_file(file, dryrun):
    logger.info("Processing file: %s", file)
    xml = etree.parse(file).getroot()
    stype, answers = xml2answers(xml)
    fnr = xml.find('respondentPersonIdNumber').text
    logger.debug('Processing %s: found %d answers from respondent: %s', stype,
                 len(answers), fnr)

    # Do the Cerebrum processing:
    p = Processing(fnr=fnr)
    ret = getattr(p, stype)(answers)
    logger.debug("Submission processed: %s" % ret)

class Processing(object):
    """Handles the processing of the parsed and validated XML data."""

    def __init__(self, fnr):
        """Set up the processing.

        @type fnr: string
        @param fnr: The fødselsnummer for the person that sent in the survey and
            requested some changes in TSD.

        """
        self.fnr = fnr

    def _get_person(self, fnr=None):
        """Return the person with the given fnr.

        If the person does not exist, it gets created. Names and all other data
        but the fnr needs to be added to the person.

        """
        if not fnr:
            fnr = self.fnr
        pe = Factory.get('Person')(db)
        try:
            pe.find_by_external_id(id_type=co.externalid_fodselsnr,
                                   external_id=fnr)
        except Errors.NotFoundError:
            logger.info("Creating new person, with fnr: %s", fnr)
            pe.clear()
            pe.populate(birth_date=None, gender=co.gender_unknown)
            pe.write_db()
            pe.affect_external_id(co.system_nettskjema, co.externalid_fodselsnr)
            pe.populate_external_id(source_system=co.system_nettskjema,
                                    id_type=co.externalid_fodselsnr,
                                    external_id=fnr)
            pe.write_db()
        return pe

    def _update_person(self, pe, input):
        """Update the data about a given person.

        Update names, contact info and other available data.

        """
        # Full name
        for key in ('pa_name', 'real_name'):
            if key in input:
                logger.debug("Updating name: %s", input[key])
                pe.affect_names(co.system_nettskjema, co.name_full)
                pe.populate_name(co.name_full, input[key])
                pe.write_db()
        # Phone
        if 'pa_phone' in input:
            logger.debug("Updating phone: %s", input['pa_phone'])
            pe.populate_contact_info(source_system=co.system_nettskjema,
                                     type=co.contact_phone, value=input['pa_phone'])
            pe.write_db()
        # E-mail
        if 'pa_email' in input:
            logger.debug("Updating mail: %s", input['pa_email'])
            pe.populate_contact_info(source_system=co.system_nettskjema,
                                     type=co.contact_email, value=input['pa_email'])
            pe.write_db()

    def _create_ou(self, input):
        """Create the project OU based in given input."""
        pid = input['p_id']
        # Make sure the project id is not already in use:
        ou.clear()
        try:
            ou.find_by_tsd_projectname(pid)
            raise Errors.CerebrumError('ProjectId already taken: %s' % pid)
        except Errors.NotFoundError: 
            pass
        ou.clear()
        ou.populate()
        ou.write_db()
        # TODO: should this be given after the project has been accepted
        # instead?
        gateway('project.create', pid)
        #gateway('project.freeze', pid)

        # Storing the names:
        ou.add_name_with_language(name_variant=co.ou_name_acronym,
                                  name_language=co.language_en, name=pid)
        longname = input['p_name']
        logger.debug("Storing name: %s", longname)
        ou.add_name_with_language(name_variant=co.ou_name_long,
                                  name_language=co.language_en, name=longname)
        shortname = input['p_shortname']
        logger.debug("Storing short name: %s", shortname)
        ou.add_name_with_language(name_variant=co.ou_name_long,
                                  name_language=co.language_en, name=shortname)
        ou.write_db()

        # Always start projects quarantined, needs to be approved first!
        ou.add_entity_quarantine(type=co.quarantine_not_approved,
                                 creator=systemaccount_id,
                                 description='Project not approved yet',
                                 start=DateTime.now())
        ou.write_db()

        # Storing the start and end date:
        endtime = input['p_end']
        if endtime < DateTime.now():
            raise Errors.CerebrumError("End date of project has passed: %s" %
                                       endtime)
        ou.add_entity_quarantine(type=co.quarantine_project_end,
                                 creator=systemaccount_id,
                                 description='Initial requested lifetime for project',
                                 start=endtime)
        ou.write_db()
        starttime = input['p_start']
        # TBD: should we always set the start date, even if it is passed, for
        # the administrators to see when the project started?
        if starttime > DateTime.now():
            ou.add_entity_quarantine(type=co.quarantine_project_start,
                                     creator=systemaccount_id,
                                     description='Initial requested starttime for project',
                                     start=DateTime.now(), end=starttime)
            ou.write_db()

        ou.populate_trait(co.trait_project_institution, target_id=ou.entity_id,
                          strval=input['institution'])
        ou.populate_trait(co.trait_project_rek, target_id=ou.entity_id,
                          strval=input['rek_approval'])
        ou.write_db()
        logger.debug("Setting up rest of project...")
        ou.setup_project(systemaccount_id)
        logger.debug("New project created successfully: %s", pid)
        return ou

    def _create_account(self, pe, pid, username):
        """Create a quarantined account for a given project."""
        ac = Factory.get('Account')(db)
        username = '%s-%s' % (pid, username)
        # Check if wanted username is already taken:
        if ac.search(name=username):
            raise Exception("Username already taken: %s" % username)
            # TODO: implement this when we have the person's name
            #for name in ac.suggest_unames(co.account_namespace, fname, lname,
            #                              maxlen=cereconf.USERNAME_MAX_LENGTH,
            #                              prefix='%s-' % pid):
            #   if not ac.search(name=name):
            #       username = name
            #       break
            #else:
            #   raise Exception("No available username for %s in %s" % (pe.entity_id, pid))

        logger.info("Creating project user for person %s: %s", pe.entity_id,
                    username)
        ac.create(name=username, owner_id=pe.entity_id,
                  creator_id=systemaccount_id)
        # Set affiliation:
        ac.set_account_type(ou.entity_id, co.affiliation_project)
        ac.write_db()
        # Set quarantine:
        ac.add_entity_quarantine(type=co.quarantine_not_approved,
                                 creator=systemaccount_id,
                                 description='User not yet approved by admin',
                                 start=DateTime.now())
        ac.write_db()
        # TODO: quarantine for start and end dates, or is the project's
        # quarantine enough for that?
        return ac

    def new_project(self, input):
        """Create a given project.

        TODO: A lot of this code should be moved into e.g. TSD's OU mixin, or
        somewhere else to be usable both by various scripts and bofhd.

        @type input: dict
        @param input: The survey answers about the requested project.

        """
        pid = input['p_id']
        logger.info('New project: %s', pid)
        ou = self._create_ou(input)

        # Update the requestee for the project:
        pe = self._get_person()
        self._update_person(pe, input)

        # Give the respondent an affiliation to the project.
        # If the respondent sets himself as the Project Owner (responsible), it
        # gets status as the owner. Otherwise we give him PA status:
        # TBD: do we need to differentiate between owner and PA?
        status = co.affiliation_status_project_admin
        if self.fnr == input['p_responsible']:
            status = co.affiliation_status_project_owner
        pe.populate_affiliation(source_system=co.system_nettskjema,
                                ou_id=ou.entity_id, status=status,
                                affiliation=co.affiliation_project)
        pe.write_db()

        # Check the responsible and give access to the project by an
        # affiliation:
        if self.fnr != input['p_responsible']:
            pe2 = self._get_person(input['p_responsible'])
            pe2.populate_affiliation(source_system=co.system_nettskjema,
                                     ou_id=ou.entity_id,
                                     affiliation=co.affiliation_project,
                                     status=co.affiliation_status_project_owner)
            # Note that no name or anything else is now set for this account.
            pe2.write_db()

        ac = self._create_account(pe, pid, input['pa_uiousername'])

        # Other members that should be added to the project:
        not_found_persons = set()
        for fnr in set(input['p_persons'].split()):
            try:
                fnr = fodselsnr.personnr_ok(fnr)
            except fodselsnr.InvalidFnrError:
                logger.debug("Ignoring invalid fnr: %s", fnr)
                continue
            ret = tuple(pe.list_external_ids(id_type=co.externalid_fodselsnr,
                                             external_id=fnr,
                                             entity_type=co.entity_person))
            if len(ret) > 1:
                raise Exception("Found more than one person fnr: %s" % fnr)
            elif len(ret) == 1:
                pe.clear()
                pe.find(ret[0]['entity_id'])
                logger.info("Adding person %s to the project", pe.entity_id)
                pe.populate_affiliation(source_system=co.system_nettskjema,
                                        ou_id=ou.entity_id,
                                        affiliation=co.affiliation_project,
                                        status=co.affiliation_status_project_member)
                pe.write_db()
                # TODO: create a project account for the person?
            else:
                not_found_persons.add(fnr)
        # TODO: Store the not found persons 
        if not_found_persons:
            logger.debug("Remaining non-existing persons: %d",
                         len(not_found_persons))
            ou.populate_trait(co.trait_project_persons_accepted,
                              target_id=ou.entity_id,
                              strval=' '.join(not_found_persons))
        ou.write_db()
        # TODO: How should we signal that a new project is waiting for approval?
        return True

    def project_access(self, input):
        """Setup a request for the respondent to join a project.

        This is a survey that should be filled out for when a person wants to
        join a certain project as a project member. We create a person object
        for the respondent, if it doesn't already exist. Next we create a
        project account that is quarantined, and have to get accepted by PA or
        administrators before it could start working on the project.

        Note that the given information could be filled out by anyone. The
        project account must therefore be approved by PA or administrators
        before the person could be used in Cerebrum. The only data we could
        trust is the FNR, which we must trust is authentic and from ID-porten,
        so we know who filled out the form.

        @type input: dict
        @param input: The survey answers.

        """
        logger.debug('Asking for project access')
        # Update the requestee for the project:
        pe = self._get_person()
        self._update_person(pe, input)

        # Find the project:
        pid = input['p_id']
        ou.clear()
        ou.find_by_tsd_projectname(pid)

        # Affiliate the person with the project:
        pe.populate_affiliation(source_system=co.system_nettskjema,
                                ou_id=ou.entity_id,
                                affiliation=co.affiliation_project,
                                status=co.affiliation_status_project_member)
        # TODO: add a 'pending' status for those not approved to a project?
        pe.write_db()
        logger.info("Person %s affiliated with project %s", pe.entity_id, pid)

        # Give the man a user:
        ac = self._create_account(pe, pid, input['uio_or_feide_username'])
        # TODO: a different quarantine to be accepted by PAs?
        # Add a quarantine, to let the PAs accept it:
        #ac.add_entity_quarantine(type=co.quarantine_not_approved,
        #                         creator=systemaccount_id,
        #                         description='User not yet approved by admin',
        #                         start=DateTime.now())
        #

        return True

    def approve_person(self, input):
        """Handle the approval of a person in Cerebrum by PA."""
        pass
        #TODO

if __name__=='__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hd',
                                   ['help', 'dryrun'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    global dryrun
    dryrun = False

    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
            dryrun = True
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    if not args:
        print "No input file given"
        usage(1)

    process_files(args, dryrun)

    if dryrun:
        db.rollback()
        logger.info("Dryrun, rolled back changes")
    else:
        db.commit()
        logger.info("Commited changes")
