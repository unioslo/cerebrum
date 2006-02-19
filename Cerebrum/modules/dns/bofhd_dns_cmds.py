# -*- coding: iso-8859-1 -*-
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
#from Cerebrum.modules import Host
from Cerebrum.modules.bofhd.cmd_param import Parameter,Command,FormatSuggestion,GroupName,GroupOperation
from Cerebrum.modules.dns.bofhd_dns_utils import DnsBofhdUtils
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns.IPUtils import IPCalc
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import Utils
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.modules import dns
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode

class Constants(Constants.Constants):
    auth_dns_superuser = _AuthRoleOpCode(
        'dns_superuser', 'Perform any DNS command')

class DnsBofhdAuth(BofhdAuth):
    def assert_dns_superuser(self, operator, query_run_any=False):
        if (not (self.is_dns_superuser(operator)) and
            not (self.is_superuser(operator))):
            raise PermissionDenied("Currently limited to dns_superusers")

    def is_dns_superuser(self, operator, query_run_any=False):
        if self.is_superuser(operator):
            return True
        return self._has_operation_perm_somewhere(
            operator, self.const.auth_dns_superuser)

def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

# Parameter types
class HostId(Parameter):
    _type = 'host_id'
    _help_ref = 'host_id'

class HostName(Parameter):
    _type = 'host_name'
    _help_ref = 'host_name'

class HostNameRepeat(Parameter):
    _type = 'host_name_repeat'
    _help_ref = 'host_name_repeat'

class HostSearchPattern(Parameter):
    _type = 'host_search_pattern'
    _help_ref = 'host_search_pattern'

class HostSearchType(Parameter):
    _type = 'host_search_type'
    _help_ref = 'host_search_type'

class ServiceName(Parameter):
    _type = 'service_name'
    _help_ref = 'service_name'

class Ip(Parameter):
    _type = 'ip'
    _help_ref = 'ip_number'

class Hinfo(Parameter):
    _type = 'hinfo'
    _help_ref = 'hinfo'

class MXSet(Parameter):
    _type = 'mx_set'
    _help_ref = 'mx_set'

class TXT(Parameter):
    _type = 'txt'
    _help_ref = 'txt'

class TTL(Parameter):
    _type = 'ttl'
    _help_ref = 'ttl'

class Contact(Parameter):
    _type = 'contact'
    _help_ref = 'contact'

class Comment(Parameter):
    _type = 'comment'
    _help_ref = 'comment'

class Priority(Parameter):
    _type = 'pri'
    _help_ref = 'pri'

class Weight(Parameter):
    _type = 'weight'
    _help_ref = 'weight'

class Port(Parameter):
    _type = 'port'
    _help_ref = 'port'



#class IpTail(Parameter):
#    _type = 'ip_tail'
#    _help_ref = 'ip_tail'

class SubNetOrIP(Parameter):
    _type = 'subnet_or_ip'
    _help_ref = 'subnet_or_ip'

class Force(Parameter):
    _type = 'force'
    _help_ref = 'force'

def int_or_none_as_str(val):
    # Unfortunately the client don't understand how to
    # format: "%i" % None
    if val is not None:
        return str(int(val))
    return None

