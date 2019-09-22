import boto3

# Get All Regions 
regions = boto3.session.Session().get_available_regions('ec2')

# List instances
def list_instances(i):
    "List EC2 instances"
    ec2 = boto3.session.Session(region_name= i ).resource('ec2')
    for i in ec2.instances.all():
        print(', '.join((
            i.id,
            i.instance_type,
            i.placement['AvailabilityZone'],
            i.state['Name'],
            i.public_dns_name)))

# Stop instances
def stop_instances(i):
    "Stop EC2 instances"
    ec2 = boto3.session.Session(region_name= i ).resource('ec2')
    instances = ec2.instances.filter(Filters=[{'Values': ['running']}])
    for i in ec2.instances.all():
        ec2.instances.stop()


for i in regions:
    print('List of all EC2 instances')
    list_instances(i)

    print('*****************************')
    
    print('Stopping all running EC2 instances')
    # TO STOP INSTANCES REMOVE COMMENT
    # stop_instances(i)

    print('*****************************')
    print('List of all EC2 instances')
    list_instances(i)   # list all Instancess again
