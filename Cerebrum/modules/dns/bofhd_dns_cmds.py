# -*- coding: iso-8859-1 -*-
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Utils
from Cerebrum import Errors
#from Cerebrum.modules import Host
from Cerebrum.modules.bofhd.cmd_param import Parameter,Command,FormatSuggestion,GroupName,GroupOperation
from Cerebrum.modules.dns.bofhd_dns_utils import DnsBofhdUtils
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import Utils
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.modules import dns
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as UiOBofhdExcension

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
        ("linux", "IBM_PC\tLINUX"),
        ("printer", "PRINTER\tPRINTER"),
        ("unix", "UNIX\tUNIX"),
        ("nett", "NET\tNET"),
        ("mac", "MAC\tDARWIN"),
        ("other", "OTHER\tOTHER"),
        )

    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uio_cmds.py
        # into seperate classes.
        for func in ('_format_changelog_entry', '_format_from_cl',
                     '_get_entity_name', '_get_account', '_get_group',
                     '_get_group_opcode'):
            setattr(cls, func, UiOBofhdExcension.__dict__.get(
            func))
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
        self.ba = BofhdAuth(self.db)

        # From uio
        self.num2const = {}
        #self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                #self.str2const[str(tmp)] = tmp


    def get_help_strings(self):
        group_help = {
            'host': "Commands for administrating IP numbers",
            'group': "Group commands",
            }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'host': {
            'host_a_add': 'Legg til en a-record',
            'host_a_remove': 'Fjern en a-record',
            'host_add': 'Registrerer ip-addresse for en ny maskin',
            'host_cname_add': 'Registrer et cname',
            'host_comment': 'Sette kommentar for en gitt maskin',
            'host_contact': 'Oppgi contact for gitt maskin',
            'host_remove': 'Sletter data for oppgitt hosnavn/ip-nr',
            'host_hinfo_list': 'List lovlige hinfo verdier',
            'host_hinfo_set': 'Sette hinfo',
            'host_info': 'Lister data for gitt hostnavn/ip-addresse eller cname',
            'host_unused_list': 'List ledige ipnr',
            'host_mx_set': 'Sette MX for host_name til en gitt MX definisjon',
            'host_mxdef_add': 'Utvid en MX definisjon med ny maskin',
            'host_mxdef_remove': 'Fjern maskin fra en MX definisjon',
            'host_mxdef_show': 'Vis innhold i en MX definisjon',
            'host_rename': 'Forande et IP-nr/navn til et annet IP-nr/navn.',
            'host_ptr_set': 'Registrer/slett override på reversemap',
            'host_srv_add': 'Opprette en SRV record',
            'host_srv_remove': 'Fjerne en SRV record',
            'host_ttl_set': 'Set TTL for en DNS-owner',
            'host_txt_set': 'sette TXT',
            },
            'group': {
            'group_hadd': 'add machine to a netgroup',
            'group_host': 'list groups where host is a member',
            'group_hrem': 'remove machine from a netgroup'
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
             'Multiple hostnames may be entered like pcusit[01..30]'],
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
             'Use "host list_mx_set" to get a list of legal values'],
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
    
    def get_commands(self, uname):
        # TODO: Do some filtering on uname to remove commands
        commands = {}
        for k in self.all_commands.keys():
            commands[k] = self.all_commands[k].get_struct(self)
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
        if operator:
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
        owner_id = self._find.find_target_by_parsing(hostname, dns.DNS_OWNER)
        group = self.Group_class(self.db)
        ret = []
        for row in group.list_groups_with_entity(owner_id):
            grp = self._get_group(row['group_id'], idtype="id")
            ret.append({'memberop': str(self.num2const[int(row['operation'])]),
                        'entity_id': grp.entity_id,
                        'group': grp.group_name,
                        'spreads': ",".join(["%s" % self.num2const[int(a['spread'])]
                                             for a in grp.get_spread()])})
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
        if operator:
            self.ba.can_alter_group(operator.get_entity_id(), dest_group)
        dest_group.remove_member(owner_id,
                                 self._get_group_opcode(group_operator))
        return "OK, removed %s from %s" % (src_name, dest_group.group_name)

    # host a_add
    all_commands['host_a_add'] = Command(
        ("host", "a_add"), HostName(), SubNetOrIP(),
        Force(optional=True))
    # TBD: Comment/contact?
    def host_a_add(self, operator, host_name, subnet_or_ip, force=False):
        force = self.dns_parser.parse_force(force)
        subnet, ip = self.dns_parser.parse_subnet_or_ip(subnet_or_ip)
        if subnet is None and ip is None:
            raise CerebrumError, "Unknown subnet and incomplete ip"
        if subnet is None and not force:
            raise CerebrumError, "Unknown subnet.  Must force"
        ip = self.mb_utils.alloc_arecord(host_name, subnet, ip, force)
        return "OK, ip=%s" % ip

    # host a_remove
    all_commands['host_a_remove'] = Command(
        ("host", "a_remove"), HostName(), Ip(optional=True))
    def host_a_remove(self, operator, host_name, ip=None):
        a_record_id = self._find.find_a_record(host_name, ip)
        self.mb_utils.remove_arecord(a_record_id)
        return "OK"

    # host alloc
    all_commands['host_add'] = Command(
        ("host", "add"), HostNameRepeat(), SubNetOrIP(), Hinfo(),
        Comment(), Contact(), Force(optional=True),
        fs=FormatSuggestion("%-30s %s", ('name', 'ip'),
                            hdr="%-30s %s" % ('name', 'ip')))
    def host_add(self, operator, hostname, subnet_or_ip, hinfo,
                 comment, contact, force=False):
        force = self.dns_parser.parse_force(force)
        hostnames = self.dns_parser.parse_hostname_repeat(hostname)
        subnet, ip = self.dns_parser.parse_subnet_or_ip(subnet_or_ip)
        if subnet is None and ip is None:
            raise CerebrumError, "Unknown subnet and incomplete ip"
        if subnet is None and not force:
            raise CerebrumError, "Unknown subnet.  Must force"
        if ip and len(hostnames) > 1:
            raise CerebrumError, "Explicit IP and multiple hostnames"
        if not len(contact.strip()) > 3:
            raise CerebrumError, "Contact is mandatory"
        hinfo = self._map_hinfo_code(hinfo)
        if not ip:
            free_ip_numbers = self._find.find_free_ip(subnet)
        else:
            free_ip_numbers = [ ip ]
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
        HostName(help_ref="host_name_exist"), Force(optional=True))
    def host_cname_add(self, operator, cname_name, target_name, force=False):
        force = self.dns_parser.parse_force(force)
        self.mb_utils.alloc_cname(cname_name, target_name, force)
        return "OK, cname registered for %s" % target_name

    # host cname_remove
    all_commands['host_cname_remove'] = Command(
        ("host", "cname_remove"), HostName(help_ref="host_name_alias"))
    def host_cname_remove(self, operator, cname_name):
        owner_id = self._find.find_target_by_parsing(
            cname_name, dns.DNS_OWNER)
        obj_ref, obj_id = self._find.find_target_type(owner_id)
        if not isinstance (obj_ref, CNameRecord.CNameRecord):
            raise CerebrumError("No such cname")
        self.mb_utils.ip_free(dns.DNS_OWNER, cname_name, False)
        return "OK, cname %s completly removed" % cname_name

    # host comment
    all_commands['host_comment'] = Command(
        ("host", "comment"), HostName(), Comment())
    def host_comment(self, operator, host_name, comment):
        owner_id = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_entity_note(
            owner_id, self.const.note_type_comment, comment)
        return "OK, %s comment for %s" % (operation, host_name)


    # host contact
    all_commands['host_contact'] = Command(
        ("host", "contact"), HostName(), Contact())
    def host_contact(self, operator, name, contact):
        owner_id = self._find.find_target_by_parsing(name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_entity_note(
            owner_id, self.const.note_type_contact, contact)
        return "OK, %s contact for %s" % (operation, name)


    # host free
    all_commands['host_remove'] = Command(
        ("host", "remove"), HostId(), Force(optional=True))
    def host_remove(self, operator, host_id, force=False):
        force = self.dns_parser.parse_force(force)
        tmp = host_id.split(".")
        if host_id.find(":") == -1 and tmp[-1].isdigit():
            # Freeing an ip-number
            self.mb_utils.ip_free(dns.IP_NUMBER, host_id, force)
            return "OK, IP-number %s completly removed" % host_id
        try:
            owner_id = self._find.find_target_by_parsing(
                host_id, dns.DNS_OWNER)
            obj_ref, obj_id = self._find.find_target_type(owner_id)
            if isinstance (obj_ref, CNameRecord.CNameRecord):
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
        ("host", "hinfo_set"), HostName(), Hinfo())
    def host_hinfo_set(self, operator, host_name, hinfo):
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
            return ret
        if host_id.startswith('ptr:'):
            owner_id = self._find.find_target_by_parsing(
                host_id[4:], dns.IP_NUMBER)
            ip = IPNumber.IPNumber(self.db)
            ret = []
            for row in ip.list_override(ip_number_id=owner_id):
                ret.append({'rev_ip': row['a_ip'],
                            'rev_name': row['name']})
            if not ret:
                return "using default PTR from A-record"
            return ret

        owner_id = self._find.find_target_by_parsing(
            host_id, dns.DNS_OWNER)
        dns_owner = DnsOwner.DnsOwner(self.db)
        dns_owner.find(owner_id)

        tmp = {'dns_owner': dns_owner.name}
        for key, note_type in (('comment', self.const.note_type_comment),
                               ('contact', self.const.note_type_contact)):
            try:
                tmp[key] = dns_owner.get_entity_note(note_type)
            except Errors.NotFoundError:
                tmp[key] = None
        ret = [tmp]

        # HINFO records
        ret.append({'zone': str(self.const.DnsZone(dns_owner.zone))})
        try:
            host = HostInfo.HostInfo(self.db)
            host.find_by_dns_owner_id(owner_id)
            hinfo_os, hinfo_cpu = host.hinfo.split("\t", 2)
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
        for a in arecord.list_ext(dns_owner_id=owner_id):
            forward_ips.append((a['a_ip'], a['ip_number_id']))
            ret.append({'ip': a['a_ip'], 'name': a['name']})

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
        ret = []
        for ip in self._find.find_free_ip(subnet):
            ret.append({'ip': ip})
        return ret

    # host mxdef_add
    all_commands['host_mxdef_add'] = Command(
        ("host", "mxdef_add"), MXSet(), Priority(), HostName())
    def host_mxdef_add(self, operator, mx_set, priority, host_name):
        host_ref = self._find.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        self.mb_utils.mx_set_add(mx_set, priority, host_ref)
        return "OK, added %s to mx_set %s" % (host_name, mx_set)

    # host mxdef_remove
    all_commands['host_mxdef_remove'] = Command(
        ("host", "mxdef_remove"), MXSet(), HostName())
    def host_mxdef_remove(self, operator, mx_set, target_host_name):
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
        ("host", "mx_set"), HostName(), MXSet())
    def host_mx_set(self, operator, name, mx_set):
        owner_id = self._find.find_target_by_parsing(
            name, dns.DNS_OWNER)
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
        ("host", "rename"), HostId(), HostId())
    def host_rename(self, operator, old_id, new_id):
        tmp = new_id.split(".")

        # Rename by IP-number
        if new_id.find(":") == -1 and tmp[-1].isdigit():
            self.mb_utils.ip_rename(dns.IP_NUMBER, old_id, new_id)
            return "OK, ip-number %s renamed to %s" % (
                old_id, new_id)
        # Rename by dns-owner
        self.mb_utils.ip_rename(dns.DNS_OWNER, old_id, new_id)
        return "OK, dns-owner %s renamed to %s" % (old_id, new_id)

    # host ptr_add
    all_commands['host_ptr_add'] = Command(
        ("host", "ptr_add"), HostId(), HostName(), Force(optional=True))
    def host_ptr_add(self, operator, ip_host_id, dest_host, force=False):
        force = self.dns_parser.parse_force(force)
        ip_owner_id = self._find.find_target_by_parsing(
            ip_host_id, dns.IP_NUMBER)
        self.mb_utils.add_revmap_override(
            ip_owner_id, dest_host, force)
        return "OK, added reversemap override for %s -> %s" % (
            ip_host_id, dest_host)

    # host ptr_remove
    all_commands['host_ptr_remove'] = Command(
        ("host", "ptr_remove"), HostId(), HostName())
    def host_ptr_remove(self, operator, ip_host_id, dest_host, force=False):
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
        Port(), HostName())
    def host_srv_add(self, operator, service_name, priority,
                   weight, port, target_name):
        target_id = self._find.find_target_by_parsing(
            target_name, dns.DNS_OWNER)
        self.mb_utils.alter_srv_record(
            'add', service_name, int(priority), int(weight),
            int(port), target_id)
        return "OK, added SRV record %s -> %s" % (service_name, target_name)

    # host srv_remove
    all_commands['host_srv_remove'] = Command(
        ("host", "srv_remove"), ServiceName(), TTL(), Priority(), Weight(),
        Port(), HostName())
    def host_srv_remove(self, operator, service_name, priority,
                   weight, port, target_name , ttl=None):
        target_id = self._find.find_target_by_parsing(
            target_name, dns.DNS_OWNER)
        if ttl:
            ttl = int(ttl)
        self.mb_utils.alter_srv_record(
            'del', service_name, int(priority), int(weight),
            int(port), target_id)
        return "OK, deletded SRV record %s -> %s" % (service_name, target_name)


    # host ttl_set
    all_commands['host_ttl_set'] = Command(
        ("host", "ttl_set"), HostName(), TTL())
    def host_ttl_set(self, operator, host_name, ttl):
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
        ("host", "txt_set"), HostName(), TXT())
    def host_txt_set(self, operator, host_name, txt):
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
