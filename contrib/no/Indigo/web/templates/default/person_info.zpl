<span tal:define="title string:Person informasjon;title_id string:person_info" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<table border=1>
  <tr><TH>Felt</TH> <TH>Verdi</TH>
  <tr><td>Navn</td> <td tal:content="person/name">En Person</td></tr>
  <tr><td valign="top">Kjent i</td> <td>
    <span tal:repeat="pspread person_spreads" tal:omit-tag="">
      <span tal:content="string:${pspread/spread_desc} (${pspread/spread})"></span><br>
    </span></td>
  </tr>
  <tr><td>Fødselsdato</td>
      <td tal:content="person/birth">1999-99-99</td></tr>
</table>

<h2>Brukerinformasjon</h2>

  <p>
  <table border="0"  tal:repeat="user userlist">
    <tr><td><strong>Brukernavn</strong></td> <td tal:content="user/username">foo</td></tr>
    <tr><td valign="top">Kjent i</td> <td>
      <span tal:repeat="uspread user/spreads" tal:omit-tag="">
        <span tal:content="string:${uspread/spread_desc} (${uspread/spread})">spreads</span><br>
      </span></td>
    </tr>
    <tr><td>E-post</td> <td tal:content="user/email">foo@bar.com</td></tr>
    <tr><td valign="top">Gruppemedlemskap</td> <td>
      <span tal:repeat="ugroup user/groups" tal:omit-tag="">
        <span tal:content="ugroup/group"></span><br>
      </span></td>
    </tr>
    <span tal:condition="python: state['authlevel'] > 'c1'" tal:omit-tag="">
    <tr> <td colspan=2><a tal:attributes="href string:?action=do_user_password&entity_id=${user/account_id}">Sett nytt</a> (tilfeldig) passord.</td></tr>
    </span>
  </table>

  <span tal:condition="python: state['authlevel'] > 'c2'" tal:omit-tag="">
  Bygge <a tal:attributes="href string:?action=show_user_create&owner_id=${person/entity_id}&owner_type=person">ny bruker</a> til denne personen
  </span>
</span></span></span>
