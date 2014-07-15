from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class InstanceProvisioningTest(test.APISimpleTestCase):
    def setUp(self):
        self.instance_list_url = reverse('instance-list')

        self.template = factories.TemplateFactory()
        self.flavor = cloud_factories.FlavorFactory()

        # XXX: This is temporary stub before proper permissions are enforced
        self.user = structure_factories.UserFactory()
        self.client.force_authenticate(user=self.user)

    # Assertions
    def assert_field_required(self, field_name):
        data = self.get_valid_data()
        del data[field_name]
        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({field_name: ['This field is required.']}, response.data)

    def assert_field_non_empty(self, field_name, empty_value=''):
        data = self.get_valid_data()
        data[field_name] = empty_value
        response = self.client.post(self.instance_list_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({field_name: ['This field is required.']}, response.data)

    # Positive tests
    def test_can_create_instance_without_volume_sizes(self):
        data = self.get_valid_data()
        del data['volume_sizes']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Negative tests
    def test_cannot_create_instance_with_empty_hostname_name(self):
        self.assert_field_non_empty('hostname')

    def test_cannot_create_instance_without_hostname_name(self):
        self.assert_field_required('hostname')

    def test_cannot_create_instance_with_empty_template_name(self):
        self.assert_field_non_empty('template')

    def test_cannot_create_instance_without_template_name(self):
        self.assert_field_required('template')

    def test_cannot_create_instance_without_flavor(self):
        self.assert_field_required('flavor')

    def test_cannot_create_instance_with_empty_flavor(self):
        self.assert_field_non_empty('flavor')

    def test_cannot_create_instance_with_negative_volume_size(self):
        self.skipTest("Not implemented yet")

        data = self.get_valid_data()
        data['volume_size'] = -12

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_size': ['Ensure this value is greater than or equal to 1.']},
                                      response.data)

    def test_cannot_create_instance_with_invalid_volume_sizes(self):
        self.skipTest("Not implemented yet")

        data = self.get_valid_data()
        data['volume_sizes'] = 'gibberish'

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_sizes': ['Enter a whole number.']},
                                      response.data)

    # Helper methods
    def get_valid_data(self):
        return {
            # Cloud independent parameters
            'hostname': 'host1',

            # Should not depend on cloud, instead represents an "aggregation" of templates
            'template': reverse('template-detail', kwargs={'uuid': self.template.uuid}),

            'volume_sizes': [10, 15, 10],
            'tags': set(),

            # Cloud dependent parameters
            'flavor': reverse('flavor-detail', kwargs={'uuid': self.flavor.uuid}),
        }


class InstanceManipulationTest(test.APISimpleTestCase):
    def setUp(self):
        # XXX: This is temporary stub before proper permissions are enforced
        self.user = structure_factories.UserFactory()
        self.client.force_authenticate(user=self.user)

        self.instance = factories.InstanceFactory()
        self.instance_url = reverse('instance-detail', kwargs={'uuid': self.instance.uuid})

    def test_cannot_delete_instance(self):
        response = self.client.delete(self.instance_url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_instance_as_whole(self):
        data = {
            'hostname': self.instance.hostname,
            'template': reverse('template-detail', kwargs={'uuid': self.instance.template.uuid}),
            'flavor': reverse('flavor-detail', kwargs={'uuid': self.instance.flavor.uuid}),
        }

        response = self.client.put(self.instance_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_cannot_change_single_instance_field(self):
        data = {
            'hostname': self.instance.hostname,
        }

        response = self.client.patch(self.instance_url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
