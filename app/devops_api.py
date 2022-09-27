import requests
import json
from dateutil import parser


def get_pipeline_data(devops_org_name, devops_project_name, token):
    data = ""
    pipelines = []
    format = "%Y-%m-%d %H:%M:%S"

    devops_data = requests.get(  # Use token to call downstream service
        f'https://dev.azure.com/{devops_org_name}/{devops_project_name}/_apis/build/builds?queryOrder=queueTimeDescending&maxBuildsPerDefinition=1',
        headers={'Authorization': 'Bearer ' + token['access_token']},
    )
    data = json.loads(devops_data.text)

    if 'value' in data:
        i = 1
        for p in data['value']:
            i += 1
            pipeline = {'name': p['definition']['name'], 'status': p['status'], 'id': p['definition']['id'],
                        'rowid': f'rowid-{i}'}
            if 'result' in p:
                pipeline['result'] = p['result']
            else:
                pipeline['result'] = ""
            if 'finishTime' in p:
                date_string = parser.parse(p['finishTime'])
                date_string = date_string.strftime(format)
                pipeline['finishTime'] = date_string
            else:
                pipeline['finishTime'] = ""
            pipelines.append(pipeline)

    return pipelines


def run_pipeline(devops_org_name, devops_project_name, id, token):
    run_data = {"stagesToSkip": [], "resources": {"repositories": {"self": {"refName": "refs/heads/main"}}},
                "variables": {}}
    json_data = json.dumps(run_data)

    devops_run = requests.post(
        f'https://dev.azure.com/{devops_org_name}/{devops_project_name}/_apis/pipelines/{id}/runs?api-version=5.1-preview.1',
        headers={'Authorization': 'Bearer ' + token['access_token'], 'content-type': 'application/json'}, data=json_data
    )
