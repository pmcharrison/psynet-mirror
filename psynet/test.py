test = "hello"

f"""
{{% extends "timeline-page.html" %}}

{{% block prompt %}}
{{{{ super() }}}}

{{{{ {test}(prompt) }}}}

{{% endblock %}}
"""