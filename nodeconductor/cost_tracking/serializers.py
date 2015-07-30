from __future__ import unicode_literals

from django.db import transaction
from rest_framework import serializers

from nodeconductor.core.serializers import GenericRelatedField, AugmentedSerializerMixin
from nodeconductor.cost_tracking import models
from nodeconductor.structure import models as structure_models


class PriceEstimateSerializer(AugmentedSerializerMixin, serializers.HyperlinkedModelSerializer):
    scope = GenericRelatedField(related_models=models.PriceEstimate.get_editable_estimated_models())

    class Meta(object):
        model = models.PriceEstimate
        fields = ('url', 'uuid', 'scope', 'total', 'details', 'month', 'year', 'is_manually_inputed')
        read_only_fields = ('is_manually_inputed',)
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }
        protected_fields = ('scope', 'year', 'month')

    def validate(self, data):
        if self.instance is None and models.PriceEstimate.objects.filter(
                scope=data['scope'], year=data['year'], month=data['month'], is_manually_inputed=True).exists():
            raise serializers.ValidationError(
                'Estimate for given month already exists. Use PATCH request to update it.')
        return data

    def create(self, validated_data):
        validated_data['is_manually_inputed'] = True
        price_estimate = super(PriceEstimateSerializer, self).create(validated_data)
        return price_estimate


class YearMonthField(serializers.CharField):
    """ Field that support year-month representation in format YYYY.MM """

    def to_internal_value(self, value):
        try:
            year, month = [int(el) for el in value.split('.')]
        except ValueError:
            raise serializers.ValidationError('Value "{}" should be valid be in format YYYY.MM'.format(value))
        if not 0 < month < 13:
            raise serializers.ValidationError('Month has to be from 1 to 12')
        return year, month


class PriceEstimateDateFilterSerializer(serializers.Serializer):
    date_list = serializers.ListField(
        child=YearMonthField(),
        required=False
    )


class PriceEstimateDateRangeFilterSerializer(serializers.Serializer):
    start = YearMonthField(required=False)
    end = YearMonthField(required=False)

    def validate(self, data):
        if 'start' in data and 'end' in data and data['start'] >= data['end']:
            raise serializers.ValidationError('Start has to be earlier than end.')
        return data


class PriceListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PriceListItem
        lookup_field = 'uuid'
        fields = ('name', 'value', 'units')


class PriceListSerializer(serializers.HyperlinkedModelSerializer):
    items = PriceListItemSerializer(
        many=True,
        required=False,
        default=(),
    )
    service = GenericRelatedField(related_models=structure_models.Service.get_all_models())

    class Meta:
        model = models.PriceList
        lookup_field = 'uuid'
        fields = ('url', 'uuid', 'service', 'items')

    def validate_service(self, value):
        if models.PriceList.objects.filter(service=value).exists():
            raise serializers.ValidationError('Service can not have more than one price list')
        return value

    def create(self, validated_data):
        items = validated_data.pop('items', [])
        price_list = super(PriceListSerializer, self).create(validated_data)
        if items:
            price_list_items = [models.PriceListItem(**item) for item in items]
            price_list.items.add(*price_list_items)
        return price_list

    def update(self, instance, validated_data):
        items_in_validated_data = 'items' in validated_data
        items = validated_data.pop('items', [])
        price_list = super(PriceListSerializer, self).update(instance, validated_data)
        if items_in_validated_data:
            price_list.items.all().delete()
        if items:
            price_list_items = [models.PriceListItem(**item) for item in items]
            price_list.items.add(*price_list_items)
        return price_list
