package no.uio.ephorte.data;

import java.text.ParseException;
import java.util.Date;
import java.util.Hashtable;
import java.util.Vector;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

import no.uio.ephorte.xml.XMLUtil;

/**
 * Represents a person-rolle entry in ePhorte
 * 
 * @author rune
 * 
 */
public class PersonRolle {
    static Hashtable<Integer, String> id2stedAkronym;
    static Hashtable<String, Integer> stedkode2Id;
    static Hashtable<String, Integer> rolleType2Id;
    static Hashtable<Integer, String> id2rolleBeskrivelse;
    private static Log log = LogFactory.getLog(PersonRolle.class);

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
        try {
            tmp = ht.get("PR_TILDATO");
            if (tmp != null)
                tilDato = Person.dayFormat.parse(tmp);
        } catch (ParseException e) {
            e.printStackTrace();
        }
    }

    public PersonRolle(Person person, String rolleType, boolean stdRolle, 
		       String sko, String arkivDel, String journalEnhet, 
		       String tittel, String stilling)
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
	// this patch seems to have caused some trouble and we will 
        // therefore revert it until we can find out more about how 
        // better role titles can be created.
        // Jazz, 2011-12-02
	// The web service sets the title automagically if empty, but
	// we want to set it explicitly to avvoid an error which occur
	// if a person has two roles where rolletype and adminDel is
	// the same, but arkivdel and journalenhet differs.
	//if (tittel == null || tittel.isEmpty()) {
	//   String ouDescr = id2stedAkronym.get(adminDel);
	//   tittel = id2rolleBeskrivelse.get(rolleId) + " " + ouDescr + 
	//	" " + arkivDel;
	//}
	this.tittel = tittel
        this.arkivDel = arkivDel;
        this.journalEnhet = journalEnhet;
        fraDato = new Date();
    }

    @Override
    public boolean equals(Object obj) {
        if (obj instanceof PersonRolle) {
            PersonRolle pr = (PersonRolle) obj;
            // Vi ser ikke på self.id ettersom denne vil være -1 fra
            // importfilen
	    if (id != -1 && pr.getId() != -1) {
		return id == pr.getId();
	    }
            return  XMLUtil.equals(rolleId, pr.rolleId) && 
		XMLUtil.equals(journalEnhet, pr.journalEnhet) && 
		XMLUtil.equals(arkivDel, pr.arkivDel) &&
		XMLUtil.equals(adminDel, pr.adminDel);
        }
        return super.equals(obj);
    }

    public void toXML(XMLUtil xml) {
        xml.startTag("PERROLLE");
        /*
         * Når man oppretter en ny entry i ePhorte, må ID for denne
         * typen være unik. Verdien er i seg selv ikke relevant, men
         * den kan benyttes som referanse dersom andre XML-blokker i
         * det samme UpdatePersonByXML kallet ønsker det.
         * 
         */
        xml.writeElement("PR_ID", "" + (person.getRoller().indexOf(this) + 1));

        xml.writeElement("PR_PEID_PE", "" + person.getId());
        xml.writeElement("PR_ROLLEID_RO", "" + rolleId);
        xml.writeElement("PR_STDROLLE", stdRolle ? "-1" : "0");
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

    // Update an earlier deleted rolle by setting tildato to null
    public void toUpdateXML(XMLUtil xml) {
        xml.startTag("PERROLLE");
        xml.writeElement("PR_ID", "" + id);
        xml.writeElement("PR_PEID_PE", "" + person.getId());
        xml.writeElement("SEEKFIELDS", "PR_ID");
        xml.writeElement("SEEKVALUES", "" + id);
        xml.writeElement("PR_TILDATO", Person.dayFormat.format(new Date(System.currentTimeMillis()+1000L*3600*24*365*20)));
        xml.endTag("PERROLLE");
    }

    // Delete by setting tildato 
    public void toDeleteXML(XMLUtil xml) {
        xml.startTag("PERROLLE");
        xml.writeElement("PR_ID", "" + id);
        xml.writeElement("PR_PEID_PE", "" + person.getId());
        xml.writeElement("SEEKFIELDS", "PR_ID");
        xml.writeElement("SEEKVALUES", "" + id);
        xml.writeElement("PR_TILDATO", Person.dayFormat.format(tilDato));
        xml.endTag("PERROLLE");
    }

    public static void setup(Vector<Hashtable<String, String>> adminDelDataSet,
            Vector<Hashtable<String, String>> rolleDataSet) {
        stedkode2Id = new Hashtable<String, Integer>();
	id2stedAkronym = new Hashtable<Integer, String>();
        for (Hashtable<String, String> ht : adminDelDataSet) {
	    try {
		stedkode2Id.put(ht.get("AI_FORKDN"), 
				Integer.parseInt(ht.get("AI_ID")));
		id2stedAkronym.put(Integer.parseInt(ht.get("AI_ID")), 
				   ht.get("AI_ADMKORT"));
	    } catch (Exception e) {
		log.warn("Wrong format: AI_FORKDN: " + ht.get("AI_FORKDN") + 
			 ", AI_ADMKORT: " + ht.get("AI_ADMKORT") +
			 ", AI_ID: " + ht.get("AI_ID"));
	    }
        }
        rolleType2Id = new Hashtable<String, Integer>();
        id2rolleBeskrivelse = new Hashtable<Integer, String>();
        for (Hashtable<String, String> ht : rolleDataSet) {
            rolleType2Id.put(ht.get("RO_NAVN"), 
			     Integer.parseInt(ht.get("RO_ROLLEID")));
            id2rolleBeskrivelse.put(Integer.parseInt(ht.get("RO_ROLLEID")), 
				    ht.get("RO_BESKRIVELSE_G"));
        }
    }

    @Override
    public String toString() {
        return "Rolle: pid=" + person.getId() + ", id=" + id + ", rolleid=" + 
	    rolleId + ", tittel=" + tittel + ", journEnhet=" + journalEnhet + 
	    ", adminDel=" + adminDel + ", arkivDel=" + arkivDel + 
	    ", stdRolle=" + (stdRolle ? "-1" : "0");
    }

    public void setTilDato(Date tilDato) {
        this.tilDato = tilDato;
    }

    public Date getTilDato() {
        return tilDato;
    }

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public int getRolleId() {
        return rolleId;
    }

}
