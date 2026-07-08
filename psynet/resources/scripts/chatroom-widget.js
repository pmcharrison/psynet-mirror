// Built-in modular-page chatroom widget.
//
// This script is contributed to the page by the ChatRoom component via its
// get_scripts() hook (rather than being inlined in the macro template), so it
// follows the same SPA contract PsyNet imposes on author-provided components.
// Per-instance configuration is injected as `window.__psynetChatroomConfig`
// immediately before this script by ChatRoom.get_scripts().
(function () {
    var CONFIG       = window.__psynetChatroomConfig || {};
    var ROOM_ID      = CONFIG.room_id;
    var GLOBAL_CH    = CONFIG.channel;
    var SHOW_PARTS   = CONFIG.show_participants;
    var SHOW_HISTORY = CONFIG.show_history;
    var MY_ID        = String(dallinger.identity.participantId);

    var chatSocket = null;
    var leftChat   = false;
    var firstOpen  = true;

    var wsScheme = location.protocol === "https:" ? "wss://" : "ws://";
    chatSocket = new ReconnectingWebSocket(
        wsScheme + location.host + "/chat?channel=" + GLOBAL_CH
        + "&worker_id=" + dallinger.identity.workerId
        + "&participant_id=" + MY_ID
    );

    chatSocket.onopen = function () {
        if (leftChat) return;
        chatSocket.send(GLOBAL_CH + ":" + JSON.stringify({
            type: "join_room",
            room_id: ROOM_ID,
            sender: MY_ID,
        }));
        if (firstOpen) {
            if (SHOW_HISTORY) {
                chatSocket.send(GLOBAL_CH + ":" + JSON.stringify({
                    type: "request_state",
                    room_id: ROOM_ID,
                    sender: MY_ID,
                }));
            }
            firstOpen = false;
        }
    };

    chatSocket.onmessage = function (event) {
        if (leftChat) return;
        if (event.data.indexOf(GLOBAL_CH + ":") !== 0) return;
        var msg;
        try {
            msg = JSON.parse(event.data.slice(GLOBAL_CH.length + 1));
        } catch (e) { return; }

        if (String(msg.room_id) !== String(ROOM_ID)) return;

        if (msg.type === "message") {
            renderMessage(msg);
        } else if (msg.type === "occupancy_update") {
            if (SHOW_PARTS) rebuildParticipantList(msg.participants || []);
        } else if (msg.type === "history") {
            if (SHOW_HISTORY && String(msg.target_participant_id) === MY_ID) {
                // Clear before re-rendering to avoid duplicates on reconnect.
                document.getElementById("chatroom-messages").innerHTML = "";
                (msg.messages || []).forEach(renderMessage);
            }
        }
    };

    function leaveChat() {
        if (leftChat) return;
        leftChat = true;
        try {
            chatSocket.send(GLOBAL_CH + ":" + JSON.stringify({
                type: "leave_room",
                room_id: ROOM_ID,
                sender: MY_ID,
            }));
        } catch (e) {}
        try {
            if (chatSocket && typeof chatSocket.close === "function") {
                chatSocket.close();
            }
        } catch (e) {}
    }

    psynet.addPageCleanupCallback(leaveChat);
    psynet.addPageEventListener(window, "beforeunload", function () {
        leaveChat();
    });

    document.getElementById("chatroom-send-btn").onclick = function () {
        var input = document.getElementById("chatroom-chat-input");
        var text  = input.value.trim();
        if (!text) return;
        chatSocket.send(GLOBAL_CH + ":" + JSON.stringify({
            type: "message",
            room_id: ROOM_ID,
            content: text,
            sender: MY_ID,
        }));
        input.value = "";
        input.focus();
    };

    psynet.addPageEventListener(document.getElementById("chatroom-chat-input"), "keypress", function (e) {
        if (e.key === "Enter") {
            document.getElementById("chatroom-send-btn").click();
            e.preventDefault();
        }
    });

    function senderLabel(senderId) {
        return String(senderId) === MY_ID ? "You" : "Participant " + senderId;
    }

    function renderMessage(msg) {
        var feed    = document.getElementById("chatroom-messages");
        var p       = document.createElement("p");
        var label   = document.createElement("strong");
        label.textContent = senderLabel(msg.sender) + ": ";
        var content = document.createTextNode(msg.content || "");
        p.appendChild(label);
        p.appendChild(content);
        feed.appendChild(p);
        feed.scrollTop = feed.scrollHeight;
    }

    function rebuildParticipantList(ids) {
        var list = document.getElementById("chatroom-participants");
        list.innerHTML = "";
        ids.forEach(function (id) {
            var li = document.createElement("li");
            li.textContent = String(id) === MY_ID ? "You" : "Participant " + id;
            list.appendChild(li);
        });
    }
})();
