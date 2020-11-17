.. _modular_page:

=============
Modular Pages
=============

Modular pages are a new way to implement pages in PsyNet.
They work by splitting page design into two main components:
the `Prompts`_, constituting the information or stimulus that is presented
to the listener, and the `Controls`_, constituting the participant's
way of responding to the information or stimulus.

.. note::
  The modular page functionality is still experimental, and its API is liable to change.

Prompts
-------

The following subclasses of :class:`~psynet.modular_page.Prompt` exist:

* :class:`~psynet.modular_page.AudioPrompt`

* :class:`~psynet.modular_page.ImagePrompt`

* :class:`~psynet.modular_page.ColourPrompt`

Controls
--------

A wide range of controls all of which inherit from :class:`~psynet.modular_page.Control` are available:

Audio/Video controls
~~~~~~~~~~~~~~~~~~~~

* :class:`~psynet.modular_page.AudioMeterControl`

.. image:: ../_static/images/audio_meter_control.png
  :width: 560
  :alt: AudioMeterControl

* :class:`~psynet.modular_page.AudioRecordControl`

.. image:: ../_static/images/audio_record_control_recording.png
  :width: 600
  :alt: AudioRecordControl (recording)

.. image:: ../_static/images/audio_record_control_finished.png
  :width: 580
  :alt: AudioRecordControl (finished)


* :class:`~psynet.modular_page.TappingAudioMeterControl`

* :class:`~psynet.modular_page.VideoSliderControl`

.. image:: ../_static/images/video_slider_control.png
  :width: 580
  :alt: VideoSliderControl

Option controls
~~~~~~~~~~~~~~~

These classes inherit from :class:`~psynet.modular_page.OptionControl`.

* :class:`~psynet.modular_page.CheckboxControl`

.. image:: ../_static/images/checkbox_control.png
  :width: 800
  :alt: CheckboxControl

* :class:`~psynet.modular_page.DropdownControl`

.. image:: ../_static/images/dropdown_control.png
  :width: 800
  :alt: DropdownControl

* :class:`~psynet.modular_page.PushButtonControl`

.. image:: ../_static/images/push_button_control.png
  :width: 800
  :alt: PushButtonControl

* :class:`~psynet.modular_page.RadioButtonControl`

.. image:: ../_static/images/radiobutton_control.png
  :width: 800
  :alt: RadioButtonControl

Other controls
~~~~~~~~~~~~~~

* :class:`~psynet.modular_page.NullControl`

* :class:`~psynet.modular_page.SliderControl`

* :class:`~psynet.modular_page.TextControl`

.. image:: ../_static/images/text_control.png
  :width: 800
  :alt: TextControl


API
---

.. automodule:: psynet.modular_page
    :show-inheritance:
    :members:
