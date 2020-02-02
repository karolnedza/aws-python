import boto3
import time
from waiting import wait, TimeoutExpired
from botocore.exceptions import ClientError


#region_list = ['eu-central-1']

region_list = ['us-east-1','us-east-2', 'us-west-1', 'us-west-2' ]




# ************************************************************************************************
# ************************************************************************************************
# ************************************************************************************************



def clean_iam():

    session = boto3.Session(profile_name="labuser3")
    client_iam = session.client('iam')

    ######### Setting variables #########


    list_role_names = ['aviatrix-role-app', 'aviatrix-role-ec2']  # this will be static list
    list_policy_arn = []  #  ARN can change


    list_policies = client_iam.list_policies(Scope = 'Local')
    for arn in list_policies['Policies']:
       if 'aviatrix' in arn['Arn']:
            list_policy_arn.append(arn['Arn'])

    print(list_policy_arn)
    assume_role_policy_arn = [arn for arn in list_policy_arn if 'aviatrix-assume-role-policy' in arn ]
    app_policy_arn = [arn for arn in list_policy_arn if 'aviatrix-app-policy' in arn ]

    ######### Step 1: Remove role from instance profile

    try:
        remove_profile_instance = client_iam.remove_role_from_instance_profile(
            InstanceProfileName='aviatrix-role-ec2',RoleName='aviatrix-role-ec2')
        print('Removed aviatrix-role-ec2 from instance profile')
    except:
        print("Role aviatrix-role-ec2 is not attached to instance profile.")


    ######### Step 2: Detach roles from policies


    try:
        detach_ec2_role_from_policy = client_iam.detach_role_policy(
                RoleName='aviatrix-role-ec2',
                PolicyArn=assume_role_policy_arn[0]
            )
        print('Removed aviatrix-role-ec2 from aviatrix-assume-role-policy')

    except:
        print("Role aviatrix-role-ec2 is not attached to policy.")


    try:
        iam_role_detach = client_iam.detach_role_policy(
                RoleName='aviatrix-role-app',
                PolicyArn=app_policy_arn[0]
                )
        print('Removed aviatrix-role-app from aviatrix-app-policy')

    except:
            print("Role aviatrix-role-app is not attached to policy.")

    ######### Step 3: Delete policies

    for i in list_policy_arn:
        if "aviatrix" in i:
            del_app_policy = client_iam.delete_policy(PolicyArn = i)

    ######### Step 4: Delete roles

    try:
        response_role_app = client_iam.delete_role(RoleName='aviatrix-role-app')
        print("Removed aviatrix-role-app")
    except:
        print("aviatrix-role-app doesn't exist")

    try:
        response_role_ec2 = client_iam.delete_role(RoleName='aviatrix-role-ec2')
        print("Removed aviatrix-role-ec2")
    except:
        print("aviatrix-role-ec2 doesn't exist")

    ####### Step 5: Delete instance profile_

    try:
        response_instance_role = client_iam.delete_instance_profile(InstanceProfileName='aviatrix-role-ec2')
        print("Removed aviatrix-role-ec2 instance")
    except:
        print("aviatrix-role-ec2 instance doesn't exist")

# ************************************************************************************************
# ************************************************************************************************
# ************************************************************************************************

