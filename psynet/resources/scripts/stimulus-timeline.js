(function () {
  if (typeof Stimulus === "undefined") {
    console.error("Stimulus is required for inplace timeline transitions.");
    return;
  }

  let getTimelineTargetId = function (event) {
    if (event.detail && event.detail.target && event.detail.target.id) {
      return event.detail.target.id;
    }
    if (event.target && event.target.id) {
      return event.target.id;
    }
    return null;
  };

  let application = Stimulus.Application.start();

  application.register(
    "timeline",
    class extends Stimulus.Controller {
      connect() {
        this.transitionState = "idle";
      }

      beginTransition() {
        this.transitionState = "activating";
      }

      completeTransition() {
        this.resolvePendingTransition();
        this.transitionState = "idle";
      }

      async abortTransition(error) {
        await psynet.handleTimelineTransitionFailure(error);
        this.rejectPendingTransition(error);
        this.transitionState = "idle";
      }

      hasPendingMainBodyTransition(event) {
        return (
          !!psynet.pendingTimelineTransition &&
          this.isMainBodyEvent(event) &&
          this.transitionState === "idle"
        );
      }

      consumePendingTransition() {
        let transition = psynet.pendingTimelineTransition;
        psynet.pendingTimelineTransition = null;
        return transition;
      }

      resolvePendingTransition() {
        let transition = this.consumePendingTransition();
        if (transition) {
          transition.resolve();
        }
      }

      rejectPendingTransition(error) {
        let transition = this.consumePendingTransition();
        if (transition) {
          transition.reject(error);
        }
      }

      isMainBodyEvent(event) {
        return getTimelineTargetId(event) === "main-body";
      }

      async cleanupCurrentPageResources() {
        await psynet.cleanupPageResources();
      }

      resetSwappedPageState() {
        psynet.clearLucidTermination();
        psynet.resetPageState();
        psynet.refreshTemplateData();
      }

      async hydrateSwappedPageAssets() {
        await psynet.hydrateFragmentAssets();
      }

      async rebuildSwappedPageTrial() {
        await psynet.rebuildTrial();
      }

      async runSwappedPageMainScripts() {
        await psynet.runFragmentScripts(psynet.getMainBodyScripts());
      }

      async initializeSwappedPage() {
        await psynet.initActivatedPage();
      }

      async runSwappedPageDeferredScripts() {
        await psynet.runFragmentScripts(psynet.getDeferredPageScripts());
      }

      async finalizeSwappedPageActivation() {
        await psynet.finalizePageReady();
        psynet.nextPagePending = false;
        psynet.setTimelineTransitionBusy(false);
        psynet.log.info("Swapped timeline page activation complete.");
      }

      async activateSwappedPageLifecycle() {
        await this.cleanupCurrentPageResources();
        this.resetSwappedPageState();
        await this.hydrateSwappedPageAssets();
        await this.rebuildSwappedPageTrial();
        await this.runSwappedPageMainScripts();
        await this.initializeSwappedPage();
        await this.runSwappedPageDeferredScripts();
        await this.finalizeSwappedPageActivation();
      }

      buildRequestFailure(event) {
        let xhrStatus =
          event.detail && event.detail.xhr ? event.detail.xhr.status : null;
        return xhrStatus === null
          ? new Error("Timeline transition request could not be sent.")
          : new Error(
              "Timeline transition request returned status " +
                xhrStatus +
                ".",
            );
      }

      async afterSettle(event) {
        if (!this.hasPendingMainBodyTransition(event)) {
          return;
        }

        psynet.log.info("Observed htmx afterSettle for main-body.");
        this.beginTransition();
        try {
          await this.activateSwappedPageLifecycle();
          this.completeTransition();
        } catch (error) {
          await this.abortTransition(error);
        }
      }

      async requestFailed(event) {
        if (!psynet.pendingTimelineTransition || !this.isMainBodyEvent(event)) {
          return;
        }

        psynet.log.info("Observed htmx request failure for main-body.");
        let error = this.buildRequestFailure(event);
        await this.abortTransition(error);
      }
    },
  );

  window.psynetStimulusApp = application;
})();
