# GMAB (Give Me A Box) v0.2.5

A CLI tool to spawn, list, and manage temporary cloud boxes.

#### Why?

- Need a quick VPS for pentesting, bug bounty, or scanning?
- Want to run commands from a different IP without using your local machine?
- No need for manual cloud console interaction - just **gmab spawn**, and you're in!


## Features

- Spawn temporary cloud instances that automatically expire
- List active instances across providers
- Terminate instances individually or in bulk
- Support for multiple cloud providers (Linode, AWS, Hetzner, OVHcloud)
- Provider-agnostic command interface
- SSH key management

## Installation

### Using pip

The easiest way to install GMAB is directly from PyPI:

```bash
pip install gmab
```

### From Source

You can also install directly from the source code:

```bash
# Clone the repository
git clone https://github.com/superfishlu/gmab.git
cd gmab

# Install the package
pip install .

# For development (editable mode)
pip install -e .
```

## Configuration
Before you can use GMAB, you need to configure it with your provider credentials and preferences. You must run the `configure` command before using any other functionality.

### Interactive Configuration

Use the configure command to set up or modify your configuration:

```bash
# Configure all settings and providers
gmab configure

# Configure a specific provider
gmab configure -p linode
```

> **Note:** GMAB will only use providers that you've explicitly configured. If you don't configure a provider, GMAB will not attempt to use it, preventing any unnecessary API calls or errors.

### Viewing Configuration

You can view your current configuration using the `--print` flag:

```bash
gmab configure --print
```

This will display:
- The location of your config files
- The contents of your configuration (with sensitive data masked)
- The current settings for all configured providers

## Usage

### Spawn a new instance
```bash
# Using default provider
gmab spawn

# Specify a provider
gmab spawn --provider linode
gmab spawn --provider aws
gmab spawn --provider hetzner
gmab spawn --provider ovh

# Override defaults
gmab spawn -p linode -r us-east -i linode/ubuntu22.04 -t 120
```

### List instances
```bash
# List all instances (summary table)
gmab list

# List instances for specific provider
gmab list --provider linode

# Per-instance detail tables (provider-specific fields: VPC/subnet for AWS,
# flavor/plan for OVH, server type for Hetzner, specs for Linode, ...)
gmab list detail

# Dump the full provider API response for each instance
gmab list detail verbose

# Detail (or verbose detail) for a single instance by id or label
gmab list detail gmab-abc123def456
gmab list detail verbose i-0abc123def456789
```

### Terminate instances
```bash
# Terminate by ID or label
gmab terminate instance-123
gmab terminate my-instance-label

# Terminate multiple instances
gmab terminate instance-1 instance-2

# Terminate all instances
gmab terminate all

# Terminate expired instances
gmab terminate expired

# Skip the y/n confirmation (useful for automation/cron)
gmab terminate my-instance-label -y
gmab terminate expired -y
```
`gmab terminate` asks for a y/n confirmation before terminating anything (a single instance,
multiple, `all`, or `expired`). Pass `-y`/`--yes` to skip the prompt.

### JSON output (for automation)

`spawn`, `list` (including `list detail [verbose]`), and `terminate` accept `-o json`
(`--output json`) to emit machine-readable JSON instead of the human-readable tables:

```bash
gmab spawn -p ovh -t 60 -o json          # the new instance as JSON
gmab list -o json                        # all instances as a JSON array
gmab list detail verbose -o json         # full provider API payload per instance
gmab terminate expired -y -o json        # {"terminated":[...],"failed":[...],...}
```

To always get JSON without passing the flag, set `output_format` to `json` in `config.json`
(or choose it during `gmab configure`); the `-o` flag overrides the config per-invocation.
In JSON mode, when `terminate` asks for confirmation it writes the to-be-terminated list (a
JSON "plan") **and** the prompt to **stderr**, so stdout carries only the final result
document and stays parseable by `jq`. For fully non-interactive use, combine it with `-y`.

### Version Information

You can check the installed version of GMAB using the `-v` or `--version` flag:

