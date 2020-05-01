#!/usr/bin/env python3
import argparse
from botocore.exceptions import ClientError
import os

# When writing a module, feel free to remove any comments, placeholders, or
# anything else that doesn't relate to your module.

module_info = {
    # Name of the module (should be the same as the filename).
    'name': 'enum__secrets',

    # Name and any other notes about the author.
    'author': 'Nick Spagnola From RSL',

    # Category of the module. Make sure the name matches an existing category.
    'category': 'ENUM',

    # One liner description of the module functionality. This shows up when a
    # user searches for modules.
    'one_liner': 'enumerates and dumps secrets from AWS Secrets Manager and AWS parameter store',

    # Full description about what the module does and how it works.
    'description': 'This module will enumerate secrets in AWS Secrets Manager and AWS Systems manager parameter store.',

    # A list of AWS services that the module utilizes during its execution.
    'services': [],

    # For prerequisite modules, try and see if any existing modules return the
    # data that is required for your module before writing that code yourself;
    # that way, session data can stay separated and modular.
    'prerequisite_modules': [],

    # External resources that the module depends on. Valid options are either
    # a GitHub URL (must end in .git), or a single file URL.
    'external_dependencies': [],

    # Module arguments to autocomplete when the user hits tab.
    'arguments_to_autocomplete': ['--regions'],
}

parser = argparse.ArgumentParser(add_help=False, description=module_info['description'])
parser.add_argument('--regions', required=False, help='One or more (comma separated) AWS regions in the format "us-east-1". Defaults to all session regions.')

def main(args, pacu_main):
    session = pacu_main.get_active_session()

    args = parser.parse_args(args)
    print = pacu_main.print
    get_regions = pacu_main.get_regions

    summary_data = {"SecretsManager": 0,"ParameterStore": 0}

    if args.regions is None:
        regions = get_regions('secretsmanager')
        if regions is None or regions == [] or regions == '' or regions == {}:
            print('This module is not supported in any regions specified in the current sessions region set. Exiting...')
            return None
    else:
        regions = args.regions.split(',')

    all_secrets_ids_sm = []
    all_secrets_ids_ssm = []

    if not os.path.exists('./sessions/{}/downloads/secrets/secrets_manager'.format(session.name)):
        os.makedirs('./sessions/{}/downloads/secrets/secrets_manager'.format(session.name))

    if not os.path.exists('./sessions/{}/downloads/secrets/parameter_store'.format(session.name)):
        os.makedirs('./sessions/{}/downloads/secrets/parameter_store'.format(session.name))

    for region in regions:
        secret_ids = []
        secrets_ssm = []

        print('Starting region {}...'.format(region))
        client = pacu_main.get_boto3_client('secretsmanager', region)
        
        
        response = None
        next_token = False
        while (response is None) or 'NextToken' in response:
            if next_token is False:
                try:
                    response = client.list_secrets()
                except ClientError as error:
                    code = error.response['Error']['Code']
                    print('FAILURE: ')
                    if code == 'UnauthorizedOperation':
                        print('  Access denied to ListSecrets.')
                    else:
                        print('  ' + code)
                    print('    Could not list secrets... Exiting')
                    return None
                    
            else:
                response = client.list_secrets()

            for secret in response['SecretList']:
                secret_ids.append({"name":secret["Name"],"region":region})

        all_secrets_ids_sm += secret_ids

        client = pacu_main.get_boto3_client('ssm', region)

        response = None
        while response is None:
            try:
                response = client.describe_parameters()
            except ClientError as error:
                code = error.response['Error']['Code']
                print('FAILURE: ')
                if code == 'UnauthorizedOperation':
                    print('  Access denied to DescribeParameters.')
                else:
                    print(' ' + code)
                print('    Could not list parameters... Exiting')
                return None
            
            for param in response["Parameters"]:
                secrets_ssm.append({"name":param["Name"],"type":param["Type"],"region":region})

            
        all_secrets_ids_ssm += secrets_ssm

    for sec in all_secrets_ids_sm:
        secret_values = []
        client = pacu_main.get_boto3_client('secretsmanager',sec["region"])

        response = None
        while response is None:
            try:
                response = client.get_secret_value(
                    SecretId=sec["name"]
                )
            except ClientError as error:
                code = error.response['Error']['Code']
                print('FAILURE: ')
                if code == 'UnauthorizedOperation':
                    print('  Access denied to GetSecretsValue.')
                else:
                    print(' ' + code)
                print('    Could not get secrets value... Exiting')
                return None

            with open('./sessions/{}/downloads/secrets/secrets_manager/secrets.txt'.format(session.name),'a') as f:
                f.write("{}:{}\n".format(sec["name"], response["SecretString"]))

    for param in all_secrets_ids_ssm:
        client = pacu_main.get_boto3_client('ssm',sec["region"])

        response = None
        while response is None:
            if param["type"] != "SecureString":
                try:
                    response = client.get_parameter(
                        Name=param["name"]
                    )
                except ClientError as error:
                    code = error.response['Error']['Code']
                    print('FAILURE: ')
                    if code == 'UnauthorizedOperation':
                        print('  Access denied to GetParameter.')
                    else:
                        print(' ' + code)
                    print('    Could not get parameter value... Exiting')
                    return None

            else:
                try:
                    response = client.get_parameter(
                        Name=param["name"],
                        WithDecryption=True
                    )
                except ClientError as error:
                    code = error.response['Error']['Code']
                    print('FAILURE: ')
                    if code == 'UnauthorizedOperation':
                        print('  Access denied to GetParameter.')
                    else:
                        print(' ' + code)
                    print('    Could not get parameter value... Exiting')
                    return None
            
            with open('./sessions/{}/downloads/secrets/parameter_store/parameters.txt'.format(session.name),'a') as f:
                f.write("{}:{}\n".format(param["name"], response["Parameter"]["Value"]))


    summary_data["SecretsManager"] = len(all_secrets_ids_sm)
    summary_data["ParameterStore"] = len(all_secrets_ids_ssm)

    # Make sure your main function returns whatever data you need to construct
    # a module summary string.
    return summary_data


# The summary function will be called by Pacu after running main, and will be
# passed the data returned from main. It should return a single string
# containing a curated summary of every significant thing that the module did,
# whether successful or not; or None if the module exited early and made no
# changes that warrant a summary being displayed. The data parameter can
# contain whatever data is needed in any structure desired. A length limit of
# 1000 characters is enforced on strings returned by module summary functions.
def summary(data, pacu_main):
    output = "    {} Secret(s) were found in AWS secretsmanager\n    {} Parameter(s) were found in AWS Systems Manager Parameter Store".format(data["SecretsManager"],data["ParameterStore"])
    output += "    \n    Check ./sessions/<session name>/downloads/secrets/ to get the values"
    return output