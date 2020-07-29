import_non_adaptive <- function(
  zip_file,
  trial_type,
  trial_type_v2
) {
  raw <- import_generic(zip_file)

  message("Preprocessing data...")

  response <- get_generic_response(raw)
  participant <- get_generic_participant(raw)

  stimulus <- get_non_adaptive_stimulus(raw)
  stimulus_version <- get_non_adaptive_stimulus_version(raw)
  trial <- get_non_adaptive_trial(raw, trial_type)
  block <- get_non_adaptive_block(raw, trial_type_v2)

  trial <- add_response(trial, response)

  stimulus_version <- left_join(stimulus_version,
                                get_stimulus_version_metadata(trial, stimulus_version, stimulus, block),
                                by = "stimulus_version_id")
  stimulus <- left_join(stimulus,
                        get_stimulus_metadata(trial, stimulus_version, stimulus, block),
                        by = "stimulus_id")

  trial <- left_join(trial,
                     get_non_adaptive_trial_metadata(trial, stimulus_version, stimulus, block),
                     by = "trial_id")

  block <- left_join(block,
                     get_non_adaptive_block_metadata(trial, stimulus_version, stimulus, block),
                     by = "block_id")

  list(
    raw = raw,
    response = response,
    participant = participant,
    trial = trial,
    stimulus = stimulus %>% order_stimulus_df(),
    stimulus = stimulus_version %>% order_stimulus_version_df(),
    block = block %>% order_block_df()
  )
}

order_stimulus_df <- function(df) {
  df %>% select(stimulus_id, block_id, target_num_trials,
                n_valid_trials, n_failed_trials, everything())
}

order_stimulus_version_df <- function(df) {
  df %>% select(stimulus_version_id, stimulus_id,
                n_valid_trials, n_failed_trials, everything())
}

order_block_df <- function(df) {
  df %>% select(block_id, block, participant_group, phase,
                n_valid_trials, n_failed_trials, full, everything())
}

non_adaptive_stimulus_properties <- function() {
  list(
    property1 = int_field("target_num_trials")
  )
}

non_adaptive_stimulus_version_properties <- function() {
  list(
    property1 = int_field("stimulus_id"),
    property2 = bool_field("has_media"),
    property3 = str_field("s3_bucket"),
    property4 = str_field("remote_media_dir"),
    property5 = str_field("media_file_name")
  )
}
non_adaptive_trial_properties <- function() {
  c(
    trial_properties(),
    list(
      property4 = int_field("stimulus_id")
    )
  )
}

non_adaptive_block_properties <- function() {
  c(
    network_properties(),
    list(
      property3 = str_field("participant_group"),
      property4 = str_field("block")
    )
  )
}

get_non_adaptive_stimulus <- function(raw) {
  get_non_adaptive_node(raw, "stimulus", non_adaptive_stimulus_properties())
}

get_non_adaptive_stimulus_version <- function(raw) {
  get_non_adaptive_node(raw, "stimulus_version", non_adaptive_stimulus_version_properties())
}

get_non_adaptive_node <- function(raw, type, properties) {
  df <- raw$node %>%
    filter(type == !!type) %>%
    label_properties(properties) %>%
    select(- creation_time, - type, - failed, - time_of_death, - participant_id) %>%
    arrange(id) %>%
    rename(definition = details,
           block_id = network_id) %>%
    select(id, block_id, everything()) %>%
    parse_json_col("definition")
  names(df) <- gsub("^definition$", paste0(type, "_definition"), names(df))
  names(df) <- gsub("^id$", paste0(type, "_id"), names(df))
  df
}

get_non_adaptive_trial <- function(raw, trial_type) {
  raw$info %>%
    filter(type == !!trial_type) %>%
    label_properties(non_adaptive_trial_properties()) %>%
    rename(trial_id = id,
           stimulus_version_id = origin_id,
           block_id = network_id,
           trial_definition = contents,
           vars = details) %>%
    unpack_json_col("vars") %>%
    select(trial_id, participant_id, stimulus_id, stimulus_version_id, block_id,
           answer, creation_time, trial_definition,
           complete, failed, time_of_death,
           response_id, everything()) %>%
    select(- type) %>%
    parse_json_col("trial_definition") %>%
    arrange(trial_id)
}

get_non_adaptive_block <- function(raw, trial_type_v2) {
  raw$network %>%
    label_properties(non_adaptive_block_properties()) %>%
    filter(type == "non_adaptive_network" &
             trial_type == !!trial_type_v2) %>%
    select(- type, - trial_type, - failed, - time_of_death, - creation_time) %>%
    unpack_json_col("details") %>%
    rename(block_id = id,
           phase = role) %>%
    select(block_id, block, participant_group, phase, full, everything())
}

get_stimulus_version_metadata <- function(trial, stimulus_version, stimulus, block) {
  df <- stimulus_version %>% select(stimulus_version_id, block_id)

  trial_df <-
    df %>%
    left_join(trial %>% select(stimulus_version_id, trial_id, failed, complete, is_repeat_trial),
              by = "stimulus_version_id") %>%
      group_by(stimulus_version_id) %>%
      summarise(n_valid_trials = sum(!is.na(trial_id) & !failed & !is_repeat_trial & complete),
                n_failed_trials = sum(!is.na(trial_id) & failed))

  block_df <- block %>% select(block_id, participant_group, phase, block)

  df %>%
    left_join(block_df, by = "block_id") %>%
    left_join(trial_df, by = "stimulus_version_id") %>%
    select(- block_id)
}

get_stimulus_metadata <- function(trial, stimulus_version, stimulus, block) {
  df <- stimulus %>% select(stimulus_id, block_id)

  stimulus_version_df <-
    df %>%
    left_join(stimulus_version %>% select(stimulus_id, n_valid_trials, n_failed_trials),
              by = "stimulus_id") %>%
    group_by(stimulus_id) %>%
    summarise(n_valid_trials = sum(n_valid_trials),
              n_failed_trials = sum(n_failed_trials))

  block_df <- block %>% select(block_id, participant_group, phase, block)

  df %>%
    left_join(block_df, by = "block_id") %>%
    left_join(stimulus_version_df, by = "stimulus_id") %>%
    select(- block_id)
}

get_non_adaptive_trial_metadata <- function(trial, stimulus_version, stimulus, block) {
  trial %>%
    select(trial_id, stimulus_version_id, stimulus_id, block_id) %>%
    left_join(block %>% select(block_id,
                               participant_group,
                               phase,
                               block),
              by = "block_id") %>%
    left_join(stimulus %>% select(stimulus_id,
                                  stimulus_definition),
              by = "stimulus_id") %>%
    left_join(stimulus_version %>% select(stimulus_version_id,
                                          stimulus_version_definition),
              by = "stimulus_version_id") %>%
    select(- stimulus_version_id, - stimulus_id, - block_id)
}

get_non_adaptive_block_metadata <- function(trial, stimulus_version, stimulus, block) {
  block %>%
    select(block_id) %>%
    left_join(stimulus %>% select(block_id, n_valid_trials, n_failed_trials),
              by = "block_id") %>%
    group_by(block_id) %>%
    summarise(n_valid_trials = sum(n_valid_trials),
              n_failed_trials = sum(n_failed_trials))
}
