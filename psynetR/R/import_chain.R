import_chain <- function(
  experiment_dir,
  label,
  node_type,
  trial_type,
  network_type
) {
  raw <- import_generic(experiment_dir, label)

  message("Preprocessing data...")

  response <- get_response(raw)
  participant <- get_chain_participant(raw)
  node <- get_chain_node(raw, node_type)
  trial <- get_chain_trial(raw, trial_type)
  network <- get_chain_network(raw, network_type)

  trial <- add_response(trial, response)

  node <- inner_join(node, get_node_metadata(trial, node, network), by = "node_id")
  trial <- inner_join(trial, get_trial_metadata(trial, node, network), by = "trial_id")

  node <- node %>% unpack_list_col("definition")
  network <- network %>% unpack_list_col("definition")

  list(
    raw = raw,
    response = response,
    participant = participant,
    trial = trial,
    node = node,
    network = network
  )
}

get_chain_node <- function(raw, node_type) {
  raw$node %>%
    filter(type == !!node_type) %>%
    filter(!failed) %>%
    label_properties(chain_node_properties()) %>%
    unpack_json_col("details") %>%
    unpack_json_col("seed", prefix = "seed_", keep_original = TRUE) %>%
    mutate(definition = map(definition, jsonlite::fromJSON)) %>%
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

get_chain_participant <- function(raw) {
  raw$participant %>%
    label_properties(participant_properties()) %>%
    unpack_json_col("details")
}