```bash
# Check version with short flag
gmab -v
# gmab 0.2.5

# Check version with long flag
gmab --version
# gmab 0.2.5
```

This is useful for debugging and ensuring you have the latest version installed.

## Provider-Specific Notes

You only need credentials for the providers you actually use. Linode and Hetzner are the
simplest and fastest to provision; AWS is the most involved (it builds its own network and
its image IDs are region-specific). If you're just getting started, begin with Linode or
Hetzner.

### Linode
- Requires an API token (personal access token) with read/write access to Linodes.
- Default instance type `g6-nanode-1` (Nanode 1GB); default image `linode/ubuntu22.04`; login user `root`.
- Fast provisioning, simple API, and image names are the same across every region.
- Tracks its instances with a `gmab` tag.

### Hetzner
- Requires an API token, ideally generated inside a dedicated "gmab" project.
- Default server type `cpx22`; default location `nbg1`; login user `root`.
- Fast provisioning and consistent image names across locations. Note that some server
  types are only offered in certain locations (e.g. the smaller `cpx11` is US-only), so a
  type/location mismatch is rejected by the API.
- Tracks its instances with `gmab` labels.

### AWS
- Requires an access key and secret key (a dedicated IAM user is recommended) with
  permissions for EC2 plus VPC/subnet/security-group management.
- Default instance type `t3.micro`; default region `eu-west-1`; login user `ubuntu`.
- AMI (image) IDs are region-specific and get deregistered over time, so changing region
  usually means changing image; instance types aren't available in every region either.
  Sticking to one region avoids surprises. Provisioning is noticeably slower than the others.
- Tracks its instances (and its own networking) by tagging everything `gmab=true`.

  On first spawn in a region, GMAB creates and then reuses its own isolated network:

  | Resource | Name | Notes |
  |---|---|---|
  | VPC | `gmab-vpc` | CIDR 10.0.0.0/16, DNS hostnames enabled |
  | Internet Gateway | `gmab-igw` | attached to `gmab-vpc` |
  | Subnet | `gmab-subnet` | CIDR 10.0.1.0/24, auto-assign public IP |
  | Route Table | `gmab-rt` | routes 0.0.0.0/0 via the internet gateway |
  | Security Group | `gmab-sg` | inbound SSH (port 22) from anywhere |

