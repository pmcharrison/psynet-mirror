(function () {
  "use strict";

  function buildUrl(channel) {
    const scheme = location.protocol === "https:" ? "wss://" : "ws://";
    return (
      scheme +
      location.host +
      "/chat?channel=" +
      encodeURIComponent(channel) +
      "&worker_id=" +
      encodeURIComponent(dallinger.identity.workerId) +
      "&participant_id=" +
      encodeURIComponent(dallinger.identity.participantId)
    );
  }

  function connect({ channel, onOpen, onMessage }) {
    if (!channel) {
      throw new Error("A WebSocket channel name is required.");
    }

    let closed = false;
    const socket = new ReconnectingWebSocket(buildUrl(channel));
    const connection = {
      close() {
        if (closed) return;
        closed = true;
        socket.onopen = function () {
          socket.close();
        };
        socket.onmessage = function () {};
        socket.onclose = function () {};
        socket.close();
      },
      send(message) {
        if (closed) {
          throw new Error(`WebSocket channel "${channel}" is closed.`);
        }
        socket.send(channel + ":" + JSON.stringify(message));
      },
    };

    socket.onopen = function (event) {
      if (!closed && onOpen) {
        onOpen(event, connection);
      }
    };
    socket.onmessage = function (event) {
      if (closed || event.data.indexOf(channel + ":") !== 0) {
        return;
      }
      let message;
      try {
        message = JSON.parse(event.data.slice(channel.length + 1));
      } catch (error) {
        return;
      }
      if (onMessage) {
        onMessage(message, connection);
      }
    };

    return connection;
  }

  window.PsyNetWebSocketChannel = { connect };
})();
