trial_properties <- function() {
  c(
    property1 = "participant_id",
    property2 = "complete",
    property3 = "is_repeat_trial"
  )
}

network_properties <- function() {
  c(
    property1 = "trial_type",
    property2 = "target_num_trials",
    property5 = "awaiting_async_processes"
  )
}

chain_node_properties <- function() {
  c(
    property1 = "degree",
    property2 = "child_id",
    property3 = "seed",
    property4 = "definition"
  )
}

gsp_node_properties <- function() {
  chain_node_properties()
}

chain_trial_properties <- function() {
  trial_properties()
}

chain_network_properties <- function() {
  network_properties()
}

gsp_trial_properties <- function() {
  chain_trial_properties()
}
