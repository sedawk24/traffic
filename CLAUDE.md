# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

{Brief description of the project. 2-3 sentences max.}

## Tech Stack

{Filled in during project planning.}

## Architecture

{Brief architecture summary. Filled in during project planning.}

## Key Documentation

| File | Purpose |
|------|---------|
| `CURRENT_STATE.md` | Current build status -- read this at the start of every session |
| `docs/development/development-tracker.md` | Phase-by-phase development tracking with change log |
| `docs/development/backlog.md` | Future features, ideas, and deferred work |
| `docs/development/phases/` | Detailed implementation plans for each phase |
| `docs/architecture/decisions.md` | Architectural decision log with reasoning |

## Development Rules

### Initial Project Setup

When this is a new project and a development plan has been created, the FIRST implementation step -- before writing any code -- is to populate the tracking files:

1. Fill in the `{placeholder}` sections of this file (`CLAUDE.md`) with the project overview, tech stack, architecture, and conventions
2. Populate `CURRENT_STATE.md` with the phase overview and first phase details
3. Populate `docs/development/development-tracker.md` with all phases, tasks, and the phase overview table
4. Create phase plan files in `docs/development/phases/` for at least the first phase
5. Log any initial architectural decisions in `docs/architecture/decisions.md`
6. Update `README.md` with the project name, description, and quick start instructions
7. Commit these tracking files before beginning any development work

### HARD RULE: Update Tracking Before Every Commit

**Before staging and committing, you MUST review and update the following files:**

1. **`CURRENT_STATE.md`** -- must reflect the current state of the project
2. **`docs/development/development-tracker.md`** -- must mark completed work, update task statuses, and add a change log entry
3. **`docs/development/backlog.md`** -- if new ideas or future work surfaced during the session, add them here

**This is not a suggestion. This is a required step. Do not stage or commit without updating tracking files first. If tracking files do not reflect the current state of the work, update them before proceeding with the commit.**

### Session Start

1. Read `CURRENT_STATE.md` to understand where the project stands
2. Read the relevant section of `docs/development/development-tracker.md` for detail on the current phase
3. If starting a new phase, check `docs/development/phases/` for a detailed implementation plan

### Session End

1. Update tracking files (see hard rule above)
2. Commit all changes
3. Push to remote

### General Conventions

- Feature branches for new work; merge to main when stable
- Update spec documents in `docs/` if architectural decisions change
- Log all significant architectural decisions in `docs/architecture/decisions.md`

## Project Conventions

{Project-specific coding conventions, style rules, etc. Filled in during project planning.}
