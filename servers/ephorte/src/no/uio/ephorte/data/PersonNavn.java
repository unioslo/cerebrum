package no.uio.ephorte.data;

import java.text.ParseException;
import java.util.Date;
import java.util.Hashtable;

import no.uio.ephorte.xml.XMLUtil;

/**
 * Represents a person-navn entry in ePhorte
 * 
 * @author rune
 * 
 */

public class PersonNavn {
    Person person;
    private boolean aktiv;
    private int id = -1;
    private String initialer;
    private String navn;
    private String fornavn;
    private String mellomnavn;
    private String etternavn;
    private Date fraDato;
    private static int xmlRefIdCounter;  // sikre at vi ikke sender to xml-blokker med samme navne-id for intern-referansene 
    private int xmlRefId;
    private boolean changed = false;
    
    public boolean isChanged() {
        return changed;
    }

    @Override
    public boolean equals(Object obj) {
        if (obj instanceof PersonNavn) {
            PersonNavn pn = (PersonNavn) obj;
            return XMLUtil.equals(initialer, pn.initialer) && XMLUtil.equals(navn, pn.navn)
                    && XMLUtil.equals(fornavn, pn.fornavn)
                    && XMLUtil.equals(mellomnavn, pn.mellomnavn)
                    && XMLUtil.equals(etternavn, pn.etternavn)/* && aktiv == pn.aktiv */;
        }
        return super.equals(obj);
    }

    protected PersonNavn(Person person, String initialer, String navn, String fornavn,
            String mellomnavn, String etternavn, boolean aktiv) {
        this.xmlRefId = ++xmlRefIdCounter; 
        this.person = person;
        this.initialer = initialer;
        this.navn = navn;
        this.fornavn = fornavn;
        this.mellomnavn = mellomnavn;
        this.etternavn = etternavn;
        this.aktiv = aktiv;
        fraDato = new Date();
    }

    protected PersonNavn(Person person, Hashtable<String, String> ht) {
        this.person = person;
        this.initialer = ht.get("PN_INIT");
        this.navn = ht.get("PN_NAVN");
        this.fornavn = ht.get("PN_FORNAVN");
        this.mellomnavn = ht.get("MNAVN");
        this.etternavn = ht.get("PN_ETTERNAVN");
        this.aktiv = "-1".equals(ht.get("PN_AKTIV")) ? true : false;
        this.id = Integer.parseInt(ht.get("PN_ID"));
        try {
            if (ht.get("PN_FRADATO") != null)
                fraDato = Person.dayFormat.parse(ht.get("PN_FRADATO"));
        } catch (ParseException e) {
            e.printStackTrace();
        }
    }

    public String toXML(XMLUtil xml) {
        xml.startTag("PERNAVN");
        if (id != -1) {
            // Når en person har skiftet navn, skal det gamle navnet få en til-dato
            xml.writeElement("PN_ID", "" + xmlRefId++);
            xml.writeElement("SEEKFIELDS", "PN_ID");
            xml.writeElement("SEEKVALUES", "" + id);
            // xml.writeElement("PN_AKTIV", "0");
            xml.writeElement("PN_TILDATO", Person.dayFormat.format(new Date()));
            xml.writeElement("PN_PEID_PE", "" + person.getId());
            xml.endTag("PERNAVN");
            xml.startTag("PERNAVN");
            xml.writeElement("PN_INIT", "_"+initialer);
            changed = true;
        } else {
            xml.writeElement("PN_INIT", initialer);
        }
        xml.writeElement("PN_PEID_PE", "" + person.getId());
        xml.writeElement("PN_ID", "" + xmlRefId);
        xml.writeElement("PN_AKTIV", "-1");            // -1 -> True
        xml.writeElement("PN_NAVN", navn);
        xml.writeElement("PN_FORNAVN", fornavn);
        // xml.writeElement("PN_MNAVN", mellomnavn); // Vi har ikke mellomnavn i
        // kildesystemet
        xml.writeElement("PN_ETTERNAVN", etternavn);
        xml.writeElement("PN_FRADATO", Person.dayFormat.format(fraDato));
        xml.endTag("PERNAVN");
        return "";
    }

    @Override
    public String toString() {
        return "PersonNavn: pid=" + person.getId() + ", initialier=" + initialer + ", navn=" + navn
                + ", aktiv=" + aktiv;
    }

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public boolean isAktiv() {
        return aktiv;
    }

    public String getInitialer() {
        return initialer;
    }

    /**
     * When a persons name is changed, we would ideally like to create the new
     * name with the correct initials during one UpdatePersonByXML call.
     * Unfortunately, this causes ePhorte to throw an exception. Therefore we
     * have to first create the new name with boggous initials, and then rename
     * the user during a second UpdatePersonByXML call.
     * 
     * @param xml
     */
    public void fixChangedName(XMLUtil xml) {
        xml.startTag("PERNAVN");
        xml.writeElement("PN_ID", "" + xmlRefId);
        xml.writeElement("SEEKFIELDS", "PN_INIT;PN_AKTIV");
        xml.writeElement("SEEKVALUES", "_" + initialer+";-1");
        xml.writeElement("PN_PEID_PE", "" + person.getId());
        xml.writeElement("PN_INIT", initialer);
        xml.endTag("PERNAVN");
    }

}
