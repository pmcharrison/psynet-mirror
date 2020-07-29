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
    property2 = numeric_field("target_n_trials"),
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
