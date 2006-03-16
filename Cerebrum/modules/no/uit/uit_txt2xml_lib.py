#-*- coding: iso-8859-1 -*-
#!/usr/bin/env python
######################################################################
## Filename:      fstalk.py
## Description:   
## Author:        Tom-Anders N. Røst <trost@student.uit.no>
## Modified at:   Fri Oct 10 15:47:54 2003
## Modified by:   Tom-Anders N. Røst <trost@student.uit.no>
##                
## $Id$
##                
######################################################################

#import DCOracle2
import thread
import time
from string import *
import xml.sax
import xml.sax.handler
from xml.dom.minidom import Document
import cereconf
import sys
#sys.path = ['/home/cerebrum/CVS/cerebrum/contrib/no/uit/create_import_data/lib'] + sys.path
#from ll import ansistyle


class PropHandler(xml.sax.handler.ContentHandler):
  def __init__(self):
      self.i = 0
      self.buffer = ""
      self.inSide = 0
      self.properties = {}
      self.tags = {'hostname' : 'self.inHost = 1',
                   'username' : 'self.inUsername = 1',
                   'passwd' : 'self.inPasswd = 1',
                   'logfile' : 'self.inLogfile = 1',
                   'oufile' : 'self.inOu = 1',
                   'persfile' : 'self.inPers = 1',
                   'studfile' : 'self.inStud = 1'
                   }
  def printI(self, where):
      self.i += 1
      print "%s:%s" % (self.i, where)
      
  def startElement(self, name, attributes):
      if self.tags.has_key(name):
          self.inSide = 1
          self.buffer = ""
          
          #print self.buffer

  def characters(self, data):
      if self.inSide:
          self.buffer += data
 
  def endElement(self, name):
      if self.tags.has_key(name):
          self.properties[name] = self.buffer
          self.inSide = 0
      
class buildXmlStructure(xml.sax.handler.ContentHandler):
    def __init__(self, filename):
        self.struct = {}
        self.node = ""
        self.attrib = []

    
