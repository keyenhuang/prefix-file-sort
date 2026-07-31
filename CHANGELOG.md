# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-07-30

### Added

- **Multiple sort modes**: groups can now be ordered by name (default), natural
  order, modification time (newest/oldest first), or total file size
  (largest/smallest first), selectable from a new "Sort by" dropdown.
- Internationalization keys and Chinese (中文) labels for the new sort options.
- `SECURITY.md` with a private vulnerability reporting policy.
- `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1).
- `pyproject.toml` with project metadata and `ruff` lint configuration.
- GitHub Actions `release.yml` that builds a portable Windows executable on
  version tags and attaches it to a GitHub Release.

### Changed

- **Extracted core logic into `core.py`**: `FileGrouper` (grouping, moving,
  undo) is now a tkinter-free module, so the business logic is unit-testable and
  runs in headless CI environments without a display server.
- **Rewrote the test suite** to import the real `FileGrouper` from `core`
  (previously the tests duplicated the class code). Added integration tests for
  `execute_move` (skip / auto-rename conflicts) and `undo_last_move`, plus sort
  mode tests — 28 tests in total, all passing headless.
- **Hardened CI**: split into a `lint` (ruff) job and a cross-platform `test`
  job (Ubuntu / Windows / macOS × Python 3.8 / 3.10 / 3.12) that installs `tk`
  on Linux, compiles all sources, runs the headless tests, and smoke-tests the
  GUI import. Fixes the previous workflow that failed on Ubuntu due to missing
  tkinter.
- Preview now displays groups in the chosen sort order (previously re-sorted
  alphabetically for display, ignoring the sort mode).

### Fixed

- **Conflict policy now works in any UI language**: previously selecting a
  conflict policy (Skip / Overwrite / Auto-Rename) silently had no effect when
  the interface was set to Chinese, because the combobox stored the localized
  label while the core compared against English codes (so conflicts fell
  through and errored instead of being skipped/overwritten/auto-renamed). The
  combobox now keeps a stable internal code separate from its localized display
  label, so behavior is consistent across languages. The same decoupling was
  applied to the sort-mode combobox, which also fixes it resetting the
  selection back to "Name" on every theme/language change.
- Restored the `datetime` import used by the GUI's logging and log-export
  features (it had been removed alongside the core extraction).
- `sum()` no longer called with an unsupported `default=` keyword in the
  size-based sort key.

## [1.0.0] - 2024-03-25

### Added

- **Core Features**
  - File prefix detection and grouping
  - Real-time preview of grouping results
  - Safe undo functionality for last batch operation
  - File extension filtering
  - Multi-threaded processing to prevent UI freezing
  - Drag and drop support (when tkinterdnd2 is installed)

- **Robustness Features**
  - Three conflict handling policies: Skip, Overwrite, Auto-Rename
  - Case-sensitive prefix matching option
  - Empty folder cleanup after undo
  - Automatic log persistence with rollback on failure
  - Unique filename generation to prevent collisions

- **Documentation**
  - README.md with comprehensive documentation
  - MIT License
  - CONTRIBUTING.md for community contributions
  - CHANGELOG.md for version tracking

- **Project Infrastructure**
  - .gitignore for clean repository
  - requirements.txt for dependency management
  - GitHub Actions CI/CD pipeline

### Technical Details

- Built with Python 3.7+ and tkinter
- Single-file architecture for easy distribution
- No external dependencies required for core functionality
- Optional tkinterdnd2 for enhanced drag-and-drop

### Known Limitations

- Currently only groups files by prefix (text before first `-`)
- No dark theme support yet
- English only (no internationalization)

## [Unreleased]

### Planned Features

- [ ] Dark/Light theme toggle
- [ ] Internationalization (i18n) support
- [ ] Executable (.exe) distribution
- [ ] Unit test coverage
- [ ] Batch rename functionality
- [ ] Custom grouping rules

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 1.0.0 | 2024-03-25 | Initial Release |

## Migration Guide

### Upgrading from v0.x to v1.0.0

This is the first official release. No migration needed.

---

*Generated with ❤️ by the prefix-file-sort team*
