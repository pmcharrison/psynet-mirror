import_chain <- function(
  zip_file,
  node_type,
  trial_type,
  network_type
) {
  raw <- import_generic(zip_file)

  message("Preprocessing data...")

  response <- get_generic_response(raw)
  participant <- get_generic_participant(raw)
  node <- get_chain_node(raw, node_type)
  trial <- get_chain_trial(raw, trial_type)
  network <- get_chain_network(raw, network_type)

  trial <- add_response(trial, response)

  node <- left_join(node, get_chain_node_metadata(trial, node, network), by = "node_id")
  trial <- left_join(trial, get_chain_trial_metadata(trial, node, network), by = "trial_id")
  network <- left_join(network, get_chain_network_metadata(trial, node, network), by = "network_id")

  # noLde <- node %>% unpack_list_col("definition", keep_original = TRUE)
  # network <- network %>% unpack_list_col("definition", keep_original = TRUE)

  list(
    raw = raw,
    response = response,
    participant = participant,
    trial = trial,
    node = node,
    network = network
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

chain_trial_properties <- function() {
  trial_properties()
}

chain_network_properties <- function() {
  network_properties()
}

get_chain_node <- function(raw, node_type) {
  raw$node %>%
    filter(type == !!node_type) %>%
    filter(!failed) %>%
    label_properties(chain_node_properties()) %>%
    unpack_json_col("details") %>%
    mutate(
      seed = map(seed, jsonlite::fromJSON),
      definition = map(definition, jsonlite::fromJSON)
    ) %>%
    rename(node_id = id)
}

get_chain_trial <- function(raw, trial_type) {
  raw$info %>%
    filter(type == !!trial_type) %>%
    label_properties(chain_trial_properties()) %>%
    unpack_json_col("details") %>%
    unpack_json_col("contents") %>%
    rename(trial_id = id,
           node_id = origin_id)
}

get_chain_network <- function(raw, network_type) {
  raw$network %>%
    filter(type == !!network_type) %>%
    label_properties(chain_network_properties()) %>%
    unpack_json_col("details") %>%
    rename(network_id = id,
           phase = role)
}

get_chain_trial_metadata <- function(trial, node, network) {
  trial_df <- trial %>% select(trial_id, network_id, node_id)

  node_df <-
    node %>%
    select(node_id, phase, degree, definition) %>%
    rename(node_definition = definition)

  network_df <-
    network %>%
    select(network_id, definition) %>%
    rename(network_definition = definition)
  # unpack_list_col("definition", prefix = "network_")

  trial_df %>%
    left_join(node_df, by = "node_id") %>%
    left_join(network_df, by = "network_id") %>%
    select(- c(network_id, node_id))
}

get_chain_network_metadata <- function(trial, node, network) {
  node_df <-
    node %>%
    select(network_id, node_id, failed)

  trial_df <-
    trial %>%
    select(network_id, trial_id, failed)

  node_stats <-
    network %>%
    select(network_id) %>%
    inner_join(node_df, by = "network_id") %>%
    group_by(network_id) %>%
    summarise(n_nodes = n(),
              n_active_nodes = sum(!failed),
              n_failed_nodes = sum(failed))

  trial_stats <-
    network %>%
    select(network_id) %>%
    inner_join(trial_df, by = "network_id") %>%
    group_by(network_id) %>%
    summarise(n_trials = n(),
              n_active_trials = sum(!failed),
              n_failed_trials = sum(failed))

  network %>%
    select(network_id) %>%
    left_join(node_stats, by = "network_id") %>%
    left_join(trial_stats, by = "network_id") %>%
    mutate_at(vars(starts_with("n_")), ~ if_else(is.na(.), 0L, .))
}
