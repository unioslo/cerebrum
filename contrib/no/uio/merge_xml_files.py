#!/usr/bin/env python2.2

import getopt
import xml.sax
import sys
from Cerebrum.Utils import XMLHelper

class CollectParser(xml.sax.ContentHandler):
    def __init__(self, filename, results, hash_keys):
        self.results = results
        self.level = 0
        self.hash_keys = hash_keys
        xml.sax.parse(filename, self)
        
    def startElement(self, name, attrs):
        self.level += 1
        if self.level > 1:
            tmp = {}
            hash_key = "¦".join([attrs[x].encode('iso8859-1') for x in self.hash_keys])
            for k in attrs.keys():
                if k not in self.hash_keys:
                    tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
            tmp['TagName'] = name.encode('iso8859-1')
            self.results.setdefault(hash_key, []).append(tmp)
    
    def endElement(self, name):
        self.level -= 1
        pass

def usage(exitcode=0):
    print """Usage: [options]

Merges data from several XML files into one big XML file.  The XML
files should look something like:

  <data><tag-to-merge common_key1="foo" common_key2="bar"></data>

For entities on level 2 (tag-to-merge above), the common_key(s)
are used as a key in an internal hash (with attributes as value),
which will contain data from all processed XML files.  Once all
files are parsed, the new XML file is written from this hash.

-t | -tag tag: name of tag in output file
-d | -delim delim: name of attribute(s) to use as common_key separated by :
-f | -file file: file to parse
-o | -out file: file to write

-d and -f can be repeated.  The last -d is used as attribute names for
the -t tag.

Example:
merge_xml_files.py -d fodselsdato:personnr -f person_file.xml -f regkort.xml -t person -o out.dat

Note that memory usage may equal the total size of all XML files."""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'd:f:o:t:', ['delim=', 'file=', 'out=', 'tag='])
    except getopt.GetoptError:
        usage(2)
        
    big_xml = {}
    for opt, val in opts:
        if opt in ('-t', '--tag'):
            tag = val
        elif opt in ('-d', '--delim'):
            delim = val.split(":")
        elif opt in ('-f', '--file'):
            CollectParser(val, big_xml, delim)
        elif opt in ('-o', '--out'):
            f=open(val, 'w')
            xml = XMLHelper()
            f.write(xml.xml_hdr + "<data>\n")
            for bx_key in big_xml.keys():
                bx_delim = bx_key.split("¦")
                f.write("<%s %s>\n" % (
                    tag, " ".join(["%s=%s" % (
                    delim[n], xml.escape_xml_attr(bx_delim[n])) for n in range(len(delim))])))
                for tmp_tag in big_xml[bx_key]:
                    tmp = tmp_tag['TagName']
                    del(tmp_tag['TagName'])

                    f.write("  <%s %s/>\n" % (
                        tmp, " ".join(["%s=%s" % (
                        tk, xml.escape_xml_attr(tmp_tag[tk])) for tk in tmp_tag.keys()])))

                f.write("</%s>\n" % tag)
            f.write("</data>\n")
            f.close()

if __name__ == '__main__':
    main()
