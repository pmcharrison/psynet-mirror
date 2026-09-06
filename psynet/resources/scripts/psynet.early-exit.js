(function (global) {
  "use strict";

  let controller = null;

  function postWorkerComplete(participantId) {
    return new Promise((resolve, reject) => {
      dallinger
        .post("/worker_complete", { participant_id: participantId })
        .done(resolve)
        .fail(reject);
    });
  }

  async function finish(participantId) {
    if (global.psynet && global.psynet.finishAndGoToExit) {
      global.psynet.finishAndGoToExit();
      return;
    }
    await postWorkerComplete(participantId);
    global.location.replace(
      "/recruiter-exit?participant_id=" + encodeURIComponent(participantId),
    );
  }

  function init() {
    if (controller) controller.abort();
    controller = new AbortController();
    const { signal } = controller;

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
        const participantId = modal.dataset.participantId;
        if (!assignmentId || !participantId) return;

        confirm.disabled = true;
        cancel.disabled = true;
        try {
          const unpaid = modal.dataset.unpaid === "true";
          const response = await fetch(
            "/set_participant_as_early_exited/" +
              encodeURIComponent(assignmentId) +
              (unpaid ? "?payment=none" : ""),
          );
          if (!response.ok) throw new Error("Failed to record early exit.");
          await finish(participantId);
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
