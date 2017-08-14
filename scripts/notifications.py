import click
from email.mime.text import MIMEText
import logging
from subprocess import Popen, PIPE


logger = logging.getLogger("notifications")


@click.group()
@click.option("--debug/--no-debug")
def cli(debug):
    level = logging.WARNING
    if debug:
        level = logging.DEBUG
    logging.basicConfig(level=level)


@click.command()
@click.option("--to")
@click.option("--subject")
@click.option("--body")
def mail(to, subject, body):
    ctx_obj = click.get_current_context().obj
    # Try and generate subject from context, this will only
    # work when mail is called as part of release.py
    try:
        subject = ctx_obj.release_subject
    except AttributeError:
        if not subject:
            raise ValueError("Subject must be supplied via --subject")
    try:
        body = ctx_obj.release_notes
    except AttributeError:
        if not body:
            raise ValueError("Body must be supplied via --body")
    msg = MIMEText(body)
    msg["From"] = "RPC-Jenkins@rackspace.com"
    msg["To"] = to
    msg["Subject"] = subject
    logger.debug("Sending notification mail To: {to} Subject:{s}".format(
        to=to, s=subject
    ))
    p = Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
    p.communicate(msg.as_string())


cli.add_command(mail)


if __name__ == "__main__":
    cli()
