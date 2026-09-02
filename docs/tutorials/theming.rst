Theming
=======

Every participant-facing page (ad, consent, timeline, waiting and error pages)
shares a default theme. The theme aims to be quiet: participants should notice
the task, not the interface. Colour is reserved for the primary action, the
progress indicator and selected options, so that the surrounding interface does
not compete with your stimuli.

The default layout places page content on a white surface over a lightly tinted
page background. This gives the content a visible boundary, which makes it
obvious where a page ends and whether it needs scrolling.

Design tokens
-------------

The theme is defined in a single stylesheet, ``psynet/resources/css/participant.css``,
which is served at ``/static/css/participant.css``. Everything it draws is
expressed through CSS custom properties, so in most cases you can restyle an
experiment by redefining a handful of tokens rather than overriding rules.

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Token
     - Default
     - Purpose
   * - ``--psynet-page-bg``
     - ``#eef1f6``
     - Page background behind the content surface.
   * - ``--psynet-surface``
     - ``#ffffff``
     - Content surface that holds page content.
   * - ``--psynet-surface-sunken``
     - ``#f7f9fc``
     - Panels that group response options.
   * - ``--psynet-border``
     - ``#dfe5ee``
     - Default border colour.
   * - ``--psynet-text``
     - ``#1f2733``
     - Body text.
   * - ``--psynet-text-muted``
     - ``#5c6b7f``
     - Secondary text, for example the reward footer.
   * - ``--psynet-accent``
     - ``#3070c8``
     - Primary action, progress fill, selected states, focus ring.
   * - ``--psynet-accent-rgb``
     - ``48, 112, 200``
     - Comma-separated channels of the accent. Bootstrap links and
       utilities such as ``text-primary`` read this, not the hex token.
   * - ``--psynet-accent-hover``
     - ``#275ba4``
     - Hover state for primary actions and links.
   * - ``--psynet-accent-hover-rgb``
     - ``39, 91, 164``
     - Comma-separated channels of the hover colour, for Bootstrap.
   * - ``--psynet-accent-contrast``
     - ``#ffffff``
     - Text drawn on the accent, for example primary-button labels.
   * - ``--psynet-content-width``
     - ``900px``
     - Maximum width of the content surface.
   * - ``--psynet-measure``
     - ``62ch``
     - Maximum width of prose, so long text stays readable.
   * - ``--psynet-graphic-vertical-chrome``
     - ``25rem``
     - Height reserved around a ``GraphicPrompt`` so the page still
       fits a typical laptop window. Shrinks the graphic when 60% of
       the window would make the page scroll.

To recolour an experiment, redefine the tokens in your own stylesheet.
Buttons, progress, and focus follow ``--psynet-accent``. Links and Bootstrap
utilities such as ``text-primary`` also need the matching ``-rgb`` tokens,
because Bootstrap composes those colours from RGB triples:

::

    /* static/theme.css */
    :root {
        --psynet-accent: #7a4fa3;
        --psynet-accent-rgb: 122, 79, 163;
        --psynet-accent-hover: #623e84;
        --psynet-accent-hover-rgb: 98, 62, 132;
        --psynet-page-bg: #f5f2f8;
    }

and register it on your experiment class:

::

    class Exp(psynet.experiment.Experiment):
        css_links = ["static/theme.css"]

Because ``participant.css`` avoids ``!important``, an ordinary rule in your own
stylesheet is enough to override a default; you should not need to escalate
specificity. See the ``custom_theme`` demo for a complete example.

.. note::

    Token overrides apply to timeline pages. ``css`` and ``css_links`` are not
    currently injected into the ad and consent pages; to restyle those, provide
    your own ``templates/ad.html`` or ``templates/consent.html``.

Wider stimuli
-------------

If a stimulus needs more room than the default content width, widen the surface
for the whole experiment:

::

    Exp.css.append(":root { --psynet-content-width: 1140px; }")

Prose remains bounded by ``--psynet-measure``, so widening the surface does not
produce over-long lines of text.

Colour and stimuli
------------------

For experiments where colour is part of the measurement, consider neutralising
the accent so that no saturated colour appears near your stimuli:

::

    Exp.css.append(":root { --psynet-accent: #44556b; --psynet-accent-rgb: 68, 85, 107; }")

Dark mode
---------

Setting ``color_mode`` to ``dark`` or ``auto`` in ``config.txt`` switches the
tokens to a dark palette; see :doc:`/experiment_development/configuration`. If
you override tokens yourself and support dark mode, define your overrides for
both schemes:

::

    :root {
        --psynet-accent: #7a4fa3;
        --psynet-accent-rgb: 122, 79, 163;
    }
    [data-bs-theme="dark"] {
        --psynet-accent: #b48ad4;
        --psynet-accent-rgb: 180, 138, 212;
    }

Response options
----------------

:class:`~psynet.modular_page.RadioButtonControl` and
:class:`~psynet.modular_page.CheckboxControl` render each option as a full-width
row with a minimum height of 46px, so the whole row is clickable. The markup is:

::

    <div class="control-container psynet-options">
        <label class="psynet-option">
            <input type="radio" id="..." name="..." class="response">
            <span class="psynet-option-label">Label</span>
        </label>
    </div>

If you previously styled these controls by targeting the bare ``label`` or
``input`` elements, target ``.psynet-option`` and ``.psynet-option-label``
instead.

The selected state is styled with ``:has()``, which is why the default
``min_browser_version`` is Chrome 105; see
:doc:`/experiment_development/configuration`.

Pages that scroll
-----------------

The footer is fixed to the bottom of the window, and the page reserves space for
it so that content is never left permanently underneath. PsyNet's front-end
tests additionally check that a page which does not declare
``expect_scrolling`` cannot scroll at all (not merely that the Next button is
visible), which catches a stimulus that has grown large enough to push content
off a typical laptop window.

If a page is genuinely meant to be longer than the window, say so:

::

    InfoPage(long_briefing_text, time_estimate=60, expect_scrolling=True)

or, for a custom page class:

::

    class MyLongPage(Page):
        expect_scrolling = True

Passing ``expect_scrolling=False`` to the constructor overrides a class-level
``True``, which is useful when a normally long page is instantiated in a short
variant. The bundled consent pages already declare it. The attribute only
affects testing; it does not change what participants see.
