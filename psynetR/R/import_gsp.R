import_gsp <- function(
  experiment_dir,
  label,
  node_type,
  trial_type,
  include_repeat_trials=FALSE
) {
  raw <- import_generic(experiment_dir, label)
  node <- get_gsp_node(raw, node_type)
  trial <- get_gsp_trial(raw, trial_type, include_repeat_trials)
  node <- inner_join(node, get_node_answers(node, trial), by = c("id" = "node_id"))
  list(
    trial = trial,
    node = node
  )
}

get_gsp_node <- function(raw, node_type) {
  raw$node %>%
    filter(type == !!node_type) %>%
    filter(!failed) %>%
    label_properties(gsp_node_properties()) %>%
    unpack_json_col("details") %>%
    unpack_json_col("contents") %>%
    unpack_json_col("definition") %>%
    select(- seed)
}

get_gsp_trial <- function(raw, trial_type, include_repeat_trials) {
  raw$info %>%
    filter(type == !!trial_type) %>%
    filter(!failed) %>%
    label_properties(gsp_trial_properties()) %>%
    unpack_json_col("details") %>%
    unpack_json_col("contents") %>%
    filter(!!include_repeat_trials | !is_repeat_trial)
}
