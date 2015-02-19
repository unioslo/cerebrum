#!/usr/local/perl5.00504/bin/perl5.00504 -00w

# diff two LDIF files and output an LDIF file to standard output.
# The resulting diff-file can be fed to ldapmodify -f diff-file.
# LDIF format is described in RFC 2849.
#
# Usage: diff-ldif [-v | -i{attr,attr...}]... old.ldif new.ldif > diff
#    -v               Visual comparison, not suitable for ldapmodify.
#    -i{attr,attr...} Ignore changes in the specified attributes.
#    An input file can be "-" for standard input.
#
# Case is significant except in DNs of entries and partly attribute names.
# Values are not normalized.  Nor base64-decoded, except DNs of entries.
# So "cn: Foo" does not match "cn: foo".
# With the -v (Visual) option, values are base64-decoded, DN-valued attributes
#   are partly normalized, and case in attribute names is normalized.

# Author: Hallvard B Furuseth <h.b.furuseth@usit.uio.no>
# Modified: Oct 2004
# Please report changes back to me so we can keep one single version.
# Should probably put it in Cerebrum or OpenLDAP or something.


#use bytes;# Prevent recent Perls from translating to Unicode.  NOTE: Does not
           # work on perl5.8.0, instead unset the locale environment variables.
# Perl5.6's forced UTF-8 support was a total trainwreck and we haven't
# tested how much more trustable 5.8 is, so we use 5.00504 which has no
# clever notions about what character set the user wants.

# Copied from Leetah

use strict;
use MIME::Base64;

# Put this option in a constant, so tests for it is optimized away.
use constant Visual => scalar(grep $_ eq '-v', @ARGV);

my(%ignore);
while (@ARGV && $ARGV[0] =~ /^-(?:(v)|i(.+))$/) {
    @ignore{split(/,/, lc $2)} = () if $2;
    shift;
}
(@ARGV == 2 && $ARGV[0] !~ /^-./)
    or die "Usage: $0 [-v | -i{attr,attr...}]... old.ldif new.ldif\n";

# Keep values of these attributes ordered as in the source LDIF file
my %ordered_attr;
@ordered_attr{map lc($_),
	      qw(telephoneNumber facsimileTelephoneNumber)
	      } = ();

# These are attributes that have equality matching rules, which is
# necessary to use 'add:' to add a 2nd value of an attribute to an entry.
# Actually we only need this for attributes there can be a _lot_ of in an
# object, i.e. memberUid.
my %eq_attr;
@eq_attr{map lc($_),
	 qw(aliasedObjectName businessCategory cn dc description gecos
	    gidNumber givenName homeDirectory host l labeledURI loginShell
	    mail member memberNisNetgroup memberUid o objectClass ou owner
	    postOfficeBox postalCode roleOccupant seeAlso sn street
	    telephoneNumber title uid uidNumber uniqueIdentifier uniqueMember

	    norEduOrgUniqueNumber norEduOrgUnitUniqueNumber
	    norEduPersonBirthDate norEduPersonLIN norEduPersonNIN
	    norEduOrgAcronym

	    acronym birthDate norInstitutionNumber norOrgUnitNumber norSSN

	    eduOrgHomePageURI eduOrgIdentityAuthNPolicyURI eduOrgLegalName
	    eduOrgSuperiorURI eduOrgWhitePagesURI

	    eduPersonAffiliation eduPersonEntitlement eduPersonNickname
	    eduPersonOrgDN eduPersonOrgUnitDN eduPersonPrimaryAffiliation
	    eduPersonPrimaryOrgUnitDN eduPersonPrincipalName

	    defaultMailAddress forwardDestination forwardMailAddress hardQuota
	    IMAPserver mailPause softQuota spamAction spamLevel spoolInfo
	    target targetType tripnote tripnoteActive virusFound virusRemoved
	    virusScanning
	    )
	 } = ();
delete @eq_attr{keys %ordered_attr};

