import os
import json
import yaml
import requests

from deepdiff import DeepDiff

# Path to folder containing the first backup
backup_path_one = os.environ.get('BACKUP_PATH_ONE')
# Path to folder containing the second backup
backup_path_two = os.environ.get('BACKUP_PATH_TWO')
# TODO: set the correct frontend
frontend = "https://instance.azurewebsites.net"

REPO_DIR = os.environ.get('REPO_DIR')

backup_files_one = []
backup_files_two = []
one_intent_backup_files = []
two_intent_backup_files = []
exclude = set(['Management Intents', 'Applications', 'Apple', 'Apple VPP Tokens', 'Managed Google Play'])
diff_files = []
intent_diff_files = []
diffs = 0


def update_frontend(frontend, data):
    """
    This function updates the frontend with the number of configurations, diff count backup stream and update stream.

    :param frontend: The frontend to update
    :param data: The data to update the frontend with
    """
    API_KEY = os.environ.get("API_KEY")

    if not API_KEY:
        raise Exception("API_KEY environment variable is not set")

    else:
        headers = {'X-API-Key': API_KEY}
        response = requests.post(frontend, json=data, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Error updating frontend, {response.text}")

if os.path.exists(backup_path_one) == True:
    for root, dirs, files in os.walk(backup_path_one, topdown=True):
        dirs[:] = [d for d in dirs if d not in exclude]
        for file in files:
            if file.endswith('.yaml') or file.endswith('.json'):
                data = {'path':root,'name':file}
                backup_files_one.append(data)

if os.path.exists(backup_path_two) == True:
    for root, dirs, files in os.walk(backup_path_two, topdown=True):
        dirs[:] = [d for d in dirs if d not in exclude]
        for file in files:
            if file.endswith('.yaml') or file.endswith('.json'):
                data = {'path':root,'name':file}
                backup_files_two.append(data)

for file in backup_files_one:
    for f in backup_files_two:
        if file['name'] == f['name']:
            s = {'one':f"{file['path']}/{file['name']}",'two':f"{f['path']}/{f['name']}"}
            diff_files.append(s)

if os.path.exists(f'{backup_path_one}/Management Intents') == True:
    for root, dirs, files in os.walk(f'{backup_path_one}/Management Intents', topdown=True):
        for file in files:
            if file.endswith('.yaml') or file.endswith('.json'):
                data = {'path':root,'name':file}
                one_intent_backup_files.append(data)

if os.path.exists(f'{backup_path_two}/Management Intents') == True:
    for root, dirs, files in os.walk(f'{backup_path_two}/Management Intents', topdown=True):
        for file in files:
            if file.endswith('.yaml') or file.endswith('.json'):
                data = {'path':root,'name':file}
                two_intent_backup_files.append(data)

for file in one_intent_backup_files:
    for f in two_intent_backup_files:
        if file['name'] == f['name'] and file['path'].split('/')[-1] == f['path'].split('/')[-1]:
            s = {'one':f"{file['path']}/{file['name']}",'two':f"{f['path']}/{f['name']}"}
            intent_diff_files.append(s)

for file in diff_files:

    with open(file['one']) as f:
        if file['one'].endswith('.yaml'):
            data = json.dumps(yaml.safe_load(f))
            one = json.loads(data)
        else:
            one = json.load(f)

    with open(file['two']) as f:
        if file['two'].endswith('.yaml'):
            data = json.dumps(yaml.safe_load(f))
            two = json.loads(data)
        else:
            two = json.load(f)

    diff = DeepDiff(two, one, ignore_order=True).get('values_changed')
    if diff:
        diffs += 1

for file in intent_diff_files:

    with open(file['one']) as f:
        if file['one'].endswith('.yaml'):
            data = json.dumps(yaml.safe_load(f))
            one = json.loads(data)
        else:
            one = json.load(f)

    with open(file['two']) as f:
        if file['two'].endswith('.yaml'):
            data = json.dumps(yaml.safe_load(f))
            two = json.loads(data)
        else:
            two = json.load(f)

    for two_setting, one_setting in zip(two['settingsDelta'], one['settingsDelta']):

        diff = DeepDiff(two_setting, one_setting, ignore_order=True).get('values_changed')
        if diff:
            diffs += 1

body = {"type": "diff_count", "diff_count": diffs}
update_frontend(f"{frontend}/api/overview/summary", body)