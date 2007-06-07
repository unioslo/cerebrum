package no.uio.ephorte.data;

import java.security.SecureRandom;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Hashtable;
import java.util.Vector;

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

    private String brukerId;
    private int id = -1;
    private PersonNavn personNavn;
    private Adresse adresse;
    private Vector<PersonRolle> roller;
    private boolean isNew = false; // Was created during this execution
    private Date fraDato;

    private final static String passwordCharacters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01234567890,.-;:_'*!#%&/()=?+";
    private SecureRandom secRand = new SecureRandom();

    public Person(String brukerId) {
        roller = new Vector<PersonRolle>();
        this.brukerId = brukerId;
        fraDato = new Date();
    }

    public Person(Hashtable<String, String> ht) {
        this(ht.get("PE_BRUKERID"));

        this.id = Integer.parseInt(ht.get("PE_ID"));
        try {
            fraDato = dayFormat.parse(ht.get("PE_FRADATO"));
        } catch (ParseException e) {
            e.printStackTrace();
        }
    }

    public String toXML(XMLUtil xml) {
        xml.startTag("PERSON");
        xml.writeElement("PE_ID", "" + id);
        xml.writeElement("PE_BRUKERID", brukerId);
        xml.writeElement("PE_FRADATO", dayFormat.format(fraDato));
        if (id == -1) {
            // Since we use FEIDE login, we assign a random password in case it
            // is possible to log in with the normal password
            StringBuffer password = new StringBuffer();
            for (int i = 0; i < 30; i++) {
                password.append(passwordCharacters.charAt(secRand.nextInt(passwordCharacters
                        .length() - 1)));
            }
            xml.writeElement("PE_PASSORD_G", password.toString());
        }
        xml.writeElement("PE_REDALLEROLLER_G", "0"); // "Skrivetilgang til
                                                        // alle registrerte
                                                        // roller av samme type"
                                                        // -> alltid nei
        xml.endTag("PERSON");
        return "";
    }

    public void toSeekXML(XMLUtil xml) {
        /*
         * The PE_ID is used for referencing other elements in the file, while the SEEKFIELDS tells
         * ePhorte that we're actually talking about an existing record.
         */
        xml.startTag("PERSON");
        xml.writeElement("PE_ID", "" + id);
        xml.writeElement("SEEKFIELDS", "PE_ID");
        xml.writeElement("SEEKVALUES", "" + id);
        xml.endTag("PERSON");
    }

    public void addName(String initialer, String navn, String fornavn, String mellomnavn,
            String etternavn, boolean aktiv) {
        personNavn = new PersonNavn(this, initialer, navn, fornavn, mellomnavn, etternavn, aktiv);
    }

    public void addAddress(String adrType, String navn, String postadr, String postnr,
            String poststed, String ePost, String tlf) {
        adresse = new Adresse(this, adrType, navn, postadr, postnr, poststed, ePost, tlf);
    }

    public void addAddress(Hashtable<String, String> ht) {
        adresse = new Adresse(this, ht);
    }

    public void addName(Hashtable<String, String> ht) {
        personNavn = new PersonNavn(this, ht);
    }

    @Override
    public String toString() {
        return "Person: pid=" + id + ", brukerId=" + brukerId;
    }

    public void addRolle(Hashtable<String, String> ht) {
        roller.add(new PersonRolle(this, ht));
    }

    public Vector<PersonRolle> getRoller() {
        return roller;
    }

    public void addRolle(String rolleType, boolean stdRolle, String sko, String arkivDel,
            String journalEnhet, String tittel, String stilling) throws BadDataException {
        roller.add(new PersonRolle(this, rolleType, stdRolle, sko, arkivDel, journalEnhet, tittel,
                stilling));
    }

    public PersonNavn getPersonNavn() {
        return personNavn;
    }

    public Adresse getAdresse() {
        return adresse;
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

}
