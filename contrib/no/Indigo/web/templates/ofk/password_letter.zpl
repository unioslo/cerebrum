<span tal:define="title string:Passordark;title_id string:password_letter" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<br>
<hr>
<h3>Du har nå fått nytt passord</h3>

<p>
Dette brevet inneholder ditt personlige brukernavn og passord som du
kan bruke for å få tilgang til IT-tjenester i Østfold fylkeskommunes
videregående skoler. Husk at brukernavn og passord er personlig, og at
det <b>ikke må oppgis til andre</b>!
</p>

  <table style="text-align: left;" border="0">
    <tr><td>Brukernavn:</td> <td tal:content="string: ${uname}"></td></tr>
    <tr><td>Passord:</td><td tal:content="string: ${pwd}"></td></tr>
    <tr><td>E-postadresse:</td><td tal:content="string: ${email}"></td></tr>
  </table>

<p>
For innlogging i portalen gå til:
<a href="http://portal.ovgs.no/">http://portal.ovgs.no/</a>
</p>

<p>

Har du behov for mer utdypende brukerveiledninger enn det
informasjonsbrosjyren gir deg, finner du fullstendige veiledninger og
annen nyttig informasjon på denne adressen
<a href="http://hjelp.ovgs.no/portal/">http://hjelp.ovgs.no/portal/</a>.
</p>

</span></span></span>
