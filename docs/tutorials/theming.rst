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
     - Primary action, progress fill, selected states.
   * - ``--psynet-content-width``
     - ``900px``
     - Maximum width of the content surface.
   * - ``--psynet-measure``
     - ``62ch``
     - Maximum width of prose, so long text stays readable.

To recolour an experiment, redefine the tokens in your own stylesheet:

::

    /* static/theme.css */
    :root {
        --psynet-accent: #7a4fa3;
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

    Exp.css.append(":root { --psynet-accent: #44556b; }")

Dark mode
---------

Setting ``color_mode`` to ``dark`` or ``auto`` in ``config.txt`` switches the
tokens to a dark palette; see :doc:`/experiment_development/configuration`. If
you override tokens yourself and support dark mode, define your overrides for
both schemes:

::

    :root { --psynet-accent: #7a4fa3; }
    [data-bs-theme="dark"] { --psynet-accent: #b48ad4; }

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
