# -*- coding: iso-8859-1 -*-
# Copyright 2004 University of Oslo, Norway
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

import re, time
import mx

import cereconf
from Cerebrum                   import Entity
from Cerebrum.Utils             import Factory, auto_super
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules.LDIFutils import *

postal_escape_re = re.compile(r'[$\\]')

class OrgLDIF(object):
    """Factory-class to generate the organization and person trees for LDAP.

    A number of cereconf.LDAP* variables control the output.
    Subclasses can also override its methods as necessary.
    Generally, each entry is built in an 'entry' dict and finally written.

    By default, entires are generated with the eduPerson/eduOrg schemas
    from EDUCAUSE: <http://www.educause.edu/eduperson/>.

    The organization gets object classes: 'top', 'organization', 'eduOrg'.
    Organizational units:  'top', 'organizationalUnit'.
    Persons:               'inetOrgPerson', 'eduPerson' and superclasses.
    Aliases, if generated: 'top', 'alias', 'extensibleObject'.
    In addition, 'labeledURIObject' is added when necessary.

    Interface:
    org_ldif = Factory.get('OrgLDIF')(Factory.get('Database')(),
                                      Factory.get_logger(...))
    org_ldif.generate_org_object(file object)
    org_ldif.generate_ou(file object)
    org_ldif.generate_person(person file obj, alias file, use_mail_module)."""

    __metaclass__ = auto_super

    def __init__(self, db, logger):
        cereconf.make_timer = self.make_timer
        self.db            = db
        self.logger        = logger
        self.const         = Factory.get('Constants')(db)
        self.ou            = Factory.get('OU')(db)
        self.org_dn        = ldapconf('ORG', 'dn', None)
        self.ou_dn         = ldapconf('OU', 'dn', None)
        self.person_dn     = ldapconf('PERSON', 'dn', None)
        self.dummy_ou_dn   = None  # Set if generate_dummy_ou() made a dummy OU
        self.aliases       = bool(cereconf.LDAP_PERSON['aliases'])
        self.ou2DN         = {None: None}  # {ou_id:      DN or None(root)}
        self.used_DNs      = {}            # {used DN:    True}
        self.person_groups = {}            # {group name: {member ID: True}}
        self.system_lookup_order = [int(getattr(self.const, s))
                                    for s in cereconf.SYSTEM_LOOKUP_ORDER]
        self.attr2syntax   = {
            'telephoneNumber': (None, verify_printableString, normalize_phone),
            'facsimileTelephoneNumber': (None, verify_printableString,
                                         normalize_phone),
            'ou':              (iso2utf, None, normalize_string),
            'labeledURI':      (iso2utf, None, normalize_caseExactString),
            'mail':            (None, verify_IA5String, normalize_IA5String)}

    def init_org_object_dump(self):
        # Set variables for the organization object dump.
        self.init_ou_root()
        if self.root_ou_id is not None:
            self.init_attr2id2contacts()

    def init_ou_dump(self):
        # Set variables for the org.unit dump.
        if not hasattr(self, 'root_ou_id'):       self.init_ou_root()
        if not hasattr(self, 'ou_tree'):          self.init_ou_structure()
        if not hasattr(self, 'attr2id2contacts'): self.init_attr2id2contacts()

    def uninit_ou_dump(self):
        del self.ou, self.ou_tree

    def init_ou_structure(self):
        # Set self.ou_tree = dict {parent ou_id: [child ou_id, ...]}
        # where the root OUs have parent id None.
        timer = self.make_timer("Fetching OU tree...")
        self.ou.clear()
        ou_list = self.ou.get_structure_mappings(
            self.const.OUPerspective(cereconf.LDAP_OU['perspective']))
        self.logger.debug("OU-list length: %d", len(ou_list))
        self.ou_tree = {None: []} # {parent ou_id or None: [child ou_id...]}
        for ou_id, parent_id in ou_list:
            if parent_id is not None:
                parent_id = int(parent_id)
            self.ou_tree.setdefault(parent_id, []).append(int(ou_id))
        timer("...OU tree done.")

    def init_ou_root(self):
        # Set self.root_ou_id = ou_id representing the organization, or None.
        if cereconf.LDAP_ORG['ou_id'] is None:
            self.root_ou_id = None
        elif cereconf.LDAP_ORG['ou_id'] is not 'base':
            self.root_ou_id = int(cereconf.LDAP_ORG['ou_id'])
        else:
            self.init_ou_structure()
            if len(self.ou_tree[None]) == 1:
                self.root_ou_id = self.ou_tree[None][0]
            else:
                print "The OU tree has %d roots:" % len(self.ou_tree[None])
                for ou_id in self.ou_tree[None]:
                    self.ou.clear()
                    self.ou.find(ou_id)
                    print "Org.unit: %-30s   ou_id=%s" % (self.ou.display_name,
                                                          self.ou.ou_id)
                print """\
Set cereconf.LDAP_ORG['ou_id'] = the organization's root ou_id or None."""
                raise ValueError("No root-OU found.")

    def init_attr2id2contacts(self):
        # Set contact information variables:
        # self.attr2id2contacts = {attr.type: {entity id: [attr.value, ...]}}
        # self.id2labeledURI    = self.attr2id2contacts['labeledURI'].
        s = getattr(self.const, cereconf.LDAP['contact_source_system'])
        c = [(a, self.get_contacts(contact_type  = t,
                                   source_system = s,
                                   convert       = self.attr2syntax[a][0],
                                   verify        = self.attr2syntax[a][1],
                                   normalize     = self.attr2syntax[a][2]))
             for a,s,t in (('telephoneNumber', s, self.const.contact_phone),
                           ('facsimileTelephoneNumber',
                            s, self.const.contact_fax),
                           ('labeledURI', None, self.const.contact_url))]
        self.id2labeledURI    = c[-1][1]
        self.attr2id2contacts = [v for v in c if v[1]]

    def generate_org_object(self, outfile):
        """Output the organization object if cereconf.LDAP_ORG['dn'] is set."""
        if not self.org_dn:
            return
        self.init_org_object_dump()
        entry = {}
        self.ou.clear()
        if self.root_ou_id is not None:
            self.ou2DN[self.root_ou_id] = None
            self.ou.find(self.root_ou_id)
            self.fill_ou_entry_contacts(entry)
        entry.update(ldapconf('ORG', 'attrs', {}))
        oc = ['top', 'organization', 'eduOrg']
        oc.extend(entry.get('objectClass', ()))
        entry['objectClass'] = (['top', 'organization', 'eduOrg']
                                + list(entry.get('objectClass', ())))
        self.update_org_object_entry(entry)
        entry['objectClass'] = self.attr_unique(entry['objectClass'],str.lower)
        outfile.write(entry_string(self.org_dn, entry))

    def update_org_object_entry(self, entry):
        # Override this to fill in the ORG object further before output.
        pass

    def generate_ou(self, outfile):
        """Output the org. unit (OU) tree if cereconf.LDAP_OU['dn'] is set."""
        if not self.ou_dn:
            return
        self.init_ou_dump()
        timer = self.make_timer("Processing OUs...")
        if self.ou_dn != self.org_dn:
            outfile.write(container_entry_string('OU'))
        self.generate_dummy_ou(outfile)
        self.traverse_ou_children(outfile, self.root_ou_id, None)
        if self.root_ou_id is not None:
            self.traverse_ou_children(outfile, None, None)
        loops = [i for i in self.ou_tree.iteritems() if i[0] not in self.ou2DN]
        if loops:
            self.logger.warn(
                "Loops in org.unit tree; ignored {parent:[children]} = %s",
                dict(loops))
        timer("...OUs done.")
        self.uninit_ou_dump()

    def generate_dummy_ou(self, outfile):
        # Output the cereconf.LDAP_OU['dummy_name'] entry, if given.
        # If so, set self.dummy_ou_dn.
        name = ldapconf('OU', 'dummy_name', None)
        if name:
            self.dummy_ou_dn = "ou=%s,%s" % (name, self.ou_dn)
            entry = {'objectClass': ['top', 'organizationalUnit']}
            self.update_dummy_ou_entry(entry)
            entry.update(ldapconf('OU', 'dummy_attrs', {}))
            outfile.write(entry_string(self.dummy_ou_dn, entry))

    def update_dummy_ou_entry(self, entry):
        # Override this to fill in the dummy object further before output.
        pass

    def traverse_ou_children(self, outfile, parent_id, parent_dn):
        # Recursively output parent_id's children according to self.ou_tree.
        # Fill in self.ou2DN[].
        for ou_id in self.ou_tree.get(parent_id, ()):
            if ou_id not in self.ou2DN:
                dn = self.write_ou(outfile, ou_id, parent_dn)
                self.ou2DN[ou_id] = dn
                self.traverse_ou_children(outfile, ou_id, dn)

    def write_ou(self, outfile, ou_id, parent_dn):
        # Output the org.unit with this ou_id if appropriate.
        # Return its DN, or its parent DN if the org.unit was not output.
        # Note that parent_dn = None if the parent is self.ou_dn, and the
        # returned parent DN must be None if it is to represent that DN.
        dn, entry = self.make_ou_entry(ou_id, parent_dn)
        if entry:
            norm_dn = normalize_string(dn)
            if norm_dn in self.used_DNs:
                self.logger.warn("Omitting ou_id %d: duplicate DN '%s'",
                                 ou_id, dn)
                dn = parent_dn
            else:
                self.used_DNs[norm_dn] = True
                outfile.write(entry_string(dn, entry, False))
        return dn

    def make_ou_entry(self, ou_id, parent_dn):
        # Return (the OU's DN,        entry) for this OU,
        #     or (the OU's parent DN, None)  to omit the OU entry.
        # Note that parent_dn = None if the parent is self.ou_dn, and the
        # returned parent DN must be None if it is to represent that DN.
        self.ou.clear()
        self.ou.find(ou_id)
        entry = {
            'objectClass': ['top', 'organizationalUnit'],
            'ou': filter(None, [iso2utf((n or '').strip())
                                for n in (self.ou.acronym, self.ou.short_name,
                                          self.ou.display_name)])}
        dn = self.make_ou_dn(entry, parent_dn or self.ou_dn)
        if not dn:
            return parent_dn, None
        entry['ou'] = self.attr_unique(entry['ou'], normalize_string)
        self.fill_ou_entry_contacts(entry)
        self.update_ou_entry(entry)
        return dn, entry

    def update_ou_entry(entry):
        # Override this to fill in an OU entry further before output.
        pass
    update_ou_entry = staticmethod(update_ou_entry)

    def make_ou_dn(entry, parent_dn):
        # Return the DN of this OU, or None if the OU should not be output.
        # (parent_dn is not None in this function.)
        #
        # The entry currently contains 'ou' and 'objectClass', where 'ou'
        # contains (if found) acronym, short name, display name and sort-name.
        #
        # If an attribute value is used in the RDN which does not exist
        # in the entry, insert it in the entry.
        # If an attribute value can match LDIFutils.dn_escape_re, escape
        # it in the DN: dn_escape_re.sub(hex_escape_match, <value>).
        return "ou=%s,%s" % (
            dn_escape_re.sub(hex_escape_match,entry['ou'][0]), parent_dn)
    make_ou_dn = staticmethod(make_ou_dn)

    def fill_ou_entry_contacts(self, entry):
        # Fill in contact info for the entry with the current ou_id.
        ou_id = self.ou.ou_id
        for attr, id2contact in self.attr2id2contacts:
            contact = id2contact.get(ou_id)
            if contact:
                entry[attr] = contact
        if entry.get('labeledURI'):
            oc = entry['objectClass']
            oc.append('labeledURIObject')
            entry['objectClass'] = self.attr_unique(oc, str.lower)
        post_string, street_string = self.make_entity_addresses(
            self.ou, self.system_lookup_order)
        if post_string:
            entry['postalAddress'] = (post_string,)
        if street_string:
            entry['street'] = (street_string,)

    def init_person_dump(self, use_mail_module):
        # Set variables for the person dump.
        self.person = Factory.get('Person')(self.db)
        if self.person_dn != (self.ou_dn or self.org_dn):
            self.person_parent_dn = self.person_dn
        else:
            self.person_parent_dn = None
        if not hasattr(self, 'attr2id2contacts'): self.init_attr2id2contacts()
        self.init_person_selections()
        self.init_person_affiliations()
        self.init_person_names()
        self.init_person_titles()
        self.init_account_info()
        self.init_account_mail(use_mail_module)
        self.init_person_addresses()
        self.init_person_aliases()
        self.visible_person_attrs = ldapconf('PERSON', 'attrs_visible', {})

    def init_person_selections(self):
        # Set self.person_spread and self.*_selector, which select
        # which persons to print, affiliations to consider, and
        # eduPersonAffiliation values for the relevant affiliations.
        self.person_spread = map_spreads(cereconf.LDAP_PERSON.get('spread'))
        self.person_aff_selector     = self.internal_selector(
            bool, cereconf.LDAP_PERSON['affiliation_selector'])
        self.visible_person_selector = self.internal_selector(
            bool, cereconf.LDAP_PERSON['visible_selector'])
        self.contact_selector        = self.internal_selector(
            bool, cereconf.LDAP_PERSON['contact_selector'])
        self.eduPersonAff_selector   = self.internal_selector(
            list, ldapconf('PERSON','eduPersonAffiliation_selector',utf8=list))

    def init_person_affiliations(self):
        # Set self.affiliations = dict {person_id: [(aff, status, ou_id), ...]}
        timer = self.make_timer("Fetching personal affiliations...")
        self.affiliations = affiliations = {}
        source = cereconf.LDAP_PERSON['affiliation_source_system']
        if source is not None:
            if isinstance(source, (list, tuple)):
                source = [getattr(self.const, s) for s in source]
            else:
                source = getattr(self.const, source)
        for row in self.person.list_affiliations(source_system = source):
            person_id   = int(row['person_id'])
            status      = row['status']
            if status is not None:
                status  = int(status)
            affiliation = (int(row['affiliation']), status, int(row['ou_id']))
            if self.select_bool(self.person_aff_selector,
                                person_id, (affiliation,)):
                if affiliations.has_key(person_id):
                    affiliations[person_id].append(affiliation)
                else:
                    affiliations[person_id] = [affiliation]
        timer("...affiliations done.")

    def init_person_names(self):
        # Set self.person_names = dict {person_id: {name_variant: name}}
        timer = self.make_timer("Fetching personal names...")
        self.person_names = person_names = {}
        for row in self.person.list_persons_name(
                source_system = self.const.system_cached,
                name_type     = [self.const.name_full,
                                 self.const.name_first,
                                 self.const.name_last]):
            person_id = int(row['person_id'])
            if not person_names.has_key(person_id):
                person_names[person_id] = {}
            person_names[person_id][int(row['name_variant'])]=row['name']
        timer("...personal names done.")

    def init_person_titles(self):
        # Set self.person_title = dict {person_id: title}
        timer = self.make_timer("Fetching personal titles...")
        self.person_title = {}
        fill = {
            int(self.const.name_personal_title): self.person_title.__setitem__,
            int(self.const.name_work_title):     self.person_title.setdefault }
        for row in self.person.list_persons_name(name_type = fill.keys()):
            fill[int(row['name_variant'])](int(row['person_id']), row['name'])
        timer("...personal titles done.")

    def init_account_info(self):
        # Set self.acc_name        = dict {account_id: user name}.
        # Set self.acc_passwd      = dict {account_id: password hash}.
        # Set self.acc_quarantines = dict {account_id: [quarantine list]}.
        timer = self.make_timer("Fetching account information...")
        timer2 = self.make_timer()
        self.account = Factory.get('Account')(self.db)
        self.acc_name = acc_name = {}
        self.acc_passwd = {}
        self.acc_quarantines = acc_quarantines = {}
        fill_passwd = {
            int(self.const.auth_type_md5_crypt):  self.acc_passwd.__setitem__,
            int(self.const.auth_type_crypt3_des): self.acc_passwd.setdefault }
        for row in self.account.list_account_authentication(
                auth_type = fill_passwd.keys()):
            account_id           = int(row['account_id'])
            acc_name[account_id] = row['entity_name']
            method               = row['method']
            if method:
                fill_passwd[int(method)](account_id, row['auth_data'])
        timer2("...account quarantines...")
        now = mx.DateTime.now()
        for row in self.account.list_entity_quarantines(
                entity_types = self.const.entity_account):
            if (row['start_date'] <= now
                and (row['end_date'] is None or row['end_date'] >= now)
                and (row['disable_until'] is None
                     or row['disable_until'] < now)):
                # The quarantine in this row is currently active.
                acc_quarantines.setdefault(int(row['entity_id']), []).append(
                    int(row['quarantine_type']))
        timer("...account information done.")

    def init_account_mail(self, use_mail_module):
        # Set self.account_mail = None if not use_mail_module, otherwise
        #                         function: account_id -> ('address' or None).
        if use_mail_module:
            timer = self.make_timer("Fetching account e-mail addresses...")
            # We don't want to import this if mod_email isn't present.
            from Cerebrum.modules.Email import EmailDomain, EmailTarget
            etarget = EmailTarget(self.db)
            rewrite = EmailDomain(self.db).rewrite_special_domains
            mail    = {}
            for row in etarget.list_email_target_primary_addresses(
                    target_type = self.const.email_target_account):
                # TBD: Should we check for multiple values for primary
                #      addresses?
                try:
                    mail[int(row['entity_id'])] = "@".join(
                        (row['local_part'], rewrite(row['domain'])))
                except TypeError:
                    self.logger.warn("email_target %d got no user.",
                                     int(row['target_id']))
            self.account_mail = mail.get
            timer("...account e-mail addresses done.")
        else:
            self.account_mail = None
            self.logger.debug("Mail-module skipped.")

    def init_person_addresses(self):
        # Set self.addr_info = dict {person_id: {address_type: (addr. data)}}.
        timer = self.make_timer("Fetching personal addresses...")
        self.addr_info = addr_info = {}
        for row in self.person.list_entity_addresses(
                entity_type  = self.const.entity_person,
                source_system= getattr(self.const,
                                       cereconf.LDAP['contact_source_system']),
                address_type = [self.const.address_street,
                                self.const.address_post]):
            entity_id = int(row['entity_id'])
            if not addr_info.has_key(entity_id):
                addr_info[entity_id] = {}
            addr_info[entity_id][int(row['address_type'])] = (
                row['address_text'], row['p_o_box'], row['postal_number'],
                row['city'], row['country'])
        timer("...personal addresses done.")

    def init_person_aliases(self):
        # Set variables for aliases: self.alias_default_parent_dn.
        if self.aliases:
            if self.ou_dn in (None, self.person_dn):
                raise ValueError("""\
cereconf.LDAP_PERSON['aliases'] requires LDAP_OU['dn'] to be different
from None and LDAP_PERSON['dn'].""")
            self.alias_default_parent_dn = self.dummy_ou_dn or self.ou_dn

    def generate_person(self, outfile, alias_outfile, use_mail_module):
        """Output person tree and aliases if cereconf.LDAP_PERSON['dn'] is set.

        Aliases are only output if cereconf.LDAP_PERSON['aliases'] is true.

        If use_mail_module is set, persons' e-mail addresses are set to
        their primary users' e-mail addresses.  Otherwise, the addresses
        are taken from contact info registered for the individual persons."""
        if not self.person_dn:
            return
        self.init_person_dump(use_mail_module)
        if self.person_parent_dn not in (None, self.org_dn):
            outfile.write(container_entry_string('PERSON'))
        timer       = self.make_timer("Processing persons...")
        round_timer = self.make_timer()
        round       = 0
        for row in self.list_persons():
            if round % 10000 == 0:
                round_timer("...rounded %d rows..." % round)
            round += 1
            dn, entry, alias_info = self.make_person_entry(row)
            if dn:
                if dn in self.used_DNs:
                    self.logger.warn("Omitting person_id %d: duplicate DN '%s'"
                                     % (row['person_id'], dn))
                else:
                    self.used_DNs[dn] = True
                    outfile.write(entry_string(dn, entry, False))
                    if self.aliases and alias_info:
                        self.write_person_alias(alias_outfile,
                                                dn, entry, alias_info)
        timer("...persons done.")

    def list_persons(self):
        # Return a list or iterator of persons to consider for output.
        return self.account.list_accounts_by_type(
            primary_only  = True,
            person_spread = self.person_spread)

    def make_person_entry(self, row):
        # Return (dn, person entry, alias_info) for a person to output,
        # or (None, anything, anything) if the person should not be output.
        # bool(alias_info) == False means no alias will be output.
        # Receives a row from list_persons() as a parameter.
        # The row must have keys 'person_id', 'account_id',
        # and if person_dn_primaryOU() is not overridden: 'ou_id'.
        person_id  = int(row['person_id'])
        account_id = int(row['account_id'])

        p_affiliations = self.affiliations.get(person_id)
        if not p_affiliations:
            return None, None, None

        names = self.person_names.get(person_id)
        if not names:
            self.logger.warn("Person %s got no names. Skipping.", person_id)
            return None, None, None
        name      = iso2utf(names.get(int(self.const.name_full),  '').strip())
        givenname = iso2utf(names.get(int(self.const.name_first), '').strip())
        lastname  = iso2utf(names.get(int(self.const.name_last),  '').strip())
        if not (lastname and givenname):
            givenname, lastname = self.split_name(name, givenname, lastname)
            if not lastname:
                self.logger.warn("Person %s got no lastname. Skipping.",
                                 person_id)
                return None, None, None
        if not name:
            name = " ".join(filter(None, (givenname, lastname)))

        entry = {
            'objectClass': ['top', 'person', 'organizationalPerson',
                            'inetOrgPerson', 'eduPerson'],
            'cn': (name,),
            'sn': (lastname,)}
        if givenname:
            entry['givenName'] = (givenname,)
        try:
            entry['uid'] = (self.acc_name[account_id],)
        except KeyError:
            pass

        passwd = self.acc_passwd.get(account_id)
        qt = self.acc_quarantines.get(account_id)
        if qt:
            qh = QuarantineHandler(self.db, qt)
            if qh.should_skip():
                return None, None, None
            if qh.is_locked():
                passwd = 0
        if passwd:
            entry['userPassword'] = ("{crypt}" + passwd,)
        elif passwd != 0 and entry.get('uid'):
            self.logger.debug("User %s got no password-hash.", entry['uid'][0])

        dn, primary_ou_dn = self.person_dn_primaryOU(entry, row, person_id)
        if not dn:
            return None, None, None

        if self.org_dn:
            entry['eduPersonOrgDN'] = (self.org_dn,)
        if primary_ou_dn:
            entry['eduPersonPrimaryOrgUnitDN'] = (primary_ou_dn,)
        edu_OUs = [primary_ou_dn] + [self.ou2DN.get(aff[2])
                                     for aff in p_affiliations]
        entry['eduPersonOrgUnitDN']   = self.attr_unique(filter(None, edu_OUs))
        entry['eduPersonAffiliation'] = self.attr_unique(self.select_list(
            self.eduPersonAff_selector, person_id, p_affiliations))

        if self.select_bool(self.contact_selector, person_id, p_affiliations):
            # title:
            title = self.person_title.get(person_id)
            if title:
                entry['title'] = (iso2utf(title),)
            # phone & fax:
            for attr, contact in self.attr2id2contacts:
                contact = contact.get(person_id)
                if contact:
                    entry[attr] = contact
            # addresses:
            addrs = self.addr_info.get(person_id)
            post  = addrs and addrs.get(int(self.const.address_post))
            if post:
                a_txt, p_o_box, p_num, city, country = post
                post = self.make_address("$", p_o_box,a_txt,p_num,city,country)
                if post:
                    entry['postalAddress'] = (post,)
            street = addrs and addrs.get(int(self.const.address_street))
            if street:
                a_txt, p_o_box, p_num, city, country = street
                street = self.make_address(", ", None,a_txt,p_num,city,country)
                if street:
                    entry['street'] = (street,)
        else:
            URIs = self.id2labeledURI.get(person_id)
            if URIs:
                entry['labeledURI'] = self.attr_unique(
                    map(iso2utf, URIs), normalize_caseExactString)

        if self.account_mail:
            mail = self.account_mail(int(account_id))
            if mail:
                entry['mail'] = (mail,)
        else:
            mail = self.get_contacts(
                entity_id    = person_id,
                contact_type = self.const.contact_email,
                verify       = verify_IA5String,
                normalize    = normalize_IA5String)
            if mail:
                entry['mail'] = mail

        alias_info = ()
        if self.select_bool(self.visible_person_selector,
                            person_id, p_affiliations):
            entry.update(self.visible_person_attrs)
            alias_info = (primary_ou_dn,)

        self.update_person_entry(entry, row)
        return dn, entry, alias_info

    def person_dn_primaryOU(self, entry, row, person_id):
        # Return (the person entry's DN,
        #         the DN of the person's primary org.unit or None),
        #     or (None, anything) to omit the person entry.
        #
        # The entry currently contains 'cn', 'sn', 'objectClass',
        # and, if found, 'uid', 'givenName' and 'userPassword'.
        # The 'row' parameter is the row returned from list_persons().
        #
        # If an attribute value is used in the RDN which does not exist
        # in the entry, insert it in the entry.
        # If an attribute value can match LDIFutils.dn_escape_re, escape
        # it in the DN: dn_escape_re.sub(hex_escape_match, <value>).
        try:
            rdn = "uid=" + entry['uid'][0]
        except KeyError:
            self.logger.warn("Person %d got no account. Skipping.", person_id)
            return None, None
        # If the dummy DN is set, make it the default primary org.unit DN so
        # that if a person has an alias there, his eduPersonPrimaryOrgUnitDN
        # will refer back to his parent DN just like with other aliases.
        primary_ou_dn = self.ou2DN.get(int(row['ou_id'])) or self.dummy_ou_dn
        dn = ",".join((rdn, (self.person_parent_dn
                             or primary_ou_dn
                             or self.person_dn)))
        return dn, primary_ou_dn

    def update_person_entry(entry, row):
        # Override this to fill in a person entry further before output.
        #
        # If there is no password, store a useless one instead of no password
        # so that a text filter can easily find and replace the password.
        entry.setdefault('userPassword', ("{crypt}*Invalid",))
    update_person_entry = staticmethod(update_person_entry)

    def write_person_alias(self, outfile, dn, entry, alias_info):
        # Output an alias returned from make_person_entry().
        outfile.write(entry_string(
            ",".join((dn.split(',', 1)[0],
                      (alias_info[0] or self.alias_default_parent_dn))),
            {'objectClass':       ('top', 'alias', 'extensibleObject'),
             'aliasedObjectName': (dn,),
             'cn':                entry['cn'],
             'sn':                entry['sn']}))

    def make_address(sep, p_o_box, address_text, postal_number, city, country):
        # Return a postal addres or street attribute value made from the input.
        # 'sep' should be '$' for postal addresses; usually ', ' for streets.
        if p_o_box:
            p_o_box = "Pb. %s" % p_o_box
        address_text = (address_text or "").strip()
        post_nr_city = None
        if city or (postal_number and country):
            post_nr_city = " ".join(filter(None, (postal_number,
                                                  (city or "").strip())))
        val = "\n".join(filter(None, (p_o_box, address_text,
                                      post_nr_city, country)))
        if sep == '$':
            val = postal_escape_re.sub(hex_escape_match, val)
        return iso2utf(val.replace("\n", sep))
    make_address = staticmethod(make_address)

    def make_entity_addresses(self, entity, lookup_order = (None,)):
        # Return [postal address, street address] for the given entity.
        result = []
        for addr_type,box,separator in ((self.const.address_post,  True,"$"),
                                        (self.const.address_street,None,", ")):
            value = None
            for source in lookup_order:
                addr = entity.get_entity_address(source, addr_type)
                if addr:
                    value = self.make_address(separator,
                                              box and addr[0]['p_o_box'],
                                              addr[0]['address_text'],
                                              addr[0]['postal_number'],
                                              addr[0]['city'],
                                              addr[0]['country'])
                    if value:
                        break
            result.append(value)
        return result

    def get_contacts(self, entity_id=None,
                     contact_type=None, source_system=None,
                     convert=None, verify=None, normalize=None):
        # Return a list of contact values for the specified parameters,
        # or if entity_id is None, a dict {entity_id: [contact values]}.
        entity = Entity.EntityContactInfo(self.db)
        cont_tab = {}
        if not convert:
            convert = str
        for row in entity.list_contact_info(entity_id     = entity_id,
                                            source_system = source_system,
                                            contact_type  = contact_type):
            c_list = [convert(str(row['contact_value']))]
            if '$' in c_list[0]:
                c_list = c_list[0].split('$')
            elif normalize == normalize_phone and '/' in c_list[0]:
                c_list = c_list[0].split('/')
            key = int(row['entity_id'])
            if cont_tab.has_key(key):
                cont_tab[key].extend(c_list)
            else:
                cont_tab[key] = c_list
        for key, c_list in cont_tab.iteritems():
            cont_tab[key] = self.attr_unique(
                filter(verify, [c for c in c_list if c not in ('', '0')]),
                normalize = normalize)
        if entity_id is None:
            return cont_tab
        else:
            return (cont_tab.values() or ((),))[0]

    def internal_selector(self, selector_type, selector):
        # Translate a selector (as described in default_config.py) to
        # a format which can be passed to select_bool() or select_list().
        #
        # This is either an internal simple selector (below), or a dict:
        # {(aff, status): simple selector,  # tried first
        #  aff:           simple selector,  # tried if (aff, status) is not set
        #  None:          simple selector } # default
        if type(selector) is not dict:
            return self.internal_simple_selector(selector_type, selector)
        mapping = {}
        for affiliations, aff_info in selector.iteritems():
            if type(affiliations) is not tuple: affiliations = (affiliations,)
            if type(aff_info)     is not dict:  aff_info = {(True,): aff_info}
            status_ssels = []
            for statuses, ssel in aff_info.iteritems():
                if type(statuses) is not tuple: statuses = (statuses,)
                ssel = self.internal_simple_selector(selector_type, ssel)
                status_ssels.extend([(status, ssel) for status in statuses])
            for affiliation in affiliations:
                if affiliation == True:  # wildcard
                    aff_id = None
                else:
                    aff_id = self.const.PersonAffiliation(affiliation)
                for status, ssel in status_ssels:
                    if status == True:   # wildcard
                        key = int(aff_id)
                    elif affiliation == True:
                        raise ValueError("Selector[True][not True: %s] illegal"
                                         % repr(status))
                    else:
                        status_id = self.const.PersonAffStatus(aff_id, status)
                        if status_id is not None:
                            status_id = int(status_id)
                        key = (int(aff_id), status_id)
                    if mapping.has_key(key):
                        raise ValueError("Duplicate selector[%s][%s]" % tuple(
                            [val == True and "True" or repr(val)
                             for val in (affiliation, status)]))
                    mapping[key] = ssel
        return mapping

    def init_person_group(self, name):
        # Return a dict {person_id: True, ...} for the named group.
        # Only supports 'union' groups.
        # Known groups are cached in self.person_groups: a dict {name: group}.
        result = self.person_groups.get(name)
        if result is None:
            result = self.person_groups[name] = {}
            group  = Factory.get('Group')(self.db)
            group.find_by_name(name)
            for e in group.list_members(
                    member_type = self.const.entity_person)[0]:
                result[int(e[1])] = True
        return result

    def internal_simple_selector(self, selector_type, ssel):
        # Return a simple selector for use by select_bool() or select_list().
        # Note: type(return value) != dict; bool(return value) == True.
        if selector_type is bool:
            # (value[False], value[True], finder function returning True/False)
            negate = False
            while type(ssel) is tuple and ssel[0] == 'not' and len(ssel) == 2:
                negate, ssel = not negate, ssel[1]
            if type(ssel) is tuple and ssel[0] == 'group' and len(ssel) == 2:
                return (negate, not negate,
                        self.init_person_group(ssel[1]).has_key)
            if type(ssel) is type(True):
                if negate:
                    ssel = not ssel
                return (ssel, ssel, bool)
        elif selector_type is list:
            # (ssel,)
            if type(ssel) is list:
                return (ssel,)
        raise ValueError("Bad simple selector: " + repr(ssel))

    def select_list(selector, person_id, p_affiliations):
        # Return a list of values selected for the person and affiliations.
        if type(selector) is dict:
            result = []
            for p_affiliation in p_affiliations:
                try:
                    ssel = selector[p_affiliation[:2]]
                except KeyError:
                    ssel = selector[p_affiliation[:2]] = \
                           selector.get(p_affiliation[0]) or selector.get(None)
                if ssel:
                    result.extend(ssel[0])
            return result
        return selector[0]
    select_list = staticmethod(select_list)

    def select_bool(selector, person_id, p_affiliations):
        # Return True if the person is selected for some of the affiliations.
        if type(selector) is dict:
            for p_affiliation in p_affiliations:
                try:
                    ssel = selector[p_affiliation[:2]]
                except KeyError:
                    ssel = selector[p_affiliation[:2]] = \
                           selector.get(p_affiliation[0]) or selector.get(None)
                if ssel and ssel[ssel[2](person_id)]:
                    return True
            return False
        return selector[selector[2](person_id)]
    select_bool = staticmethod(select_bool)

    def attr_unique(values, normalize=None):
        """Return the input list of values with duplicates removed.

        Pass values through optional function 'normalize' before comparing.
        Preserve the order of values.  Use the first value of any duplicate."""
        if len(values) < 2:
            return values
        result = []
        done = {}
        for val in values:
            if normalize:
                norm = normalize(val)
            else:
                norm = val
            if not done.has_key(norm):
                done[norm] = True
                result.append(val)
        return result
    attr_unique = staticmethod(attr_unique)

    # used by split_name()
    _unicode_space_split = re.compile(ur'\S+').findall

    def split_name(self, fullname=None, givenname=None, lastname=None):
        """Return (UTF-8 given name, UTF-8 last name)."""
        full,given,last = [self._unicode_space_split(unicode(n or '', 'utf-8'))
                           for n in (fullname, givenname, lastname)]
        if full and not (given and last):
            if last:
                rest_l = last
                while full and rest_l and rest_l[-1].lower()==full[-1].lower():
                    rest_l.pop()
                    full.pop()
                if full and rest_l:
                    given = [full.pop(0)]
                    if not [True for n in rest_l if not n.islower()]:
                        while full and not full[0].islower():
                            given.append(full.pop(0))
                else:
                    given = full
            else:
                last = [full.pop()]
                got_given = rest_g = given
                if got_given:
                    while full and rest_g:
                        if rest_g[0].lower() != full[0].lower():
                            try:
                                rest_g = rest_g[rest_g.index(full[0]):]
                            except ValueError:
                                try:
                                    full = full[full.index(rest_g[0]):]
                                except ValueError:
                                    pass
                        rest_g.pop(0)
                        full.pop(0)
                elif full:
                    given = [full.pop(0)]
                if full and not (given[0].islower() or last[0].islower()):
                    while full and full[-1].islower():
                        last.insert(0, full.pop())
                if not got_given:
                    given.extend(full)
        return [u' '.join(n).encode('utf-8') for n in given, last]

    def make_timer(self, msg=None):
        # t = make_timer(message) logs the message and starts a stop watch.
        # t(message) logs that message and #seconds since last message.
        def timer(msg):
            prev        = timer.start
            timer.start = time.time()
            self.logger.debug("%s (%d seconds)", msg, timer.start - prev)
        if msg:
            self.logger.debug(msg)
        timer.start = time.time()
        return timer

# arch-tag: 3081b642-8577-4f6f-bc98-b9a144bbb2c1
