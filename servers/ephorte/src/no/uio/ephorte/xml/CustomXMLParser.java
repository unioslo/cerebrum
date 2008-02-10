package no.uio.ephorte.xml;

import java.io.File;
import java.io.IOException;
import java.util.Vector;

import javax.xml.parsers.ParserConfigurationException;
import javax.xml.parsers.SAXParser;
import javax.xml.parsers.SAXParserFactory;

import no.uio.ephorte.connection.EphorteGW;
import no.uio.ephorte.data.Adresse;
import no.uio.ephorte.data.BadDataException;
import no.uio.ephorte.data.Person;
//import no.uio.ephorte.data.OrgUnit;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.xml.sax.Attributes;
import org.xml.sax.SAXException;
import org.xml.sax.helpers.DefaultHandler;

/**
 * Parses the XML file to be imported, and generates a custom datastructure
 * representing its contents.
 * 
 * @author runefro
 * 
 */
public class CustomXMLParser {
    private Vector<Person> persons;
    //private Vector<OrgUnit> ous;
    Person tmpPerson;
    //OrgUnit tmpOrgUnit;
    // Hashtable<String, Person> potentialFeideId2Person = new Hashtable<String, Person>();
    private Log log = LogFactory.getLog(EphorteGW.class);

    class MyHandler extends DefaultHandler {
        @Override
        public void startElement(String uri, String localName, String qName, 
				 Attributes attr)
	    throws SAXException {
            // System.out.println("QN: " + qName);
	    //if ("ou".equals(qName)) {
	    //	tmpOrgUnit = new OrgUnit(attr.getValue("sko"), 
	    //				 attr.getValue("parent"),
	    //				 attr.getValue("akronym"), 
	    //				 attr.getValue("long"), 
	    //				 attr.getValue("journalEnhet"));
	    //	if ("1".equals(attr.getValue("delete"))) {
	    //	    tmpOrgUnit.setDeletable(true);
	    //	}
	    //	ous.add(tmpOrgUnit);
	    //} else if ("person".equals(qName)) {
	    if ("person".equals(qName)) {
                tmpPerson = new Person(attr.getValue("feide_id"), false);
                if ("1".equals(attr.getValue("delete"))) {
		    tmpPerson.setDeletable(true);
		}
                tmpPerson.addName(attr.getValue("initials"), 
				  attr.getValue("full_name"), 
				  attr.getValue("first_name"), 
				  null, 
				  attr.getValue("last_name"), 
				  "-1".equals(attr.getValue("PN_AKTIV")));
                tmpPerson.addAddress(Adresse.ADRTYPE_A, 
				     attr.getValue("full_name"), 
				     attr.getValue("address_text"), 
				     attr.getValue("postal_number"), 
				     attr.getValue("city"), 
				     attr.getValue("email"), 
				     attr.getValue("phone"));
                persons.add(tmpPerson);
            } else if ("roles".equals(qName)) {
                try {
                    tmpPerson.addRolle(attr.getValue("role_type"), 
				       "T".equals(attr.getValue("standard_role")), 
				       attr.getValue("adm_enhet"), 
				       attr.getValue("arkivdel"), 
				       attr.getValue("journalenhet"), 
				       attr.getValue("rolletittel"), 
				       attr.getValue("stilling"));
                } catch (BadDataException e) {
                    log.error("Caught BadDataException: " + e.toString() + " for "
			      + tmpPerson.getBrukerId());
                }
            } else if ("permissions".equals(qName)) {
		try {
		    // legge til start og sluttdato?
                    tmpPerson.addTgKode(attr.getValue("perm_type"),
					attr.getValue("adm_enhet"),
					attr.getValue("operator"));
                } catch (BadDataException e) {
                    log.error("Caught BadDataException: " + e.toString() + " for "
			      + tmpPerson.getBrukerId());
                }
            } else if ("potential_feideid".equals(qName)) {
            	//potentialFeideId2Person.put(attr.getValue("id"), tmpPerson);
            	tmpPerson.addPotentialFeideId(attr.getValue("id"));
            }
        }
    }

    public void parseFile(String fname) 
	throws SAXException, IOException, ParserConfigurationException 
    {
        SAXParserFactory factory = SAXParserFactory.newInstance();
        SAXParser sp = factory.newSAXParser();
        MyHandler mh = new MyHandler();
        sp.parse(new File(fname), mh);
    }

    public CustomXMLParser(String fname) 
	throws SAXException, IOException, ParserConfigurationException 
    {
        persons = new Vector<Person>();
        // ous = new Vector<OrgUnit>();
        parseFile(fname);
    }

    // public Vector<OrgUnit> getOrgUnits() {
    //     return ous;
    // }
    public Vector<Person> getPersons() {
        return persons;
    }
}