def clean_ec2(region):

    session = boto3.Session(profile_name="labuser3", region_name = region)
    ec2_resource = session.resource('ec2')
    ec2_client = session.client('ec2')
    ssh_keys = ec2_client.describe_key_pairs()
    instances = ec2_resource.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopped']}])


    ########## Terminating all  EC2s ###############


    try:
        for instance in instances:
            ec2_client.stop_instances(InstanceIds=[instance.id])
            waiter_stop = ec2_client.get_waiter('instance_stopped')
            waiter_stop.wait(InstanceIds=[instance.id], WaiterConfig={
        'Delay': 20,
        'MaxAttempts': 15
        })


        for instance in instances:
            ec2_client.modify_instance_attribute(InstanceId=instance.id,Attribute="disableApiTermination",Value='False')

        for instance in instances:
            ec2_client.terminate_instances(InstanceIds=[instance.id])
            waiter_terminated = ec2_client.get_waiter('instance_terminated')
            waiter_terminated.wait(InstanceIds=[instance.id], WaiterConfig={
        'Delay': 20,
        'MaxAttempts': 15
        })


    except:
        print("Something went wrong with deleting EC2....will try again")

    ####### Deleting interfaces ###############
    try:
        for vpc in ec2_resource.vpcs.all():
            for ni in vpc.network_interfaces.all():
                ni.delete()
    except:
        print("Something went wrong with deleting ENI....will try again")
    #finally:
    #    print("All ENIs have been deleted")

    ############ Releasing Elastic IP Addresses  ##################

    try:
        elastic_ip = ec2_client.describe_addresses()

        for eip_dict in elastic_ip['Addresses']:
              ec2_client.release_address(AllocationId=eip_dict['AllocationId'])
    except:
        print("Something went wrong with realsing EIP")
    #finally:
    #    print("All EIPs have been released")

    ############# Deleting key KeyPairs

    try:
        for key in ssh_keys['KeyPairs']:
            ec2_client.delete_key_pair(KeyName = key['KeyName'])
    except:
        print('Something went wrong with deleting key pairs')
#    finally:
#        print('All ssh key pairs have been deleted!')


    terminated_ec2 = ec2_client.describe_instances()
    ec2_state = []
    for i in terminated_ec2['Reservations']:
        ec2_state.append(i['Instances'][0]['State']['Name'] == 'terminated')
    return(all(ec2_state))

# ************************************************************************************************
# ************************************************************************************************
# ************************************************************************************************

def clean_tgw(region):

    session = boto3.Session(profile_name="labuser3", region_name = region)
    ec2_client = session.client('ec2')

    # Delete all TGW Attachemnts

    tgw_aws = ec2_client.describe_transit_gateways()
    tgw_aws_attachment = ec2_client.describe_transit_gateway_attachments()

    for i in tgw_aws_attachment['TransitGatewayAttachments']:
        ec2_client.delete_transit_gateway_vpc_attachment(TransitGatewayAttachmentId=i['TransitGatewayAttachmentId'])

    print('Deleting TGW attachments')
    # Wait until all TGW attachments are deleted

    def tgw_aws_attachment_deleted():
        attachments_state = []
        tgw_attachment_status = ec2_client.describe_transit_gateway_attachments()
        for i in tgw_attachment_status['TransitGatewayAttachments']:
            attachments_state.append(i['State'] == 'deleted')
        return(all(attachments_state))


    tgw_attachement_delete_status = lambda: tgw_aws_attachment_deleted()

    try:
        wait(tgw_attachement_delete_status, sleep_seconds=5, timeout_seconds=240)
    except:
        print('TGW Attachments delete failed')
#    finally:
#        print('All TGW attachments have been deleted.')
    # Delete all AWS Transit Gateways

    print('Deleting TGWs')

    for i in tgw_aws['TransitGateways']:
        ec2_client.delete_transit_gateway(TransitGatewayId=i['TransitGatewayId'])

    # Wait until all TGW are deleted

    def tgw_aws_deleted():
        tgw_state = []
        tgw_status = ec2_client.describe_transit_gateways()
        for i in tgw_status['TransitGateways']:
            tgw_state.append(i['State'] == 'deleted')
        return(all(tgw_status))

    tgw_delete_status = lambda: tgw_aws_deleted()

    try:
        wait(tgw_delete_status, sleep_seconds=10, timeout_seconds=240)
    except:
        print('TGW  delete failed')
#    finally:
#        print('All TGWs have been deleted.')

# ************************************************************************************************
# ************************************************************************************************
# ************************************************************************************************

############ Deleting Routing Tables - except main ones

