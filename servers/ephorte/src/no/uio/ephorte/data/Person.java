package no.uio.ephorte.data;

import java.security.SecureRandom;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Hashtable;
import java.util.Vector;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

import no.uio.ephorte.xml.XMLUtil;

/**
 * Represents a person entry in ePhorte. Has navn, adresse and rolle as
 * children.
 * 
 * @author rune
 * 
 */

public class Person {
    public static SimpleDateFormat dayFormat = new SimpleDateFormat("yyyy-MM-dd");
    private static Log log = LogFactory.getLog(Person.class);

    private String brukerId;
    private int id = -1;
    private PersonNavn personNavn;
    private Hashtable<String, Adresse> adresse;
    private Vector<PersonRolle> roller, deletedRoller;
    private Vector<PersonTgKode> tgKoder, deletedTgKoder;
    private Vector<String> potentialFeideIds;
    private boolean isNew = false; // Was created during this execution
    private Date fraDato, tilDato;
    private boolean tilDatoNeedsUpdate = false;
    private boolean brukerIdNeedsUpdate = false;
    private boolean isDeletable = false;
    private boolean fromEphorte;
    
    private final static String passwordCharacters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01234567890,.-;:_'*!#%/()=?+";
    private SecureRandom secRand = new SecureRandom();

    public Person(String brukerId, boolean fromEphorte) {
        if(brukerId == null)
            throw new IllegalArgumentException("brukerId cannot be NULL");
        roller = new Vector<PersonRolle>();
        deletedRoller = new Vector<PersonRolle>();
	tgKoder = new Vector<PersonTgKode>();
	deletedTgKoder = new Vector<PersonTgKode>();
        potentialFeideIds = new Vector<String>();
        adresse = new Hashtable<String, Adresse>();
        this.brukerId = brukerId;
        fraDato = new Date();
        this.fromEphorte = fromEphorte;
    }

    // Brukes for å populere personer hentet fra ephorte
    public Person(Hashtable<String, String> ht, boolean fromEphorte) {
        this(ht.get("PE_BRUKERID"), fromEphorte);

        this.id = Integer.parseInt(ht.get("PE_ID"));
        try {
            fraDato = dayFormat.parse(ht.get("PE_FRADATO"));
            if(ht.get("PE_TILDATO") != null) {
                tilDato = dayFormat.parse(ht.get("PE_TILDATO"));                
            }
        } catch (ParseException e) {
            e.printStackTrace();
        }
    }
    
    public void toXML(XMLUtil xml) {
        xml.startTag("PERSON");
        xml.writeElement("PE_ID", "" + id);
        xml.writeElement("PE_BRUKERID", brukerId);
	// New user?
        if (id == -1) {
            // Since we use FEIDE login, we assign a random password
            // in case it is possible to log in with the normal
            // password
            StringBuffer password = new StringBuffer();
            for (int i = 0; i < 30; i++) {
                password.append(passwordCharacters.charAt(secRand.nextInt(passwordCharacters.length() - 1)));
            }
            xml.writeElement("PE_PASSORD_G", password.toString());
            // "Skrivetilgang til alle registrerte roller av samme
            // type" -> alltid nei
            xml.writeElement("PE_REDALLEROLLER_G", "0");
            xml.writeElement("PE_FRADATO", dayFormat.format(fraDato));
        } else {
	    // Old user. Seek in ephorte
            xml.writeElement("SEEKFIELDS", "PE_ID");
            xml.writeElement("SEEKVALUES", "" + id);
	    // If person is deleted or reactivated tilDato must be changed
            if(tilDatoNeedsUpdate) {
                xml.writeElement("PE_TILDATO", dayFormat.format(tilDato));
	    }
        }
        xml.endTag("PERSON");
    }

    public void toSeekXML(XMLUtil xml) {
        /*
	 * The PE_ID is used for referencing other elements in the file, while
	 * the SEEKFIELDS tells ePhorte that we're actually talking about an
	 * existing record.
	 */
        xml.startTag("PERSON");
        xml.writeElement("PE_ID", "" + id);
        xml.writeElement("SEEKFIELDS", "PE_ID");
        xml.writeElement("SEEKVALUES", "" + id);
	if (brukerIdNeedsUpdate) {
	    xml.writeElement("PE_BRUKERID", brukerId);
	}
        xml.endTag("PERSON");
    }

