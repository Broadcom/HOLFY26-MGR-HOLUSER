import time
import gitlab
import sys
import json
import os
import functions.file_functions as file

#Constants
debug = False

ACCESS_LEVELS = {
    "guest": gitlab.const.AccessLevel.GUEST,
    "reporter": gitlab.const.AccessLevel.REPORTER,
    "developer": gitlab.const.AccessLevel.DEVELOPER,
    "maintainer": gitlab.const.AccessLevel.MAINTAINER,
}


# Function Definitions

def get_project_id(url, token, projectName, groupName=None):
    print(f"INFO: Getting project ID for '{projectName}'")  
    if debug:
        print(f"IN: get_project_id")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        projects = gl.projects.list(search=projectName, get_all=False)

        if len(projects) == 0:
            print(f"ERROR: Project '{projectName}' not found")
            return None
        elif len(projects) == 1:
            return projects[0].id
        else:
            print(f"WARN: There are '{len(projects)}' projects found with name '{projectName}'. Returning the first one.")
            return projects[0].id

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get project: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: get_project_id")
        
def new_project(url, token, projectName, groupId=None, visibility='private'):

    print(f"TASK: Creating project '{projectName}' with visibility '{visibility}'")

    if debug:
        print(f"IN: new_project")
    try:
    
        projectName = projectName.replace(' ', '-').strip()

        project_data = {
            'name': projectName,
            'visibility': visibility,
            'namespace_id': groupId if groupId else None,
        }

        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()
        
        project = gl.projects.create(project_data)

        print(f"INFO: Project Created: {project.web_url}")
    
        return project.id
    
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabCreateError:
        print(f"ERROR: Failed to create project: {e.error_message}")
    except Exception as e:
        if e is not None:
            print (f"ERROR: Unexpected Error: {str(e)}")
        else:
            print("An unexpected error occurred, but no details were provided.")
    finally:
        if debug:
            print(f"OUT: new_project")

def get_group_id_from_project(url, token, projectName):

    print(f"INFO: Getting group ID from project '{projectName}'")

    if debug:
        print(f"IN: get_group_id_from_project")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        project = get_project(url, token, projectName)

        print(project.namespace[0].id)
        return project.group_id

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get project: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: get_group_id_from_project")

def new_group(url, token, groupName, visibility, description=None):

    print(f"TASK: Creating group '{groupName}' with visibility '{visibility}'")

    if debug:
        print(f"IN: new_group")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        path = groupName.replace(' ', '-').strip()
        
        group_data = {
            'name': groupName,
            'path': path,
            'visibility': visibility,
            'description': description
        }

        group = gl.groups.create(group_data)
        
        print(f"INFO: Group Created: {group.web_url}")
        return group.id
    
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabCreateError as e:
        print(f"ERROR: Failed to create group: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: new_group")

def get_group_id(url, token, groupName):

    print(f"INFO: Getting group ID for '{groupName}'")

    if debug:
        print(f"IN: get_group_id")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        groups = gl.groups.list(search=groupName, get_all=False)

        if len(groups) == 0:
            print(f"ERROR: Group '{groupName}' not found")
            return None
        else:
            for group in groups:
                if group.name == groupName:
                    print(f"INFO: Found group '{groupName}' with ID: {group.id}")
                    return group.id        
            
            return None

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get group: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: get_group_id")

def get_group(url, token, groupName):

    print(f"INFO: Getting group for '{groupName}'")

    if debug:
        print(f"IN: get_group_id")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        return gl.groups.list(search=groupName, get_all=False)[0]
    
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get group: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug: 
            print(f"OUT: get_group_id")

def get_group_name(url, token, groupId):
    
    print(f"INFO: Getting group name for ID '{groupId}'")

    if debug:
        print(f"IN: get_group_name")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        return gl.groups.list(search=groupId, get_all=False)[0].name

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get group: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: get_group_name")

def get_user_id(url, token, userName):

    print(f"INFO: Getting User ID for '{userName}'")

    if debug:
        print(f"IN: get_user_id")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        users = gl.users.list(username=userName, get_all=False)
        if len(users) == 0:
            print(f"ERROR: User '{userName}' not found")
            return None
        elif len(users) == 1:
            return users[0].id
        else:
            print(f"WARN: There are {len(users)} users found with username '{userName}'. Returning the first ID.")
            return users[0].id

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get user: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: get_user_id")