class FSImport:
    def __init__(self):
	pass
        #self.readConfig("/cerebrum/lib/python2.3/site-packages/Cerebrum/modules/no/uit/uit_txt2xml_config.xml")
            
    def readConfig(self, filename):
      parser = xml.sax.make_parser()
      handler = PropHandler()
      parser.setContentHandler(handler)
      parser.parse(filename)
      self.properties = handler.properties
      
      return 1


    def writeXML(self, what, fs_data, file=""):
	'''write to XML after dtd'''

	global doc
	doc = Document()
        
        def writeElem(param, parent=doc):
            global doc

            #writing new elem in Document
            #print "param = %s" % param
            node = doc.createElement(param['name'])
            #if element has attributes write them
            if param['attr'] != 'None':
                for attrib in param['attr'].keys():
                    node.setAttribute(attrib, param['attr'][attrib])
            #add this too the parent node
            parent.appendChild(node)

            #if children do it again.
            if param['child'] != 'None':
                parent = node
                for elem in param['child']:
                    writeElem(elem, parent)
            else:
                return 'done'

        
        #call to the recursive func.
        if what == 'person':
          dtd = self.studXML()  
          fila = open(self.properties['persfile'], 'w')
        elif what == 'ou':
          dtd = self.ouXML()
          fila = open(self.properties['oufile'], 'w')
        elif what == 'studprog':
          dtd = self.studieprogXML()
          fila = open(self.properties['studfile'], 'w')
        elif what == 'kenny':
          #dtd = self.testXML(fs_data)
          dtd = fs_data
          #print dtd
          fila = open(file, 'w')

        writeElem(dtd)
	#print "### %s" % fila
        enc = 'iso-8859-1'
	doc.writexml(fila,encoding=enc,indent="  ",newl="\n")
	#print doc.toprettyxml(indent="  ")

        
    def persXML(self):
      """not implemented"""
      return 0

    def studXML(self):
      #Cerebrum XML
      '''
      <data>
      <person fodselsdato="180879" personnr="36585">
       <aktiv fornavn="Calvin Esben" etternavn="Krogh"  faknr="30" instituttnr="0"
         institusjonsnr="186" gruppenr="10" adrlin1_semadr=""
         adrlin2_semadr="Peder Hanssens Gate 11" adrlin3_semadr="9009 TROMSØ "
         postnr_semadr="9009" adresseland_semadr=""/>
       </aktiv>
      </person>
      </data>
      '''
      
      #FS attribs
      '''p.fodselsdato, p.personnr,p.fornavn, p.ETTERNAVN, r.arstall, r.terminkode, \
      r.faknr_stemmerett, r.instituttnr_stemmerett, s.adrlin1_semadr, s.adrlin2_semadr, \
      s.adrlin3_semadr, s.postnr_semadr,s.adresseland_semadr, p.EMAILADRESSe\
      r.institusjonsnr_stemmerett, r.gruppenr_stemmerett'''


      #the FSquery
      query = "SELECT p.fodselsdato, p.personnr, p.fornavn, p.ETTERNAVN, r.arstall, r.terminkode, r.faknr_stemmerett, r.instituttnr_stemmerett, s.adrlin1_semadr, s.adrlin2_semadr, s.adrlin3_semadr, s.postnr_semadr,s.adresseland_semadr, p.EMAILADRESSe, r.institusjonsnr_stemmerett, r.gruppenr_stemmerett FROM fs.registerkort r, fs.person p, fs.student s \
WHERE (r.arstall = '2003' AND r.terminkode = 'HØST' AND r.regformkode <> 'KUNBETALT' AND r.fodselsdato = p.fodselsdato and r.personnr = p.personnr AND r.fodselsdato = s.fodselsdato and r.personnr = s.personnr) OR (r.arstall = '2003' AND r.terminkode = 'VÅR' AND r.regformkode <> 'KUNBETALT' AND r.fodselsdato = p.fodselsdato and r.personnr = p.personnr AND r.fodselsdato = s.fodselsdato and r.personnr = s.personnr)"

      fsdata = self.getFSdata(query)
      
      # {xml:attrib}
      attribMatchPerson =  {'fodselsdato':'fodselsdato',
                            'personnr':'personnr'
                            }
      
      attribMatchAktiv = {'fornavn':'fornavn',
                          'etternavn':'etternavn',
                          'faknr':'faknr_stemmerett',
                          'instituttnr':'INSTITUTTNR_STEMMERETT',
                          'institusjonsnr' : 'INSTITUSJONSNR_STEMMERETT',
                          'gruppenr': 'gruppenr_stemmerett',
                          'adrlin1_semadr': 'adrlin1_semadr',
                          'adrlin2_semadr': 'adrlin2_semadr',
                          'adrlin3_semadr': 'ADRLIN3_SEMADR',
                          'postnr_semadr': 'postnr_semadr',
                          'adresseland_semadr' :'adresseland_semadr' 
                          }

      #the dtd for the students..
      aktivAttr = ['fornavn', 'etternavn', 'faknr', 'instituttnr',
                   'institusjonsnr', 'gruppenr', 'adrlin1_semadr',
                   'adrlin2_semadr', 'adrlin3_semadr', 'postnr_semadr',
                   'adresseland_semadr'
                   ]
      personAttr = ['fodselsdato', 'personnr']
      
      heritage = {'name' : 'data', 'attr' : 'None',
                  'child' :
                  [{'name' : 'person', 'attr' : personAttr,
                    'child' :
                    [{'name' : 'aktiv', 'attr' : aktivAttr, 'child':'None'}
                     ]
                    }
                   ]
                  }        

      #build the datasource for the xml
      persons = []
      
      for item in fsdata:
        pattr = {}
        aattr = {}
        person = {'name' : 'person'}
        aktiv = {'name' : 'aktiv'}
        
        #build the person attributes
        for item2 in attribMatchPerson.keys():
          pattr[item2] = str(item[attribMatchPerson[item2].upper()])
          
        person['attr'] = pattr
        person['child'] = []

        #find attributes of the children of person, aktiv
        for item2 in attribMatchAktiv.keys():
          aattr[item2] = str(item[attribMatchAktiv[item2].upper()])
        
        aktiv['attr'] = aattr
        aktiv['child'] = 'None'
        person['child'].append(aktiv)

        persons.append(person)
        
      xmldtd = {'name' : 'data', 'attr' : 'None',
                  'child' : persons}
      return xmldtd


    def testXML(self,fs_data):
      """
      <data>
      <sted fakultetnr="ff" instituttnr="ii" gruppenr="gg"
      forkstednavn="foo" stednavn="foo bar" akronym="fb"
      stedkortnavn_bokmal="fooen" stedkortnavn_nynorsk="fooa"
      stedkortnavn_engelsk="thefoo"
      stedlangnavn_bokmal="foo baren" stedlangnavn_nynorsk="foo bara"
      stedlangnavn_engelsk="the foo bar"
      fakultetnr_for_org_sted="FF" instituttnr_for_org_sted="II"
      gruppenr_for_org_sted="GG"
      opprettetmerke_for_oppf_i_kat="X"
      telefonnr="22851234" innvalgnr="228" linjenr="51234"
      stedpostboks="1023"
      adrtypekode_besok_adr="INT" adresselinje1_besok_adr="adr1_besok"
      adresselinje2_besok_adr="adr2_besok"
      poststednr_besok_adr="postnr_besok"
      poststednavn_besok_adr="postnavn_besok" landnavn_besok_adr="ITALIA"
      adrtypekode_intern_adr="INT" adresselinje1_intern_adr="adr1_int"
      adresselinje2_intern_adr="adr2_int"
      poststednr_intern_adr="postnr_int"
      poststednavn_intern_adr="postnavn_int" landnavn_intern_adr="ITALIA"
      adrtypekode_alternativ_adr="INT"
      adresselinje1_alternativ_adr="adr1_alt"
      adresselinje2_alternativ_adr="adr2_alt"
      poststednr_alternativ_adr="postnr_alt"
      poststednavn_alternativ_adr="postnavn_alt"
      landnavn_alternativ_adr="ITALIA">
      <komm kommtypekode=("EKSTRA TLF" | "FAX" | "FAXUTLAND" | "JOBBTLFUTL" |
      "EPOST")
      telefonnr="foo" kommnrverdi="bar">
      </komm>
      </sted>
      </data>"""
      


      heritage = {'name' : 'data', 'attr' : 'None','child' :
                 [{'name' : 'sted', 'attr' :
                   fs_data.keys(),'child' : 'None'}]}
     
      #build the datasource for the xml
      ous = []
    
      #for item in fs_data:
      sattr = {}
        
      sted = {'name' : 'sted'}
      #del(fs_data['temp_inst_nr'])
      #build the person attributes
      for item2 in fs_data.keys():
          sattr[item2] = str(fs_data[item2].upper())
          
      #rof
      sted['attr'] = sattr
      sted['child'] = 'None'
      ous.append(sted)
      #rof
       
      xmldtd = {'name' : 'data', 'attr' : 'None',
                 'child' : ous}
       
      return xmldtd


    
    def ouXML(self):
      """
      <data>
      <sted akronym="UBTØ" forkstednavn="UB-Tromsø"
      instituttnr="0" telefonnr="776440\ 00" postnr="9037"
      stednavn="Universitetsbiblioteket i Tromsø" fakultetnr_for_or\
      g_sted="0" instituttnr_for_org_sted="0"
      gruppenr_for_org_sted="0" gruppenr="0" \ fakultetnr="2" >
      </sted>
      </data>
      """

      
      #get the data from FS.
      query = "SELECT stedakronym, stedkortnavn, instituttnr, telefonnr, postnr, stednavn_bokmal, faknr_org_under, instituttnr_org_under, gruppenr_org_under, gruppenr, faknr FROM fs.sted "

      fsdata = self.getFSdata(query)

      #the match xml-props against DBvalues
      attribMatchSted = {'akronym':'stedakronym',
                         'forkstednavn':'stedkortnavn',
                         'instituttnr':'instituttnr',
                         'telefonnr':'telefonnr',
                         'postnr':'postnr',
                         'stednavn':'stednavn_bokmal',
                         'fakultetnr_for_org_sted':'faknr_org_under',
                         'instituttnr_for_org_sted':'instituttnr_org_under',
                         'gruppenr_for_org_sted':'gruppenr_org_under',
                         'gruppenr':'gruppenr',
                         'fakultetnr':'faknr'
                         }


      heritage = {'name' : 'data', 'attr' : 'None',
                  'child' :
                  [{'name' : 'sted', 'attr' : attribMatchSted.keys(),
                    'child' : 'None'}]
                  }
      
      #build the datasource for the xml
      ous = []
      
      for item in fsdata:
        sattr = {}
        
        sted = {'name' : 'sted'}
        
        #build the person attributes
        for item2 in attribMatchSted.keys():
          sattr[item2] = str(item[attribMatchSted[item2].upper()])
          
        #rof
        sted['attr'] = sattr
        sted['child'] = 'None'
        ous.append(sted)
      #rof
      
      xmldtd = {'name' : 'data', 'attr' : 'None',
                'child' : ous}

      return xmldtd

    def studieprogXML(self):
      """
      <?xml version="1.0" encoding="ISO-8859-1"?>
      <data>                                            
      <studprog status_utdplan="N" studieprogramkode="ALITTDG"     
      instituttnr_studieansv="15" gruppenr_studieansv="0"
      faknr_studieansv="66" />
      """
      
      #get the data from FS.
      query = "SELECT status_utdplan, studieprogramkode, instituttnr_studieansv, \
      gruppenr_studieansv, faknr_studieansv FROM studieprogram "

      fsdata = self.getFSdata(query)

      #the match xml-props against DBvalues
      attribMatchStudProg = {'status_utdplan':'status_utdplan',
                             'studieprogramkode':'studieprogramkode',
                             'instituttnr_studieansv':'Instituttnr_Studieansv',
                             'gruppenr_studieansv' : 'Gruppenr_Studieansv',
                             'faknr_studieansv':'Faknr_Studieansv'
                             }


      heritage = {'name' : 'data', 'attr' : 'None',
                  'child' :
                  [{'name' : 'studprog', 'attr' : attribMatchStudProg.keys(),
                    'child' : 'None'}]
                  }
      
      #build the datasource for the xml
      studprogs = []
      
      for item in fsdata:
        sattr = {}
        
        studprog = {'name' : 'studprog'}
        
        #build the person attributes
        for item2 in attribMatchSted.keys():
          sattr[item2] = str(item[attribMatchStudProg[item2].upper()])
          
        #rof
        studprog['attr'] = sattr
        studprog['child'] = 'None'
        studprogs.append(sted)
      #rof
      
      xmldtd = {'name' : 'data', 'attr' : 'None',
                'child' : studprogs}

      return xmldtd

    

      
    def getFSdata(self, query):
      '''takes a query as input and returns a list of dicts with key:value'''
      
      db = DCOracle2.connect('fskurs/fskurs@FSKURS')
      c = db.cursor()
      c.execute(query)

      attribs = c.describe()
      
      struct = {}
      foo = []
      list = c.fetchall()
      
      for elem in list:
        j = 0
        for value in elem:
          struct[attribs[j][0]] = value
          j += 1
        #rof
        foo.append(struct)
        struct = {}
      #rof
      
      return foo
      
