export async function activate({root}) {
    window.__psynetManagedJavascript.events.push("activate:first");
    const marker = root.querySelector("#managed-javascript-marker");
    marker.dataset.firstActive = "true";

    return async function cleanup() {
        window.__psynetManagedJavascript.events.push("cleanup:first");
    };
}