def clean_rtb(region):
    session = boto3.Session(profile_name="labuser3", region_name = region )
    ec2_client = session.client('ec2')
    vpcs = ec2_client.describe_vpcs()
    rtbs = ec2_client.describe_route_tables()
    ############ Deleting Routing Tables - except main ones

    try:
        print('Deleting route tables')
        for rtb in rtbs['RouteTables']:
            if rtb['Associations'] == []:
                ec2_client.delete_route_table(RouteTableId = rtb['RouteTableId'])

    except:
        print('Something went wrong with deleting Route Tables')

    finally:
        print('All Route Tables have been deleted!')


    #### Checking if all not-main RT have been deleted

    deleted_rtb = ec2_client.describe_route_tables()
    rtb_state = []
    for i in deleted_rtb['RouteTables']:

        if i['Associations'][0]['Main'] == True:
            rtb_state.append(True)
        else:
            rtb_state.append(False)
    return(all(rtb_state))



def clean_subnets(region):
    session = boto3.Session(profile_name="labuser3", region_name = region )
    ec2_client = session.client('ec2')
    subnets = ec2_client.describe_subnets()

    ############ Deleting Subnets

    try:
        print('Deleting Subnets')
        for subnet in subnets['Subnets']:
            ec2_client.delete_subnet(SubnetId = subnet['SubnetId'])

    except:
        print('Something went wrong with deleting subnets')

#    finally:
#        print('All Subnets have been deleted!')
# ************************************************************************************************
# ************************************************************************************************
# ************************************************************************************************


def clean_vpc(region):
    session = boto3.Session(profile_name="labuser3", region_name = region )
    ec2_client = session.client('ec2')
    vpcs = ec2_client.describe_vpcs()
    igws = ec2_client.describe_internet_gateways()
    sgs = ec2_client.describe_security_groups()

#    def clean_igw():
    try:
        for igw in igws['InternetGateways']:
            ec2_client.detach_internet_gateway(InternetGatewayId=igw['InternetGatewayId'], VpcId=igw['Attachments'][0]['VpcId'])
    except:
        print('Something might go wrong with detaching IGWs')

#        finally:
#            print('All IGWs have been detached')

#    clean_igw()



    try:
        for igw in igws['InternetGateways']:
            ec2_client.delete_internet_gateway(InternetGatewayId=igw['InternetGatewayId'])
    except:
        print('Something might go wrong with deleting IGWs')

    #finally:
    #    print('All IGWs have been deleted')



    ########## Deleting Security Groups

    try:
        for sg in sgs['SecurityGroups']:
            if sg['GroupName'] == 'default':
                pass
            else:
                ec2_client.delete_security_group(GroupId = sg['GroupId'])
    except:
        print("Something went wrong with deleting security groups")

    #finally:
    #    print('All Security Groups have been deleted!')


    ############ Deleting VPCs
    time.sleep(5)
    try:
        for vpc in vpcs['Vpcs']:
            ec2_client.delete_vpc(VpcId = vpc['VpcId'])

    except:
            print("Something went wrong with deleting VPCs")

    finally:
            print('All VPCs have been deleted')


# ************************************************************************************************
# ************************************************************************************************
# ************************************************************************************************


#cleaning_iam = clean_iam()  # this global resource

###### First TGWs!!

for reg in region_list:
    print('********************************')
    print('Region name: ', reg )
    print('*********************************')
    cleaning_tgw = clean_tgw(reg)



###### Next EC2!!



for reg in region_list:
    print('********************************')
    print('Region name: ', reg )
    print('*********************************')


    ec2_terminated = lambda : clean_ec2(reg)

    try:
        print("Terminating EC2s")
        wait(ec2_terminated, sleep_seconds=5, timeout_seconds=240)
    except:
        print('Something went wrong with deleting EC2s')

    finally:
        print('All EC2 have been terminated')



##### Next subnets

for reg in region_list:
    subnets_removed = clean_subnets(reg)


### Next Route tables

for reg in region_list:
    print('********************************')
    print('Region name: ', reg )
    print('*********************************')
    rtb_removed = lambda : clean_rtb(reg)

    try:
        wait(rtb_removed, sleep_seconds=5, timeout_seconds=240)
    except:
        print('Something went wrong with deleting route tables')

#    finally:
#        print('All route tables have been terminated')


### Finally VPCs


for reg in region_list:
    print('********************************')
    print('Region name: ', reg )
    print('*********************************')
    cleaning_vpc = clean_vpc(reg)