    public void addName(String initialer, String navn, String fornavn, 
			String mellomnavn, String etternavn, boolean aktiv) {
        if(personNavn == null || ! personNavn.isAktiv()) {
            // Vi er kun interessert i det aktive personnavnet
            // ettersom det er det vi evt. skal endre
            personNavn = new PersonNavn(this, initialer, navn, fornavn, 
					mellomnavn, etternavn, aktiv);
        }
    }

    public void addAddress(String adrType, String navn, String postadr, 
			   String postnr, String poststed, String ePost, 
			   String tlf) {
        adresse.put(adrType, new Adresse(this, adrType, navn, postadr, postnr, 
					 poststed, ePost, tlf));
    }

    public void addAddress(Hashtable<String, String> ht) {
    	Adresse tmp = new Adresse(this, ht);
        adresse.put(tmp.getAdrType(), tmp);
    }

    public void addName(Hashtable<String, String> ht) {
        if(personNavn != null && personNavn.isAktiv())
            return;
        personNavn = new PersonNavn(this, ht);
    }

    @Override
    public String toString() {
        return "Person: pid=" + id + ", brukerId=" + brukerId;
    }

    public Vector<PersonRolle> getRoller() {
        return roller;
    }

    public Vector<PersonRolle> getDeletedRoller() {
	return deletedRoller;
    }

    public void addRolle(PersonRolle pr) {
	Date tildato, today = new Date();
	tildato = pr.getTilDato();
	if (tildato != null && !tildato.after(today)) {
	    deletedRoller.add(pr);
	} else {
	    roller.add(pr);
	}	
    }

    public void addRolle(Hashtable<String, String> ht) {
	this.addRolle(new PersonRolle(this, ht));
    }

    public void addRolle(String rolleType, boolean stdRolle, String sko, 
			 String arkivDel, String journalEnhet, String tittel, 
			 String stilling) throws BadDataException {
        this.addRolle(new PersonRolle(this, rolleType, stdRolle, sko, arkivDel, 
				      journalEnhet, tittel, stilling));
    }

    public void addTgKode(PersonTgKode ptg) {
	Date tildato, today = new Date();
	tildato = ptg.getTilDato();
	if (tildato != null && !tildato.after(today)) {
	    deletedTgKoder.add(ptg);
	} else {
	    tgKoder.add(ptg);
	}	
    }

    public void addTgKode(Hashtable<String, String> tk) {
        this.addTgKode(new PersonTgKode(this, tk));
    }

    public void addTgKode(String tgKodeType, String sko, String feideId)
	throws BadDataException {
        this.addTgKode(new PersonTgKode(this, tgKodeType, sko, feideId));
    }

    public Vector<PersonTgKode> getTgKoder() {
        return tgKoder;
    }

    public Vector<PersonTgKode> getDeletedTgKoder() {
        return deletedTgKoder;
    }

    public PersonNavn getPersonNavn() {
        return personNavn;
    }

    public Adresse getAdresse(String adrType) {
        return adresse.get(adrType);
    }

    public void setId(int id) {
        this.id = id;
    }

    public int getId() {
        return id;
    }

    public void setBrukerId(String brukerId) {
        this.brukerId = brukerId;
    }

    public String getBrukerId() {
        return brukerId;
    }

    public void setNew(boolean isNew) {
        this.isNew = isNew;
    }

    public boolean isNew() {
        return isNew;
    }

    public boolean isDeletable() {
	return isDeletable;
    }

    public void setDeletable(boolean isDeletable) {
	this.isDeletable = isDeletable;
    }
    
    public void addPotentialFeideId(String feideId) {
	potentialFeideIds.add(feideId);
    }
    
    public Vector<String> getPotentialFeideIds() {
	return potentialFeideIds;
    }

    public void setTilDatoNeedsUpdate(boolean tilDatoNeedsUpdate) {
	this.tilDatoNeedsUpdate = tilDatoNeedsUpdate;
    }
    public void setBrukerIdNeedsUpdate(boolean brukerIdNeedsUpdate) {
	this.brukerIdNeedsUpdate = brukerIdNeedsUpdate;
    }

    public void setTilDato(Date tilDato) {
        this.tilDato = tilDato;
    }

    public Date getTilDato() {
        return tilDato;
    }
}