# Attributes that contain DNs
my %DN_attr;
@DN_attr{map lc($_),
	 qw(aliasedObjectName member owner roleOccupant seeAlso
	    eduPersonOrgDN eduPersonOrgUnitDN eduPersonPrimaryOrgUnitDN)
	 } = ();

# Convert reversed DN to private collating order.
# Each component in the reversed DN is separated by a \cA instead of ','.
sub collate_key {
    my($key) = @_;

    # Add aliases in ou=organization after the people they point at.
    # Add groups in ou=groups after the users they refer to.
    # Needed for consistency and because of an OpenLDAP bug (ITS#2186).
    $key =~ s/^((?:dc=[-\w]+\cA)+)ou=([ofg]\w+\cA)/$1z$2/;

    $key;
}


my(%old_entries, %new_entries, %keys);
for my $f ([$ARGV[0], \%old_entries], [$ARGV[1], \%new_entries]) {
    my($filename, $rec) = @$f;
    open(IN, "<$filename") or die "$filename: $!\n";
    while (<IN>) {
	s/\n //g;		# Remove line folding
	s/^\#.*\n//gm;		# Remove comments
	s/\A\n+|\n+\Z//g;	# Remove initial and trailing newlines
	next if $_ eq '';
	# One space after attr.names
	s/^(\w[-\w.\;]*:(?:[:<]|(?![:<])))(?:  +)?(?! )/$1 /gm;
	s/\Adn:/dn:/i;
	/\Adn:(:?) (.*)/ or bad_entry([0, $filename, $.], "No DN");
	my $key = lc($1 ? decode_base64($2) : $2);
	my @dn = reverse split(/ *, *(?=\w[-.\w]*=)/, $key);
	@dn = map join("\cB", sort split(/ *\+ *(?=\w[-.\w]*=)/)), @dn
	    if Visual && $key =~ /\+ *\w[-.\w]*=/;
	$key = collate_key(join("\cA", @dn));
	$rec->{$key} = [$_, $filename, $.];
	$keys{$key} = 0;
    }
    close(IN) or die "Error while reading $filename: $!\n";
}

# Print first additions (parents before children), then replacements (which may
# refer to the additions/deletions), then deletions (children before parents).
my $version = "version: 1\n\n";
my(@delete, @modify);
for my $key (sort keys %keys) {
    my $old_info = (delete($old_entries{$key}) || []);
    my $new_info = (delete($new_entries{$key}) || []);
    my $old_entry = $old_info->[0];
    my $new_entry = $new_info->[0];
    if (!$old_entry) {
	$new_entry =~ s/\A(dn:.*\n)/$1changetype: add\n/
	    or bad_entry($new_info, "No DN");
	print $version, $new_entry, "\n\n";
	$version = "";
    } elsif (!$new_entry) {
	$old_entry =~ /\A(dn:.*)/ or bad_entry($old_info, "No DN");
	push @delete, "$1\nchangetype: delete\n\n";
    } elsif ($new_entry ne $old_entry) {
	my(@ldif, $old_attrs, $new_attrs, %types);
	my(@del_add, @replace, @del, @add, $cmp, @old_vals, @new_vals);
	$old_attrs = parse_entry($old_entry, $old_info);
	$new_attrs = parse_entry($new_entry, $new_info);
	@types{keys(%$old_attrs), keys(%$new_attrs)} = ();
	for my $type (sort keys %types) {
	    next if exists $ignore{$type};
	    if (!exists $old_attrs->{$type}) {
		push @ldif, "add: $type\n", @{$new_attrs->{$type}}, "-\n";
	    } elsif (!exists $new_attrs->{$type}) {
		push @ldif, "delete: $type\n-\n";
	    } else {
		@old_vals = @{$old_attrs->{$type}};
		@new_vals = @{$new_attrs->{$type}};
		unless (exists $ordered_attr{$type}) {
		    @old_vals = sort @old_vals;
		    @new_vals = sort @new_vals;
		}
		next if (@old_vals == @new_vals
			 && join("", @old_vals) eq join("", @new_vals));

		# If the attribute has an equality matching rule, there
		# are two ways to effect this change: 'replace:', or
		# 'delete:' + 'add:'.  Compute both and pick the shortest.
		@replace = ("replace: $type\n", @new_vals, "-\n");
		@del_add = ();
		if (Visual
		    ? !exists $ordered_attr{$type}
		    : exists $eq_attr{$type})
		{
		    @del = @add = ();
		    while (@old_vals && @new_vals) {
			$cmp = ($old_vals[0] cmp $new_vals[0]);
			if ($cmp == 0) {
			    shift(@old_vals);
			    shift(@new_vals);
			} elsif ($cmp < 0) {
			    push(@del, shift(@old_vals));
			} else {
			    push(@add, shift(@new_vals));
			}
		    }
		    push(@del, @old_vals);
		    push(@add, @new_vals);
		    push @del_add, "delete: $type\n", @del, "-\n" if @del;
		    push @del_add, "add: $type\n",    @add, "-\n" if @add;
		    next unless @del_add;
		}
		# Pick the shortest set of commands
		push @ldif, ((@del_add <= @replace + (Visual ? 9 : 0)
			      && @del_add)
			     ? @del_add : @replace);
	    }
	}
	if (@ldif) {
	    $old_entry =~ /\A(dn::? .+\n)/
		or bad_entry($old_info, "No DN");
	    push @modify, $1, "changetype: modify\n", @ldif, "\n";
	}
    }
}
print $version, @modify, reverse(@delete) if @modify || @delete;


