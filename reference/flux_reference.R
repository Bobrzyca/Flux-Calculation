#!/usr/bin/env Rscript
# =============================================================================
# Flux Calculation — reference method-of-record  (SCAFFOLD — replace me)
# =============================================================================
#
# WHAT THIS IS
#   A standalone R implementation of the closed-chamber flux method, pointed at
#   the repo's sample files so it runs out of the box. It is NOT called by the
#   app; it exists to independently reproduce the fluxes so we can check the
#   Python tool against a second implementation on a known campaign.
#
# ⚠️  IMPORTANT — THIS IS A PYTHON-DERIVED SCAFFOLD, NOT YET A TRUE REFERENCE.
#   These formulas were transcribed from the Python implementation
#   (backend/app/flux/). Because it is a port, running it will (by construction)
#   reproduce the Python numbers — so on its own it does NOT provide independent
#   validation. Its job right now is only to give you a working, path-clean
#   skeleton.
#
#   >>> Replace the body below with your ACTUAL original R script <<<
#   (the one with the hard-coded C:/Users/... paths and the fake pressure value),
#   cleaned only so it reads the four files from ../backend/sample_data. THAT
#   version — an independent expression of the method — is the real
#   method-of-record. If it and the Python tool ever disagree, that disagreement
#   is the useful signal (see project-brief.md "R script as reference").
#
#   Until then, the flux math is validated by the hand-computed values in
#   backend/tests/test_flux.py.
#
# HOW TO RUN
#   Rscript reference/flux_reference.R
#   Requires the 'readxl' package for the temperature xlsx:
#       install.packages("readxl")
#   Writes reference/reference_output.csv and prints a per-spot summary.
# =============================================================================

suppressPackageStartupMessages(library(readxl))

# ---- Locate the sample files relative to this script -----------------------
args <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", args[grepl("^--file=", args)])
script_dir <- if (length(file_arg)) dirname(normalizePath(file_arg)) else getwd()
sample_dir <- normalizePath(file.path(script_dir, "..", "backend", "sample_data"))

# ---- Campaign config (matches the app defaults for the sample campaign) -----
WORK_DATE        <- "2026-07-02"
TIME_OFFSET_S    <- 0          # instrument-clock offset (seconds)
CHAMBER_AREA_M2  <- 0.0625
CHAMBER_VOLUME_L <- 15.625

# ---- Physical constants + fit thresholds (mirror app/flux/constants.py) -----
R_GAS          <- 8.314462618              # J mol^-1 K^-1
MOLAR_MASS_G   <- c(CO2 = 44.0095, CH4 = 16.0425)  # g mol^-1
MOLAR_MASS_C   <- 12.011                   # g mol^-1 (one C per molecule)
GWP_100YR      <- c(CO2 = 1.0, CH4 = 28.0) # IPCC AR5 (assumption)
CH4_PPB_TO_PPM <- 1e-3
FIT_SKIP_S     <- 30                       # skip the first 30 s
FIT_WINDOW_S   <- 300                      # then fit the next 300 s
MIN_FIT_POINTS <- 10
LOW_R2         <- 0.80

# ---- Helpers ---------------------------------------------------------------

# "9.38" / "9:38" / "09:38:00" -> "09:38:00"; NA if unparseable.
normalize_time <- function(raw) {
  s <- gsub("\\.", ":", trimws(raw))
  if (s == "") return(NA_character_)
  parts <- strsplit(s, ":")[[1]]
  nums <- suppressWarnings(as.integer(parts))
  if (any(is.na(nums))) return(NA_character_)
  if (length(nums) == 2) nums <- c(nums, 0L)
  if (length(nums) != 3) return(NA_character_)
  if (nums[1] < 0 || nums[1] > 23 || nums[2] < 0 || nums[2] > 59 ||
      nums[3] < 0 || nums[3] > 59) return(NA_character_)
  sprintf("%02d:%02d:%02d", nums[1], nums[2], nums[3])
}

# HH:MM:SS on the work date -> unix seconds (UTC).
to_unix <- function(hhmmss) {
  as.numeric(as.POSIXct(paste(WORK_DATE, hhmmss), tz = "UTC"))
}

nearest_value <- function(timestamps, values, t) {
  if (length(timestamps) == 0) return(NA_real_)
  values[which.min(abs(timestamps - t))]
}

read_li7810 <- function(path) {
  df <- read.delim(path, skip = 1, header = TRUE, na.strings = c("nan", "NA"))
  data.frame(
    timestamp = as.numeric(df$SECONDS) + TIME_OFFSET_S,
    co2_ppm   = as.numeric(df$CO2),
    ch4_ppb   = as.numeric(df$CH4)
  )
}

read_temperature <- function(path) {
  tt <- readxl::read_excel(path)
  # readxl returns Excel datetimes as POSIXct; as.numeric() -> unix seconds.
  data.frame(
    timestamp     = as.numeric(tt$Date),
    temperature_c = as.numeric(tt$Temp)
  )
}

