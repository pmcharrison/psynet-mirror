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
    continueToRelease(result.release_url);
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

      async function run() {
        pending.hidden = false;
        failure.hidden = true;
        retry.hidden = true;
        try {
          await execute(
            automatic.dataset.assignmentId,
            automatic.dataset.offerId,
          );
        } catch (error) {
          pending.hidden = true;
          failure.hidden = false;
          retry.hidden = false;
          if (global.psynet && global.psynet.log) {
            global.psynet.log.error(error.stack || String(error));
          }
        }
      }

      retry.addEventListener("click", run, { signal });
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
          await execute(assignmentId, offerId);
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
