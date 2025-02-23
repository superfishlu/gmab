# gmab/providers/aws.py

import boto3
import random
import string
import time
from pathlib import Path
from gmab.providers.base import ProviderBase

def generate_random_string(length=12):
    """Generate a random string of lowercase letters and digits."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

class AWSProvider(ProviderBase):
    """
    Provider implementation for AWS EC2.
    """

    def __init__(self, provider_cfg):
        super().__init__(provider_cfg)
        self.session = boto3.Session(
            aws_access_key_id=provider_cfg.get('access_key'),
            aws_secret_access_key=provider_cfg.get('secret_key'),
            region_name=provider_cfg.get('default_region', 'us-east-1')
        )
        self.ec2 = self.session.client('ec2')
        self.ec2_resource = self.session.resource('ec2')

    def get_or_create_vpc(self):
        """Get existing gmab VPC or create a new one."""
        # Check for existing gmab VPC
        vpcs = self.ec2.describe_vpcs(
            Filters=[
                {'Name': 'tag:Name', 'Values': ['gmab-vpc']}
            ]
        )['Vpcs']

        if vpcs:
            return vpcs[0]['VpcId']

        # Create new VPC
        vpc = self.ec2_resource.create_vpc(
            CidrBlock='10.0.0.0/16',
            TagSpecifications=[
                {
                    'ResourceType': 'vpc',
                    'Tags': [
                        {'Key': 'Name', 'Value': 'gmab-vpc'},
                        {'Key': 'gmab', 'Value': 'true'}
                    ]
                }
            ]
        )
        vpc.wait_until_available()

        # Enable DNS hostnames
        self.ec2.modify_vpc_attribute(
            VpcId=vpc.id,
            EnableDnsHostnames={'Value': True}
        )

        # Create and attach internet gateway
        igw = self.ec2_resource.create_internet_gateway(
            TagSpecifications=[
                {
                    'ResourceType': 'internet-gateway',
                    'Tags': [
                        {'Key': 'Name', 'Value': 'gmab-igw'},
                        {'Key': 'gmab', 'Value': 'true'}
                    ]
                }
            ]
        )
        vpc.attach_internet_gateway(InternetGatewayId=igw.id)

        # Create subnet
        subnet = vpc.create_subnet(
            CidrBlock='10.0.1.0/24',
            TagSpecifications=[
                {
                    'ResourceType': 'subnet',
                    'Tags': [
                        {'Key': 'Name', 'Value': 'gmab-subnet'},
                        {'Key': 'gmab', 'Value': 'true'}
                    ]
                }
            ]
        )

        # Create route table and add route to internet
        route_table = vpc.create_route_table(
            TagSpecifications=[
                {
                    'ResourceType': 'route-table',
                    'Tags': [
                        {'Key': 'Name', 'Value': 'gmab-rt'},
                        {'Key': 'gmab', 'Value': 'true'}
                    ]
                }
            ]
        )
        route_table.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw.id
        )
        route_table.associate_with_subnet(SubnetId=subnet.id)

        # Enable auto-assign public IP
        self.ec2.modify_subnet_attribute(
            SubnetId=subnet.id,
            MapPublicIpOnLaunch={'Value': True}
        )

        return vpc.id

    def get_or_create_security_group(self, vpc_id):
        """Get existing gmab security group or create a new one."""
        try:
            # Check for existing security group
            security_groups = self.ec2.describe_security_groups(
                Filters=[
                    {'Name': 'group-name', 'Values': ['gmab-sg']},
                    {'Name': 'vpc-id', 'Values': [vpc_id]}
                ]
            )['SecurityGroups']

            if security_groups:
                return security_groups[0]['GroupId']

            # Create new security group
            response = self.ec2.create_security_group(
                GroupName='gmab-sg',
                Description='Security group for GMAB instances',
                VpcId=vpc_id,
                TagSpecifications=[
                    {
                        'ResourceType': 'security-group',
                        'Tags': [
                            {'Key': 'Name', 'Value': 'gmab-sg'},
                            {'Key': 'gmab', 'Value': 'true'}
                        ]
                    }
                ]
            )
            security_group_id = response['GroupId']

            # Add SSH ingress rule
            self.ec2.authorize_security_group_ingress(
                GroupId=security_group_id,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    }
                ]
            )

            return security_group_id

        except Exception as e:
            raise Exception(f"Failed to setup security group: {str(e)}")

    def get_subnet_id(self, vpc_id):
        """Get the gmab subnet ID for the given VPC."""
        subnets = self.ec2.describe_subnets(
            Filters=[
                {'Name': 'vpc-id', 'Values': [vpc_id]},
                {'Name': 'tag:Name', 'Values': ['gmab-subnet']}
            ]
        )['Subnets']

        if not subnets:
            raise Exception("Could not find gmab subnet")
        
        return subnets[0]['SubnetId']

    def get_instance_id_by_label(self, label):
        """Find instance ID by label, but only for instances with the 'gmab' tag."""
        try:
            response = self.ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:Name', 'Values': [label]},
                    {'Name': 'tag:gmab', 'Values': ['true']},
                    {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
                ]
            )

            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    return instance['InstanceId']
            
            return None
        except Exception as e:
            return None

    def _get_instance_expiry_info(self, instance):
        """Helper method to get expiry information from instance tags."""
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        creation_time = int(tags.get('gmab-creation-time', '0'))
        lifetime_minutes = int(tags.get('gmab-lifetime', '60'))
        current_time = int(time.time())
        
        is_expired = (current_time - creation_time) > (lifetime_minutes * 60)
        return creation_time, lifetime_minutes, is_expired

    def spawn_instance(self, image=None, region=None, ssh_key_path=None, lifetime_minutes=None):
        # Use provided region or fall back to default
        default_region = self.provider_cfg.get("default_region", "us-east-1")
        chosen_region = region or default_region

        # Use provided image or fall back to default
        default_image = self.provider_cfg.get("default_image", "ami-0574da719dca65348")
        chosen_image = image or default_image

        # Get instance type from config or use default
        instance_type = self.provider_cfg.get("default_type", "t2.micro")

        # Generate a unique name tag
        instance_name = f"gmab-{generate_random_string(12)}"

        # Current timestamp for creation time
        creation_time = int(time.time())
        
        # Default lifetime if not specified
        if lifetime_minutes is None:
            lifetime_minutes = 60

        # Read SSH key
        ssh_key_path = ssh_key_path or self.provider_cfg.get("ssh_key_path", "~/.ssh/id_ed25519.pub")
        keyfile = Path(ssh_key_path).expanduser()
        if not keyfile.exists():
            raise FileNotFoundError(f"SSH key not found at {keyfile}")

        with open(keyfile, 'r') as f:
            ssh_key_content = f.read().strip()

        # Setup networking
        vpc_id = self.get_or_create_vpc()
        security_group_id = self.get_or_create_security_group(vpc_id)
        subnet_id = self.get_subnet_id(vpc_id)

        # Import SSH key to AWS
        key_name = f"gmab-key-{generate_random_string(8)}"
        try:
            self.ec2.import_key_pair(
                KeyName=key_name,
                PublicKeyMaterial=ssh_key_content.encode()
            )
        except Exception as e:
            raise Exception(f"Failed to import SSH key to AWS: {str(e)}")

        # Launch instance with standardized tags
        try:
            response = self.ec2.run_instances(
                ImageId=chosen_image,
                InstanceType=instance_type,
                MinCount=1,
                MaxCount=1,
                KeyName=key_name,
                SecurityGroupIds=[security_group_id],
                SubnetId=subnet_id,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': instance_name},
                            {'Key': 'gmab', 'Value': 'true'},
                            {'Key': 'gmab-creation-time', 'Value': str(creation_time)},
                            {'Key': 'gmab-lifetime', 'Value': str(lifetime_minutes)}
                        ]
                    }
                ]
            )
        except Exception as e:
            # Clean up the key pair if instance launch fails
            try:
                self.ec2.delete_key_pair(KeyName=key_name)
            except:
                pass
            raise Exception(f"Failed to launch AWS instance: {str(e)}")

        instance = response['Instances'][0]
        instance_id = instance['InstanceId']

        try:
            # Wait for instance to be running and get its public IP
            waiter = self.ec2.get_waiter('instance_running')
            waiter.wait(InstanceIds=[instance_id])

            # Get instance details
            instance_info = self.ec2.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]
            ip_address = instance_info.get('PublicIpAddress', 'No IP Assigned')

            return {
                "provider": self.provider_name,
                "instance_id": instance_id,
                "label": instance_name,
                "ip": ip_address,
                "status": instance_info['State']['Name'],
                "region": chosen_region,
                "image": chosen_image,
                "creation_time": creation_time,
                "lifetime_minutes": lifetime_minutes
            }
        except Exception as e:
            # Clean up on error
            try:
                self.ec2.terminate_instances(InstanceIds=[instance_id])
                self.ec2.delete_key_pair(KeyName=key_name)
            except:
                pass
            raise Exception(f"Failed to get instance details: {str(e)}")

    def terminate_instance(self, instance_identifier):
        """
        Terminate an EC2 instance by ID or label.
        Args:
            instance_identifier: Can be either an instance ID (i-xxxxx) or a label (gmab-xxxxx)
        """
        try:
            # If it's not a typical AWS instance ID format, try to find by label
            if not instance_identifier.startswith('i-'):
                instance_id = self.get_instance_id_by_label(instance_identifier)
                if instance_id is None:
                    raise Exception(f"No instance found with label '{instance_identifier}'")
            else:
                instance_id = instance_identifier

            # Get the instance tags to find our key pair name if it exists
            response = self.ec2.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            
            # Find any gmab key pairs associated with this instance
            key_name = instance.get('KeyName')
            if key_name and key_name.startswith('gmab-key-'):
                try:
                    self.ec2.delete_key_pair(KeyName=key_name)
                except:
                    pass  # Best effort cleanup

            self.ec2.terminate_instances(InstanceIds=[instance_id])
        except Exception as e:
            raise Exception(f"Failed to terminate AWS instance: {str(e)}")

    def list_instances(self):
        """List all EC2 instances tagged with 'gmab'."""
        try:
            response = self.ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:gmab', 'Values': ['true']},
                    {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
                ]
            )

            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    name_tag = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), 'Unknown')
                    creation_time, lifetime_minutes, is_expired = self._get_instance_expiry_info(instance)
                    
                    # Modify status to include expiry information
                    base_status = instance['State']['Name']
                    status = f"{base_status} (expired)" if is_expired else base_status

                    instances.append({
                        "provider": self.provider_name,
                        "instance_id": instance['InstanceId'],
                        "label": name_tag,
                        "ip": instance.get('PublicIpAddress', 'No IP Assigned'),
                        "status": status,
                        "region": instance['Placement']['AvailabilityZone'][:-1],
                        "image": instance['ImageId'],
                        "creation_time": creation_time,
                        "lifetime_minutes": lifetime_minutes,
                        "is_expired": is_expired
                    })

            return instances

        except Exception as e:
            raise Exception(f"Failed to list AWS instances: {str(e)}")

    def list_expired_instances(self):
        """List all expired instances."""
        return [inst for inst in self.list_instances() if inst['is_expired']]