read_pressure <- function(path) {
  pp <- read.csv(path, check.names = FALSE)
  ts <- suppressWarnings(as.numeric(pp$timestamp))
  if (any(is.na(ts))) ts <- as.numeric(as.POSIXct(pp$timestamp, tz = "UTC"))
  data.frame(timestamp = ts, pressure_hpa = as.numeric(pp$pressure_hpa))
}

# Closed-chamber flux + full unit ladder for one gas.
flux_ladder <- function(slope, gas, temp_c, pressure_hpa) {
  slope_ppm_s <- if (gas == "CH4") slope * CH4_PPB_TO_PPM else slope
  p_pa <- pressure_hpa * 100
  v_m3 <- CHAMBER_VOLUME_L / 1000
  t_k  <- temp_c + 273.15
  mol_air_per_m2 <- (p_pa * v_m3) / (R_GAS * t_k * CHAMBER_AREA_M2)

  umol_m2_s  <- slope_ppm_s * mol_air_per_m2
  umol_m2_h  <- umol_m2_s * 3600
  mol_m2_h   <- umol_m2_h * 1e-6
  gC_m2_day  <- mol_m2_h * 24 * MOLAR_MASS_C
  kg_m2_h    <- mol_m2_h * MOLAR_MASS_G[[gas]] / 1000
  kg_ha_h    <- kg_m2_h * 1e4
  kg_ha_day  <- kg_ha_h * 24
  kg_ha_year <- kg_ha_day * 365
  Mg_ha_year <- kg_ha_year / 1000

  c(umol_m2_s = umol_m2_s, umol_m2_h = umol_m2_h, mol_m2_h = mol_m2_h,
    gC_m2_day = gC_m2_day, kg_m2_h = kg_m2_h, kg_ha_h = kg_ha_h,
    kg_ha_day = kg_ha_day, kg_ha_year = kg_ha_year, Mg_ha_year = Mg_ha_year,
    Mg_ha_year_co2equiv = Mg_ha_year * GWP_100YR[[gas]])
}

# ---- Load the campaign ------------------------------------------------------
readings    <- read_li7810(file.path(sample_dir, "li7810_sample.txt"))
temperature <- read_temperature(file.path(sample_dir, "temperature_sample.xlsx"))
pressure    <- read_pressure(file.path(sample_dir, "pressure_sample.csv"))
notes       <- read.csv(file.path(sample_dir, "notes_sample.csv"),
                        check.names = FALSE, colClasses = "character")

# ---- Fit each spot ----------------------------------------------------------
rows <- list()
for (i in seq_len(nrow(notes))) {
  nr    <- suppressWarnings(as.integer(sub("\\D.*$", "", trimws(notes$Nr[i]))))
  start <- normalize_time(notes$Start[i])
  stop  <- normalize_time(notes$Stop[i])

  if (is.na(start) || is.na(stop)) {
    cat(sprintf("Spot %s skipped: unparseable start/stop time\n", notes$Nr[i]))
    next
  }
  su <- to_unix(start); pu <- to_unix(stop)
  if (pu <= su) {
    cat(sprintf("Spot %d skipped: stop before start\n", nr)); next
  }
  win <- readings[readings$timestamp >= su & readings$timestamp <= pu, ]
  if (nrow(win) == 0) {
    cat(sprintf("Spot %d skipped: empty window (no data in %s-%s)\n",
                nr, start, stop)); next
  }

  temp_used <- nearest_value(temperature$timestamp, temperature$temperature_c, su)
  pres_used <- nearest_value(pressure$timestamp, pressure$pressure_hpa, su)

  t0  <- min(win$timestamp)
  rel <- win$timestamp - t0
  sub <- win[rel >= FIT_SKIP_S & rel < FIT_SKIP_S + FIT_WINDOW_S, ]

  for (gas in c("CO2", "CH4")) {
    col   <- if (gas == "CO2") "co2_ppm" else "ch4_ppb"
    valid <- !is.na(sub[[col]])
    y <- sub[[col]][valid]
    x <- sub$timestamp[valid] - t0
    n <- length(y)
    if (n < MIN_FIT_POINTS) {
      cat(sprintf("Spot %d %s skipped: too few points (%d)\n", nr, gas, n)); next
    }
    fit    <- lm(y ~ x)
    slope  <- unname(coef(fit)[2])
    r2     <- summary(fit)$r.squared
    ladder <- flux_ladder(slope, gas, temp_used, pres_used)
    rows[[length(rows) + 1]] <- data.frame(
      nr = nr, gas = gas, slope = slope, r2 = r2, n_points = n,
      temperature_c = temp_used, pressure_hpa = pres_used,
      as.list(ladder)
    )
  }
}

result <- if (length(rows)) do.call(rbind, rows) else data.frame()
out_path <- file.path(script_dir, "reference_output.csv")
write.csv(result, out_path, row.names = FALSE)

cat("\n=== Reference fluxes (per spot x gas) ===\n")
if (nrow(result)) {
  print(result[, c("nr", "gas", "slope", "r2", "n_points", "umol_m2_s")],
        row.names = FALSE)
} else {
  cat("(no spots produced fluxes)\n")
}
cat(sprintf("\nWrote %s\n", out_path))
