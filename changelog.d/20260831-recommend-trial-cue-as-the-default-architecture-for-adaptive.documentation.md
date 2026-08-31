Revised the experiment-development skills to recommend ``Trial.cue`` as the
default architecture for adaptive trial selection, reserving ``StaticTrialMaker``
for authored node banks that need balancing and chain trial makers for state
derived from earlier trials. Static ``select_node`` guidance moved to a
reference file, and adaptive stopping rules are now documented with
``while_loop``.
