#!/usr/bin/env python

# This script contains github related utilties for Jenkins.


import click
import git
import github3
import json
import logging

logger = logging.getLogger("ghutils")


@click.group(chain=True)
@click.pass_context
@click.option(
    '--org',
    help='Github Organisation that owns the target repo',
    required=True,
)
@click.option(
    '--repo',
    help='Name of target repo',
    required=True,
)
@click.option(
    '--pat',
    help="Github Personal Access Token",
    envvar="PAT",
    required=True,
)
@click.option(
    '--debug/--no-debug'
)
def cli(ctxt, org, repo, pat, debug):
    level = logging.WARNING
    if debug:
        level = logging.DEBUG
    logging.basicConfig(level=level)
    gh = github3.login(token=pat)
    repo_ = gh.repository(org, repo)
    if not repo_:
        raise ValueError("Failed to connect to repo {o}/{r}".format(
            o=org, r=repo
        ))
    ctxt.obj = repo_


@cli.command()
@click.pass_obj
@click.option('--tag',
              help='Jenkins build tag',
              required=True)
@click.option('--link',
              help='Link to related build in Jenkins UI',
              required=True)
@click.option('--label',
              help="Add label to issue, can be specified multiple times",
              multiple=True,
              required=True)
def create_issue(repo, tag, link, label):
    repo.create_issue(
        title="JBF: {tag}".format(tag=tag),
        body="[link to failing build]({url})".format(url=link),
        labels=label
    )


@cli.command()
@click.pass_obj
@click.option(
    '--pull-request-number',
    help="Pull request to update",
    required=True,
)
@click.option(
    '--issue-key',
    help='Issue being resolved by pull request',
    required=True,
)
def add_issue_url_to_pr(repo, pull_request_number, issue_key):
    jira_url = "https://rpc-openstack.atlassian.net/browse/"
    pull_request = repo.pull_request(pull_request_number)
    current_body = pull_request.body or ""

    issue_text = "Issue: [{key}]({url}{key})".format(
        url=jira_url,
        key=issue_key,
    )

    if issue_text in current_body:
        click.echo(
            "Pull request not updated, it already includes issue reference."
        )
    else:
        if current_body:
            updated_body = "{body}\n\n{issue}".format(
                body=current_body,
                issue=issue_text,
            )
        else:
            updated_body = issue_text

        success = pull_request.update(body=updated_body)
        if success:
            click.echo("Pull request updated with issue reference.")
        else:
            raise Exception("There was a failure updating the pull request.")


def branch_api_request(repo, branch, method, postfix="", data=None):
    """Make Requests to the github branch protection api.

    Not supported by github3.py yet (6th September 2017)
    """
    url = "{branch_url}/protection{postfix}".format(
        branch_url=repo.branches_urlt.expand(branch=branch),
        postfix=postfix
    )
    # Branch protection api is in preview and requires a specific content type
    response = repo._session.request(
        method, url,
        headers={'Accept': 'application/vnd.github.loki-preview+json'},
        data=data)
    return response


