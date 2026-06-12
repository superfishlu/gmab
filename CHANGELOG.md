# Changelog

All notable changes to GMAB will be documented in this file.

## [0.2.0] - 2026-06-12
### Changed
- Refactored provider integration into a self-registering plugin model: providers are
  auto-discovered from `gmab/providers/`, so adding one is a single drop-in file with no
  edits to the factory, config loader, configure command, or CLI.
- Replaced per-provider `get_default_config`/`get_config_prompts` with a declarative
  `CONFIG_SCHEMA`; the base class now derives defaults, prompts, validation, and secret masking.
- Hoisted shared logic (SSH key reading, label generation, expiry math, label-to-id lookup)
  into `ProviderBase` and `gmab/utils/naming.py`.

### Added
- `gmab/providers/_template.py` reference implementation and an "Adding a provider" guide.
- A mocked, offline test suite (stdlib unittest, no new dependencies) covering provider
  lifecycle, base helpers, the command layer, and the config layer.

### Fixed
- Provider config defaults handed Hetzner AWS's defaults.
- `__version__` was left at 0.1.3 in the 0.1.4 release.

## [0.1.4] - 2026-01-20
### Changed
- Re-published to PyPI after account restoration

## [0.1.3] - 2025-03-05
### Changed/Fixed
- Removed old dependencies as documented in issue #5

## [0.1.2] - 2025-03-03

### Added
- **--version** and **-v** flags to print the current version of gmab
```bash
gmab --version
gmab 0.1.2
```

### Changed/Fixed
- Merged PR6 to introduce (very) basic unit testing and remove (almost) all provider specific code from **configure.py**

## [0.1.1] - 2025-02-26

### Added
- Added a config check to ensure config files exist before running commands
- Better error handling throughout the codebase
- Improved documentation in code with docstrings
- Added timeouts to API requests for better reliability

### Changed
- Configuration workflow now only creates configs when `gmab configure` is run
- Only providers that are explicitly configured are added to the config
- Improved error messages that guide users to run configuration when needed
- Configuration checks to ensure required API keys are present
- Better error messages when working with unconfigured providers

### Fixed
- Removed default empty provider configuration to prevent unnecessary API calls
- Fixed error handling for network issues in API requests
- More robust exception handling throughout the code

## [0.1.0] - Initial Release

### Added
- Initial release of GMAB with basic functionality
- Support for Linode, AWS, and Hetzner Cloud providers
- Commands for spawning, listing, and terminating instances
- Configuration management system