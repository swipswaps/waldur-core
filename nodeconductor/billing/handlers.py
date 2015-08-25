import logging

from nodeconductor.billing.log import event_logger


logger = logging.getLogger('nodeconductor.billing')


def log_invoice_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.invoice.info(
            'Invoice for customer {customer_name} for the period of {invoice_date} has been created.',
            event_type='invoice_creation_succeeded',
            event_context={
                'invoice': instance,
            })
    else:
        event_logger.invoice.info(
            'Invoice for customer {customer_name} for the period of {invoice_date} has been updated.',
            event_type='invoice_update_succeeded',
            event_context={
                'invoice': instance,
            })


def log_invoice_delete(sender, instance, **kwargs):
    event_logger.invoice.info(
        'Invoice for customer {customer_name} for the period of {invoice_date} has been deleted.',
        event_type='invoice_deletion_succeeded',
        event_context={
            'invoice': instance,
        })


def track_order(sender, instance, name=None, source=None, **kwargs):
    if source == instance.States.PROVISIONING and name == instance.set_online.__name__:
        instance.order.subscribe()


def terminate_purchase(sender, instance=None, **kwargs):
    instance.order.terminate()
