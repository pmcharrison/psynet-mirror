(function () {
    var N = psynet.var["num_chatrooms"];
    var MAX_OCC = psynet.var["max_occupancy"];  // null = no limit
    var GLOBAL_CH = psynet.var["chatroom_global_channel"];

    function buildButtons(rooms) {
        var container = document.getElementById("room-buttons");
        container.innerHTML = "";
        for (var i = 0; i < N; i++) {
            var room  = (rooms && rooms[String(i)]) || {};
            var count = room.count || 0;
            var full  = MAX_OCC != null && count >= MAX_OCC;
            var btn   = document.createElement("button");
            btn.className = "btn btn-primary m-2" + (full ? " disabled" : "");
            btn.disabled  = full;
            btn.dataset.roomIndex = String(i);
            var countLabel = MAX_OCC ? count + "/" + MAX_OCC : String(count);
            btn.innerHTML = "Room " + (i + 1)
                + "<br><small>" + countLabel
                + " participant" + (count === 1 ? "" : "s") + "</small>"
                + (full ? "<br><small>(full)</small>" : "");
            container.appendChild(btn);
        }
    }

    psynet.addPageEventListener(document.getElementById("room-buttons"), "click", function (event) {
        var button = event.target.closest("button[data-room-index]");
        if (button && !button.disabled) {
            psynet.nextPage(button.dataset.roomIndex);
        }
    });

    var wsScheme = location.protocol === "https:" ? "wss://" : "ws://";
    // Dallinger's WebSocket relay routes messages by channel name. The client
    // prefixes each outgoing message with "chatrooms:" so the relay knows which
    // channel to publish to. Incoming messages arrive with the same prefix, which
    // we strip before parsing the JSON payload.
    var occSocket = new ReconnectingWebSocket(
        wsScheme + location.host + "/chat?channel=" + GLOBAL_CH
        + "&worker_id=" + dallinger.identity.workerId
        + "&participant_id=" + dallinger.identity.participantId
    );

    psynet.addPageCleanupCallback(function () {
        occSocket.close();
    });

    // On every (re)connect, request a fresh occupancy snapshot. The server
    // responds by broadcasting occupancy_update to all subscribers, so every
    // client on this page receives the same consistent state simultaneously.
    // Any join/leave that occurs after the request will also trigger a broadcast,
    // so there is no window where counts can drift out of sync.
    occSocket.onopen = function () {
        occSocket.send(GLOBAL_CH + ":" + JSON.stringify({ type: "request_occupancy" }));
    };

    occSocket.onmessage = function (event) {
        if (event.data.indexOf(GLOBAL_CH + ":") !== 0) return;
        try {
            var msg = JSON.parse(event.data.slice(GLOBAL_CH.length + 1));
            if (msg.type === "occupancy_update") {
                buildButtons(msg.rooms || {});
            }
        } catch (e) {}
    };
})();
