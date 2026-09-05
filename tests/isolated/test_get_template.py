import json
import re
import subprocess
from importlib import resources

from psynet.timeline import get_template, templates


def get_template_legacy(name):
    assert isinstance(name, str)
    return resources.files(templates).joinpath(name).read_text()


def test_get_template():
    page = "timeline-page.html"
    assert get_template(page) == get_template_legacy(page)


def test_start_template_only_creates_after_participant_not_found():
    template = resources.files("psynet").joinpath("templates/start.html").read_text()
    function = re.search(
        r"function shouldAttemptCreate\(resp\) \{.*?^\s*\}",
        template,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert function is not None
    responses = [
        {"status": 403, "errorCode": "participant_not_found"},
        {"status": 403, "errorCode": "assignment_id_missing"},
        {"status": 403, "errorCode": "other_forbidden_error"},
        {"status": 500, "errorCode": "participant_not_found"},
    ]
    script = (
        f"{function.group(0)}\n"
        f"console.log(JSON.stringify({json.dumps(responses)}"
        ".map(response => shouldAttemptCreate(response))));"
    )

    result = subprocess.run(
        ["node", "-e", script], check=True, capture_output=True, text=True
    )

    assert json.loads(result.stdout) == [True, True, False, False]
