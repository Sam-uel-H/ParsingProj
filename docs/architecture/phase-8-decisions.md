# Phase 8 Decisions

## Template and version identity

A `Template` remains the stable identity referenced by users and routes. Each edit cycle is a
`TemplateVersion`; creating a new version copies a selected published version and its columns into a
new draft under the same template identity. Cloning copies a published version into version 1 of a
new template identity.

Only the latest version is returned by the template detail endpoint. The version-history endpoint
returns every immutable published version and any current draft, including its ordered columns and
prompts. Version numbers remain unique per template, and creation is serialized by locking the
template row.

## Archive and deletion behavior

Archive metadata belongs to the template identity rather than an individual version. Archived
templates and their versions remain readable so historical parsing jobs continue to resolve their
exact template version. Archived templates cannot be edited, published, versioned, or selected for a
new parsing job.

An unused template may be deleted. Deletion is rejected before mutation when any parsing job points
to one of its versions; the database foreign key remains the final integrity boundary.

## Search and indexes

The templates browser searches the latest version name and description and filters by domain,
author, and effective status. The effective status is `archived` when the template has archive
metadata; otherwise it is the latest version's draft or published status.

Indexes cover domain/archive/update ordering, template creator, archive state, version status/name,
version creator, and the existing template/version uniqueness and lookup paths.

## Column ordering

The reorder operation accepts every column ID exactly once, locks the current draft version, and
updates all display positions in one transaction. Published columns remain immutable. Parsing and
export continue ordering by the columns stored on the exact version used by the job.
