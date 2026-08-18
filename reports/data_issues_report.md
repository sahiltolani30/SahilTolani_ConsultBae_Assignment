# Task 4: Data Issues & Audit Report

## Overview
- **Total raw rows processed**: 106
- **Total structural issues fixed/dropped**: 3
- **Final unique golden records generated**: 60

## Structural Issues Found (Pre-Normalization)
- Source 2, Row 12: EMPTY ROW — dropped
- Source 2, Row 20: COLUMN SHIFT DETECTED — realigning
- Source 3, Row 16: REPEATED HEADER — dropped

## Pipeline Architecture Recap
- **Phase 1**: Native Python `csv` parsing to catch shifted columns and repeated headers before Pandas crashes.
- **Phase 2**: Pure-function normalization (emails lowercased, phones to 10-digit, CTC Lakhs to INR).
- **Phase 3**: Transitive O(1) clustering using the `Union-Find` algorithm (matches by Phone OR Email).
- **Phase 4**: Strict conflict-resolution prioritization to generate a single Golden Record per person.
- **Phase 5**: SQLite WAL-mode bulk insert, with normalized skills stored in a junction table.
