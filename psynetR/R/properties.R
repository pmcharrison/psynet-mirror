trial_properties <- function() {
  list(
    property1 = int_field("participant_id"),
    property2 = bool_field("complete"),
    property3 = bool_field("is_repeat_trial")
  )
}

network_properties <- function() {
  list(
    property1 = str_field("trial_type"),
    property2 = numeric_field("target_num_trials"),
    property5 = bool_field("awaiting_async_processes")
  )
}

response_properties <- function() {
  list(
    property1 = str_field("page_type"),
    property2 = bool_field("successful_validation")
  )
}


participant_properties <- function() {
  list(
    property1 = int_field("event_id"),
    property2 = str_field("page_uuid"),
    property3 = bool_field("complete"),
    property4 = misc_field("answer"),
    property5 = misc_field("branch_log")
  )
}

chain_node_properties <- function() {
  list(
    property1 = int_field("degree"),
    property2 = int_field("child_id"),
    property3 = misc_field("seed"),
    property4 = misc_field("definition")
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

field <- function(name, coerce) {
  x <- list(name = name, coerce = coerce)
  class(x) <- c("field", class(x))
  x
}

int_field <- function(name) {
  field(name, as.integer)
}

numeric_field <- function(name) {
  field(name, as.numeric)
}

bool_field <- function(name) {
  field(name, function(x) as.logical(as.integer(x)))
}

str_field <- function(name) {
  field(name, as.character)
}

misc_field <- function(name) {
  field(name, identity)
}