### OVHcloud
- Requires an Application Key, Application Secret, and Consumer Key (create them at
  https://api.ovh.com/createToken with GET/POST/PUT/DELETE on `/cloud/*`), plus your Public
  Cloud **project ID** (`service_name`).
- Default region `GRA9` (EU); default instance type `d2-2`; default image `Ubuntu 22.04`;
  login user `ubuntu`.
- `flavor` and `image` are configured as human names and resolved to region-specific IDs at
  spawn time, so the defaults don't go stale the way raw UUIDs would. Available
  regions/flavors vary by project; if a spawn fails with "not found", the error lists what
  your project actually offers.
- OVH instances have no tags, so gmab tracks its boxes by encoding the creation time and
  lifetime in the instance name (`gmab-<creation>-<lifetime>-<random>`).

## Best Practices

1. **Use a dedicated, least-privilege credential per provider**, so revoking gmab's access
   never affects anything else:
   - AWS: a dedicated IAM user with EC2 + VPC permissions
   - Linode: a dedicated API token
   - Hetzner: an API token generated inside a dedicated "gmab" project
   - OVH: an application credential scoped to `/cloud/*` on the gmab project

2. **Use an ed25519 SSH key:**
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```

3. **Set a lifetime and let boxes expire, then actually clean them up.** Expiry only marks
   a box; you still have to terminate it. gmab spawns real, billable cloud resources, so an
   unattended box keeps costing money until it's gone. Automate the cleanup:
   ```bash
   gmab spawn -t 60                      # 60-minute lifetime
   # Linux/macOS cron, sweep expired boxes every hour:
   0 * * * * gmab terminate expired -y
   # Windows: run the same command from Task Scheduler:
   #   gmab.exe terminate expired -y
   ```

4. **Automate with `-o json`** instead of scraping the human-readable tables
   (see [JSON output](#json-output-for-automation)).

5. **Keep credentials safe:** `providers.json` stores provider secrets in plain text, so don't
   commit it, restrict its file permissions, and rotate keys periodically.

## Example Commands and Outputs

### List Command
```text
$ gmab list
╭──────────┬──────────────────────────────────────┬─────────────────────────────┬────────────────┬───────────────────┬───────────┬──────────────────────┬───────────╮
│ Provider │ Instance ID                          │ Label                       │ IP Address     │ Status            │ Region    │ Image                │ Time Left │
├──────────┼──────────────────────────────────────┼─────────────────────────────┼────────────────┼───────────────────┼───────────┼──────────────────────┼───────────┤
│ ovh      │ dfe10f41-4c29-4af5-8cec-175881f023ab │ gmab-1781265913-60-33xnxgqs │ 79.137.120.108 │ running           │ GRA9      │ Ubuntu 22.04         │ 58m       │
│ linode   │ 12345678                             │ gmab-abc123def456           │ 192.168.1.100  │ running           │ us-east   │ linode/ubuntu22.04   │ 45m       │
│ aws      │ i-0xyz987wvu654321                   │ gmab-mno345pqr678           │ 10.0.2.200     │ running (expired) │ eu-west-1 │ ami-02ad7d74d71067c63│ expired   │
╰──────────┴──────────────────────────────────────┴─────────────────────────────┴────────────────┴───────────────────┴───────────┴──────────────────────┴───────────╯
```
The table is **responsive** (powered by [rich](https://github.com/Textualize/rich)): it
auto-sizes to your terminal width and wraps long cells rather than truncating them, so the
full **Instance ID** and **Label** are always recoverable. On narrower terminals it drops
columns by priority (Image first, then the wide Instance ID, then Region) while always
keeping Provider, **Label** (your `terminate` handle), IP, Status and Time Left. A separator line is
drawn between instances, the status is colorized (green running, orange expired) and an
expired Time Left is shown in red. Borders fall back to ASCII on consoles that can't render
box-drawing characters.

### Terminate Command
```bash
$ gmab terminate gmab-abc123def456 i-0abc123def456789
The following instances will be terminated:
╭──────────┬────────────────────┬───────────────────┬───────────────┬─────────┬─────────┬───────────╮
│ Provider │ Instance ID        │ Label             │ IP Address    │ Status  │ Region  │ Time Left │
├──────────┼────────────────────┼───────────────────┼───────────────┼─────────┼─────────┼───────────┤
│ linode   │ 12345678           │ gmab-abc123def456 │ 192.168.1.100 │ running │ us-east │ 45m       │
├──────────┼────────────────────┼───────────────────┼───────────────┼─────────┼─────────┼───────────┤
│ aws      │ i-0abc123def456789 │ gmab-def456abc789 │ 10.0.1.100    │ running │ us-west │ 30m       │
╰──────────┴────────────────────┴───────────────────┴───────────────┴─────────┴─────────┴───────────╯
Do you want to proceed? [y/N]: y
Terminated instance 'gmab-abc123def456' on 'linode'.
Terminated instance 'i-0abc123def456789' on 'aws'.
Successfully terminated 2 instance(s).

$ gmab terminate all
The following instances will be terminated:
╭──────────┬────────────────────┬───────────────────┬────────────┬───────────────────┬───────────┬───────────╮
│ Provider │ Instance ID        │ Label             │ IP Address │ Status            │ Region    │ Time Left │
├──────────┼────────────────────┼───────────────────┼────────────┼───────────────────┼───────────┼───────────┤
│ hetzner  │ 98765432           │ gmab-ghi789jkl012 │ 10.0.0.100 │ running           │ nbg1      │ 15m       │
├──────────┼────────────────────┼───────────────────┼────────────┼───────────────────┼───────────┼───────────┤
│ aws      │ i-0xyz987wvu654321 │ gmab-mno345pqr678 │ 10.0.2.200 │ running (expired) │ eu-west-1 │ expired   │
╰──────────┴────────────────────┴───────────────────┴────────────┴───────────────────┴───────────┴───────────╯
Do you want to proceed? [y/N]: y
Successfully terminated 2 instance(s).
```
The termination preview uses the same responsive table as `gmab list`.

### Terminate Expired Command
```bash
$ gmab terminate expired
The following expired instances will be terminated:
╭──────────┬────────────────────┬───────────────────┬────────────┬───────────────────┬───────────┬───────────╮
│ Provider │ Instance ID        │ Label             │ IP Address │ Status            │ Region    │ Time Left │
├──────────┼────────────────────┼───────────────────┼────────────┼───────────────────┼───────────┼───────────┤
│ aws      │ i-0xyz987wvu654321 │ gmab-mno345pqr678 │ 10.0.2.200 │ running (expired) │ eu-west-1 │ expired   │
╰──────────┴────────────────────┴───────────────────┴────────────┴───────────────────┴───────────┴───────────╯
Do you want to proceed? [y/N]: y
Successfully terminated 1 instance(s).

$ gmab terminate expired
No expired instances found.
```

## Configuration Storage
GMAB follows platform-specific standards for storing configuration:

- Linux/macOS: `~/.config/gmab/` or `$XDG_CONFIG_HOME/gmab/`
- Windows: `%APPDATA%\gmab\`
- Override: Set `GMAB_CONFIG_DIR` environment variable

Two main configuration files are used:
1. `config.json` - General settings (SSH key, default lifetime, default provider, default output format)
2. `providers.json` - Provider-specific credentials and defaults (stored in plain text, so keep it private)

The resources GMAB creates on AWS are documented in the [AWS provider note](#aws) above.

## Example configuration session:
```bash
$ gmab configure
Using config directory: /home/user/.config/gmab

Configuring general settings:
SSH public key path [~/.ssh/id_ed25519.pub]: 
Default instance lifetime (minutes) [60]: 
Default provider (linode, aws, hetzner, ovh) [linode]: 
Default output format (text, json) [text]: 

Do you want to configure linode? [Y/n]: y

Configuring linode provider:
API Key: your-api-key-here
Default region [nl-ams]: 
Default instance type [g6-nanode-1]: 
Default image [linode/ubuntu22.04]: 
Default root password: your-root-password

Do you want to configure aws? [Y/n]: y

Configuring aws provider:
Access Key: your-access-key
Secret Key: your-secret-key
Default region [eu-west-1]: 
Default image [ami-02ad7d74d71067c63]: 
Default instance type [t3.micro]: 

Do you want to configure hetzner? [Y/n]: n

Do you want to configure ovh? [Y/n]: n

Configuration completed successfully!
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Adding a new provider

Providers are auto-discovered, so adding one is a single-file drop-in: you do **not**
touch the factory, config loader, configure command, or CLI:

1. Copy `gmab/providers/_template.py` to `gmab/providers/<yourprovider>.py`.
2. Set the class `name` (the value users pass to `-p`) and declare `CONFIG_SCHEMA`
   (a list of `ConfigField`s describing your credentials and defaults).
3. Implement the four lifecycle methods: `spawn_instance`, `terminate_instance`,
   `list_instances`, `list_expired_instances`.

The base class derives the interactive `gmab configure` prompts, defaults, validation,
and secret-masking from your `CONFIG_SCHEMA`, and provides shared helpers
(`_read_ssh_key`, `is_expired`, `find_instance_id_by_label`, and `make_label`). Tag your
instances with `gmab` so `list`/`terminate` only ever touch gmab-owned resources. To add
a contract test, mix `ProviderContractMixin` (`tests/providers/provider_contract.py`)
into a `unittest.TestCase` and set `provider_cls`.

## Disclaimer

GMAB spawns real, billable cloud resources and is intended for **authorized use only**. You
are responsible for the instances you create, the costs they incur, and how you use them
(for example, only scan or test systems you own or are permitted to test). The software is
provided "as is", without warranty of any kind, and the author accepts no liability for any
damage, loss, cost, or misuse arising from it.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
The MIT license already disclaims warranty and limits liability.
