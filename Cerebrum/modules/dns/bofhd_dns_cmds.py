# -*- coding: iso-8859-1 -*-

from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum import Utils
from Cerebrum import Errors
#from Cerebrum.modules import Host
from Cerebrum.modules.bofhd.cmd_param import Parameter
from Cerebrum.modules.bofhd.cmd_param import Command,FormatSuggestion
from Cerebrum.modules.dns.bofhd_dns_utils import DnsBofhdUtils
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules import dns

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
    all_commands = {}

    def __init__(self, server):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.mb_utils = DnsBofhdUtils(server)

    def get_help_strings(self):
        group_help = {
            'ip': "Commands for administrating IP numbers",
            }

        # The texts in command_help are automatically line-wrapped, and should
        # not contain \n
        command_help = {
            'ip': {
            'ip_a_add': 'legg til en a-record',
            'ip_a_rem': 'fjern en a-record',
            'ip_alloc': 'Registrerer ip-addresse for en ny maskin',
            'ip_cname_add': 'registrer et cname',
            'ip_comment': 'Sette kommentar for en gitt maskin',
            'ip_contact': 'Oppgi contact for gitt maskin',
            'ip_free': 'Sletter data for oppgitt hosnavn/ip-nr',
            'ip_hinfo_list': 'list definerte hinfo',
            'ip_hinfo_set': 'sette hinfo',
            'ip_info': 'Lister data for gitt hostnavn/ip-addresse eller cname',
            'ip_list_free': 'list ledige ipnr',
            'ip_mx_add': 'legg ny entry til et MX set',
            'ip_mx_del': 'fjern entry fra et MX set',
            'ip_mx_list': 'list definerte MX set',
            'ip_mx_set': 'sette MX',
            'ip_mx_show': 'Vid definisjonen av et MX set',
            'ip_rename': 'Forande et IP-nr/navn til et annet IP-nr/navn.',
            'ip_revmap_override': 'Registrer/slett override på reversemap',
            'ip_srv_add': 'Opprette en SRV record',
            'ip_srv_del': 'Fjerne en SRV record',
            'ip_ttl_set': 'Set TTL for en DNS-owner',
            'ip_txt_set': 'sette TXT',
            },
            }
        
        arg_help = {
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
            'host_name_repeat':
            ['host_name_repeat', 'Enter host name(s)',
             'Multiple hostnames may be entered like pcusit[01..30]'],
            'service_name':
            ['service_name', 'Enter service name',
             'Enter the service name for this operation'],
            'subnet_or_ip':
            ['subnet_or_ip', 'Enter subnet or ip',
             'Enter subnet or ip for this operation.  IP-numbers must '
             'be marked as such by prepending a final dot, otherwise it '
             'will be interpreted as a subnet.  You may skip the 129.240 part'],
            'hinfo':
            ['hinfo', 'Enter HINFO code',
             'Use "ip list_hinfo" to get a list of legal values, some examples are:\n'
             "- unix\n",
             "- windows\n",
             "- mac\n",
             "- nettboks"],
            'mx_set':
            ['mx_set', 'Enter mx_set',
             'Use "ip list_mx_set" to get a list of legal values'],
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
        try:
            return self.const.HinfoCode(code_str)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown hinfo: %s" % code_str

#    def _alloc_arecord(self, host_name, subnet, ip, force):
#        return self.mb_utils.alloc_arecord(host_name, subnet, ip, force)

    # ip a_add
    all_commands['ip_a_add'] = Command(
        ("ip", "a_add"), HostName(), SubNetOrIP(),
        Force(optional=True))
    # TBD: Comment/contact?
    def ip_a_add(self, operator, host_name, subnet_or_ip, force=False):
        force = self.mb_utils.parse_force(force)
        subnet, ip, ip_ref = self.mb_utils.parse_subnet_or_ip(subnet_or_ip)
        if subnet is None and not force:
            raise CerebrumError, "Unknown subnet.  Must force"
        #ip = self._alloc_arecord(host_name, subnet, ip, force)
        ip = self.mb_utils.alloc_arecord(host_name, subnet, ip, force)
        return "OK, ip=%s" % ip

    # ip a_rem
    all_commands['ip_a_rem'] = Command(
        ("ip", "a_rem"), HostName(), Ip(optional=True))
    def ip_a_rem(self, operator, host_name, ip=None):
        a_record_id = self.mb_utils.find_a_record(host_name, ip)
        self.mb_utils.remove_arecord(a_record_id)
        return "OK"

    # ip alloc
    all_commands['ip_alloc'] = Command(
        ("ip", "alloc"), HostNameRepeat(), SubNetOrIP(), Hinfo(),
        Comment(), Contact(), Force(optional=True),
        fs=FormatSuggestion("%-30s %s", ('name', 'ip'),
                            hdr="%-30s %s" % ('name', 'ip')))
    def ip_alloc(self, operator, hostname, subnet_or_ip, hinfo,
                 comment, contact, force=False):
        force = self.mb_utils.parse_force(force)
        hostnames = self.mb_utils.parse_hostname_repeat(hostname)
        subnet, ip, ip_ref = self.mb_utils.parse_subnet_or_ip(subnet_or_ip)
        if subnet is None and not force:
            raise CerebrumError, "Unknown subnet.  Must force"
        if ip and len(hostnames) > 1:
            raise CerebrumError, "Explicit IP and multiple hostnames"
        hinfo = self._map_hinfo_code(hinfo)
        if not ip:
            free_ip_numbers = self.mb_utils.find_free_ip(subnet)
        else:
            free_ip_numbers = [ ip ]
        # If user don't want mx_set, it must be removed with "ip mx_set"
        mx_set=self.mb_utils.find_mx_set(cereconf.DNS_DEFAULT_MX_SET)
        ret = []
        for name in hostnames:
            ip = self.mb_utils.alloc_arecord(
                name, subnet, free_ip_numbers.pop(0), force)
            self.mb_utils.alloc_host(
                name, hinfo, mx_set, comment, contact)
            ret.append({'name': name, 'ip': ip})
        return ret

    # ip cname_add
    all_commands['ip_cname_add'] = Command(
        ("ip", "cname_add"), HostName(), HostName(), Force(optional=True))
    def ip_cname_add(self, operator, cname_name, target_name, force=False):
        force = self.mb_utils.parse_force(force)
        self.mb_utils.alloc_cname(cname_name, target_name, force)
        return "OK, cname registered for %s" % target_name

    # ip comment
    all_commands['ip_comment'] = Command(
        ("ip", "comment"), HostName(), Comment())
    def ip_comment(self, operator, host_name, comment):
        owner_id = self.mb_utils.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_entity_note(
            owner_id, self.const.note_type_comment, comment)
        return "OK, %s comment for %s" % (operation, host_name)


    # ip contact
    all_commands['ip_contact'] = Command(
        ("ip", "contact"), HostName(), Contact())
    def ip_contact(self, operator, name, contact):
        owner_id = self.mb_utils.find_target_by_parsing(name, dns.DNS_OWNER)
        operation = self.mb_utils.alter_entity_note(
            owner_id, self.const.note_type_contact, contact)
        return "OK, %s contact for %s" % (operation, name)


    # ip free
    all_commands['ip_free'] = Command(
        ("ip", "free"), HostId(), Force(optional=True))
    def ip_free(self, operator, host_id, force=False):
        force = self.mb_utils.parse_force(force)
        tmp = host_id.split(".")
        if host_id.find(":") == -1 and tmp[-1].isdigit():
            # Freeing an ip-number
            self.mb_utils.ip_free(dns.IP_NUMBER, host_id, force)
            return "OK, IP-number %s completly removed" % host_id

        self.mb_utils.ip_free(dns.DNS_OWNER, host_id, force)
        return "OK, DNS-owner %s completly removed" % host_id

    # ip hinfo_list
    all_commands['ip_hinfo_list'] = Command(
        ("ip", "hinfo_list"), 
        fs=FormatSuggestion("%-10s %-10s %-10s",
                            ('hinfo.code', 'hinfo.os', 'hinfo.cpu'),
                            hdr="%-10s %-10s %-10s" % ('Code', 'OS', 'CPU')))
    def ip_hinfo_list(self, operator):
        ret = []
        for row in self.const.HinfoCode.list(self.db):
            ret.append({'hinfo.code': row['code_str'],
                        'hinfo.os': row['os'],
                        'hinfo.cpu': row['cpu']})
        return ret

    # ip hinfo_set
    all_commands['ip_hinfo_set'] = Command(
        ("ip", "hinfo_set"), HostName(), Hinfo())
    def ip_hinfo_set(self, operator, host_name, hinfo):
        hinfo = self._map_hinfo_code(hinfo)
        owner_id = self.mb_utils.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        host = HostInfo.HostInfo(self.db)
        host.find_by_dns_owner_id(owner_id)
        host.hinfo = hinfo
        host.write_db()
        return "OK, hinfo set for %s" % host_name

    # ip info
    all_commands['ip_info'] = Command(
        ("ip", "info"), HostId(),
        fs=FormatSuggestion([("  %-20s %s %s",
                              ('name', 'ip', 'a_comment'), "%-22s IP" % 'A-records'),
                             ("  %-20s %s", ('rev_ip', 'rev_name'), "Rev-map override:"),
                             ("%-22s %s" % ("Name:", "%s"),
                              ('dns_owner', )),
                             ("%-22s %s\n%-22s %s\n%-22s %s" % (
        'Hinfo:', 'os=%s cpu=%s (code=%s)',
        ' ', 'contact=%s', ' ', 'owner=%s'),
                              ('hinfo.os', 'hinfo.cpu', 'hinfo.code',
                               'host_contact', 'host_comment')),
                             ("%-22s %s" % ("MX-set:", "%s"), ('mx_set',)),
                             ("%-22s %s" % ("TXT:", "%s"), ('txt', )),
                             ("%-22s %s" % ('Cname:', '%s -> %s %s'),
                              ('cname', 'cname_target', 'cname_comment')),
                             ("SRV: %s %i %i %i %s %s", ('srv_owner', 'srv_pri',
                                          'srv_weight', 'srv_port',
                                          'srv_ttl', 'srv_target'))]))
    def ip_info(self, operator, host_id):
        # TODO: fikse formateringen av output fra denne komandoen

        arecord = ARecord.ARecord(self.db)
        tmp = host_id.split(".")
        if host_id.find(":") == -1 and tmp[-1].isdigit():
            # When host_id is an IP, we only return A-records
            owner_id = self.mb_utils.find_target_by_parsing(
                host_id, dns.IP_NUMBER)
            ret = []
            for a in arecord.list_ext(ip_number_id=owner_id):
                ret.append({'ip': a['a_ip'], 'name': a['name'],
                        'a_comment': ''})
            return ret

        owner_id = self.mb_utils.find_target_by_parsing(
            host_id, dns.DNS_OWNER)
        dns_owner = DnsOwner.DnsOwner(self.db)
        dns_owner.find(owner_id)

        # TOOD: Bedre måte å vise contact + comment for A-records,
        # hosts og cnames

        # HINFO records
        ret = []
        try:
            ret.append({'dns_owner': dns_owner.name})
            
            host = HostInfo.HostInfo(self.db)
            host.find_by_dns_owner_id(owner_id)
            hinfo = self._map_hinfo_code(int(host.hinfo))
            ret.append({'hinfo.os': hinfo.os,
                        'hinfo.cpu': hinfo.cpu,
                        'hinfo.code': str(hinfo),
                        'host_comment': None,
                        'host_contact': None})
            try:
                ret[-1]['host_comment'] = host.get_entity_note(
                    self.const.note_type_comment, host.entity_id)
            except Errors.NotFoundError:
                pass
            try:
                ret[-1]['host_contact'] = host.get_entity_note(
                    self.const.note_type_contact, host.entity_id)
            except Errors.NotFoundError:
                pass

            txt = dns_owner.list_ttl_records(
                field_type=self.const.field_type_txt,
                dns_owner_id=dns_owner.entity_id)
            if txt:
                ret.append({'txt': txt[0]['data']})
        except Errors.NotFoundError:  # not found
            pass

        forward_ips = []
        # A records
        for a in arecord.list_ext(dns_owner_id=owner_id):
            forward_ips.append((a['a_ip'], a['ip_number_id']))
            ret.append({'ip': a['a_ip'], 'name': a['name'], 'a_comment': ''})
            try:
                ret[-1]['a_comment'] = "(%s)" % arecord.get_entity_note(
                    self.const.note_type_comment, a['a_record_id'])
            except Errors.NotFoundError: 
                pass

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
                    'cname_target': c['target_name'],
                    'cname_comment': ''})
            try:
                row['cname_comment'] = "(%s)" % cname.get_entity_note(
                    self.const.note_type_comment, c['cname_id'])
            except Errors.NotFoundError:  # not found
                pass
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

    # ip list_free
    all_commands['ip_list_free'] = Command(
        ("ip", "list_free"), SubNetOrIP(),
        fs=FormatSuggestion("%s", ('ip',), hdr="Ip"))
    def ip_list_free(self, operator, subnet):
        # TODO: Skal det være mulig å få listet ut ledige reserved IP?
        subnet, ip, ip_ref = self.mb_utils.parse_subnet_or_ip(subnet)
        ret = []
        for ip in self.mb_utils.find_free_ip(subnet):
            ret.append({'ip': ip})
        return ret

    # ip mx_add
    all_commands['ip_mx_add'] = Command(
        ("ip", "mx_add"), MXSet(), Priority(), HostName())
    def ip_mx_add(self, operator, mx_set, priority, host_name):
        host_ref = self.mb_utils.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        self.mb_utils.mx_set_add(mx_set, priority, host_ref)
        return "OK, added %s to mx_set %s" % (host_name, mx_set)

    # ip mx_del
    all_commands['ip_mx_del'] = Command(
        ("ip", "mx_del"), MXSet(), HostName())
    def ip_mx_del(self, operator, mx_set, target_host_name):
        host_ref = self.mb_utils.find_target_by_parsing(
            target_host_name, dns.DNS_OWNER)
        self.mb_utils.mx_set_del(mx_set, host_ref)
        return "OK, deleted %s from mx_set %s" % (target_host_name, mx_set)

    # ip mx_list
    all_commands['ip_mx_list'] = Command(
        ("ip", "mx_list"), 
        fs=FormatSuggestion("%s", ('mx_set',),
                            hdr="%s" % ('Name')))
    def ip_mx_list(self, operator):
        m = DnsOwner.MXSet(self.db)
        ret = []
        for row in m.list():
            ret.append({'mx_set': row['name']})
        return ret

    # ip mx_set
    all_commands['ip_mx_set'] = Command(
        ("ip", "mx_set"), HostName(), MXSet())
    def ip_mx_set(self, operator, name, mx_set):
        owner_id = self.mb_utils.find_target_by_parsing(
            name, dns.DNS_OWNER)
        dns_owner = DnsOwner.DnsOwner(self.db)
        dns._ownerfind(owner_id)
        dns_owner.mx_set_id = self.mb_utils.find_mx_set(mx_set)
        dns_owner.write_db()
        return "OK, mx set for %s" % name

    # ip mx_show
    all_commands['ip_mx_show'] = Command(
        ("ip", "mx_show"), MXSet(),
        fs=FormatSuggestion("%-20s %-12s %-10i %s",
                            ('mx_set', 'ttl', 'pri', 'target'),
                            hdr="%-20s %-12s %-10s %s" % (
        'MX-set', 'TTL', 'Priority', 'Target')))
    def ip_mx_show(self, operator, mx_set):
        m = DnsOwner.MXSet(self.db)
        try:
            m.find_by_name(mx_set)
        except Errors.NotFoundError:
            raise CerebrumError, "No mx-set with name %s" % mx_set
        ret = []
        for row in m.list_mx_sets(mx_set_id=m.mx_set_id):
            ret.append({'mx_set': m.name,
                        'ttl': int_or_none_as_str(row['ttl']),
                        'pri': row['pri'],
                        'target': row['target_name']})
        return ret

    # ip rename
    all_commands['ip_rename'] = Command(
        ("ip", "rename"), HostId(), HostId())
    def ip_rename(self, operator, old_id, new_id):
        tmp = new_id.split(".")

        # Rename by IP-number
        if new_id.find(":") == -1 and tmp[-1].isdigit():
            self.mb_utils.ip_rename(dns.IP_NUMBER, old_id, new_id)
            return "OK, ip-number %s renamed to %s" % (
                old_id, new_id)
        # Rename by dns-owner
        self.mb_utils.ip_rename(dns.DNS_OWNER, old_id, new_id)
        return "OK, dns-owner %s renamed to %s" % (old_id, new_id)

    # ip revmap_override
    all_commands['ip_revmap_override'] = Command(
        ("ip", "revmap_override"), HostId(),
        HostId(help_ref='new_host_id_or_clear'), Force(optional=True))
    def ip_revmap_override(self, operator, ip_host_id, dest_host, force=False):
        force = self.mb_utils.parse_force(force)
        ip_owner_id = self.mb_utils.find_target_by_parsing(
            ip_host_id, dns.IP_NUMBER)
        operation = self.mb_utils.register_revmap_override(
            ip_owner_id, dest_host, force)

        return "OK, %s reversemap override for %s" % (operation, ip_host_id)
        
    # ip srv_add
    all_commands['ip_srv_add'] = Command(
        ("ip", "srv_add"), ServiceName(), Priority(), Weight(),
        Port(), HostName())
    def ip_srv_add(self, operator, service_name, priority,
                   weight, port, target_name):
        target_id = self.mb_utils.find_target_by_parsing(
            target_name, dns.DNS_OWNER)
        self.mb_utils.alter_srv_record(
            'add', service_name, int(priority), int(weight),
            int(port), target_id)
        return "OK, added SRV record %s -> %s" % (service_name, target_name)

    # ip srv_del
    all_commands['ip_srv_del'] = Command(
        ("ip", "srv_del"), ServiceName(), TTL(), Priority(), Weight(),
        Port(), HostName())
    def ip_srv_del(self, operator, service_name, priority,
                   weight, port, target_name , ttl=None):
        target_id = self.mb_utils.find_target_by_parsing(
            target_name, dns.DNS_OWNER)
        if ttl:
            ttl = int(ttl)
        self.mb_utils.alter_srv_record(
            'del', service_name, int(priority), int(weight),
            int(port), target_id)
        return "OK, deletded SRV record %s -> %s" % (service_name, target_name)


    # ip ttl_set
    all_commands['ip_ttl_set'] = Command(
        ("ip", "ttl_set"), HostName(), TTL())
    def ip_ttl_set(self, operator, host_name, ttl):
        owner_id = self.mb_utils.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        if ttl:
            ttl = int(ttl)
        else:
            ttl = None
        operation = self.mb_utils.set_ttl(
            owner_id, ttl)
        return "OK, set TTL record for %s to %s" % (host_name, ttl)

    # ip txt
    all_commands['ip_txt_set'] = Command(
        ("ip", "txt_set"), HostName(), TXT())
    def ip_txt_set(self, operator, host_name, txt):
        owner_id = self.mb_utils.find_target_by_parsing(
            host_name, dns.DNS_OWNER)
        if ttl:
            ttl = int(ttl)
        else:
            ttl = None
        operation = self.mb_utils.alter_ttl_record(
            owner_id, int(self.const.field_type_txt), txt)
        return "OK, %s TXT record for %s" % (operation, host_name)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

if __name__ == '__main__':
    pass

# arch-tag: c8f44ecd-c4fb-464c-a871-e81768793319
