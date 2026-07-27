# README

This experiment family illustrates the Create and Rate paradigm. These demos
are meant to show how the paradigm works and showcase certain features, not to
be run as real studies.

- `basic`: creators describe an image of a dog; raters rate descriptions in
  isolation or select the best one. Also shows including a previous iteration.
- `picnic`: creators guess a rule from positive and negative picnic examples;
  raters judge whether the guessed rule is correct, rating all creations at once.
- `robot_voice`: audio GSP ported to Create and Rate. Creators invent a robot
  voice; raters pick the best match. Shows integrating richer trials such as
  `AudioGibbsTrial`, and supports both isolated and select-all rating.
- `gap`: implementation behind
  [Bridging the prosody GAP](https://arxiv.org/abs/2205.04820). Creators re-record
  a sentence in an imagined situation; raters pick the most emotional creation.
  Creators and raters are separate roles to avoid emotion priming.

See also the Create and Rate tutorial in the documentation.

## Usage

For instructions on how to run PsyNet experiments like this one, visit the
[PsyNet documentation](https://psynetdev.gitlab.io/PsyNet/).
