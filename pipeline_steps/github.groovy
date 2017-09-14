
def create_issue(
    String tag,
    String link,
    String label="jenkins-build-failure",
    String org="rcbops",
    String repo="u-suk-dev"){
  withCredentials([
    string(
      credentialsId: 'rpc-jenkins-svc-github-pat',
      variable: 'pat'
    )
  ]){
    sh """#!/bin/bash -xe
      cd ${env.WORKSPACE}
      set +x; . .venv/bin/activate; set -x
      python rpc-gating/scripts/ghutils.py\
        --org '$org'\
        --repo '$repo'\
        --pat '$pat'\
        create_issue\
        --tag '$tag'\
        --link '$link'\
        --label '$label'
    """
  }
}

/**
 * Add issue link to pull request description
 *
 * Pull request commit messages include the issue key for an issue on Jira.
 * Update the description of the current GitHub pull request with a link to
 * the Jira issue.
 */
void add_issue_url_to_pr(String upstream="upstream"){
  List org_repo = env.ghprbGhRepository.split("/")
  String org = org_repo[0]
  String repo = org_repo[1]

  Integer pull_request_number = env.ghprbPullId as Integer

  dir(repo) {
    git branch: env.ghprbSourceBranch, url: env.ghprbAuthorRepoGitUrl
    sh """#!/bin/bash
      set -x
      git remote add ${upstream} https://github.com/${org}/${repo}.git
      git remote update
    """
  }
  String issue_key = common.get_jira_issue_key(repo)

  withCredentials([
    string(
      credentialsId: 'rpc-jenkins-svc-github-pat',
      variable: 'pat'
    )
  ]){
    sh """#!/bin/bash -xe
      cd $env.WORKSPACE
      set +x; . .venv/bin/activate; set -x
      python rpc-gating/scripts/ghutils.py\
        --org '$org'\
        --repo '$repo'\
        --pat '$pat'\
        add_issue_url_to_pr\
        --pull-request-number '$pull_request_number'\
        --issue-key '$issue_key'
    """
  }
  return null
}

void create_pr(repo, org, source_branch, target_branch, title, body){
  withCredentials([
    string(
      credentialsId: 'rpc-jenkins-svc-github-pat',
      variable: 'pat'
    )
  ]){
    sh """#!/bin/bash -xe
      cd $env.WORKSPACE
      set +x; . .venv/bin/activate; set -x
      python rpc-gating/scripts/ghutils.py\
        --org '$org' \
        --repo '$repo' \
        --pat '$pat' \
        create_pr \
        --source-branch ${source-branch} \
        --target-branch ${target-branch} \
        --title "${title}" \
        --body "${body}"
    """
  }
}


return this;
