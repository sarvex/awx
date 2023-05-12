import logging

from django.utils.encoding import smart_text

from awx.main.utils.common import set_current_apps
from awx.main.utils.common import parse_yaml_or_json

logger = logging.getLogger('awx.main.migrations')


def _get_instance_id(from_dict, new_id, default=''):
    """logic mostly duplicated with inventory_import command Command._get_instance_id
    frozen in time here, for purposes of migrations
    """
    instance_id = default
    for key in new_id.split('.'):
        if not hasattr(from_dict, 'get'):
            instance_id = default
            break
        instance_id = from_dict.get(key, default)
        from_dict = instance_id
    return smart_text(instance_id)


def _get_instance_id_for_upgrade(host, new_id):
    if host.instance_id:
        # this should not have happened, but nothing to really do about it...
        logger.debug(f'Unexpectedly, host {host.name}-{host.pk} has instance_id set')
        return None
    host_vars = parse_yaml_or_json(host.variables)
    new_id_value = _get_instance_id(host_vars, new_id)
    if not new_id_value:
        # another source type with overwrite_vars or pesky users could have done this
        logger.info(
            f'Host {host.name}-{host.pk} has no {new_id} var, probably due to separate modifications'
        )
        return None
    if len(new_id) > 255:
        # this should never happen
        logger.warn(
            f'Computed instance id "{new_id_value}"" for host {host.name}-{host.pk} is too long'
        )
        return None
    return new_id_value


def set_new_instance_id(apps, source, new_id):
    """This methods adds an instance_id in cases where there was not one before"""
    from django.conf import settings

    id_from_settings = getattr(settings, f'{source.upper()}_INSTANCE_ID_VAR')
    if id_from_settings != new_id:
        # User applied an instance ID themselves, so nope on out of there
        logger.warn(f'You have an instance ID set for {source}, not migrating')
        return
    logger.debug(f'Migrating inventory instance_id for {source} to {new_id}')
    Host = apps.get_model('main', 'Host')
    modified_ct = 0
    for host in Host.objects.filter(inventory_sources__source=source).iterator():
        new_id_value = _get_instance_id_for_upgrade(host, new_id)
        if not new_id_value:
            continue
        host.instance_id = new_id_value
        host.save(update_fields=['instance_id'])
        modified_ct += 1
    if modified_ct:
        logger.info(
            f'Migrated instance ID for {modified_ct} hosts imported by {source} source'
        )


def back_out_new_instance_id(apps, source, new_id):
    Host = apps.get_model('main', 'Host')
    modified_ct = 0
    for host in Host.objects.filter(inventory_sources__source=source).iterator():
        host_vars = parse_yaml_or_json(host.variables)
        predicted_id_value = _get_instance_id(host_vars, new_id)
        if predicted_id_value != host.instance_id:
            logger.debug(
                f'Host {host.name}-{host.pk} did not get its instance_id from {new_id}, skipping'
            )
            continue
        host.instance_id = ''
        host.save(update_fields=['instance_id'])
        modified_ct += 1
    if modified_ct:
        logger.info(
            f'Reverse migrated instance ID for {modified_ct} hosts imported by {source} source'
        )


def delete_cloudforms_inv_source(apps, schema_editor):
    set_current_apps(apps)
    InventorySource = apps.get_model('main', 'InventorySource')
    InventoryUpdate = apps.get_model('main', 'InventoryUpdate')
    CredentialType = apps.get_model('main', 'CredentialType')
    InventoryUpdate.objects.filter(inventory_source__source='cloudforms').delete()
    InventorySource.objects.filter(source='cloudforms').delete()
    if ct := CredentialType.objects.filter(namespace='cloudforms').first():
        ct.credentials.all().delete()
        ct.delete()


def delete_custom_inv_source(apps, schema_editor):
    set_current_apps(apps)
    InventorySource = apps.get_model('main', 'InventorySource')
    InventoryUpdate = apps.get_model('main', 'InventoryUpdate')
    ct, deletions = InventoryUpdate.objects.filter(source='custom').delete()
    if ct:
        logger.info(f'deleted {(ct, deletions)}')
        if update_ct := deletions['main.InventoryUpdate']:
            logger.info(f'Deleted {update_ct} custom inventory script sources.')
    ct, deletions = InventorySource.objects.filter(source='custom').delete()
    if ct:
        logger.info(f'deleted {(ct, deletions)}')
        if src_ct := deletions['main.InventorySource']:
            logger.info(f'Deleted {src_ct} custom inventory script updates.')
            logger.warning('Custom inventory scripts have been removed, see awx-manage export_custom_scripts')
