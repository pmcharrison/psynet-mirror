# Create and Rate demos

To demonstrate and test the Create and Rate paradigm, we have created a few demos. These demos are not meant to be used
in a real study, but to show how the paradigm works and showcase certain features.

Here is a brief description of each demo:

- `basic`: the creators are prompted with an image of a dog and need to describe it. Raters either rate each creation in
  isolation or select the best description from a few creations. The demo also shows how you can include a previous
  iteration.
- `picnic`: participants play the game of picnic, in which creators see positive and negative examples of a rule and
  have to guess the rule behind the examples. The raters rate if the guessed rule by the creators is correct. Here each
  rater, rates all creations at once.
- `robot_voice`: the audio GSP example ported to Create and Rate. Creators need to create a voice for a robot, raters
  pick which voice best matches the image of a robot. The demo also shows how you can incorporate more complex Trials
  such as AudioGibbsTrial into the Create and Rate paradigm. While it does not always makes sense to allow revisiting
  across chains, it can be practical in the case of GSP so participants can do more chains in one experiment or simply
  for testing purposes. The demo supports both rating creations in isolation and selecting from all creations at once.
- `gap`: implementation behind "Bridging the prosody GAP: Genetic Algorithm with People to efficiently sample emotional
  prosody" (https://arxiv.org/abs/2205.04820). The paradigm plays a recording of a recording of a sentence. Creators
  have to listen to it and think of a situation this could have happened in. They now have to record the same sentence
  as if they were in that situation. The raters pick the most emotional creation. To avoid priming creators with
  emotions, creators and raters are entirely separate roles.

Make sure, you also check out the tutorial in the documentation.