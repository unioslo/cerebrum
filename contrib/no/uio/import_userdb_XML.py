#!/usr/bin/env python2.2
# $Id$

"""
Reads XML files with user and person data from file, and imports them
into cerebrum.  Contains some UREG specific parts, but attempt has
been made to isolate these so that this script also can be used with
other sources.
"""

import cerebrum_path

import pprint
import xml.sax
import sys
import getopt
import cereconf
from Cerebrum import Database
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum import Person
from Cerebrum import Errors
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.Utils import Factory

default_personfile = '/local2/home/runefro/usit/cerebrum/contrib/no/uio/users.xml'
default_groupfile = '/local2/home/runefro/usit/cerebrum/contrib/no/uio/filegroups.xml'
Cerebrum = Database.connect()
personObj = Person.Person(Cerebrum)
co = Factory.getConstants()(Cerebrum)
pp = pprint.PrettyPrinter(indent=4)

class PersonUserData(object):
    """This class is used to iterate over all users/persons in the ureg dump. """

    def __init__(self, filename):
        # Ugly memory-wasting, inflexible way:
        self.tp = PersonUserParser()
        xml.sax.parse(filename, self.tp)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about the next person in ureg."""
        try:
            return self.tp.personer.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

class PersonUserParser(xml.sax.ContentHandler):
    """Parser for the users.xml file.  Stores recognized data in an
    internal datastructure"""

    def __init__(self):
        self.personer = []
        self.elementstack = []

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        name = name.encode('iso8859-1')
        if name == "persons":
            pass
        elif name == "person":
            self.person = {'bdate': tmp['bdate']}
        elif self.elementstack[-1] == "user":
            if name in ("auth", "spread", "name"):
                self.user[name] = self.user.get(name, []) + [tmp]
            elif name in ("uio",):
                self.user[name] = tmp
            else:
                print "WARNING: unknown user element: %s" % name
        elif self.elementstack[-1] == "person":
            if name in ("contact", "name", "extid"):
                self.person[name] = self.person.get(name, []) + [tmp]
            elif name in ("uio",):
                self.person[name] = tmp
            elif name == "user":
                self.user = {}
                for k in tmp.keys():
                    self.user[k] = tmp[k]
            else:
                print "WARNING: unknown person element: %s" % name
        else:
            print "WARNING: unknown element: %s" % name
        self.elementstack.append(name)

    def endElement(self, name): 
        if name == "person":
            self.personer.append(self.person)
            pass
        elif name == "user":
            self.person['user'] = self.person.get('user', []) + [self.user]
        self.elementstack.pop()


class GroupData(object):
    """This class is used to iterate over all groups from ureg."""

    def __init__(self, filename):
        # Ugly memory-wasting, inflexible way:
        self.tp = FilegroupParser()
        xml.sax.parse(filename, self.tp)

    def __iter__(self):
        return self

    def next(self):
        """Returns a dict with data about the next group in ureg."""
        try:
            return self.tp.groups.pop(0)
        except IndexError:
            raise StopIteration, "End of file"

class FilegroupParser(xml.sax.ContentHandler):
    """Parser for the filegroups.xml file.  Stores recognized data in an
    internal datastructure"""

    def __init__(self):
        self.groups = []
        self.elementstack = []

    def startElement(self, name, attrs):
        tmp = {}
        for k in attrs.keys():
            tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
        name = name.encode('iso8859-1')
        if name == "groups":
            pass
        elif name == "group":
            self.group = {}
            for k in attrs.keys():
                self.group[k] = tmp[k]
        elif self.elementstack[-1] == "group":
            if name == "member":
                self.group[name] = self.group.get(name, []) + [tmp]
            else:
                print "WARNING: unknown group element: %s" % name
        else:
            print "WARNING: unknown element: %s" % name
        self.elementstack.append(name)

    def endElement(self, name): 
        if name == "group":
            self.groups.append(self.group)
        self.elementstack.pop()

def import_groups(groupfile, fill=0):
    account = Account.Account(Cerebrum)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)

    print """Processing groups.  Progress indicators means:
    . : a group with members has been read from XML file
    G : a group in the file did not exist (when -M is used)
    A : an account was added as member to a group
    n : the member being populated was missing"""
    for group in GroupData(groupfile):
        # pp.pprint(group)
        print ".",
        sys.stdout.flush()
        if int(group['gid']) < 1:
            continue
        groupObj = Group.Group(Cerebrum)
        pg = PosixGroup.PosixGroup(Cerebrum)
        if not fill:
            groupObj.populate(account, co.group_visibility_all,
                              group['name'], group['comment'])
            groupObj.write_db()
            pg.populate(parent=groupObj, gid=group['gid'])
            pg.write_db()
        else:
            try:
                pg.find_by_gid(group['gid'])
            except Errors.NotFoundError:
                print "G",
                continue
            for m in group.get('member', []):
                try:
                    account.find_by_name(m['uname'])
                    pg.add_member(account, co.group_memberop_union);
                    print "A",
                except Errors.NotFoundError:
                    print "n",
                    continue
    Cerebrum.commit()

def import_person_users(personfile):
    namestr2const = {'lname': co.name_last, 'fname': co.name_first}
    account = Account.Account(Cerebrum)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    acc_creator_id = account.entity_id
    
    for person in PersonUserData(personfile):
        # pp.pprint(person)

        personObj.clear()
        fnr = None
        for e in person['extid']:
            if e['type'] == 'fnr':
                if e['val'] <> '00000000000':
                    fnr = e['val']
        person_id = None
        if fnr is not None:
            try:
                print "Fnr: %s" % fnr,
                personObj.find_by_external_id(co.externalid_fodselsnr, fnr)
                person_id = personObj.person_id
                print " ********* OLD *************"
            except Errors.NotFoundError:
                print " ********* NEW *************"
                pass
        if person_id is None:
            # Personen fantes ikke, lag den
            try:
                bdate = [int(x) for x in person['bdate'].split('-')]
                bdate = Cerebrum.Date(*bdate)
            except:
                print "Warning, %s is an illegal date" % person['bdate']
                bdate = [1970, 1, 1]
                bdate = Cerebrum.Date(*bdate)
            personObj.populate(bdate,
                                co.gender_unknown)
            personObj.affect_names(co.system_ureg, *(namestr2const.values()))

            for k in person['name']:
                if namestr2const.has_key(k['type']):
                    personObj.populate_name(namestr2const[k['type']], k['val'])
            if fnr is not None:
                personObj.populate_external_id(co.system_ureg, co.externalid_fodselsnr, fnr)
            for c in person['contact']:
                if c['type'] == 'workphone':
                    personObj.populate_contact_info(co.contact_phone, c['val'],
                                                    contact_pref=1)
                elif c['type'] == 'privphone':
                    personObj.populate_contact_info(co.contact_phone, c['val'],
                                                    contact_pref=2)
                elif c['type'] == 'workfax':
                    personObj.populate_contact_info(co.contact_phone, c['val'])
                elif c['type'] == 'privaddress':
                    personObj.affect_addresses(co.system_ureg, co.address_post)
                    a = c['val'].split('$', 2)
                    personObj.populate_address(co.address_post,
                                               addr="\n".join(a))
            if person.has_key('uio'):
                if person['uio'].has_key('psko'):
                    # Typer v/uio: A B M S X a b s
                    aff = co.affiliation_student   # TODO: define all const
                    affstat = co.affiliation_status_student_valid
                    if person['uio']['ptype'] in ('A', 'a'):
                        aff = co.affiliation_employee
                        affstat = co.affiliation_status_employee_valid

                    try:
                        s = person['uio']['psko']
                        fak, inst, gruppe = s[0:2], s[2:4], s[4:6]
                        ou.find_stedkode(int(fak), int(inst), int(gruppe))
                        personObj.affect_affiliations(co.system_ureg,
                                                      aff)
                        personObj.populate_affiliation(ou.ou_id, aff,
                                                       affstat)
                    except:
                        print "Error setting stedkode: %s" % s

            personObj.write_db()
            person_id = personObj.person_id

        # Bygg brukeren

        # TODO:
        # - ta hensyn til spread
        # - sette rett create_date og creator_id

        for u in person['user']:
            expire_date = None  # TODO
            gecos = None        # TODO
            shell = co.posix_shell_bash # TODO: shell2shellconst[u['shell']]
            
            group=PosixGroup.PosixGroup(Cerebrum)
            try:
                group.find_by_gid(u['dfg'])
            except Errors.NotFoundError:
                print "WARNING: could not find dfg=%s for %s" % (u['dfg'], u['uname']) 
                continue
            account.clear()
            account.populate(u['uname'],
                             co.entity_person,  # Owner type TODO
                             person_id,
                             None, 
                             acc_creator_id, expire_date)
            account.affect_auth_types(co.auth_type_md5, co.auth_type_crypt)
            for au in u.get('auth', []):
                if au['type'] == 'plaintext':   # TODO: Should be called last?
                    account.set_password(au['val'])
                elif au['type'] == 'md5':
                    account.populate_authentication_type(co.auth_type_md5,
                                                            au['val'])
                elif au['type'] == 'crypt':
                    account.populate_authentication_type(co.auth_type_crypt,
                                                            au['val'])
            account.write_db()

            posix_user = PosixUser.PosixUser(Cerebrum)
            posix_user.clear()

            posix_user.populate(u['uid'],
                                group.entity_id,
                                gecos,
                                u['home'],
                                shell,
                                parent=account)

            posix_user.write_db(account)
    Cerebrum.commit()

def usage():
    print """import_userdb_XML.py [-p file | -g file] {-P | -G | -M}

-G : generate the groups
-P : generate persons and accounts
-M : populate the groups with members

Normaly first run with -G, then -P and finally with -M.  The program
is not designed to be ran multiple times.

This script is designed to be ran on a database that contains no users
or groups.  ou and person tables should preferable be populated.  When
importing accounts, the persons will be created iff they cannot be
located by their extid (currently only fnr is supported).
    """

if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "p:g:PGM",
                                   ["pfile=", "gfile=", "persons", "groups",
                                    "groupmembers"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    pfile = default_personfile
    gfile = default_groupfile
    for o, a in opts:
        if o in ('-p', '--pfile'):
            pfile = a
        elif o in ('-g', '--gfile'):
            gfile = a
        elif o in ('-P', '--persons'):
            import_person_users(pfile)
        elif o in ('-G', '--groups'):
            import_groups(gfile, 0)
        elif o in ('-M', '--groupmembers'):
            import_groups(gfile, 1)
    if(len(opts) == 0):
        usage()
