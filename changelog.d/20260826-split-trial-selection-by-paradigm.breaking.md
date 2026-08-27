Replaced trial assignment hooks ``find_networks``, ``find_node``,
``prioritize_networks``, and ``custom_network_filter`` with
paradigm-specific APIs. Chain trial makers use ``find_chains``,
``select_chain``, and ``chain_is_eligible``; static trial makers use
``find_nodes``, ``select_node``, and ``node_is_eligible``. Eligibility
hooks return booleans (or a boolean mask via ``chains_are_eligible`` /
``nodes_are_eligible``). Selection hooks receive a nonempty eligible list
and may return the selected value or ``Selection(value, context)``.
``get_trial_class`` must return a trial class for every eligible
selection; synchronized followers reuse their leader's concrete trial
class without calling this hook again. PsyNet raises an actionable
``TypeError`` at construction when a removed or wrong-paradigm hook is
overridden.