@cli.command()
@click.pass_context
@click.option(
    '--mainline',
    required=True,
    help="Mainline branch to cut from"
)
@click.option(
    '--rc',
    help="Release Candidate branch (re)create"
)
def update_rc_branch(ctx, mainline, rc):
    """Update rc branch.

    1. Store branch protection data
    2. Delete rc branch
    3. Create rc branch from head of mainline
    4. Enable branch protection with skeleton or previously stored settings.
    """
    repo = ctx.obj
    try:
        rc = repo.rc_ref
    except AttributeError:
        if not rc:
            raise ValueError("--rc is required for update_rc_branch")
    branch_protection_enabled = False

    # check if branch exists
    if rc in (b.name for b in repo.iter_branches()):
        logger.debug("Branch {} exists".format(rc))
        # rc branch exists
        branch_protection_response = branch_api_request(repo, rc, 'GET')
        if branch_protection_response.status_code == 200:
            # rc branch exists and protection enabled
            logger.debug("Branch {} has protection enabled".format(rc))
            branch_protection_enabled = True
            # disable branch protection
            r = branch_api_request(repo, rc, 'DELETE')
            r.raise_for_status()
            logger.debug("Branch protection disabled")
        elif branch_protection_response.status_code == 404:
            # rc branch exists without protection, so it doesn't need
            # to be disabled
            # TODO: create jira issue about unprotected branch?
            pass
        else:
            # failure retrieving branch protection status
            branch_protection_response.raise_for_status()

        # Delete branch
        r = repo._session.request(
            'DELETE',
            repo.git_refs_urlt.expand(sha="heads/{}".format(rc)))
        r.raise_for_status()
        logger.debug("Branch {} deleted".format(rc))

    mainline_sha = repo.branch(mainline).commit.sha
    logger.debug("Mainline SHA: {}".format(mainline_sha))

    # create rc branch pointing at head of mainline
    repo.create_ref("refs/heads/{}".format(rc), mainline_sha)
    logger.debug("Branch {} created".format(rc))

    # Skeleton branch protection data, used to protect a new branch.
    protection_data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismissal_restrictions": {},
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False
        },
        "restrictions": None
    }

    # Incorporate previous branch protection data if the branch was
    # protected perviously
    if branch_protection_enabled:
        stored_bpd = branch_protection_response.json()
        protection_data.update(stored_bpd)
        # The github api returns enforce_admins as dict, but requires it to
        # be sent as a bool.
        protection_data['enforce_admins'] \
            = stored_bpd['enforce_admins']['enabled']

    # Enable branch protection
    r = branch_api_request(repo, rc, 'PUT',
                           data=json.dumps(protection_data))
    r.raise_for_status()
    logger.debug("Branch Protection enabled for branch {}".format(rc))

    # Ensure the rc branch was not updated to anything else while it was
    # unprotected. Stored mainline_sha is used incase mainline has
    # moved on since the SHA was acquired.
    assert mainline_sha == repo.branch(rc).commit.sha
    logger.debug("rc branch update complete")


@cli.command()
@click.pass_obj
@click.option(
    '--version',
    required=True,
    help="version to release"
)
@click.option(
    '--ref',
    help="Reference to create release from (branch, SHA etc)"
)
@click.option(
    '--body',
    type=click.File('r'),
    help="File containing release message body"
)
def create_release(repo, version, ref, body):
    ctx_obj = click.get_current_context().obj
    # Attempt to read release_notes from context
    # They may have been set by release.generate_release_notes
    try:
        release_notes = ctx_obj.release_notes
    except AttributeError:
        release_notes = body.read()
    try:
        ref = ctx_obj.rc_ref
    except AttributeError:
        if not ref:
            raise ValueError("--ref is required")
    # Store version in context for use in notifications
    ctx_obj.version = version
    # Create a subject for use by notifications
    ctx_obj.release_subject = "Version {v} of {o}/{r} released".format(
        v=version,
        o=repo.owner.login,
        r=repo.name
    )
    try:
        repo.create_release(
            version,            # tag name
            ref,                # tag reference
            version,            # release name
            release_notes       # release body
        )
        print "Release {} created.".format(version)
    except github3.models.GitHubError as e:
        print "Error creating release: {}".format(e)
        if e.code == 422:
            print "Failed to create release, tag already exists?"
            raise SystemExit(5)
        if e.code == 404:
            print "Failed to create release, Jenkins lacks repo perms?"
            raise SystemExit(6)
        else:
            raise e


@cli.command()
@click.option("--url")
@click.option("--ref", help="ref to checkout", default="master")
@click.option("--refspec", help="refspec to fetch",
              default="+refs/heads/*:refs/remotes/origin/* "
                      "+refs/tags/*:refs/tags/*")
def clone(url, ref, refspec):
    ctx_obj = click.get_current_context().obj
    try:
        url = ctx_obj.clone_url
    except AttributeError:
        if not url:
            raise ValueError("URL required, please use --url")
    ctx_obj.rc_ref = ref
    logger.debug("Cloning {url}@{ref}".format(url=url, ref=ref))
    repo = git.Repo.init()
    repo.init()
    try:
        origin = repo.remotes.origin
        origin.set_url(url)
    except Exception as e:
        origin = repo.create_remote('origin', url)
    origin.fetch(refspec.split())
    try:
        getattr(origin.refs, ref).checkout()
    except AttributeError as e:
        print ("Ref {ref} not found in {url}".format(
            ref=ref,
            url=url
        ))
        raise e


if __name__ == "__main__":
    cli()
