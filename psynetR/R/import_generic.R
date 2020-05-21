import_generic <- function(experiment_dir, label) {
  files <- unpack_files(experiment_dir, label)
  raw <- load_raw_data(files)
  raw
}

# theme_set(theme_pubr())

unpack_files <- function(experiment_dir, label, dir = tempfile(pattern = "dir")) {
  zip_file <- file.path(experiment_dir, "data", paste0(label, "-data.zip"))

  if (!file.exists(zip_file))
    stop("input file ", zip_file, " does not exist")

  files <- list(
    root = dir,
    # code_zip = file.path(dir, paste0(label, "-code.zip")),
    # code = file.path(dir, "code"),
    data = file.path(dir, "data")
  )

  # files$config <- file.path(files$code, "config.txt")

  extract <- function(zip_file, dir) {
    message("Extracting ", zip_file, " into ", dir, "...")
    unzip(zip_file, exdir = dir)
  }

  extract(zip_file, files$root)
  # extract(files$code_zip, files$code)

  files
}

get_config <- function(files) {
  tibble(raw = readLines(files$config)) %>%
    filter(grepl("=", raw)) %>%
    mutate(
      key = gsub(" = .*", "", raw),
      value = gsub(".* = ", "", raw)
    ) %>% {
      set_names(as.list(.$value), .$key)
    }
}

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

get_response <- function(raw) {
  raw$question %>%
    label_properties(response_properties()) %>%
    rename(answer = response,
           metadata = details) %>%
    mutate(answer = map(answer, jsonlite::fromJSON),
           metadata = map(metadata, jsonlite::fromJSON))
}
