library "rpc-gating@${RPC_GATING_BRANCH}"
common.shared_slave(){
  stage("Configure Git"){
    common.configure_git()
  }
  stage("Release"){
    withCredentials([
      string(
        credentialsId: 'rpc-jenkins-svc-github-pat',
        variable: 'PAT'
      )
    ]){
      sh """#!/bin/bash -xe
        set +x; . .venv/bin/activate; set -x
        ${env.COMMAND}
      """
    }
  }
}
