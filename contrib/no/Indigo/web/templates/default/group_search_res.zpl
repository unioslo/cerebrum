<span tal:define="title string:Grupper;title_id string:group_search_res" tal:omit-tag=""><span metal:use-macro="tpl/macros/page">
<span metal:fill-slot="body" tal:omit-tag="">

<span tal:condition="not:grouplist" tal:omit-tag="">
  Ingen treff
</span>

<span tal:condition="grouplist" tal:omit-tag="">

Klikk på gruppenavnet for detaljert informasjon om gruppen.
<p>

  <table border="1">
    <tr><th>Navn</th> <th>Beskrivelse</th></tr>
    <tr valign="top" tal:repeat="group grouplist"
        tal:attributes="class python:test(path('repeat/group/odd'), 'white', 'grey')">
      <td><a tal:attributes="href string:?action=do_select_target&type=group&entity_id=${group/entity_id}" tal:content="group/name">foogroup</a></td>
      <td tal:content="group/desc">en fin gruppe</td>
    </tr>
  </table>
</span>
</span></span></span>
