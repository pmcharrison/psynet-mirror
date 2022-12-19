Applications
============

PsyNet can be used for many kinds of psychology experiments.
However there are certain scenarios to which PsyNet is particularly well suited.

**Online experiments.** PsyNet experiments run in the web browser and therefore can be
used either for in-person or online data collection.

**Experiments using large stimulus sets.** PsyNet provides extensive support for
managing stimulus sets, including useful hooks for generating stimuli
in Python and hosting media assets on web servers.

**Experiments whose state evolves over time.** PsyNet makes it easy to
implement certain kinds of experiments that are very difficult to implement in
static platforms such as jsPsych and PsychoPy, for example cultural evolution
or serial reproduction studies.

**Experiments using recordings.** Recording media from e.g. the webcam or the microphone
is straightforward in PsyNet. The results can be processed in near real-time using
custom Python functions and used to determine experiment logic (e.g. feedback).

**Experiments using financial rewards.** PsyNet integrates with crowdsourcing services
(e.g. Prolific, Amazon Mechanical Turk) and can automate the dispensation of
performance-related financial rewards, which is a great way to motivate good
task performance.


Examples
--------

Here are a few examples of research projects that have successfully used
PsyNet since its inception in 2020. These projects were carried out by a variety
of researchers based at institutions including the Max Planck Institute for
Empirical Aesthetics, the University of Cambridge, City University of New York,
Princeton University, and the University of Oxford.

**Gibbs Sampling with People**. This project developed a new adaptive technique for
mapping semantic associations of a stimulus space. The procedure constructs a series
of stimulus 'chains', where a stimulus is passed from one participant to the next,
and each participant adjusts a particular stimulus dimension in order to maximise
a particular subjective criterion (e.g. 'beauty'). The project takes advantage of
PsyNet's support for experiments whose state evolves over time.

**Consonance and timbre**. This project explored ways in which the timbre of chord tones affects the consonance
subjective pleasantness) of musical chords. PsyNet enabled the exploration of
very large stimulus spaces, with each stimulus corresponding to a different combination
of timbre and pitch intervals.

**Large-scale tapping experiments**. This project used PsyNet to conduct large-scale
online studies where participants had to tap along to the beat of musical pieces.
The paradigm used a newly constructed signal-processing pipeline that records
participant tapping through the laptop microphone. Implementing this in PsyNet
allowed participant performance to be monitored in real time, enabling live feedback
and financial rewards for good performances.

**Vocal pitch matching**. This project investigated participants' abilities to identify
and sing back the notes in musical chords. This took advantage of PsyNet's support
for audio recording and online signal-processing.

**Emotional connotations of musical scales**. This project studied how different musical
scales evoke different kinds of emotions within listeners. This took advantage of PsyNet's
support for large, programmatically generated stimulus sets.

**Governance simulations**. This project studied the success of different self-governance
systems within a online social network. Participants experienced this network
through a 3D video game programmed in the Unity game engine. This took advantage
of PsyNet's ability to orchestrate complex interactions between many participants.
