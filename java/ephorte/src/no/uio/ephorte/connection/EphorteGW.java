package no.uio.ephorte.connection;

import java.rmi.RemoteException;
import java.util.Date;
import java.util.Hashtable;
//import java.util.Iterator;
import java.util.Properties;

import no.uio.ephorte.data.Adresse;
import no.uio.ephorte.data.Person;
import no.uio.ephorte.data.PersonRolle;
import no.uio.ephorte.xml.XMLUtil;

import org.apache.axis.AxisFault;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

/**
 * Performs the actual logic to sync data from the XML file with ePhorte.
 * 
 * @author runefro
 * 
 */
public class EphorteGW {
    // Set to true to perform off-line debugging
    private final static boolean USE_DEBUG_CONNECTION = false;

    Hashtable<String, Person> brukerId2Person;
    EphorteConnection conn;
    private Log log = LogFactory.getLog(EphorteGW.class);

    public EphorteGW() {
        this(null);
    }

    public EphorteGW(Properties props) {
        brukerId2Person = new Hashtable<String, Person>();
        if (USE_DEBUG_CONNECTION) {
            conn = new EphorteConnectionTest();
        } else {
            conn = new EphorteConnectionImpl(props);
        }
    }
    
    /**
     * Must be called prior to using the update functions 
     */
    public void prepareSync() {
        try {
            fetchPersons();
        } catch (RemoteException e) {
            e.printStackTrace();
        } catch (TooManyRecordsException e) {
            log.error(e.toString());
        }
    }

    /**
     * Henter ut informasjon om definerte personer++ i ePhorte. Såvidt vi vet,
     * er det stort sett kun GetDataSet som kan benyttes til å liste data i
     * ePhorte, og denne metoden returnerer en relativt rå dump av en enkelt
     * tabell i basen. Vi må derfor dumpe flere tabeller, og skjøte sammen data
     * manuelt basert på kjennskap til fremmednøkler i datamodellen.
     * 
     */
private void fetchPersons() throws RemoteException, TooManyRecordsException {
        /*
         * Følgende er eksempler på datastrukturer returnert med ePhortes
         * GetDataSet metode der criteriaCollectionString er angitt f.eks som
         * "object=adrperson".
         */
        /*
         * <Person> <PE_BRUKERID>IWONARL</PE_BRUKERID>
         * <PE_FRADATO>2007-04-27T00:00:00+02:00</PE_FRADATO> <PE_ID>51</PE_ID>
         * <PE_REDALLEROLLER_G>0</PE_REDALLEROLLER_G> </Person>
         * 
         * <PerNavn> <PN_AKTIV>-1</PN_AKTIV> <PN_ETTERNAVN>Langdalen</PN_ETTERNAVN>
         * <PN_FORNAVN>Iwona</PN_FORNAVN> <PN_FRADATO>2007-04-27T00:00:00+02:00</PN_FRADATO>
         * <PN_ID>101</PN_ID> <PN_INIT>IWONARL</PN_INIT> <PN_MNAVN>Romaniec</PN_MNAVN>
         * <PN_NAVN>Iwona Romaniec Langdalen</PN_NAVN> <PN_PEID_PE>51</PN_PEID_PE>
         * </PerNavn>
         * 
         * <PerRolle> <PR_PEID_PE>61</PR_PEID_PE> <PR_ROLLEID_RO>4</PR_ROLLEID_RO>
         * <PR_STDROLLE>0</PR_STDROLLE> <PR_TITTEL>Saksbehandler TF</PR_TITTEL>
         * <PR_JENHET_JE>J-UIO</PR_JENHET_JE> <PR_ADMID_AI>2</PR_ADMID_AI>
         * <PR_ARKDEL_AD>SAK UIO</PR_ARKDEL_AD>
         * <PR_FRADATO>2007-05-10T00:00:00+02:00</PR_FRADATO> <PR_ID>119</PR_ID>
         * </PerRolle>
         * 
         * <AdresseKP> <AK_ADRGRUPPE>0</AK_ADRGRUPPE> <AK_ADRID>69</AK_ADRID>
         * <AK_KORTNAVN>JUS</AK_KORTNAVN> <AK_NAVN>Juristforeningen</AK_NAVN>
         * <AK_OPDGRUPPE>0</AK_OPDGRUPPE> <AK_POSTADR>Professorboligen, pb 6706
         * St. Olavs plass</AK_POSTADR> <AK_POSTNR_PO>0130</AK_POSTNR_PO>
         * <AK_POSTSTED_PO>Oslo</AK_POSTSTED_PO> <AK_REGEPOST>0</AK_REGEPOST>
         * <AK_TGGRUPPE>0</AK_TGGRUPPE> <AK_TYPE>V</AK_TYPE> </AdresseKP>
         * 
         * <AdrPerson> <AP_ADRID_AK>57</AP_ADRID_AK> <AP_PEID_PE>45</AP_PEID_PE>
         * </AdrPerson>
         */

        Hashtable<Integer, Person> personId2Person = new Hashtable<Integer, Person>();
        log.info("EphorteGW.fetchPersons() started...");
        for (Hashtable<String, String> ht : conn.getDataSet("object=person", "Person")) {
            Person p = new Person(ht, true);
            personId2Person.put(p.getId(), p);
            brukerId2Person.put(p.getBrukerId(), p);
        }
        for (Hashtable<String, String> ht : conn.getDataSet("object=pernavn", "PerNavn")) {
            Person p = personId2Person.get(Integer.parseInt(ht.get("PN_PEID_PE")));
            if (p != null)
                p.addName(ht);
        }
        Hashtable<String, Integer> adrId2PersonId = new Hashtable<String, Integer>();
        for (Hashtable<String, String> ht : conn.getDataSet("object=adrperson", "AdrPerson")) {
            adrId2PersonId.put(ht.get("AP_ADRID_AK"), Integer.parseInt(ht.get("AP_PEID_PE")));
        }
        for (Hashtable<String, String> ht : conn.getDataSet("object=adressekp", "AdresseKP")) {
            Integer pid = adrId2PersonId.get(ht.get("AK_ADRID"));
            if (pid == null)
                continue;
            Person p = personId2Person.get(pid);
            if (p == null)
                continue;
            p.addAddress(ht);
        }
	// setup is a static method
        PersonRolle.setup(conn.getDataSet("object=admindel", "AdminDel"),
			  conn.getDataSet("object=rolle", "Rolle"));

        for (Hashtable<String, String> ht : conn.getDataSet("object=perrolle", "PerRolle")) {
            Person p = personId2Person.get(Integer.parseInt(ht.get("PR_PEID_PE")));
            if (p == null)
                continue;
            p.addRolle(ht);

        }
        // if (log.isDeqbugEnabled()) {
        //     log.debug("Parsed persons from ePhorte:");
        //     for (Iterator iter = personId2Person.values().iterator(); iter.hasNext();) {
        //         Person p = (Person) iter.next();
        //         log.debug(p + "; " + p.getPersonNavn() + "; " + 
	// 		  p.getAdresse(Adresse.ADRTYPE_A) + "; " +
	// 		  p.getRoller());
        //     }
        // }
        log.info("EphorteGW.fetchPersons() done...");
    }