my %attr2attr;

sub parse_entry {
    my($entry, $info) = @_;
    my(%attrs, $attr);
    for my $line (split(/\n\b/, $entry)) {
	if (!Visual) {
	    $line =~ /\A(\w[-\w.\;]*):/s
		or bad_entry($info, "Syntax error");
	    push @{$attrs{lc $1}}, "$line\n";
	} else {
	    $line =~ /\A(\w[-\w.\;]*):(:?) *(?! )(.*)/s
		or bad_entry($info, "Syntax error");
	    $attr2attr{$attr = lc $1} ||= $1;
	    if ($2 || exists $DN_attr{$attr}) {
		my($raw, $val) = ($3, ($2 ? decode_base64($3) : $3));
		if (exists $DN_attr{$attr}) {
		    $val = join(",", map {
			(/\+/
			 ? join("+", sort map {
			     /\A(\w[-.\w]*)(=.*)\Z/s
				 or bad_entry($info, "Bad $attr2attr{$attr}");
			     ($attr2attr{lc $1} ||= $1) . $2;
			   } split(/ *\+ *(?=\w[-.\w]*=)/, $_))
			 : /\A(\w[-.\w]*)(=.*)\Z/s
			 ? ($attr2attr{lc $1} ||= $1) . $2
			 : bad_entry($info, "Bad $attr2attr{$attr}"));
		    } split(/ *, *(?=\w[-.\w]*=)/, $val));
		    undef $raw;
		}
		push(@{$attrs{$attr}},
		     ($val !~ /\A\s|[\0\n\r]|\s\z/
		      ? "$attr2attr{$attr}: $val\n"
		      : join('', $attr2attr{$attr}, ":: ",
			     (defined($raw) ? $raw : Base64($val)), "\n")));
	    } else {
		push @{$attrs{$attr}}, "$attr2attr{$attr}: $3\n";
	    }
	}
    }
    delete $attrs{'dn'};
    \%attrs;
}

sub Base64 {
    (my $b64 = encode_base64($_[0])) =~ tr/ \n\r//d;
    $b64;
}

sub bad_entry {
    my($filename, $num, $message) = (@{$_[0]}[1,2], $_[1]);
    die "$filename:entry \#$num: $message.\n";
}

# arch-tag: b6f6e0ba-b426-11da-9482-1d5a0f5505a3
