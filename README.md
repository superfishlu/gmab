# GMAB (Give Me A Box) v0.1.1

A CLI tool to spawn, list, and manage temporary cloud boxes.

#### Why?

- Need a quick VPS for pentesting, bug bounty, or scanning?
- Want to run commands from a different IP without using your local machine?
- No need for manual cloud console interaction—just **gmab spawn**, and you're in!


## Features

- Spawn temporary cloud instances that automatically expire
- List active instances across providers
- Terminate instances individually or in bulk
- Support for multiple cloud providers (Linode, AWS, Hetzner)
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
git clone https://github.com/yourusername/gmab.git
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

# Override defaults
gmab spawn -p linode -r us-east -i linode/ubuntu22.04 -t 120
```

### List instances
```bash
# List all instances
gmab list

# List instances for specific provider
gmab list --provider linode
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
```
### Version Information

You can check the installed version of GMAB using the `-v` or `--version` flag:

```bash
# Check version with short flag
gmab -v
# gmab 0.1.1

# Check version with long flag
gmab --version
# gmab 0.1.1
```

This is useful for debugging and ensuring you have the latest version installed.

## Provider-Specific Notes

### Linode
- Requires API key with full access
- Default instance type: Nanode 1GB
- Supports all regions

### AWS
- Requires access key and secret key
- Default instance type: t2.micro
- Creates VPC and security group if needed
- Supports all regions

### Hetzner
- Requires API token
- Default instance type: CPX11
- Supports all Hetzner Cloud regions
- Uses label-based instance tracking

## Best Practices

1. **SSH Key**: Use an ed25519 key pair for better security
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

2. **Instance Lifetime**: Set reasonable expiration times and automatic cleanup
```bash
# Set lifetime when spawning
gmab spawn -t 60  # 60 minutes lifetime

# Set up automatic cleanup with cron (Linux/Mac)
# Run every hour to clean up expired instances
0 * * * * gmab terminate expired -y

# For Windows, use Task Scheduler to run:
# gmab.exe terminate expired -y
```

3. **Regular Cleanup**: Periodically check and terminate expired instances
```bash
gmab terminate expired
```

4. **Provider Organization**:
- AWS: Create a dedicated IAM user for GMAB
- Linode: Use a dedicated API key
- Hetzner: Create a dedicated project named "gmab" and generate the API token specifically for this project

5. **Security**:
- Store configuration files securely
- Don't commit provider credentials to version control
- Regularly rotate API keys and tokens

## Example Commands and Outputs

### List Command
```bash
$ gmab list
Provider    Instance ID            Label                IP Address        Status              Region        Image                     Time Left
=====================================================================================================================
linode      12345678              gmab-abc123def456    192.168.1.100    running             us-east       linode/ubuntu22.04        45m
aws         i-0abc123def456789    gmab-def456abc789    10.0.1.100       running             us-west-2     ami-123456789abc         30m
hetzner     98765432              gmab-ghi789jkl012    10.0.0.100       running             nbg1          ubuntu-22.04             15m
aws         i-0xyz987wvu654321    gmab-mno345pqr678    10.0.2.200       running (expired)   us-east-1     ami-987654321xyz         expired
```

### Terminate Command
```bash
$ gmab terminate gmab-abc123def456 i-0abc123def456789
Are you sure you want to terminate instances: 'gmab-abc123def456', 'i-0abc123def456789'? [y/N]: y
Terminated instance 'gmab-abc123def456' on 'linode'.
Terminated instance 'i-0abc123def456789' on 'aws'.
Successfully terminated 2 instance(s).

$ gmab terminate all
The following instances will be terminated:
- 98765432 (hetzner: gmab-ghi789jkl012)
- i-0xyz987wvu654321 (aws: gmab-mno345pqr678)
Do you want to proceed? [y/N]: y
Successfully terminated 2 instance(s).
```

### Terminate Expired Command
```bash
$ gmab terminate expired
The following expired instances will be terminated:
- i-0xyz987wvu654321 (aws: gmab-mno345pqr678)
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
1. `config.json` - General settings (SSH key, default lifetime, default provider)
2. `providers.json` - Provider-specific credentials and defaults


### AWS Resources Created
When using AWS as a provider, GMAB automatically creates and manages the following resources:

1. **VPC (Virtual Private Cloud)**
   - Named: 'gmab-vpc'
   - CIDR: 10.0.0.0/16
   - DNS hostnames enabled

2. **Internet Gateway**
   - Named: 'gmab-igw'
   - Attached to gmab-vpc

3. **Subnet**
   - Named: 'gmab-subnet'
   - CIDR: 10.0.1.0/24
   - Auto-assign public IP enabled

4. **Route Table**
   - Named: 'gmab-rt'
   - Routes all traffic (0.0.0.0/0) through the internet gateway
   - Associated with gmab-subnet

5. **Security Group**
   - Named: 'gmab-sg'
   - Inbound rules: SSH (port 22) from anywhere
   - All resources are tagged with 'gmab=true'

### Provider Recommendations
While GMAB supports multiple cloud providers, it has been primarily developed and tested with Linode in mind. Linode typically offers:

- Faster instance provisioning times
- Simpler setup (no VPC/networking configuration needed)
- More straightforward API and authentication
- Lower costs for basic instances
- Consistent image names across regions (e.g., "linode/ubuntu22.04" works everywhere)

Hetzner Cloud provides similar ease of use and speed to Linode, with:
- Simple API and quick instance provisioning
- Consistent image names across regions
- Automatic network configuration
- Competitive pricing

AWS on the other hand adds some complexity due to:
- Network setup (VPC, subnet, security groups) required per region
- AMI IDs (image IDs) are different between regions
- Instance types may not be available in all regions
- Slower API responses and instance provisioning
- More complex authentication setup

For these reasons, when using GMAB with AWS we recommend:
- Stick to one region for all your instances
- Make sure your chosen AMI ID exists in your region
- Use modern instance types (t3.micro instead of t2.micro) for better region compatibility
- Configure your AWS credentials properly with sufficient permissions for VPC/networking
- Be patient as instance creation takes longer than other providers

If you're just getting started with GMAB, we recommend beginning with Linode or Hetzner for the simplest experience.

## Example configuration session:
```bash
$ gmab configure
Using config directory: /home/user/.config/gmab

Configuring general settings:
SSH public key path [~/.ssh/id_ed25519.pub]: 
Default instance lifetime (minutes) [60]: 
Default provider (linode, aws, hetzner) [linode]: 

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
Default image [ami-12345678]: 
Default instance type [t2.micro]: 

Do you want to configure hetzner? [Y/n]: n

Configuration completed successfully!
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.