    /**
     * Oppdater, eller opprett person i ePhorte med informasjon om navn og
     * adresser. newPerson er fra xml-dumpen fra Cerebrum.
     * 
     * @param newPerson
     * @throws RemoteException
     */
    public void updatePersonInfo(Person newPerson) throws RemoteException {
        XMLUtil xml = new XMLUtil();
        Person oldPerson = getPerson(newPerson);
        boolean isDirty = false;
        xml.startTag("PersonData");
	// Check if Person needs to be updated
        if (oldPerson == null || oldPerson.getId() == -1) {
            // Person doesn't exist in ePhorte. Create new person
            newPerson.toXML(xml);
            brukerId2Person.put(newPerson.getBrukerId(), newPerson);
            newPerson.setNew(true);
            isDirty = true;
        } else {
            // old person. There are no data that we want to update
            newPerson.setId(oldPerson.getId());
	    // We can't delete persons in ePhorte. Instead the tilDato is set.
            newPerson.setTilDato(oldPerson.getTilDato());
            if(! newPerson.equals(oldPerson)) {
		log.debug("Set tilDato for person " + newPerson.getBrukerId() +
			  " to " + newPerson.getTilDato().toString());
                newPerson.toXML(xml); 
                isDirty = true;
            } else {                
		newPerson.toSeekXML(xml);
	    }
        }
	// Check if PersonName needs to be updated
        if (oldPerson == null || !(newPerson.getPersonNavn().equals(oldPerson.getPersonNavn()))) {
            if (oldPerson != null && oldPerson.getPersonNavn() != null) {
                newPerson.getPersonNavn().setId(oldPerson.getPersonNavn().getId());
            }
            newPerson.getPersonNavn().toXML(xml);
            isDirty = true;
        }
	// Check if Adresse needs to be updated
        if (oldPerson == null || oldPerson.getAdresse(Adresse.ADRTYPE_A) == null
	    || !(oldPerson.getAdresse(Adresse.ADRTYPE_A).equals(newPerson.getAdresse(Adresse.ADRTYPE_A)))) {
            if (oldPerson != null && oldPerson.getAdresse(Adresse.ADRTYPE_A) != null) {
                newPerson.getAdresse(Adresse.ADRTYPE_A).setId(oldPerson.getAdresse(Adresse.ADRTYPE_A).getId());
            }
            newPerson.getAdresse(Adresse.ADRTYPE_A).toXML(xml);
            isDirty = true;
        }
	// Check if roles need to be updated
        isDirty = updateRoles(xml, newPerson) || isDirty;
        xml.endTag("PersonData");
        if (isDirty) {
	    // We need to update ephorte 
            try {
                int ret = conn.updatePersonByXML(xml.toString());
                if (newPerson.getId() == -1)
                    newPerson.setId(ret);
		if (ret > 0) {
		    log.info("Successfully updated person " + 
			     newPerson.getBrukerId() + " (" + ret + ")");
		    // Check if name info must be updated
		    if(newPerson.getPersonNavn().isChanged()) {
			xml = new XMLUtil();
			xml.startTag("PersonData");
			newPerson.toSeekXML(xml);
			newPerson.getPersonNavn().fixChangedName(xml);
			xml.endTag("PersonData");
			ret = conn.updatePersonByXML(xml.toString());
			if (ret < 0) {
			    log.warn("Problem fixing name-change for " + 
				     newPerson.getBrukerId() + ", ret should be > 0, was: "
				     + ret + " problematic request:" + xml.toString());
			}
		    }
		} else {
                    log.warn("Problem modifying " + newPerson.getBrukerId() + 
			     ", ret should be > 0, was: " + ret + 
			     " problematic request:" + xml.toString());
                } 
            } catch (AxisFault e) {
                log.warn("Problems updating ephorte. Sent xml: " + xml.toString() + 
			 " -> " + e.toString());
	    }
        } else {
            log.debug(newPerson.getBrukerId() + " not modified");
        }
    }

