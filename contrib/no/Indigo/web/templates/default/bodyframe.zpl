<html metal:use-macro="tpl/macros/page">
<span metal:fill-slot="menuframe" tal:content="structure menuframe" tal:omit-tag="">menu</span>
<span metal:fill-slot="bodyframe" tal:content="structure bodyframe" tal:omit-tag="">body</span>
</html>