class CLI:
    def __init__(self):
        #testing ansicolors..
        #self.s = ansistyle.Stream(sys.stdout)
        
        self.FSlink = FSImport()

        self.commands = {
            'set' :
            {'function' : 'self.setProp', 'help' : "set <property> <value>"},
            'fsdump' :
            {'function' : 'self.fsdump', 'help' : 'Get info from FS and dump to XMLfiles'
             },
            'help' :
            {'function' : 'self.help', 'help' : 'help'}
            }


        #fire up the CLI
        self.run()

    def printColorHeading(self, string):
        self.s.pushcolor(0xe)
        self.s.write(string)
        self.s.popcolor()
        self.s.finish()
        self.s.write("\n")

    def help(self, *args):
        if len(args) == 0:
          #self.printColorHeading('functions:')
            #print "functions:"
            for elem in self.commands.keys():
                print "%s " % elem
            print "\nfor details use help <command>"
        else:
            if self.commands.has_key(args[0]):
                print "func: %s: %s " % (args[0], self.commands[args[0]]['help'])
            else:
                print "command: [%s] not found" % args[0]
            
    def setProp(self, *args):
        print "not implemented\n"
        return 0
        

    def fsdump(self, *args):
        #self.FSlink.writeXML('kenny')
        self.FSlink.writeXML('student.xml', 'test')

        return 0
    
    def run(self):

        welcomeText = "Welcome to the FStalk\n"
        prompt = '>'
        
        # __--__mainloop__--__
        print welcomeText
        while 1:
            try:
                text = raw_input(prompt)
            except:
                break

            splittext = text.split(" ")
            if(self.commands.has_key(splittext[0])):
                if (len(splittext) > 1):
                    #[0] = function name, [1:] arguments                    
                    apply(eval(self.commands[splittext[0]]['function']), splittext[1:])
                
                else:
                    apply(eval(self.commands[splittext[0]]['function']))
                #esle
            elif(text == 'exit'):
                print "leaving\n"
                break
            else:
                print"err: command not found"



if __name__ == "__main__":
            
    #check switches

    #run the cli
    cli = CLI()
