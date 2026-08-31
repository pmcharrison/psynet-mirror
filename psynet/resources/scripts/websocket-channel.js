(function () {
  "use strict";

  const channels = new Map();

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

  function createChannel(channel) {
    const subscribers = new Set();
    const socket = new ReconnectingWebSocket(buildUrl(channel));
    const entry = { channel, socket, subscribers };

    socket.onopen = function (event) {
      subscribers.forEach((subscriber) => subscriber.onOpen?.(event));
    };
    socket.onmessage = function (event) {
      if (event.data.indexOf(channel + ":") !== 0) {
        return;
      }
      let message;
      try {
        message = JSON.parse(event.data.slice(channel.length + 1));
      } catch (error) {
        console.warn(`Ignored malformed JSON on WebSocket channel "${channel}".`);
        return;
      }
      subscribers.forEach((subscriber) => subscriber.onMessage?.(message));
    };

    channels.set(channel, entry);
    return entry;
  }

  function connect({ channel, onOpen, onMessage }) {
    if (!channel) {
      throw new Error("A WebSocket channel name is required.");
    }

    const entry = channels.get(channel) || createChannel(channel);
    let closed = false;
    let subscriber;
    const connection = {
      close() {
        if (closed) return;
        closed = true;
        entry.subscribers.delete(subscriber);
      },
      send(message) {
        if (closed) {
          throw new Error(`WebSocket channel "${channel}" is closed.`);
        }
        entry.socket.send(channel + ":" + JSON.stringify(message));
      },
    };
    subscriber = {
      onOpen: (event) => {
        if (!closed && onOpen) onOpen(event, connection);
      },
      onMessage: (message) => {
        if (!closed && onMessage) onMessage(message, connection);
      },
    };
    entry.subscribers.add(subscriber);
    if (entry.socket.readyState === WebSocket.OPEN) {
      setTimeout(() => subscriber.onOpen({ isReconnect: false }), 0);
    }

    return connection;
  }

  window.PsyNetWebSocketChannel = { connect };
})();