def add_project_member(url, token, user, projectName, accessLevel, groupName=None):

    print(f"TASK: Adding user '{user}' with access level '{accessLevel}' to project '{projectName}'")

    if debug:
        print(f"IN: add_project_member")
       
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        userId = get_user_id(url, token, user)
  
        project = get_project(url, token, projectName, groupName)

        print(f"TASK: Adding User '{user}' (UserId:'{userId}') to project '{projectName}' with access level '{accessLevel}'")

        if userId and project:
            user_data = {
                'user_id': userId,
                'access_level': accessLevel,
            }

            project.members.create(user_data)


    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get group: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:            
        if debug:
            print(f"OUT: add_project_member")

def is_project_member(url, token, username, projectName, groupName=None):

    print(f"INFO: Checking if user '{username}' is a member of project '{projectName}'")

    if debug:
        print(f"IN: is_project_member")

    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        project = get_project(url, token, projectName, groupName)
        groupId = get_group_id_from_project(url, token, projectName)

        if groupId:
            group = get_group(url, token, groupId)
            members = group.members_all.list(get_all=True)
        else:
            members = project.members_all.list(get_all=True)

        for member in members:
            if member.username == username:
                print(f"INFO: User '{username}' is a member of project '{projectName}'")
                return True
        
        print(f"INFO: User '{username}' is NOT a member of project '{projectName}'")
        return False

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get project: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")

def delete_project(url, token, projectName):

    print(f"TASK: Deleting project '{projectName}'")
    
    if debug:
        print(f"IN: delete_project")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        project = gl.projects.get(projectName)
        project.delete()
        print(f"INFO: Project '{projectName}' deleted successfully.")
    
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get project: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: delete_project")

def delete_group(url, token, groupName):
    
    print(f"TASK: Deleting group '{groupName}'")

    if debug:
        print(f"IN: delete_group")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        group = gl.groups.get(groupName)
        group.delete()
        print(f"INFO: Group '{groupName}' deleted successfully.")
    
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get group: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: delete_group")

def list_projects(url, token):
    
    print(f"INFO: Listing all projects")

    if debug:
        print(f"IN: list_projects")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        projects = gl.projects.list(all=True)
        if len(projects) > 0:
            for project in projects:
                print(f"INFO: Project ID: {project.id}, Name: {project.name}, Web URL: {project.web_url}")
        else:
            print("INFO: No projects found.")

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get projects: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: list_projects")
def list_users(url, token):

    print(f"INFO: Listing all users")

    if debug:
        print(f"IN: list_users")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        users = gl.users.list(all=True)
        if len(users) > 0:
            for user in users:
                print(f"INFO: User ID: {user.id}, Username: {user.username}, Name: {user.name}")
        else:
            print("INFO: No users found.")

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get users: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: list_users")

def list_groups(url, token):
    
    print(f"INFO: Listing all groups")

    if debug:
        print(f"IN: list_groups")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        groups = gl.groups.list(all=True)
        if len(groups) > 0:
            for group in groups:
                print(f"INFO: Group ID: {group.id}, Name: {group.name}, Path: {group.path}")
        else:
            print("INFO: No groups found.")

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get groups: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: list_groups")

def get_project(url, token, projectName, groupName=None):

    print(f"INFO: Getting project '{projectName}'")

    if debug:
        print(f"IN: get_project")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        if groupName:
            print(f"INFO: Searching for project '{projectName}' in group '{groupName}'")
            return gl.projects.get(f"{groupName.replace(' ', '-').strip()}/{projectName}")
        else:
            print(f"INFO: Searching for project '{projectName}'")
            return gl.projects.get(get_project_id(url, token, projectName))

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get project: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: get_project")

