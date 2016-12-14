from __future__ import unicode_literals

import logging

from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from nodeconductor.structure.models import ProjectRole
from nodeconductor.users import models


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.users.cancel_expired_invitations')
def cancel_expired_invitations(invitations=None):
    """
    Invitation lifetime must be specified in NodeConductor settings with parameter
    "INVITATION_LIFETIME". If invitation creation time is less than expiration time, the invitation will set as expired.
    """
    expiration_date = timezone.now() - settings.NODECONDUCTOR['INVITATION_LIFETIME']
    if not invitations:
        invitations = models.Invitation.objects.filter(state=models.Invitation.State.PENDING)
    invitations = invitations.filter(created__lte=expiration_date)
    invitations.update(state=models.Invitation.State.EXPIRED)


@shared_task(name='nodeconductor.users.send_invitation')
def send_invitation(invitation_uuid, sender_name):
    invitation = models.Invitation.objects.get(uuid=invitation_uuid)

    if invitation.project_role is not None:
        context = dict(type='project', name=invitation.project_role.project.name)
        role_prefix = 'project' if invitation.project_role.role_type == ProjectRole.MANAGER else 'system'
        context['role'] = '%s %s' % (role_prefix, invitation.project_role.get_role_type_display())

    else:
        context = dict(
            type='organization',
            name=invitation.customer_role.customer.name,
            role=invitation.customer_role.get_role_type_display()
        )

    context['sender'] = sender_name
    context['link'] = invitation.link_template.format(uuid=invitation_uuid)

    subject = render_to_string('users/invitation_subject.txt', context)
    text_message = render_to_string('users/invitation_message.txt', context)
    html_message = render_to_string('users/invitation_message.html', context)

    logger.debug('About to send invitation to {email} to join {name} {type} as {role}'.format(
        email=invitation.email, **context))
    try:
        send_mail(subject, text_message, settings.DEFAULT_FROM_EMAIL, [invitation.email], html_message=html_message)
    except SMTPException as e:
        invitation.error_message = str(e)
        invitation.save(update_fields=['error_message'])
        raise
