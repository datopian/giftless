from .identity import DefaultIdentity, Permission
import requests  
from . import Unauthorized
import getpass
from flask import request
import base64

class GitHubUser(DefaultIdentity):
    def __init__(self, gh_username, user_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = gh_username
        self.id = user_id


def extract_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Basic '):
        raise Unauthorized("Basic auth required")

    encoded_credentials = auth_header.split(' ')[1]
    decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
    username, token = decoded_credentials.split(':', 1)

    return token

def authenticate_request(request):
    
    gh_token = extract_token()

    headers = {'Authorization': f'token {gh_token}'}

    response = requests.get('https://api.github.com/user', headers=headers)
  
    if response.status_code != 200:
        raise Unauthorized("Authentication required: Invalid GitHub token.")
    
    user_data = response.json()
    
    username = user_data.get("login")
    user_id = user_data.get("id")
    path_parts = request.path.split('/')
    owner, repo = path_parts[1], path_parts[2]

    repo_url = f"https://api.github.com/repos/{owner}/{repo}/collaborators/{username}/permission"

    repo_response = requests.get(repo_url, headers=headers)
    if repo_response.status_code != 200:
        raise Unauthorized("Failed to retrieve repository permissions.")

    user = GitHubUser(username, user_id)
    print(user)
    repo_data = repo_response.json()
    permission = repo_data.get("permission")
    print(permission)

    if permission == 'write' or permission == 'admin':
        user.allow(permissions=Permission.all())
    elif permission == 'read':
        user.allow(permissions={Permission.READ, Permission.READ_META})
    else:
        user.deny(permissions=Permission.all())
    
    return user




