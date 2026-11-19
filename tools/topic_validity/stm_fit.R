#!/usr/bin/env Rscript
# STM sensitivity: prevalence ~ perspective + event; content ~ perspective
args <- commandArgs(trailingOnly = TRUE)
root <- if (length(args) >= 1) args[[1]] else "."
exp_dir <- file.path(root, "output/experiments/2026-11-16_youtube_en_robot_imagination_self_bertopic")
validity <- file.path(exp_dir, "validity", "stm")
dir.create(validity, recursive = TRUE, showWarnings = FALSE)

suppressPackageStartupMessages({
  library(stm)
  library(quanteda)
  library(readr)
  library(dplyr)
})

corpus_path <- file.path(exp_dir, "comment_assignments.csv")
if (!file.exists(corpus_path)) {
  stop("Missing comment_assignments.csv")
}

df <- read_csv(corpus_path, show_col_types = FALSE, progress = FALSE)
df <- df %>%
  mutate(
    doc_text = as.character(content),
    perspective = case_when(
      has_robot == TRUE & has_imagination == FALSE & has_self == FALSE ~ "Robot_only",
      has_imagination == TRUE & has_robot == FALSE & has_self == FALSE ~ "Imagination_only",
      has_self == TRUE & has_robot == FALSE & has_imagination == FALSE ~ "Self_only",
      has_robot == TRUE ~ "Robot_mixed",
      has_imagination == TRUE ~ "Imagination_mixed",
      has_self == TRUE ~ "Self_mixed",
      TRUE ~ "other"
    ),
    event = as.factor(source_batch)
  ) %>%
  filter(nchar(doc_text) > 0)

corp <- corpus(df, text_field = "doc_text", docid_field = "comment_id")
docvars(corp, "perspective") <- df$perspective
docvars(corp, "event") <- df$event

tok <- tokens(corp, remove_punct = TRUE, remove_numbers = TRUE) %>%
  tokens_remove(stopwords("en"))
dfm <- dfm_trim(dfm(tok), min_termfreq = 5, max_docfreq = 0.9, docfreq_type = "prop")

temp <- quanteda::convert(dfm, to = "stm")
meta <- temp$meta %>% select(perspective, event)
out <- prepDocuments(temp$documents, temp$vocab, meta, lower.thresh = 5)

docs <- out$documents
vocab <- out$vocab
meta_out <- out$meta

Ks <- c(20, 40, 60)
search_path <- file.path(validity, "stm_searchK.csv")
if (file.exists(search_path)) {
  search_df <- read_csv(search_path, show_col_types = FALSE)
  k_pick <- search_df$K[which.max(search_df$exclus)]
} else {
  set.seed(42)
  n_docs <- length(docs)
  idx <- if (n_docs > 6000) sample.int(n_docs, 6000) else seq_len(n_docs)
  search <- searchK(docs[idx], vocab, K = Ks, verbose = FALSE, init.type = "Spectral")
  search_df <- data.frame(
    K = as.integer(search$results[, "K"]),
    heldout = search$results[, "heldout"],
    residual = search$results[, "residual"],
    bound = search$results[, "bound"],
    lbound = search$results[, "lbound"],
    exclus = search$results[, "exclus"],
    semcoh = search$results[, "semcoh"],
    em_its = search$results[, "em.its"]
  )
  write_csv(search_df, file.path(validity, "stm_searchK.csv"))
  k_pick <- search_df$K[which.max(search_df$exclus)]
}
if (length(k_pick) == 0 || is.na(k_pick)) k_pick <- 40L

model <- stm(
  documents = docs,
  vocab = vocab,
  K = k_pick,
  prevalence = ~ perspective + event,
  content = ~ perspective,
  data = meta_out,
  init.type = "Spectral",
  seed = 42,
  verbose = FALSE
)

saveRDS(model, file.path(validity, sprintf("stm_K%d.rds", k_pick)))
effect <- estimateEffect(1:k_pick ~ perspective + event, model, metadata = meta_out, uncertainty = "Global")
saveRDS(effect, file.path(validity, sprintf("stm_prevalence_effects_K%d.rds", k_pick)))

capture.output(summary(effect), file = file.path(validity, "stm_prevalence_summary.txt"))

topic_labels <- labelTopics(model, n = 12)
lab_df <- as.data.frame(topic_labels$prob)
write_csv(lab_df, file.path(validity, sprintf("stm_top_terms_K%d.csv", k_pick)))

compare_notes <- c(
  paste("# STM run", Sys.time()),
  paste("K selected:", k_pick, "(max exclusivity among", paste(Ks, collapse = ","), ")"),
  paste("N docs after prep:", length(docs)),
  paste("Vocab:", length(vocab)),
  "",
  "## Model",
  "- prevalence ~ perspective + event",
  "- content ~ perspective",
  "",
  "## Compare to BERTopic",
  "- BERTopic fixes embedding+UMAP+HDBSCAN then compares three codebook slices on same topic ids.",
  "- STM jointly models prevalence/content covariates; expect directionally similar perspective contrasts on war/China/imagination tokens, not 1:1 topic alignment.",
  "",
  "Artifacts: stm_searchK.csv, stm_top_terms_*.csv, stm_prevalence_summary.txt"
)
writeLines(compare_notes, file.path(validity, "STM_NOTES.md"))
if (file.exists(file.path(validity, "STM_BLOCKED.md"))) {
  file.remove(file.path(validity, "STM_BLOCKED.md"))
}