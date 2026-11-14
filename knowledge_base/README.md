---
title: How the knowledge base is used
category: about
last_reviewed: 2026-11-01
---

# How the knowledge base is used

This folder holds the source documents the assistant answers from.

## Ground rules

- **Everything here is fictional.** Bramble Court Surgery, its address, staff,
  fees and policies do not exist. Never treat any of it as real medical advice.
- Each file is a self-contained topic with a YAML header (`title`, `category`,
  `last_reviewed`). The ingestion script copies those values into each chunk's
  metadata so retrieval can be filtered by category.
- Sections are separated by `##` headings. The chunker splits on those headings
  first, so a chunk is a complete thought rather than a fixed slice of text.
- Facts are stated plainly and repeated where they matter. Retrieval is
  sentence-level pattern matching, so "repeat prescriptions take two working
  days" retrieves far better than "they take two working days".

## Adding content

1. Add a `.md` file (or extend an existing one) and keep one topic per file.
2. Fill in the header: `title`, `category`, and `last_reviewed`.
3. Keep a section under about 200 words. Longer sections get split, which often
   splits a fact away from the condition it belongs to.
4. State the answer in the first sentence of the section, then qualify it.
5. Re-run ingestion once the pipeline exists. Re-ingestion is idempotent: chunk
   IDs are derived from the file path and heading, so updating a file replaces
   its chunks instead of duplicating them.

## Categories in use

`about`, `appointments`, `services`, `prescriptions`, `urgent-care`,
`registration`, `fees`, `staff`, `results`, `policies`
