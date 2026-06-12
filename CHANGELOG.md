# Changelog

All notable changes to GMAB will be documented in this file.

## [0.2.5] - 2026-06-12
### Added
- JSON output for automation: `-o json` (`--output`) on `spawn`, `list` (including
  `list detail [verbose]`), and `terminate`. The default format can also be set once via
  `output_format` in `config.json` (`text` or `json`); the `-o` flag overrides it. In JSON
  mode, `terminate` writes its to-be-terminated "plan" and confirmation prompt to stderr so
  stdout stays a single valid JSON result document.
- OVHcloud Public Cloud provider (`-p ovh`). Instances are scoped to a Public Cloud
  project (`service_name`); since OVH instances carry no tags, gmab encodes the creation
  time and lifetime in the instance name and filters on the `gmab-` prefix. Region-specific
  `flavorId`/`imageId` UUIDs are resolved from human names (`d2-2`, `Ubuntu 22.04`) per
  region at spawn time, so the defaults don't rot. Uses AK/AS/CK authentication.
- Mocked, offline test coverage for the OVH provider.
- `gmab list detail` and `gmab list detail verbose`: per-instance detail tables. The
  non-verbose view shows the common fields plus provider-specific extras (AWS VPC/subnet/
  security groups/AZ, OVH flavor/plan, Hetzner server type/datacenter, Linode specs);
  `verbose` dumps the full provider API response (flattened). Pass an instance id or label
  to show just that one instance, otherwise every instance is shown. Providers expose this
  via two new optional hooks, `get_instance_details()` and `detail_extras()`.
- `gmab list` now renders a responsive table (via `rich`) that auto-sizes to the terminal
  width, wraps long cells instead of truncating them (so full instance IDs and labels are
  always recoverable), drops low-priority columns (Image, then Region, then Instance ID) on
  narrow terminals while always keeping Provider/Label/IP/Status/Time Left, draws a separator
  line between instances, colorizes status (green running, orange expired) and an expired
  Time Left in red, and falls back to ASCII borders on consoles that can't render box-drawing
  characters.

### Changed
- Added `ovh` and `rich` to the runtime dependencies.
- OVH `gmab list` shows the friendly image name (e.g. `Ubuntu 22.04`) instead of the raw
  image UUID, resolved per region and cached.
- `gmab terminate` now previews the instances to be terminated using the same responsive
  table as `gmab list` in every case (a single instance, several, `all`, or `expired`)
  instead of a plain bulleted list or a bare confirmation prompt. Identifiers that don't
  resolve are shown as a "not found" row.

## [0.2.0] - 2026-06-12
### Changed
- Refactored provider integration into a self-registering plugin model: providers are
  auto-discovered from `gmab/providers/`, so adding one is a single drop-in file with no
  edits to the factory, config loader, configure command, or CLI.
- Replaced per-provider `get_default_config`/`get_config_prompts` with a declarative
  `CONFIG_SCHEMA`; the base class now derives defaults, prompts, validation, and secret masking.
- Hoisted shared logic (SSH key reading, label generation, expiry math, label-to-id lookup)
  into `ProviderBase` and `gmab/utils/naming.py`.
- `gmab terminate` now asks for y/n confirmation in every case, including a single instance
  (which previously skipped the prompt). Pass `-y`/`--yes` to bypass it.
- The post-spawn "Connect via" SSH hint now shows the correct login user per provider
  (`ubuntu` for the default AWS image, `root` for Linode/Hetzner) instead of always `root`.

### Added
- `gmab/providers/_template.py` reference implementation and an "Adding a provider" guide.
- A mocked, offline test suite (stdlib unittest, no new dependencies) covering provider
  lifecycle, base helpers, the command layer, and the config layer.

### Fixed
- Provider config defaults handed Hetzner AWS's defaults.
- Updated the AWS default AMI (the previous one had been deregistered) to a current
  Ubuntu 22.04 LTS image for eu-west-1.
- Updated the Hetzner default server type from `cpx11` (now US-only) to `cpx22`, which is
  available in the default `nbg1` location.
- `__version__` was left at 0.1.3 in the 0.1.4 release, so `gmab --version` reported the
  wrong number.

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