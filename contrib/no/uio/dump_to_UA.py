#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

import cerebrum_path
import cereconf
import getopt
import sys
import time
import os
import ftplib
from xml.sax import parse, SAXParseException, ContentHandler

class LTParser( ContentHandler ):
    """This class is used to iterate over all users in LT, and get personnr,and map to tils:dato_fra and tils:dato_til """
    
    persons = {}
    current_p = None
    
    def __init__(self, filename):        
        parse(filename, self)
        
    def startElement(self, name, attrs):
        if name == "tils":
            if attrs.getValue('prosent_tilsetting').encode('iso8859-1') > self.persons[self.current_p]['tilsetting']:
                start=attrs.getValue('dato_fra').encode('iso8859-1')
                end=attrs.getValue('dato_til').encode('iso8859-1')
                self.persons[self.current_p]['startdato'] = "%s.%s.%s" % (start[6:],start[4:6],start[:4])
                self.persons[self.current_p]['sluttdato'] = "%s.%s.%s" % (end[6:],end[4:6],end[:4])
                self.persons[self.current_p]['arbsted'] = sko_format((attrs.getValue('fakultetnr_utgift').encode('iso8859-1'),attrs.getValue('instituttnr_utgift').encode('iso8859-1'),attrs.getValue('gruppenr_utgift').encode('iso8859-1')))
                self.persons[self.current_p]['tilsetting'] = attrs.getValue('prosent_tilsetting').encode('iso8859-1')
        elif name == "person":             
            try:
                fnavn = attrs.getValue('fornavn').upper().encode('iso8859-1')
                enavn = attrs.getValue('etternavn').upper().encode('iso8859-1')
                self.current_p = fnr_format(attrs.getValue('fodtdag').encode('iso8859-1'), attrs.getValue('fodtmnd').encode('iso8859-1'), attrs.getValue('fodtar').encode('iso8859-1'), attrs.getValue('personnr').encode('iso8859-1'))
                self.persons[self.current_p] = {'fname':fnavn,'lname':enavn,'tilsetting':'0'}
            except KeyError:
                pass
        else:
            pass     

def fnr_format(fdag,fmnd,faar,pnr): 
    return '%s%s%s%s' % (fdag.zfill(2),fmnd.zfill(2),faar.zfill(2),pnr.zfill(5))

def sko_format(tupl):
    sko = ''
    for t in tupl:
        sko = '%s%s' % (sko,t.zfill(2))
    return sko

    
def format_person(fnr,dta):

## Format: 
## 0: fødselsnummer, 1: systemnummer, 2: korttype, 3: fornavn, 4: etternavn
## 5..10: adgnivå 1..6,  11: sit-bet-semesteravgift, 12: betalingsdato
## 13: startdato, 14: sluttdato, 15: privattlf, 16: interntlf, 
## 17: avdelingsnr, 18: arbeidssted, 19: studieniva,
## 20..23: tilhørighet hjemmeaddr[1..4], 24..27: semesteraddr[1..4])
## 28..29: Ukjent.

    global korttype, systemnr
    
    felter = ['systemnr', 'korttype', 'fname', 'lname', 'adg1',
              'adg2', 'adg3', 'adg4', 'adg5', 'adg6', 'sistbetsem',
              'betdato', 'startdato', 'sluttdato', 'privtlf',
              'interntlf', 'avdnr', 'arbsted', 'tilhorighet',
              'hjemadr1', 'hjemadr2', 'hjemadr3', 'hjemadr4',
              'semadr1', 'semadr2', 'semadr3', 'semadr4']
    ret = ["%s%s" % (fnr,systemnr)]
    for f in felter:
        if f == 'systemnr':
            ret.append(systemnr)
        elif f == 'korttype':
            ret.append(korttype)
        else:
            ret.append(dta.get(f, ''))
    ret.append('')
    ret.append('')
    return ";".join(ret)


def do_sillydiff(dirname, oldfile, newfile, outfile):
    today = time.strftime("%d.%m.%Y")
    try:
        oldfile = file("%s/%s" % (dirname, oldfile))
        line = oldfile.readline()
        line.rstrip()
    except IOError:
        print "Warning, old file did not exist, assuming first run ever"
        os.link("%s/%s" % (dirname,newfile),"%s/%s" % (dirname, outfile))
        return

    old_dict = {}
    while line != "":
        old_dict[line[0:12]] = line[13:]
        line = oldfile.readline()        
        line.rstrip()           
    oldfile.close()


    out = file("%s/%s" % (dirname, outfile), 'w')
    newin = file("%s/%s" % (dirname, newfile))
    
    newline = newin.readline()        
    newline.rstrip()           
    while newline != "":
        pnr = newline[0:12]
        dta = newline[13:]
        if pnr in old_dict:
            if old_dict[pnr] != dta:
                #Some change, want to update with new values.
                out.write(newline)            
            del old_dict[pnr]
        else:
            out.write(newline)
        newline = newin.readline()        
        newline.rstrip()           

    for leftpnr in old_dict:
        vals = old_dict[leftpnr].split(";")
        vals[13] = today
        vals[17] = ""
        out.write("%s;%s" % (leftpnr,";".join(vals)))

    out.close()    
    newin.close()


def ftpput(host,uname,password,local_dir,file,dir):
    ftp=ftplib.FTP(host,uname,password)
    ftp.cwd(dir)
    ftp.storlines("STOR %s" % (file),open("%s/%s" % (local_dir,file)))
    ftp.quit()

        
def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'f:k:S:o:',
                                   ['sql-file=', 'kort-type=', 'system-nr=', 'out-dir='])
    except getopt.GetoptError:
        usage(1)

    global korttype, systemnr
    out_dir = None
    korttype = None
    systemnr = None
    sqlfile = None
    for opt, val in opts:
        if opt in ('-f', '--sql-file'):
            sqlfile = val
        elif opt in ('-k', '--kort-type'):
            korttype = val
        elif opt in ('-S', '--system-nr'):
            systemnr = val
        elif opt in ('-o', '--out-dir'):
            out_dir = val
    print out_dir    
    print sqlfile    

    if korttype is None or systemnr is None:
        print "Must set korttype and systemnr"
        sys.exit(1)
    LTParser(sqlfile)
    outfile = file("%s/%s" % (out_dir, "uadata.new"), 'w')
    for pers in LTParser.persons:
        if len(LTParser.persons[pers].items()) >= 4:
            form = format_person(pers.encode('iso8859-1'),LTParser.persons[pers])
            outfile.write(form+'\n')
    outfile.close()
    diff_file = "uadata.%s" % (time.strftime("%Y-%m-%d"))
    do_sillydiff(out_dir, "uadata.old", "uadata.new", diff_file)
    os.rename("%s/uadata.new" % out_dir, "%s/uadata.old" % out_dir)
    ftpput("heimdall.ua.uio.no","ltimport","nOureg289337",out_dir,diff_file,"ua-lt")    

    
def usage(exitcode=0):
    print """Usage: dump_to_UA.py [options]
    -o | --out-dir name: dump to this directory
    -S | --system-nr nr: systemnr (UA begrep)
    -k | --kort-type kt: kort type (UA begrep)

    Example: dump_to_UA.py -o /tmp -S 2 -k 'Tilsatt UiO'

    """
    sys.exit(exitcode)


if __name__ == '__main__':
    main()
