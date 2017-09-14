void configure_git(){
  sh """/bin/bash -xe
    git config --global user.email "rpc-jenkins-svc@github.com"
    git config --global user.name "rpc.jenkins.cit.rackspace.net"
  """
}

void clone(String repo_url){
  print "Cloning ${repo_url} to ./repo"
  // using sh to clone so the ssh agent creds can be used.
  sshagent (credentials:['rpc-jenkins-svc-github-ssh-key']){
    sh """/bin/bash -xe
      mkdir -p ~/.ssh
      ssh-keyscan github.com >> ~/.ssh/known_hosts
      git clone "${repo_url}" repo
    """
  }
}

void tag(String version, String ref){
  print "Tagging ${version} at ${ref}"
  sshagent (credentials:['rpc-jenkins-svc-github-ssh-key']){
    sh """/bin/bash -xe
      cd repo
      mkdir -p ~/.ssh
      ssh-keyscan github.com >> ~/.ssh/known_hosts
      git fetch --all --tags
      git tag -a -m \"$version\" \"$version\" origin/$ref
      git push --tags origin
    """
  }
}

void reset_rc_branch(String repo, String mainline, String rc){
  print "Resetting ${rc} to head of ${mainline}"
  sshagent (credentials:['rpc-jenkins-svc-github-ssh-key']){
    sh """/bin/bash -xe
      cd repo
      mkdir -p ~/.ssh
      ssh-keyscan github.com >> ~/.ssh/known_hosts
      git fetch --all --tags
      git checkout -b ${rc} || git checkout ${rc}
      git reset --hard origin/${mainline}
      git push -f origin ${rc}:${rc}
    """
  }
}

// run a script, and propose any changes the script made as a PR
void branch_update_script(String script, // script to run
                          String next_vesion, // version we are preparing for
                          String mainline, // branch PR should target
                          String release_stage, // stage of the process
                                               // (eg pre/post rc branch cut)
                          String repo,
                          String org
                          ){
  if (!(fileExists(script))){
    print "RC Branch preparation script ${script} not found" \
          + ", skipping branch preparation."
    return
  }

  String pr_source="${release_stage}_${next_version}"

  sh """#!/bin/bash -xe
    rm -f pr_required
    cd repo
    git checkout -b ${pr_source} || git checkout ${pr_source}
    git reset --hard ${mainline}
    git clean -df
    /bin/bash -xe ${script}
    if [[ -z "\$(git status -s)" ]]; then
      echo "Repo is clean, prep script made no changes to comitted"
    else
      echo "Repo is dirty, proposing changes"
      git commit -a -m "${pr_source}"
      git push origin ${pr_source}:${pr_source}
      touch ../pr_required
    fi
  """
  if(fileExists("pr_required")){
    title=pr_source
    body="PR Proposed by Jenkins Job: ${env.BUILD_URL}"
    github.create_pr(repo, org, source_branch, target_branch, title, body)
  }
}

return this
