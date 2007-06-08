package no.uio.ephorte.data;

import java.util.Hashtable;

import no.uio.ephorte.xml.XMLUtil;

/**
 * Represents an adresse entry in ePhorte, only tested for person adresses.
 * 
 * @author rune
 * 
 */

public class Adresse {
    /*
     * Fra ePhorte.adrtype
     */
    public final static String ADRTYPE_A = "A"; // Persons arbeidsadresse
    public final static String ADRTYPE_P = "P"; // Persons privatadresse
    public final static String ADRTYPE_V = "P"; // Adresse til virksomhet

    private int id = -1;
    private String adrType; // AK_TYPE
    private String navn; // AK_NAVN
    private String postadr; // AK_POSTADR
    private String postnr; // AK_POSTNR_PO
    private String poststed; // AK_POSTSTED_PO
    private String ePost; // AK_EPOST
    private String tlf; // AK_TLF
    private Person person;

    @Override
    public boolean equals(Object obj) {
        if (obj instanceof Adresse) {
            Adresse ad = (Adresse) obj;
            return XMLUtil.equals(adrType, ad.adrType) && XMLUtil.equals(navn, ad.navn)
                    && XMLUtil.equals(postadr, ad.postadr) && XMLUtil.equals(postnr, ad.postnr)
                    && XMLUtil.equals(poststed, ad.poststed) && XMLUtil.equals(ePost, ad.ePost)
                    && XMLUtil.equals(tlf, ad.tlf);
        }
        return super.equals(obj);
    }

    protected Adresse(Person person, String adrType, String navn, String postadr, String postnr,
            String poststed, String post, String tlf) {
        this.person = person;
        this.adrType = adrType;
        this.navn = navn;
        this.postadr = postadr;
        this.postnr = postnr;
        this.poststed = poststed;
        ePost = post;
        this.tlf = tlf;
    }

    public Adresse(Person person, Hashtable<String, String> ht) {
        this.person = person;
        this.navn = ht.get("AK_NAVN");
        this.adrType = ht.get("AK_TYPE");
        this.postadr = ht.get("AK_POSTADR");
        this.postnr = ht.get("AK_POSTNR_PO");
        this.poststed = ht.get("AK_POSTSTED_PO");
        this.ePost = ht.get("AK_EPOST");
        this.tlf = ht.get("AK_TLF");
        this.id = Integer.parseInt(ht.get("AK_ADRID"));
    }

    public String toXML(XMLUtil xml) {
        xml.startTag("ADRESSEKP");
        if (id != -1) {
            xml.writeElement("SEEKFIELDS", "AK_ADRID");
            xml.writeElement("SEEKVALUES", "" + id);
        }
        xml.writeElement("AP_PEID_PE", "" + person.getId());
        xml.writeElement("AK_ADRID", "" + id);
        xml.writeElement("AK_TYPE", adrType);
        xml.writeElement("AK_NAVN", navn);
        xml.writeElement("AK_POSTADR", postadr);
        xml.writeElement("AK_POSTNR_PO", postnr);
        xml.writeElement("AK_POSTSTED_PO", poststed);
        xml.writeElement("AK_EPOST", ePost);
        xml.writeElement("AK_TLF", tlf);
        xml.endTag("ADRESSEKP");
        return "";
    }

    @Override
    public String toString() {
        return "Adresse: pid=" + person.getId() + ", adrType=" + adrType + ", navn=" + navn
                + ", postadr=" + postadr + ", postnr=" + postnr + ", poststed=" + poststed
                + ", ePost=" + ePost + ", tlf=" + tlf;
    }

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

	public String getAdrType() {
		return adrType;
	}

}