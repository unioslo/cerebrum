package no.uio.ephorte.data;

import java.text.ParseException;
import java.util.Date;
import java.util.Hashtable;
import java.util.Vector;

import no.uio.ephorte.xml.XMLUtil;

/**
 * Represents a person-rolle entry in ePhorte
 * 
 * @author rune
 * 
 */
public class PersonRolle {
    static Hashtable<String, Integer> stedkode2Id;
    static Hashtable<String, Integer> rolleType2Id;

    private Person person;
    private int id = -1;
    private int rolleId;
    private String tittel;
    private String journalEnhet;
    private String arkivDel;
    private Integer adminDel;
    private boolean stdRolle = false;
    private Date tilDato;
    private Date fraDato;

    public PersonRolle(Person person, Hashtable<String, String> ht) {
        this.person = person;
        id = Integer.parseInt(ht.get("PR_ID"));
        rolleId = Integer.parseInt(ht.get("PR_ROLLEID_RO"));
        stdRolle = ht.get("PR_STDROLLE").equals("0") ? false : true;
        tittel = ht.get("PR_TITTEL");
        journalEnhet = ht.get("PR_JENHET_JE");
        arkivDel = ht.get("PR_ARKDEL_AD");
        String tmp = ht.get("PR_ADMID_AI");
        if (tmp != null)
            adminDel = Integer.parseInt(tmp);
        try {
            tmp = ht.get("PR_FRADATO");
            if (tmp != null)
                fraDato = Person.dayFormat.parse(tmp);
        } catch (ParseException e) {
            e.printStackTrace();
        }
    }

    public PersonRolle(Person person, String rolleType, boolean stdRolle, String sko,
            String arkivDel, String journalEnhet, String tittel, String stilling)
            throws BadDataException {
        this.person = person;
        Integer tmp = rolleType2Id.get(rolleType);
        if (tmp == null)
            throw new BadDataException("Illegal rolletype: " + rolleType);
        rolleId = tmp;
        this.stdRolle = stdRolle;
        tmp = stedkode2Id.get(sko);
        if (tmp == null)
            throw new BadDataException("Illegal sko: " + sko);
        adminDel = tmp;
        this.arkivDel = arkivDel;
        this.journalEnhet = journalEnhet;
        this.tittel = tittel;
        fraDato = new Date();
    }

    @Override
    public boolean equals(Object obj) {
        if (obj instanceof PersonRolle) {
            PersonRolle pr = (PersonRolle) obj;
            // Vi ser ikke på self.id ettersom denne vil være -1 fra import filen
            return  XMLUtil.equals(rolleId, pr.rolleId) && XMLUtil.equals(journalEnhet, pr.journalEnhet)
                    && XMLUtil.equals(arkivDel, pr.arkivDel)
                    && XMLUtil.equals(adminDel, pr.adminDel);
        }
        return super.equals(obj);
    }

    public void toXML(XMLUtil xml) {
        xml.startTag("PERROLLE");
        /*
         * Når man oppretter en ny entry i ePhorte, må ID for denne typen være
         * unik. Verdien er i seg selv ikke relevant, men den kan benyttes som
         * referanse dersom andre XML-blokker i det samme UpdatePersonByXML
         * kallet ønsker det.
         * 
         */
        xml.writeElement("PR_ID", "" + (person.getRoller().indexOf(this) + 1));

        xml.writeElement("PR_PEID_PE", "" + person.getId());
        xml.writeElement("PR_ROLLEID_RO", "" + rolleId);
        xml.writeElement("PR_STDROLLE", stdRolle ? "0" : "-1");
        xml.writeElement("PR_TITTEL", tittel);
        if (journalEnhet != null)
            xml.writeElement("PR_JENHET_JE", journalEnhet);
        if (adminDel != null)
            xml.writeElement("PR_ADMID_AI", "" + adminDel);
        if (arkivDel != null)
            xml.writeElement("PR_ARKDEL_AD", arkivDel);
        xml.writeElement("PR_FRADATO", Person.dayFormat.format(fraDato));
        if (tilDato != null)
            xml.writeElement("PR_TILDATO", Person.dayFormat.format(tilDato));
        xml.endTag("PERROLLE");
    }

    public void toDeleteXML(XMLUtil xml) {
        xml.startTag("PERROLLE");
        xml.writeElement("PR_PEID_PE", "" + person.getId());
        /*
         * F.eks: <SEEKFIELDS>PR_PEID_PE;PR_ROLLEID_RO</SEEKFIELDS>
         * <SEEKVALUES>80;4</SEEKVALUES> <DELETERECORD>1</DELETERECORD>
         */
        xml.writeElement("SEEKFIELDS", "PR_ID");
        xml.writeElement("SEEKVALUES", "" + id);
        xml.writeElement("DELETERECORD", "1");
        xml.endTag("PERROLLE");
    }

    public static void setup(Vector<Hashtable<String, String>> adminDelDataSet,
            Vector<Hashtable<String, String>> rolleDataSet) {
        stedkode2Id = new Hashtable<String, Integer>();
        for (Hashtable<String, String> ht : adminDelDataSet) {
            stedkode2Id.put(ht.get("AI_FORKDN"), Integer.parseInt(ht.get("AI_ID")));
        }

        rolleType2Id = new Hashtable<String, Integer>();
        for (Hashtable<String, String> ht : rolleDataSet) {
            rolleType2Id.put(ht.get("RO_NAVN"), Integer.parseInt(ht.get("RO_ROLLEID")));
        }
    }

    @Override
    public String toString() {
        return "Rolle: pid=" + person.getId() + ", id=" + id + ", rolleid=" + rolleId + ", tittel="
                + tittel + ", journEnhet=" + journalEnhet + ", adminDel=" + adminDel
                + ", arkivDel=" + arkivDel;
    }

    public void setTilDato(Date tilDato) {
        this.tilDato = tilDato;
    }

    public Date getTilDato() {
        return tilDato;
    }

    int getId() {
        return id;
    }

    int getRolleId() {
        return rolleId;
    }

}
