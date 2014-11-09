from __future__ import unicode_literals

import logging

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from nodeconductor.cloud.backend import CloudBackendError
from nodeconductor.core.models import (
    DescribableMixin, SshPublicKey, SynchronizableMixin, SynchronizationStates, UuidMixin,
)
from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import filter_queryset_for_user


logger = logging.getLogger(__name__)


def validate_known_keystone_urls(value):
    from nodeconductor.cloud.backend.openstack import OpenStackBackend
    backend = OpenStackBackend()
    try:
        backend.get_credentials(value)
    except CloudBackendError:
        raise ValidationError('%s is not a known OpenStack deployment.' % value)


@python_2_unicode_compatible
class Cloud(UuidMixin, SynchronizableMixin, models.Model):
    """
    A cloud instance information.

    Represents parameters set that are necessary to connect to a particular cloud,
    such as connection endpoints, credentials, etc.
    """
    class Meta(object):
        unique_together = (
            ('customer', 'name'),
        )

    class Permissions(object):
        customer_path = 'customer'
        project_path = 'projects'
        project_group_path = 'customer__projects__project_groups'

    name = models.CharField(max_length=100)
    customer = models.ForeignKey(structure_models.Customer, related_name='clouds')
    projects = models.ManyToManyField(
        structure_models.Project, related_name='clouds', through='CloudProjectMembership')

    # OpenStack backend specific fields
    auth_url = models.CharField(max_length=200, help_text='Keystone endpoint url',
                                validators=[URLValidator(), validate_known_keystone_urls])

    def get_backend(self):
        # TODO: Support different clouds instead of hard-coding
        # Importing here to avoid circular imports hell
        from nodeconductor.cloud.backend.openstack import OpenStackBackend
        return OpenStackBackend()

    def __str__(self):
        return self.name

    def sync(self):
        """
        Synchronizes nodeconductor cloud with real cloud account
        """


def get_related_clouds(obj, request):
    related_clouds = obj.clouds.all()

    try:
        user = request.user
        related_clouds = filter_queryset_for_user(related_clouds, user)
    except AttributeError:
        pass

    from nodeconductor.cloud.serializers import BasicCloudSerializer
    serializer_instance = BasicCloudSerializer(related_clouds, context={'request': request})

    return serializer_instance.data


# These hacks are necessary for Django <1.7
# TODO: Refactor to use app.ready() after transition to Django 1.7
# See https://docs.djangoproject.com/en/1.7/topics/signals/#connecting-receiver-functions

# @receiver(pre_serializer_fields, sender=CustomerSerializer)
@receiver(pre_serializer_fields)
def add_clouds_to_related_model(sender, fields, **kwargs):
    # Note: importing here to avoid circular import hell
    from nodeconductor.structure.serializers import CustomerSerializer, ProjectSerializer

    if not sender in (CustomerSerializer, ProjectSerializer):
        return

    fields['clouds'] = UnboundSerializerMethodField(get_related_clouds)


@python_2_unicode_compatible
class CloudProjectMembership(SynchronizableMixin, models.Model):
    """
    This model represents many to many relationships between project and cloud
    """

    cloud = models.ForeignKey(Cloud)
    project = models.ForeignKey(structure_models.Project)

    # OpenStack backend specific fields
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    tenant_id = models.CharField(max_length=64, blank=True)

    class Meta(object):
        unique_together = ('cloud', 'tenant_id')

    class Permissions(object):
        customer_path = 'cloud__customer'
        project_path = 'project'
        project_group_path = 'project__project_groups'

    def __str__(self):
        return '{0} | {1}'.format(self.cloud.name, self.project.name)