def is_project_branch(url, token, projectName, groupName, branchName):
    print(f"INFO: Checking if branch '{branchName}' exists in project '{projectName}'")
    if debug:
        print(f"IN: is_project_branch")
        
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        project = get_project(url, token, projectName, groupName)
        branches = project.branches.list()
        
        for branch in branches:
            if branch.name == branchName:
                print(f"INFO: Branch '{branchName}' found in project '{projectName}'")
                return True
        print(f"INFO: Branch '{branchName}' not found in project '{projectName}'")
        return False
        
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get project: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: is_project_branch")

def new_branch(url, token, projectName, groupName, branchName, sourceBranch='main', protected=False):

    print(f"TASK: Creating branch '{branchName}' from '{sourceBranch}' in project '{projectName}'")

    if debug:
        print(f"IN: new_branch")
    try:

        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        project = get_project(url, token, projectName, groupName)

        if not protected:
            branch_data = {
                'branch': branchName,
                'ref': sourceBranch,
            }
            
            branch = project.branches.create(branch_data)
            print(f"INFO: Branch '{branchName}' created from '{sourceBranch}' in project '{projectName}'")
        else:
            branch_data = {
                'name': branchName,
                'merge_access_level': ACCESS_LEVELS['developer'],
                'push_access_level': ACCESS_LEVELS['developer'],
            }
            branch = project.protectedbranches.create(branch_data)
    
            print(f"INFO: Protected Branch '{branchName}' created from '{sourceBranch}' in project '{projectName}'")

    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get project: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: new_branch")
def get_branch(url, token, projectName, groupName, branchName):

    print(f"INFO: Getting branch '{branchName}' from project '{projectName}'")

    if debug:
        print(f"IN: get_branch")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        project = get_project(url, token, projectName, groupName)
        branch = project.branches.get(branchName)

        return branch
    
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get branch: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"OUT: get_branch")

def new_commit(url, token, projectName, groupName, branchName, commitMessage, commitAction, filePath, fileContent):
    print(f"TASK: Creating commit in branch '{branchName}' of project '{projectName}'")
    if debug:
        print(f"IN: new_commit")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()

        project = get_project(url, token, projectName, groupName)
        
        commit_data = {
            'branch': branchName,
            'commit_message': commitMessage,
            'actions': [
                {
                    'action': commitAction,
                    'file_path': filePath,
                    'content': fileContent
                }
            ]
        }
    
        print(f"INFO: Commit created in branch '{branchName}' of project '{projectName}'")
        
        commit = project.commits.create(commit_data)
    
        if commit:
            print(f"INFO: Commit ID: {commit.id}")
            return commit.id
    except gitlab.exceptions.GitlabAuthenticationError:
        print(f"ERROR: Authentication failed. Check your token")
    except gitlab.exceptions.GitlabGetError as e:
        print(f"ERROR: Failed to get project: {e.error_message}")
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")

    finally:
        if debug:
            print(f"OUT: new_commit")

        else:
            print("ERROR: Commit creation failed.")
            return None

def new_readme(url, token, projectName, groupName, branchName, rootFolder):
    print(f"TASK: Creating README file for project '{projectName}' in branch '{branchName}'")
    if debug:
        print(f"IN: new_readme")
    try:
        gl = gitlab.Gitlab(url, private_token=token)
        gl.auth()
    
        content ="""
# Welcome to the Git Repo for {project}

## Purpose

This Readme markdown file is programmatically created in the following location within {github}.

* Group: {group}
* Project: {project}
* Branch: {branch}

This is meant as a demonstration to enable the Management Pack Builder to show commits within VCF Operations.
        """.format(project=projectName, github=url, group=groupName, branch=branchName)

        file.createFolder(f"{rootFolder}/{projectName}")
        filePath = f"{rootFolder}/{projectName}/README.md"
        file.createFile(filePath, content)

        return filePath

    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
    finally:
        if debug:
            print(f"INFO: new_readme")

def get_access_level(access_level):
    print(f"INFO: Getting access level for '{access_level}'")
    if debug:
        print(f"IN: get_access_level")
    try:
        return ACCESS_LEVELS.get(access_level, gitlab.const.AccessLevel.DEVELOPER)
    
    except Exception as e:
        print (f"ERROR: Unexpected Error: {str(e)}")
        return gitlab.const.AccessLevel.DEVELOPER
    finally:
        if debug:
            print(f"OUT: get_access_level")
