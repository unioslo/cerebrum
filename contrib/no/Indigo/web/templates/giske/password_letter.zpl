<span tal:define="title string:Passordark;title_id string:password_letter" 
      tal:omit-tag="">
  <span metal:use-macro="tpl/macros/page">
    <span metal:fill-slot="body" tal:omit-tag="">

      <h1>Brukarnamn og passord</h1>

      <p>
        Velkommen til den nye digitale skulekvardagen i Giskeskulen. I
        dette brevet finn du ditt personlege brukarnamn og passord som
        du kan bruke for å logge deg inn i Giske skuleportal.
      </p>

      <p>
        Hugs at brukarnamn og passord er personleg, og at du
        <strong>ikkje må gje det til andre!</strong>
      </p>

      <table border="0">
        <tr>
	  <td>Namn:</td>
	  <td tal:content="string: ${name}"></td>
        </tr>
        <tr>
	  <td>Fødselsdato:</td>
	  <td tal:content="string: ${birthdate}"></td>
        </tr>
	
	<tr tal:repeat="aff affiliations">
	  <td>Skule:</td>
          <td tal:content="aff/aff_sted_desc">Skulenavn</td>
        </tr>

        <tr>
          <td>Brukernamn:</td> 
          <td tal:content="string: ${uname}"></td>
        </tr>
        <tr>
          <td>Passord:</td>
          <td tal:content="string: ${pwd}"></td>
        </tr>
        <tr>
          <td>E-postadresse:</td>
          <td tal:content="string: ${email}"></td>
        </tr>
      </table>

      <p>
        Undervisningsportalen finn du på 
	<a href="https://portal.skule.giske.no/">https://portal.skule.giske.no/</a>.
      </p>
    </span>
  </span>
</span>
