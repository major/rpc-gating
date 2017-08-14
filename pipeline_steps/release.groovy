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

void update_rc_branch(String repo, String mainline, String rc){
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

return this
