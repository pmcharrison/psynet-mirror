(function () {
    var ROOM_ID = psynet.var["chatroom_room_id"];
    var GLOBAL_CH = psynet.var["chatroom_global_channel"];
    var LABEL = psynet.var["chatroom_room_label"];
    var SHOW_HISTORY = psynet.var["chatroom_show_history"];
    var MY_ID = dallinger.identity.participantId;
    var pageActive = true;

    psynet.addPageCleanupCallback(function () {
        pageActive = false;
    });

    // ROOM_ID could be absent if the participant reached this page without
    // completing room selection (e.g. via browser history navigation).
    // We wait for psynet.pageLoaded before calling nextPage because
    // nextPage requires the PsyNet timeline to be fully initialised.
    if (ROOM_ID === null || ROOM_ID === undefined) {
        (function wait() {
            if (!pageActive) return;
            if (!psynet.pageLoaded) { psynet.trial.setTimer(wait, 50); return; }
            psynet.nextPage();
        })();
        return;
    }

    ROOM_ID = String(ROOM_ID);

    var chatSocket = null;
    var leftChat = false;

    document.getElementById("chatroom-room-label").textContent = LABEL;

    openWebSocket();

    psynet.addPageCleanupCallback(function () {
        leaveChat({ advance: false });
        chatSocket && chatSocket.close();
    });

    function leaveChat(options) {
        options = options || {};
        if (leftChat) return;
        leftChat = true;
        try {
            chatSocket && chatSocket.send(GLOBAL_CH + ":" + JSON.stringify({
                type: "leave_room",
                room_id: ROOM_ID,
                sender: MY_ID,
            }));
        } catch (e) {}
        if (options.advance !== false) {
            psynet.nextPage();
        }
    }

    function openWebSocket() {
        var wsScheme = location.protocol === "https:" ? "wss://" : "ws://";
        // Dallinger's WebSocket relay routes messages by channel name.
        // We connect to GLOBAL_CH ("chatrooms") and prefix every outgoing
        // message with "chatrooms:" so the relay knows which channel to
        // publish to. Incoming messages arrive with the same prefix, which
        // we strip before parsing the JSON payload.
        chatSocket = new ReconnectingWebSocket(
            wsScheme + location.host + "/chat?channel=" + GLOBAL_CH
            + "&worker_id=" + dallinger.identity.workerId
            + "&participant_id=" + MY_ID
        );

        var firstOpen = true;
        chatSocket.onopen = function () {
            if (leftChat) return;
            chatSocket.send(GLOBAL_CH + ":" + JSON.stringify({
                type: "join_room",
                room_id: ROOM_ID,
                sender: MY_ID,
            }));
            // Request a fresh occupancy snapshot on every (re)connect.
            // The server responds with an occupancy_update broadcast (see
            // onmessage below) that rebuilds the participant sidebar.
            // On a fresh join, the join_room above already triggers a
            // broadcast; on reconnects it does not (join_room is a no-op
            // server-side), so request_occupancy ensures we always resync.
            chatSocket.send(GLOBAL_CH + ":" + JSON.stringify({
                type: "request_occupancy",
            }));
            // History is only fetched once — on reconnects the feed already
            // contains messages received before the drop.
            if (firstOpen && SHOW_HISTORY) {
                fetchHistory();
            }
            firstOpen = false;
        };

        // Dallinger relays every incoming message to all channel subscribers,
        // including the sender. Participants also receive their own chat
        // messages, so sent messages appear via this handler rather than
        // being added to the feed manually.
        chatSocket.onmessage = function (event) {
            if (event.data.indexOf(GLOBAL_CH + ":") !== 0) return;
            var msg;
            try {
                msg = JSON.parse(event.data.slice(GLOBAL_CH.length + 1));
            } catch (e) { return; }

            // occupancy_update is a server-initiated broadcast (no room_id).
            // Use it to rebuild the participant sidebar from the server's
            // authoritative state — same mechanism as the room-selection page,
            // but here we also extract per-room participant IDs.
            if (msg.type === "occupancy_update") {
                var roomData = msg.rooms && msg.rooms[ROOM_ID];
                rebuildParticipantList(roomData ? roomData.participants || [] : []);
                return;
            }

            if (String(msg.room_id) !== ROOM_ID) return;

            if (msg.type === "message") {
                renderMessage(msg);
            }
        };

        psynet.addPageEventListener(document.getElementById("send-btn"), "click", function () {
            var input = document.getElementById("chat-input");
            var text = input.value.trim();
            if (text) {
                chatSocket.send(GLOBAL_CH + ":" + JSON.stringify({
                    type: "message",
                    room_id: ROOM_ID,
                    content: text,
                    sender: MY_ID,
                }));
                input.value = "";
                input.focus();
            }
        });

        psynet.addPageEventListener(document.getElementById("leave-btn"), "click", function () {
            leaveChat();
        });

        psynet.addPageEventListener(document.getElementById("chat-input"), "keypress", function (e) {
            if (e.key === "Enter") {
                document.getElementById("send-btn").click();
                e.preventDefault();
            }
        });
    }

    function fetchHistory() {
        fetch("/chatroom_history?room_id=" + ROOM_ID + "&participant_id=" + MY_ID + "&unique_id=" + psynet.uniqueId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.messages || data.messages.length === 0) return;
                var feed = document.getElementById("chatroom-messages");
                feed.innerHTML = "";
                data.messages.forEach(function (msg) { renderMessage(msg); });
            })
            .catch(function () {});
    }

    function rebuildParticipantList(participants) {
        var list = document.getElementById("chatroom-participants");
        list.innerHTML = "";
        participants.forEach(function (pid) {
            var li = document.createElement("li");
            li.id = "participant-" + pid;
            li.textContent = "Participant " + pid;
            list.appendChild(li);
        });
        var count = participants.length;
        document.getElementById("participant-count").textContent = count;
        document.getElementById("participant-count-plural").textContent =
            count === 1 ? "" : "s";
    }

    function renderMessage(msg) {
        var feed = document.getElementById("chatroom-messages");
        var p = document.createElement("p");
        var sender = document.createElement("strong");
        sender.textContent = "Participant " + msg.sender + ": ";
        var content = document.createTextNode(msg.content || "");
        p.appendChild(sender);
        p.appendChild(content);
        feed.appendChild(p);
        feed.scrollTop = feed.scrollHeight;
    }
})();
