trial_properties <- function() {
  c(
    property1 = "participant_id",
    property2 = "complete",
    property3 = "is_repeat_trial"
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

gsp_trial_properties <- function() {
  chain_trial_properties()
}
