(function (global) {
  "use strict";

  let controller = null;
  let autoRedirectTimer = null;

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

  async function executePlan(assignmentId, offerId, reloadStaleOffer = true) {
    if (!assignmentId || !offerId) {
      throw new Error("The server did not provide an early-exit plan.");
    }
    const response = await fetch(
      "/execute_early_exit_plan/" + encodeURIComponent(assignmentId),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offer_id: offerId }),
      },
    );
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      // A stale offer cannot be fixed by resending it. Voluntary Leave reloads
      // immediately; automatic recovery waits for the participant to retry so
      // a persistently stale server cannot cause a reload loop.
      if (result.error_code === "stale_early_exit_offer") {
        if (reloadStaleOffer) {
          global.location.reload();
          return;
        }
        const error = new Error("The early-exit offer is no longer current.");
        error.code = result.error_code;
        throw error;
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
    if (autoRedirectTimer) {
      global.clearTimeout(autoRedirectTimer);
      autoRedirectTimer = null;
    }
    controller = new AbortController();
    const { signal } = controller;

    const automatic = document.getElementById("automatic-early-exit");
    if (automatic) {
      const pending = document.getElementById("automatic-early-exit-pending");
      const failure = document.getElementById("automatic-early-exit-failure");
      const retry = document.getElementById("automatic-early-exit-retry");
      const ready = document.getElementById("automatic-early-exit-ready");
      const finish = document.getElementById("automatic-early-exit-continue");
      const preparationPostUrl = automatic.dataset.preparationPostUrl;
      const preparationPostData = JSON.parse(
        automatic.dataset.preparationPostData || "{}",
      );
      const actionPostUrl = automatic.dataset.actionPostUrl;
      const actionPostData = JSON.parse(
        automatic.dataset.actionPostData || "{}",
      );
      const destinationUrl = automatic.dataset.destinationUrl;
      const autoRedirectDelay = Number(
        automatic.dataset.autoRedirectDelayMs || 0,
      );
      let releaseUrl = null;
      let prepared = false;
      let reloadOnRetry = false;

      function showFailure(error) {
        reloadOnRetry = error.code === "stale_early_exit_offer";
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
        if (autoRedirectTimer) {
          global.clearTimeout(autoRedirectTimer);
          autoRedirectTimer = null;
        }
        if (finish) finish.disabled = true;
        try {
          if (actionPostUrl) {
            await postForm(actionPostUrl, actionPostData);
          }
          continueToRelease(destinationUrl || releaseUrl);
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
        reloadOnRetry = false;
        try {
          if (automatic.dataset.offerId) {
            releaseUrl = await executePlan(
              automatic.dataset.assignmentId,
              automatic.dataset.offerId,
              false,
            );
            if (!releaseUrl) return;
          }
          if (preparationPostUrl) {
            await postForm(preparationPostUrl, preparationPostData);
          }
          prepared = true;
          pending.hidden = true;
          ready.hidden = false;
          if (finish) finish.hidden = false;
          if (autoRedirectDelay > 0) {
            autoRedirectTimer = global.setTimeout(
              followParticipantAction,
              autoRedirectDelay,
            );
          }
        } catch (error) {
          showFailure(error);
        }
      }

      retry.addEventListener(
        "click",
        () => {
          if (reloadOnRetry) {
            global.location.reload();
          } else if (prepared) {
            followParticipantAction();
          } else {
            run();
          }
        },
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
          const releaseUrl = await executePlan(assignmentId, offerId);
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
