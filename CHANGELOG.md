# Changelog

All notable changes to GMAB will be documented in this file.

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