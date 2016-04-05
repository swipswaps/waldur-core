import collections

import requests
from django.contrib.auth import get_user_model

from nodeconductor.core.models import SshPublicKey


Coordinates = collections.namedtuple('Coordinates', ('latitude', 'longitude'))


class GeoIpException(Exception):
    pass


def serialize_ssh_key(ssh_key):
    return {
        'name': ssh_key.name,
        'user_id': ssh_key.user_id,
        'fingerprint': ssh_key.fingerprint,
        'public_key': ssh_key.public_key,
        'uuid': ssh_key.uuid.hex
    }


def deserialize_ssh_key(data):
    return SshPublicKey(
        name=data['name'],
        user_id=data['user_id'],
        fingerprint=data['fingerprint'],
        public_key=data['public_key'],
        uuid=data['uuid']
    )


def serialize_user(user):
    return {
        'username': user.username,
        'email': user.email
    }


def deserialize_user(data):
    return get_user_model()(
        username=data['username'],
        email=data['email']
    )


def get_coordinates_by_ip(ip_address):
    url = 'http://freegeoip.net/json/{}'.format(ip_address)

    try:
        response = requests.get(url)
    except requests.exceptions.RequestException as e:
        raise GeoIpException("Request to geoip API %s failed: %s" % (url, e))

    if response.ok:
        data = response.json()
        return Coordinates(latitude=data['latitude'],
                           longitude=data['longitude'])
    else:
        params = (url, response.status_code, response.text)
        raise GeoIpException("Request to geoip API %s failed: %s %s" % params)