class BofhdExtension(object):
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')
    all_commands = {}

    legal_hinfo = (
        ("win", "IBM-PC\tWINDOWS"),
        ("linux", "IBM-PC\tLINUX"),
        ("printer", "PRINTER\tPRINTER"),
        ("unix", "UNIX\tUNIX"),
        ("nett", "NET\tNET"),
        ("mac", "MAC\tDARWIN"),
        ("other", "OTHER\tOTHER"),
        ("dhcp", "DHCP\tDHCP"),
        )

    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uio_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
             UiOBofhdExtension

        for func in ('_format_changelog_entry', '_format_from_cl',
                     '_get_entity_name', '_get_account', '_get_group',
                     '_get_group_opcode'):
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
        x = object.__new__(cls)
        return x

    def __init__(self, server, default_zone='uio'):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.default_zone = self.const.DnsZone(default_zone)
        self.mb_utils = DnsBofhdUtils(server, self.default_zone)
        self.dns_parser = Utils.DnsParser(server.db, self.default_zone)
        self._find = Utils.Find(server.db, self.default_zone)
        #self.ba = BofhdAuth(self.db)
        self.ba = DnsBofhdAuth(self.db)

        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)


    def get_help_strings(self):
        group_help = {
            'host': "Commands for administrating IP numbers",
            'group': "Group commands",
            }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'host': {
            'host_a_add': 'Add an A record',
            'host_a_remove': 'Remove an A record',
            'host_add': 'Add a new host with IP address',
            'host_cname_add': 'Add a CNAME',
            'host_cname_remove': 'Remove a CNAME',
            'host_comment': 'Set comment for a host',
            'host_contact': 'Set contact for a host',
            'host_find': 'List hosts matching search criteria',
            'host_remove': 'Remove data for specified host or IP',
            'host_hinfo_list': 'List acceptable HINFO values',
            'host_hinfo_set': 'Set HINFO',
            'host_history': 'Show history for a host',
            'host_info': 'List data for given host, IP-address or CNAME',
            'host_unused_list': 'List unused IP addresses',
            'host_mx_set': 'Set MX for host to specified MX definition',
            'host_mxdef_add': 'Add host to MX definition',
            'host_mxdef_remove': 'Remove host from MX definition',
            'host_mxdef_show': ('List all MX definitions, or show hosts in '
                                'one MX definition'),
            'host_rename': 'Rename an IP address or hostname',
            'host_ptr_add': 'Add override for IP reverse map',
            'host_ptr_remove': 'Remove override for IP reverse map',
            'host_srv_add': 'Add a SRV record',
            'host_srv_remove': 'Remove a SRV record',
            'host_ttl_set': 'Set TTL for a host',
            'host_txt_set': 'Set TXT for a host',
            },
            'group': {
            'group_hadd': 'Add machine to a netgroup',
            'group_host': 'List groups where host is a member',
            'group_hrem': 'Remove machine from a netgroup'
            }
            }
        
        arg_help = {
            'group_name_dest':
            ['gname', 'Enter the destination group'],
            'group_operation':
            ['op', 'Enter group operation',
             """Three values are legal: union, intersection and difference.
             Normally only union is used."""],
            'ip_number':
            ['ip', 'Enter IP numner',
             'Enter the IP number for this operation'],
            'host_id':
            ['host_id', 'Enter host_id',
             'Enter a unique host_id for this machine, typicaly the DNS name or IP'],
            'new_host_id_or_clear':
            ['new_host_id', 'Enter new host_id/leave blank',
             'Enter a new host_id, or leave blank to clear'],
            'host_name':
            ['host_name', 'Enter host name',
             'Enter the host name for this operation'],
            'host_name_exist':
            ['existing_host', 'Enter existing host name',
             'Enter the host name for this operation'],
            'host_name_alias':
            ['alias_name', 'Enter new alias',
             'Enter the host name for this operation'],
            'host_name_repeat':
            ['host_name_repeat', 'Enter host name(s)',
             'To specify 20 names starting at pcusitN+1, where N is '
             'the highest currently existing number, use pcusit#20.  To '
             'get the names pcusit20 to pcusit30 use pcusit#20-30.'],
            'host_search_pattern':
            ['pattern', 'Enter pattern',
             "Use ? and * as wildcard characters.  If there are no wildcards, "
             "it will be a substring search.  If there are no capital letters, "
             "the search will be case-insensitive."],
            'host_search_type':
            ['search_type', 'Enter search type',
             'You can search by "name", "comment" or "contact".'],
            'service_name':
            ['service_name', 'Enter service name',
             'Enter the service name for this operation'],
            'subnet_or_ip':
            ['subnet_or_ip', 'Enter subnet or ip',
             'Enter subnet or ip for this operation.  129.240.x.y = IP. '
             '129.240.x or 129.240.x.y/ indicates a subnet.'],
            'hinfo':
            ['hinfo', 'Enter HINFO code',
             'Legal values are: \n%s' % "\n".join(
            [" - %-8s -> %s" % (t[0], t[1]) for t in BofhdExtension.legal_hinfo])],
            'mx_set':
            ['mxdef', 'Enter name of mxdef',
             'Use "host mxdef_show" to get a list of legal values'],
            'contact':
            ['contact', 'Enter contact',
             'Typically an e-mail address'],
            'comment':
            ['comment', 'Enter comment',
             'Typically location'],
            'txt':
            ['txt', 'Enter TXT value'],
            'pri':
            ['pri', 'Enter priority value'],
            'weight':
            ['weight', 'Enter weight value'],
            'port':
            ['port', 'Enter port value'],
            'ttl':
            ['ttl', 'Enter TTL value'],
            'force':
            ['force', 'Force the operation',
             'Enter y to force the operation']
            }
        return (group_help, command_help,
                arg_help)
    
    def get_commands(self, account_id):
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for k in self.all_commands.keys():
            tmp = self.all_commands[k]
            if tmp is not None:
                if tmp.perm_filter:
                    if not getattr(self.ba, tmp.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands


    def _map_hinfo_code(self, code_str):
        for k, v in BofhdExtension.legal_hinfo:
            if code_str == k:
                return v
        raise CerebrumError("Illegal HINFO '%s'" % code_str)

#    def _alloc_arecord(self, host_name, subnet, ip, force):
#        return self.mb_utils.alloc_arecord(host_name, subnet, ip, force)

    # group hadd
    all_commands['group_hadd'] = Command(
        ("group", "hadd"), HostName(),
        GroupName(help_ref="group_name_dest"),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_hadd(self, operator, src_name, dest_group,
                  group_operator=None):
        dest_group = self._get_group(dest_group)
        owner_id = self._find.find_target_by_parsing(src_name, dns.DNS_OWNER)
        self.ba.can_alter_group(operator.get_entity_id(), dest_group)
        dest_group.add_member(owner_id, self.const.entity_dns_owner,
                              self._get_group_opcode(group_operator))
        return "OK, added %s to %s" % (src_name, dest_group.group_name)

    # group host
    all_commands['group_host'] = Command(
        ('group', 'host'), HostName(), fs=FormatSuggestion(
        "%-9s %-25s %s", ("memberop", "group", "spreads"),
        hdr="%-9s %-25s %s" % ("Operation", "Group", "Spreads")))
    def group_host(self, operator, hostname):
        # TODO: Should make use of "group memberships" command instead
        owner_id = self._find.find_target_by_parsing(hostname, dns.DNS_OWNER)
        group = self.Group_class(self.db)
        co = self.const
        ret = []
        for row in group.list_groups_with_entity(owner_id):
            grp = self._get_group(row['group_id'], idtype="id")
            ret.append({'memberop': str(co.GroupMembershipOp(row['operation'])),
                        'entity_id': grp.entity_id,
                        'group': grp.group_name,
                        'spreads': ",".join([str(co.Spread(a['spread']))
                                             for a in grp.get_spread()])
                        })
        ret.sort(lambda a,b: cmp(a['group'], b['group']))
        return ret

    # group hrem
    all_commands['group_hrem'] = Command(
        ("group", "hrem"), HostName(),
        GroupName(help_ref="group_name_dest"),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_hrem(self, operator, src_name, dest_group, group_operator=None):
        dest_group = self._get_group(dest_group)
        owner_id = self._find.find_target_by_parsing(src_name, dns.DNS_OWNER)
        self.ba.can_alter_group(operator.get_entity_id(), dest_group)
        dest_group.remove_member(owner_id,
                                 self._get_group_opcode(group_operator))
        return "OK, removed %s from %s" % (src_name, dest_group.group_name)

    # host a_add
    all_commands['host_a_add'] = Command(
        ("host", "a_add"), HostName(), SubNetOrIP(),
        Force(optional=True), perm_filter='is_dns_superuser')
    # TBD: Comment/contact?
    def host_a_add(self, operator, host_name, subnet_or_ip, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        subnet, ip = self.dns_parser.parse_subnet_or_ip(subnet_or_ip)
        free_ip_numbers = self.mb_utils.get_relevant_ips(subnet_or_ip, force)
        ip = self.mb_utils.alloc_arecord(host_name, subnet, free_ip_numbers[0], force)
        return "OK, ip=%s" % ip

    # host a_remove
    all_commands['host_a_remove'] = Command(
        ("host", "a_remove"), HostName(), Ip(optional=True),
        perm_filter='is_dns_superuser')
    def host_a_remove(self, operator, host_name, ip=None):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        a_record_id = self._find.find_a_record(host_name, ip)
        self.mb_utils.remove_arecord(a_record_id)
        return "OK"

    # host alloc
    all_commands['host_add'] = Command(
        ("host", "add"), HostNameRepeat(), SubNetOrIP(), Hinfo(),
        Contact(), Comment(), Force(optional=True),
        fs=FormatSuggestion("%-30s %s", ('name', 'ip'),
                            hdr="%-30s %s" % ('name', 'ip')),
        perm_filter='is_dns_superuser')
    def host_add(self, operator, hostname, subnet_or_ip, hinfo,
                 contact, comment, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        hostnames = self.dns_parser.parse_hostname_repeat(hostname)
        subnet, ip = self.dns_parser.parse_subnet_or_ip(subnet_or_ip)
        hinfo = self._map_hinfo_code(hinfo)
        free_ip_numbers = self.mb_utils.get_relevant_ips(subnet_or_ip, force)
        if len(free_ip_numbers) < len(hostnames):
            raise CerebrumError("Not enough free ips")
        # If user don't want mx_set, it must be removed with "ip mx_set"
        mx_set=self._find.find_mx_set(cereconf.DNS_DEFAULT_MX_SET)
        ret = []
        for name in hostnames:
            # TODO: bruk hinfo ++ for å se etter passende sekvens uten
            # hull (i en passende klasse)
            ip = self.mb_utils.alloc_arecord(
                name, subnet, free_ip_numbers.pop(0), force)
            self.mb_utils.alloc_host(
                name, hinfo, mx_set.mx_set_id, comment, contact)
            ret.append({'name': name, 'ip': ip})
        return ret

    # host cname_add
    all_commands['host_cname_add'] = Command(
        ("host", "cname_add"), HostName(help_ref="host_name_alias"),
        HostName(help_ref="host_name_exist"), Force(optional=True),
        perm_filter='is_dns_superuser')
    def host_cname_add(self, operator, cname_name, target_name, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        self.mb_utils.alloc_cname(cname_name, target_name, force)
        return "OK, cname registered for %s" % target_name

    # host cname_remove
    all_commands['host_cname_remove'] = Command(
        ("host", "cname_remove"), HostName(help_ref="host_name_alias"),
        perm_filter='is_dns_superuser')
    def host_cname_remove(self, operator, cname_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(
            cname_name, dns.DNS_OWNER)
        obj_ref, obj_id = self._find.find_target_type(owner_id)
        if not isinstance (obj_ref, CNameRecord.CNameRecord):
            raise CerebrumError("No such cname")
        self.mb_utils.ip_free(dns.DNS_OWNER, cname_name, False)
        return "OK, cname %s completly removed" % cname_name

    # host comment
    all_commands['host_comment'] = Command(
        ("host", "comment"), HostName(), Comment(),
        perm_filter='is_dns_superuser')
    def host_comment(self, operator, host_name, comment):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_entity_note(
            owner_id, self.const.trait_dns_comment, comment)
        return "OK, %s comment for %s" % (operation, host_name)


    # host contact
    all_commands['host_contact'] = Command(
        ("host", "contact"), HostName(), Contact(),
        perm_filter='is_dns_superuser')
    def host_contact(self, operator, name, contact):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_entity_note(
            owner_id, self.const.trait_dns_contact, contact)
        return "OK, %s contact for %s" % (operation, name)

    all_commands['host_find'] = Command(
        ("host", "find"), HostSearchType(), HostSearchPattern(),
        fs=FormatSuggestion("%-30s %s", ('name', 'info'),
                            hdr="%-30s %s" % ("Host", "Info")))
    def host_find(self, operator, search_type, pattern):
        if '*' not in pattern and '?' not in pattern:
            pattern = '*' + pattern + '*'
        if search_type == 'contact':
            matches = self._hosts_matching_trait(self.const.trait_dns_contact,
                                                 pattern)
        elif search_type == 'comment':
            matches = self._hosts_matching_trait(self.const.trait_dns_comment,
                                                 pattern)
        elif search_type == 'name':
            if pattern[-1].isalpha():
                # All names should be fully qualified, but it's easy to
                # forget the trailing dot.
                pattern += "."
            matches = self._hosts_matching_name(pattern)
        else:
            raise CerebrumError, "Unknown search type %s" % search_type
        matches.sort(lambda a,b: cmp(a['name'], b['name']))
        return matches

    def _assert_limit(self, rows, limit):
        if len(rows) > limit:
            raise CerebrumError, \
                  "More than %d matches (%d).  Refine your search." % \
                  (limit, len(rows))

    def _hosts_matching_trait(self, trait, pattern, limit=500):
        dns_owner = DnsOwner.DnsOwner(self.db)
        matches = []
        rows = dns_owner.list_traits(trait, strval_like=pattern, fetchall=True)
        self._assert_limit(rows, limit)
        for row in rows:
            dns_owner.clear()
            dns_owner.find(row['entity_id'])
            matches.append({'name': dns_owner.name, 'info': row['strval']})
        return matches

    def _hosts_matching_name(self, pattern, limit=500):
        dns_owner = DnsOwner.DnsOwner(self.db)
        matches = []
        rows = dns_owner.search(name_like=pattern, fetchall=True)
        self._assert_limit(rows, limit)
        for row in rows:
            matches.append({'name': row['name'], 'info': ""})
        return matches

    # host free
    all_commands['host_remove'] = Command(
        ("host", "remove"), HostId(), Force(optional=True),
        perm_filter='is_dns_superuser')
    def host_remove(self, operator, host_id, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        tmp = host_id.split(".")
        if host_id.find(":") == -1 and tmp[-1].isdigit():
            # Freeing an ip-number
            owner_id = self._find.find_target_by_parsing(host_id, dns.IP_NUMBER)
            arecord = ARecord.ARecord(self.db)
            names = dict([(a['name'], True)
                          for a in arecord.list_ext(ip_number_id=owner_id)])
            if len(names) > 1:
                raise CerebrumError, "IP matches multiple names"
            owner_id = names.keys()[0]
        try:
            owner_id = self._find.find_target_by_parsing(
                host_id, dns.DNS_OWNER)
            owners =  self._find.find_dns_owners(owner_id)
            if dns.CNAME_OWNER in owners:
                raise CerebrumError("Use 'host cname_remove' to remove cnames")
        except Errors.NotFoundError:
            pass
        self.mb_utils.ip_free(dns.DNS_OWNER, host_id, force)
        return "OK, DNS-owner %s completly removed" % host_id

    # host hinfo_list
    all_commands['host_hinfo_list'] = Command(
        ("host", "hinfo_list"))
    def host_hinfo_list(self, operator):
        return "\n".join(["%-10s -> %s" % (x[0], x[1])
                          for x in self.legal_hinfo])

    # host hinfo_set
    all_commands['host_hinfo_set'] = Command(
        ("host", "hinfo_set"), HostName(), Hinfo(),
        perm_filter='is_dns_superuser')
    def host_hinfo_set(self, operator, host_name, hinfo):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        hinfo = self._map_hinfo_code(hinfo)
        owner_id = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        host = HostInfo.HostInfo(self.db)
        host.find_by_dns_owner_id(owner_id)
        host.hinfo = hinfo
        host.write_db()
        return "OK, hinfo set for %s" % host_name

    # host info
    all_commands['host_info'] = Command(
        ("host", "info"), HostId(),
        fs=FormatSuggestion([
        # Name line
        ("%-22s %%s\n%-22s contact=%%s\n%-22s comment=%%s" % (
        "Name:", ' ', ' '), ('dns_owner', 'contact', 'comment')),
        # A-records
        ("  %-20s %s", ('name', 'ip'), "%-22s IP" % 'A-records'),
        # Hinfo line
        ("%-22s %s" % ('Hinfo:', 'os=%s cpu=%s'), ('hinfo.os', 'hinfo.cpu')),
        # MX
        ("%-22s %s" % ("MX-set:", "%s"), ('mx_set',)),
        # TXT
        ("%-22s %s" % ("TXT:", "%s"), ('txt', )),
        # Cnames
        ("%-22s %s" % ('Cname:', '%s -> %s'), ('cname', 'cname_target')),
        # SRV
        ("SRV: %s %i %i %i %s %s",
         ('srv_owner', 'srv_pri', 'srv_weight', 'srv_port','srv_ttl',
          'srv_target')),
        # Rev-map
        ("  %-20s %s", ('rev_ip', 'rev_name'), "Rev-map override:"),
        ]))
    def host_info(self, operator, host_id):
        arecord = ARecord.ARecord(self.db)
        tmp = host_id.split(".")
        if host_id.find(":") == -1 and tmp[-1].isdigit():
            # When host_id is an IP, we only return A-records
            owner_id = self._find.find_target_by_parsing(
                host_id, dns.IP_NUMBER)
            ret = []
            for a in arecord.list_ext(ip_number_id=owner_id):
                ret.append({'ip': a['a_ip'], 'name': a['name']})

            ip = IPNumber.IPNumber(self.db)
            added_rev = False
            for row in ip.list_override(ip_number_id=owner_id):
                ret.append({'rev_ip': row['a_ip'],
                            'rev_name': row['name']})
                added_rev = True
            if not ret:
                self.logger.warn("Nothing known about '%s'?" % host_id)
            if not added_rev:
                ret.append({'rev_ip': host_id,
                            'rev_name': "using default PTR from A-record"})
            return ret

        owner_id = self._find.find_target_by_parsing(
            host_id, dns.DNS_OWNER)
        dns_owner = DnsOwner.DnsOwner(self.db)
        dns_owner.find(owner_id)

        tmp = {'dns_owner': dns_owner.name}
        for key, trait in (('comment', self.const.trait_dns_comment),
                           ('contact', self.const.trait_dns_contact)):
            tmp[key] = dns_owner.get_trait(trait)
            if tmp[key] is not None:
                tmp[key] = tmp[key]['strval']
        ret = [tmp]

        # HINFO records
        ret.append({'zone': str(self.const.DnsZone(dns_owner.zone))})
        try:
            host = HostInfo.HostInfo(self.db)
            host.find_by_dns_owner_id(owner_id)
            hinfo_cpu, hinfo_os = host.hinfo.split("\t", 2)
            ret.append({'hinfo.os': hinfo_os,
                        'hinfo.cpu': hinfo_cpu})
        except Errors.NotFoundError:  # not found
            pass

        txt = dns_owner.list_general_dns_records(
            field_type=self.const.field_type_txt,
            dns_owner_id=dns_owner.entity_id)
        if txt:
            ret.append({'txt': txt[0]['data']})

        forward_ips = []
        # A records
        tmp = []
        for a in arecord.list_ext(dns_owner_id=owner_id):
            forward_ips.append((a['a_ip'], a['ip_number_id']))
            tmp.append({'ip': a['a_ip'], 'name': a['name']})
        tmp.sort(lambda x, y: cmp(IPCalc.ip_to_long(x['ip']),
                                  IPCalc.ip_to_long(y['ip'])))
        ret.extend(tmp)

        ip_ref = IPNumber.IPNumber(self.db)
        for a_ip, ip_id in forward_ips:
            for r in ip_ref.list_override(ip_number_id=ip_id):
                ret.append({'rev_ip': a_ip, 'rev_name': r['name']})

        # MX records
        if dns_owner.mx_set_id:
            mx_set = DnsOwner.MXSet(self.db)
            mx_set.find(dns_owner.mx_set_id)
            ret.append({'mx_set': mx_set.name})
        # CNAME records with this as target, or this name
        cname = CNameRecord.CNameRecord(self.db)
        tmp = cname.list_ext(target_owner=owner_id)
        tmp.extend(cname.list_ext(cname_owner=owner_id))
        for c in tmp:
            row = ({'cname': c['name'],
                    'cname_target': c['target_name']})
            ret.append(row)

        # SRV records dersom dette er target/owner for en srv record
        r = dns_owner.list_srv_records(owner_id=owner_id)
        r.extend(dns_owner.list_srv_records(target_owner_id=owner_id))
        for srv in r:
            ret.append({'srv_owner': srv['service_name'],
                        'srv_pri': srv['pri'],
                        'srv_weight': srv['weight'],
                        'srv_port': srv['port'],
                        'srv_ttl': int_or_none_as_str(srv['ttl']),
                        'srv_target': srv['target_name']})
        return ret

    # host unused_list
    all_commands['host_unused_list'] = Command(
        ("host", "unused_list"), SubNetOrIP(),
        fs=FormatSuggestion("%s", ('ip',), hdr="Ip"))
    def host_unused_list(self, operator, subnet):
        # TODO: Skal det være mulig å få listet ut ledige reserved IP?
        subnet, ip = self.dns_parser.parse_subnet_or_ip(subnet)
        if subnet is None:
            raise CerebrumError, "Unknown subnet, check cereconf_dns.py"
        ret = []
        for ip in self._find.find_free_ip(subnet):
            ret.append({'ip': ip})
        return ret

    # host mxdef_add
    all_commands['host_mxdef_add'] = Command(
        ("host", "mxdef_add"), MXSet(), Priority(), HostName(),
        perm_filter='is_dns_superuser')
    def host_mxdef_add(self, operator, mx_set, priority, host_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host_ref = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        self.mb_utils.mx_set_add(mx_set, priority, host_ref)
        return "OK, added %s to mx_set %s" % (host_name, mx_set)

    # host mxdef_remove
    all_commands['host_mxdef_remove'] = Command(
        ("host", "mxdef_remove"), MXSet(), HostName(),
        perm_filter='is_dns_superuser')
    def host_mxdef_remove(self, operator, mx_set, target_host_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        host_ref = self._find.find_target_by_parsing(
            target_host_name, dns.DNS_OWNER)
        self.mb_utils.mx_set_del(mx_set, host_ref)
        return "OK, deleted %s from mx_set %s" % (target_host_name, mx_set)

    # host history
    all_commands['host_history'] = Command(
        ("host", "history"), HostName(),
        perm_filter='can_show_history')
    def host_history(self, operator, host_name):
        host_ref = self._find.find_target_by_parsing(host_name, dns.DNS_OWNER)
        ret = []
        for r in self.db.get_log_events(0, subject_entity=host_ref):
            ret.append(self._format_changelog_entry(r))
        return "\n".join(ret)

    # host mx_set
    all_commands['host_mx_set'] = Command(
        ("host", "mx_set"), HostName(), MXSet(), Force(optional=True),
        perm_filter='is_dns_superuser')
    def host_mx_set(self, operator, name, mx_set, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        mx_set_id = self._find.find_mx_set(mx_set).mx_set_id
        force = self.dns_parser.parse_force(force)
        try:
            owner_id = self._find.find_target_by_parsing(
                name, dns.DNS_OWNER)
        except CerebrumError:
            # FIXME: a bit ugly, since all kinds of errors in
            # find_target_by_parsing will raise CerebrumError
            if not force:
                raise
            name = self.dns_parser.qualify_hostname(name)
            owner_id = self.mb_utils.alloc_dns_owner(name, mx_set=mx_set_id)
        self.mb_utils.mx_set_set(owner_id, mx_set)
        return "OK, mx set for %s" % name

    # host mxdef_show
    all_commands['host_mxdef_show'] = Command(
        ("host", "mxdef_show"), MXSet(optional=True),
        fs=FormatSuggestion("%-20s %-12s %-10i %s",
                            ('mx_set', 'ttl', 'pri', 'target'),
                            hdr="%-20s %-12s %-10s %s" % (
        'MX-set', 'TTL', 'Priority', 'Target')))
    def host_mxdef_show(self, operator, mx_set=None):
        m = DnsOwner.MXSet(self.db)
        if mx_set is None:
            mx_set = [row['name'] for row in m.list()]
        else:
            self._find.find_mx_set(mx_set)
            mx_set = [mx_set]
        ret = []
        for name in mx_set:
            m.clear()
            m.find_by_name(name)
            for row in m.list_mx_sets(mx_set_id=m.mx_set_id):
                ret.append({'mx_set': m.name,
                            'ttl': int_or_none_as_str(row['ttl']),
                            'pri': row['pri'],
                            'target': row['target_name']})
        return ret

    # host rename
    all_commands['host_rename'] = Command(
        ("host", "rename"), HostId(), HostId(), Force(optional=True),
        perm_filter='is_dns_superuser')
    def host_rename(self, operator, old_id, new_id, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        lastpart = new_id.split(".")[-1]
        # Rename by IP-number
        if (new_id.find(":") == -1 and lastpart and
            (lastpart[-1] == '/' or lastpart.isdigit())):
            free_ip_numbers = self.mb_utils.get_relevant_ips(new_id, force)
            new_id = free_ip_numbers[0]
            self.mb_utils.ip_rename(dns.IP_NUMBER, old_id, new_id)
            return "OK, ip-number %s renamed to %s" % (
                old_id, new_id)
        # Rename by dns-owner
        new_id = self.dns_parser.qualify_hostname(new_id)
        self.mb_utils.ip_rename(dns.DNS_OWNER, old_id, new_id)
        arecord = ARecord.ARecord(self.db)
        owner_id = self._find.find_target_by_parsing(new_id, dns.DNS_OWNER)
        ips = [row['a_ip'] for row in arecord.list_ext(dns_owner_id=owner_id)]
        return "OK, dns-owner %s renamed to %s (IP: %s)" % (
            old_id, new_id, ", ".join(ips))

    # host ptr_add
    all_commands['host_ptr_add'] = Command(
        ("host", "ptr_add"), Ip(), HostName(), Force(optional=True),
        perm_filter='is_dns_superuser')
    def host_ptr_add(self, operator, ip_host_id, dest_host, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        self.mb_utils.add_revmap_override(ip_host_id, dest_host, force)
        return "OK, added reversemap override for %s -> %s" % (
            ip_host_id, dest_host)

    # host ptr_remove
    all_commands['host_ptr_remove'] = Command(
        ("host", "ptr_remove"), Ip(), HostName(),
        perm_filter='is_dns_superuser')
    def host_ptr_remove(self, operator, ip_host_id, dest_host, force=False):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        force = self.dns_parser.parse_force(force)
        ip_owner_id = self._find.find_target_by_parsing(
            ip_host_id, dns.IP_NUMBER)
        if dest_host:
            dest_owner_id = self._find.find_target_by_parsing(
                dest_host, dns.DNS_OWNER)
        else:
            dest_owner_id = None
        self.mb_utils.remove_revmap_override(ip_owner_id, dest_owner_id)
        return "OK, removed reversemap override for %s -> %s" % (
            ip_host_id, dest_host)
        
    # host srv_add
    all_commands['host_srv_add'] = Command(
        ("host", "srv_add"), ServiceName(), Priority(), Weight(),
        Port(), HostName(), perm_filter='is_dns_superuser')
    def host_srv_add(self, operator, service_name, priority,
                   weight, port, target_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        target_id = self._find.find_target_by_parsing(
            target_name, dns.DNS_OWNER)
        self.mb_utils.alter_srv_record(
            'add', service_name, int(priority), int(weight),
            int(port), target_id)
        return "OK, added SRV record %s -> %s" % (service_name, target_name)

    # host srv_remove
    all_commands['host_srv_remove'] = Command(
        ("host", "srv_remove"), ServiceName(), Priority(), Weight(),
        Port(), HostName(), perm_filter='is_dns_superuser')
    def host_srv_remove(self, operator, service_name, priority,
                   weight, port, target_name):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        target_id = self._find.find_target_by_parsing(
            target_name, dns.DNS_OWNER)
        self.mb_utils.alter_srv_record(
            'del', service_name, int(priority), int(weight),
            int(port), target_id)
        return "OK, deletded SRV record %s -> %s" % (service_name, target_name)


    # host ttl_set
    all_commands['host_ttl_set'] = Command(
        ("host", "ttl_set"), HostName(), TTL(), perm_filter='is_dns_superuser')
    def host_ttl_set(self, operator, host_name, ttl):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        if ttl:
            ttl = int(ttl)
        else:
            ttl = None
        operation = self.mb_utils.set_ttl(
            owner_id, ttl)
        return "OK, set TTL record for %s to %s" % (host_name, ttl)

    # host txt
    all_commands['host_txt_set'] = Command(
        ("host", "txt_set"), HostName(), TXT(), perm_filter='is_dns_superuser')
    def host_txt_set(self, operator, host_name, txt):
        self.ba.assert_dns_superuser(operator.get_entity_id())
        owner_id = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_general_dns_record(
            owner_id, int(self.const.field_type_txt), txt)
        return "OK, %s TXT record for %s" % (operation, host_name)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

if __name__ == '__main__':
    pass

# arch-tag: c8f44ecd-c4fb-464c-a871-e81768793319