    /**
     * Try to match the person from XML (newPerson) with an existing ePhorte
     * person. Note that we also check any previous feide IDs the XML-person
     * might have had, as this should result in a change of username.
     * 
     * @param newPerson
     * @return
     */
    private Person getPerson(Person newPerson) {
	// brukerId2Person are persons from ePhorte
	Person ret = brukerId2Person.get(newPerson.getBrukerId());
	if(ret != null) return ret;
	// Didn't find person in brukerId2Person. Check potentialFeideIds
    	for (String feideId : newPerson.getPotentialFeideIds()) {
	    ret = brukerId2Person.get(feideId);
	    if(ret != null) return ret;
	}
	// Didn't find person in potentialFeideIds either. Check if
	// another PersonObject has the same initialer (aka user name)
        for(Person p: brukerId2Person.values()){
            String oldInit = null;
            if(p.getPersonNavn() != null) oldInit = p.getPersonNavn().getInitialer(); 
            if(newPerson.getPersonNavn().getInitialer().equals(oldInit)){
                log.warn("Used brukerid match to return "+p+" when looking for "+newPerson);
                return p;
            }
        }
    	return null;
    }

    private boolean updateRoles(XMLUtil xml, Person p) {
        boolean isDirty = false;
        Person oldPerson = getPerson(p);
        if (oldPerson == null || (oldPerson.getId() == -1 && !oldPerson.isNew())) {
            log.warn("updateRoles for non-existing person " + p.getBrukerId());
            return isDirty;
        }
        for (PersonRolle pr : p.getRoller()) {
            if (oldPerson.isNew() || !oldPerson.getRoller().contains(pr)) {
                log.debug("Add role: " + pr);
                pr.toXML(xml);
                isDirty = true;
            } else {
                log.debug("Person already has role: " + pr);
                oldPerson.getRoller().remove(pr);
            }
        }
        if (!oldPerson.isNew()) {
            for (PersonRolle pr : oldPerson.getRoller()) {
                log.debug("Remove role: " + pr);
                pr.setTilDato(new Date());
                pr.toDeleteXML(xml);
                isDirty = true;
            }
        }
        return isDirty;
    }

    public EphorteConnection getConn() {
        return conn;
    }

}
