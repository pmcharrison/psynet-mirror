from markupsafe import Markup

import psynet.experiment
from psynet.page import InfoPage
from psynet.timeline import Timeline


SESSION_ID = "shared-session"


def unity_stub_script():
    return """
    psynet.page.attributes = {
        session_id: "__SESSION_ID__",
        is_unity_page: true,
    };
    psynet.page.contents = {
        step: 1,
        label: "first",
    };
    window.__sameSessionUnityMessages = window.__sameSessionUnityMessages || [];
    var unityInstance = {
        SendMessage: function (objectName, methodName, payload) {
            window.__sameSessionUnityMessages.push({
                objectName: objectName,
                methodName: methodName,
                payload: JSON.parse(payload),
            });
        },
    };
    """.replace("__SESSION_ID__", SESSION_ID)


class Exp(psynet.experiment.Experiment):
    label = "Same-session page update test"

    timeline = Timeline(
        InfoPage(
            Markup("<p id='same-session-marker'>First same-session page</p>"),
            time_estimate=1,
            session_id=SESSION_ID,
            scripts=[unity_stub_script()],
            contents={"step": 1, "label": "first"},
        ),
        InfoPage(
            Markup("<p id='same-session-marker'>Second same-session page</p>"),
            time_estimate=1,
            session_id=SESSION_ID,
            contents={"step": 2, "label": "second"},
        ),
        InfoPage("Different-session finish page", time_estimate=1),
    )
