<span tal:define="title string:Personinformasjon;title_id string:person_info" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<br>
<hr>

<table border=1>
  <tr><td>Navn</td> <td tal:content="person/name">En Person</td></tr>
  <tr><td valign="top">Tilgjengelige tjenester:</td> <td>
    <span tal:repeat="pspread person_spreads" tal:omit-tag="">
      <span tal:content="string:${pspread/spread_desc}"></span><br>
      <!--(${pspread/spread})"></span><br>-->
    </span></td>
  </tr>
  <tr><td>Fødselsdato</td><td tal:content="person/birth">1999-99-99</td></tr>
  <tr><td>Fødselsnummer</td><td tal:content="person/fnrs">fnr</td></tr>
<!--TODO: noe er galt med uthenting av affs...-->
<!--  <tr><td>Tilknytning</td><td>tal:content="person/affiliations">affs</td></tr>-->
</table>

<h1>Brukerinformasjon</h1>

  <table border="0" tal:repeat="user userlist">
    <tr><td>Brukernavn:</td> <td tal:content="user/username">foo</td></tr>
    <tr><td>E-postadresse:</td> <td tal:content="user/email">foo@bar.com</td></tr>
    <tr><td valign="top">Gruppemedlemskap:</td> <td>
      <span tal:repeat="ugroup user/groups" tal:omit-tag="">
      <span tal:content="ugroup/group"></span><br>
      </span></td></tr>
    <tr><td colspan=2></td></tr>
    <tr><td colspan=2></td></tr>
    <span tal:condition="python: state['authlevel'] > 'c1'" tal:omit-tag="">
    <tr> <td colspan=2><a tal:attributes="href string:?action=do_user_password&entity_id=${user/account_id}">Sett nytt passord (automatisk generert)</a></td></tr>
    <tr><td colspan=2></td></tr>
    <tr><td colspan=2><a tal:attributes="href string:?action=show_user_get_password&entity_id=${user/account_id}">Hent ut brukerens nåværende passord</a></td></tr>
    </span>
    <tr><td colspan=2></td></tr>
    <tr><td colspan=2></td></tr>
    <span tal:condition="python: state['authlevel'] > 'c2'" tal:omit-tag="">
    <tr><td colspan=2><a tal:attributes="href string:?action=show_user_create&owner_id=${person/entity_id}&owner_type=person">Opprett ny bruker til denne personen</a></td></tr>
    </span>
  </table>

</span></span></span>

