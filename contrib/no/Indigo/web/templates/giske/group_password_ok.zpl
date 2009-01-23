<span tal:define="title string:Passord for gruppemedlemmer;title_id string:group_info" tal:omit-tag="">
  <span metal:use-macro="tpl/macros/page">
    <span metal:fill-slot="body" tal:omit-tag="">

      <h1>Passordliste for medlemmer av gruppen 
      <b tal:replace="string:${group_name}">group name</b>:
      </h1>
      <table>
        <tr>
          <th>Navn</th><th>Fødselsdato</th><th>Skole</th><th>Brukernavn</th><th>Passord</th>
	</tr>
        <tr valign="top" tal:repeat="member members"
            tal:attributes="class python:test(path('repeat/member/odd'), 'white', 'grey')">
          <td tal:content="string:${member/name}">navn</td>
          <td tal:content="member/birth_date">dato</td>
          <td tal:content="member/institution_name">skolenavn</td>
          <td tal:content="member/uname">bruker</td>
          <td tal:content="member/password">passord</td>
        </tr>
      </table>
    </span>
  </span>
</span>