@receiver(signals.post_save, sender=SshPublicKey)
def propagate_new_key(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    # TODO: Schedule propagation task(s)? instead of doing it inline
    # XXX: Come up with a solid strategy which projects are to be affected
    cloud_project_memberships = filter_queryset_for_user(
        CloudProjectMembership.objects.filter(state=SynchronizationStates.IN_SYNC), instance.user)

    for membership in cloud_project_memberships.iterator():
        backend = membership.cloud.get_backend()
        backend.push_ssh_public_key(membership, instance)


@python_2_unicode_compatible
class Flavor(UuidMixin, models.Model):
    """
    A preset of computing resources.
    """

    class Permissions(object):
        customer_path = 'cloud__projects__customer'
        project_path = 'cloud__projects'
        project_group_path = 'cloud__projects__project_groups'

    name = models.CharField(max_length=100)
    cloud = models.ForeignKey(Cloud, related_name='flavors')

    cores = models.PositiveSmallIntegerField(help_text=_('Number of cores in a VM'))
    ram = models.FloatField(help_text=_('Memory size in GB'))
    disk = models.FloatField(help_text=_('Root disk size in GB'))

    def __str__(self):
        return self.name


# These should come from backend properly
@receiver(signals.post_save, sender=Cloud)
def create_dummy_flavors(sender, instance=None, created=False, **kwargs):
    if created:
        instance.flavors.create(
            name='Weak & Small',
            cores=2,
            ram=2.0,
            disk=10.0,
        )
        instance.flavors.create(
            name='Powerful & Small',
            cores=16,
            ram=2.0,
            disk=10.0,
        )
        instance.flavors.create(
            name='Weak & Large',
            cores=2,
            ram=32.0,
            disk=100.0,
        )
        instance.flavors.create(
            name='Powerful & Large',
            cores=16,
            ram=32.0,
            disk=100.0,
        )


class SecurityGroup(UuidMixin, DescribableMixin, models.Model):

    class Permissions(object):
        customer_path = 'cloud_project_membership__project__customer'
        project_path = 'cloud_project_membership__project'
        project_group_path = 'cloud_project_membership__project__project_groups'

    """
    This class contains openstack security groups.
    """
    cloud_project_membership = models.ForeignKey(CloudProjectMembership, related_name='security_groups')
    name = models.CharField(max_length=127)

    # openstack specific
    os_security_group_id = models.CharField(max_length='128', blank=True,
                                            help_text='Reference to a SecurityGroup in a remote cloud')

    def __str__(self):
        return self.name


class SecurityGroupRule(models.Model):

    tcp = 'tcp'
    udp = 'udp'

    PROTOCOL_CHOICES = (
        (tcp, _('tcp')),
        (udp, _('udp')),
    )

    group = models.ForeignKey(SecurityGroup, related_name='rules')

    protocol = models.CharField(max_length=3, choices=PROTOCOL_CHOICES)
    from_port = models.IntegerField(validators=[MaxValueValidator(65535),
                                                MinValueValidator(1)])
    to_port = models.IntegerField(validators=[MaxValueValidator(65535),
                                              MinValueValidator(1)])
    ip_range = models.IPAddressField()
    netmask = models.SmallIntegerField(null=False)

    # openstack specific
    os_security_group_rule_id = models.CharField(max_length='128', blank=True)

    def __str__(self):
        return '%s (%s): %s/%s (%s -> %s)' % \
               (self.group, self.protocol, self.ip_range, self.netmask, self.from_port, self.to_port)


# TODO: make the defaults configurable
@receiver(signals.post_save, sender=CloudProjectMembership)
def create_dummy_security_groups(sender, instance=None, created=False, **kwargs):
    if created:
        # group http
        http_group = instance.security_groups.create(
            name='http',
            description='Security group for web servers'
        )
        http_group.rules.create(
            protocol='tcp',
            from_port=80,
            to_port=80,
            ip_range='0.0.0.0',
            netmask=0
        )


class IpMapping(UuidMixin, models.Model):
    class Permissions(object):
        project_path = 'project'
        customer_path = 'project__customer'
        project_group_path = 'project__project_groups'

    public_ip = models.GenericIPAddressField(null=False)
    private_ip = models.GenericIPAddressField(null=False)
    project = models.ForeignKey(structure_models.Project, related_name='ip_mappings')
