import_generic <- function(zip_file) {
  files <- unpack_files(zip_file)
  raw <- load_raw_data(files)
  raw
}

# theme_set(theme_pubr())

unpack_files <- function(zip_file, output_dir = tempfile(pattern = "dir")) {
  if (!file.exists(zip_file))
    stop("input file ", zip_file, " does not exist")

  files <- list(
    root = output_dir,
    # code_zip = file.path(dir, paste0(label, "-code.zip")),
    # code = file.path(dir, "code"),
    data = file.path(output_dir, "data")
  )

  # files$config <- file.path(files$code, "config.txt")

  extract <- function(zip_file, output_dir) {
    message("Extracting ", zip_file, " into ", output_dir, "...")
    unzip(zip_file, exdir = output_dir)
  }

  extract(zip_file, files$root)
  # extract(files$code_zip, files$code)

  files
}

# get_config <- function(files) {
#   tibble(raw = readLines(files$config)) %>%
#     filter(grepl("=", raw)) %>%
#     mutate(
#       key = gsub(" = .*", "", raw),
#       value = gsub(".* = ", "", raw)
#     ) %>% {
#       set_names(as.list(.$value), .$key)
#     }
# }

load_raw_data <- function(files) {
  tibble(
    path = list.files(files$data, full.names = TRUE),
    file = basename(path),
    id = gsub("\\.csv", "", file),
    data = map(path, readr::read_csv, col_types = readr::cols()) #, guess_max = 21474836)
  ) %>% {
    set_names(.$data, .$id)
  }
}

get_generic_response <- function(raw) {
  raw$question %>%
    label_properties(response_properties()) %>%
    rename(answer = response,
           metadata = details) %>%
    mutate(answer = map(answer, jsonlite::fromJSON),
           metadata = map(metadata, jsonlite::fromJSON))
}

get_generic_participant <- function(raw) {
  raw$participant %>%
    label_properties(participant_properties()) %>%
    rename(participant_id = id) %>%
    arrange(participant_id) %>%
    unpack_json_col("details")
}
