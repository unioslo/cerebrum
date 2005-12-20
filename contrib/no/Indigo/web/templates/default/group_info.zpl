<span tal:define="title string:Gruppe informasjon;title_id string:group_info" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<table border=1>
  <tr><TH>Felt</TH> <TH>Verdi</TH> </tr>
  <tr><td>Navn</td>      <td tal:content="group/name">name</td></tr>
  <tr><td>Opprettet dato</td>      <td tal:content="group/create_date">create_date</td></tr>
  <tr>
    <td><a tal:replace="structure python:help_link('group_spread', 'Kjent i')">spread</a></td>
    <td><span tal:repeat="spread spreads" tal:omit-tag="">
      <span tal:content="string:${spread/spread_desc} (${spread/spread})">spreads</span><br>
      </span>
    </td>
  </tr>
  <tr><td>Beskrivelse</td>      <td tal:content="group/description">description</td></tr>
  <tr><td>Medlemmer</td>      <td><div tal_omit-tag="" tal:content="string:${group/c_account_u} brukere, ${group/c_group_u} grupper"/></td></tr>
</table>

<p>

<a tal:attributes="href string:?action=show_group_mod&entity_id=${group/entity_id}">Liste/endre</a> medlemmer
</p>

<span tal:condition="python: state['authlevel'] > 'c2'" tal:omit-tag="">
<p>

Bygge <a tal:attributes="href string:?action=show_user_create&owner_id=${group/entity_id}&owner_type=group">ny bruker</a> eid av denne gruppen
</p>
</span>

</span></span></span>
