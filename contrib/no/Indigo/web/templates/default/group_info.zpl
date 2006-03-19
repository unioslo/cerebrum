<span tal:define="title string:Gruppeinformasjon;title_id string:group_info" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<table border=0>
  <tr><td><strong>Navn:</strong></td><td tal:content="group/name">name</td></tr>
  <tr><td><strong>Opprettet:</strong></td><td tal:content="group/create_date">create_date</td></tr>
  <tr>
    <td valign="top"><strong>Brukes i:</strong></td>
    <!--TODO: fix hjelpetekst her-->
    <!--<a tal:replace="structure python:help_link('group_spread', 'Tilgjengeligelighet:')">spread</a></td>-->
    <td><span tal:repeat="spread spreads" tal:omit-tag="">
      <span tal:content="string:${spread/spread_desc}">spreads</span><br>
      <!--TODO: skal vi vise spread-kode her-->
      <!-- (${spread/spread})-->
      </span>
    </td>
  </tr> 
  <tr><td valign="top"><strong>Beskrivelse:</strong></td><td tal:content="group/description">description</td></tr>
  <tr><td><strong>Medlemmer:</strong></td><td><div tal_omit-tag="" tal:content="string:${group/c_account_u} brukere, ${group/c_group_u} grupper"/></td></tr>
</table>

<p>
<a tal:attributes="href string:?action=show_group_mod&entity_id=${group/entity_id}">Se på eller endre medlemslisten</a>
</p>

<span tal:condition="python: state['authlevel'] > 'c2'" tal:omit-tag="">
<p>
<a tal:attributes="href string:?action=show_user_create&owner_id=${group/entity_id}&owner_type=group">Opprett ny bruker eid av denne gruppen</a>
</p>
</span>

</span></span></span>
