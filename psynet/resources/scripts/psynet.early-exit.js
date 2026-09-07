(function (global) {
  "use strict";

  let controller = null;

  function continueToRelease(releaseUrl) {
    if (!releaseUrl) throw new Error("The server did not provide a release URL.");
    if (global.dallinger && global.dallinger.allowExit) {
      global.dallinger.allowExit();
    }
    global.location.replace(releaseUrl);
  }

  async function postForm(url, data) {
    if (!url) throw new Error("The server did not provide the next action.");
    const response = await fetch(url, {
      method: "POST",
      body: new URLSearchParams(data),
    });
    if (!response.ok) throw new Error("The next action did not succeed.");
  }

  async function execute(assignmentId, offerId) {
    if (!assignmentId || !offerId) {
      throw new Error("The server did not provide an early-exit plan.");
    }
    const response = await fetch(
      "/set_participant_as_early_exited/" +
        encodeURIComponent(assignmentId),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offer_id: offerId }),
      },
    );
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      // A stale offer cannot be fixed by resending it, so reload the page and
      // let the server decide what it now offers.
      if (result.error_code === "stale_early_exit_offer") {
        global.location.reload();
        return;
      }
      throw new Error("Failed to record early exit.");
    }
    if (!result.release_url) {
      throw new Error("The server did not provide a release URL.");
    }
    return result.release_url;
  }

  function init() {
    if (controller) controller.abort();
    controller = new AbortController();
    const { signal } = controller;

    const automatic = document.getElementById("automatic-early-exit");
    if (automatic) {
      const pending = document.getElementById("automatic-early-exit-pending");
      const failure = document.getElementById("automatic-early-exit-failure");
      const retry = document.getElementById("automatic-early-exit-retry");
      const ready = document.getElementById("automatic-early-exit-ready");
      const finish = document.getElementById("automatic-early-exit-continue");
      const action = automatic.dataset.action;
      const participantId = automatic.dataset.participantId;
      const postUrl = automatic.dataset.postUrl;
      const redirectUrl = automatic.dataset.redirectUrl;
      const postData = JSON.parse(automatic.dataset.postData || "{}");
      let releaseUrl = null;
      let prepared = false;

      function showFailure(error) {
        pending.hidden = true;
        ready.hidden = true;
        if (finish) {
          finish.hidden = true;
          finish.disabled = false;
        }
        failure.hidden = false;
        retry.hidden = false;
        if (global.psynet && global.psynet.log) {
          global.psynet.log.error(error.stack || String(error));
        }
      }

      async function followParticipantAction() {
        if (finish) finish.disabled = true;
        try {
          if (action === "follow_release") {
            continueToRelease(releaseUrl);
            return;
          }
          if (action === "post_and_redirect") {
            await postForm(postUrl, postData);
            continueToRelease(redirectUrl);
            return;
          }
          throw new Error("The server provided an unknown recovery action.");
        } catch (error) {
          showFailure(error);
        }
      }

      async function run() {
        pending.hidden = false;
        failure.hidden = true;
        retry.hidden = true;
        ready.hidden = true;
        if (finish) finish.hidden = true;
        releaseUrl = null;
        prepared = false;
        try {
          releaseUrl = await execute(
            automatic.dataset.assignmentId,
            automatic.dataset.offerId,
          );
          if (!releaseUrl) return;
          if (action === "close_page") {
            await postForm("/worker_complete", {
              participant_id: participantId,
            });
          }
          prepared = true;
          pending.hidden = true;
          ready.hidden = false;
          if (finish) finish.hidden = false;
        } catch (error) {
          showFailure(error);
        }
      }

      retry.addEventListener(
        "click",
        () => (prepared ? followParticipantAction() : run()),
        { signal },
      );
      if (finish) {
        finish.addEventListener("click", followParticipantAction, { signal });
      }
      run();
      return;
    }

    const trigger =
      document.getElementById("early-exit-button") ||
      document.getElementById("early-exit-open");
    const modal = document.getElementById("early-exit-modal");
    const cancel = document.getElementById("early-exit-cancel");
    const confirm = document.getElementById("early-exit-confirm");
    if (!trigger || !modal || !cancel) return;

    function closeModal() {
      modal.hidden = true;
      modal.style.display = "none";
      trigger.focus();
    }

    function openModal() {
      modal.hidden = false;
      modal.style.display = "block";
      cancel.focus();
    }

    trigger.addEventListener("click", openModal, { signal });
    cancel.addEventListener("click", closeModal, { signal });
    modal.addEventListener(
      "click",
      (event) => {
        if (event.target === modal) closeModal();
      },
      { signal },
    );
    document.addEventListener(
      "keydown",
      (event) => {
        if (event.key === "Escape" && !modal.hidden) closeModal();
      },
      { signal },
    );

    if (!confirm) return;
    confirm.addEventListener(
      "click",
      async () => {
        const assignmentId = modal.dataset.assignmentId;
        const offerId = modal.dataset.offerId;
        if (!assignmentId || !offerId) return;

        confirm.disabled = true;
        cancel.disabled = true;
        try {
          const releaseUrl = await execute(assignmentId, offerId);
          if (releaseUrl) continueToRelease(releaseUrl);
        } catch (error) {
          confirm.disabled = false;
          cancel.disabled = false;
          if (global.psynet && global.psynet.log) {
            global.psynet.log.error(error.stack || String(error));
            await global.psynet.alert(
              "We could not end the experiment. Please try again.",
            );
          } else {
            dallinger.error(error);
          }
        }
      },
      { signal },
    );
  }

  global.psynetEarlyExit = { init };
})(window);
