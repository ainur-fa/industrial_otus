import json
from collections import Counter
from sqlalchemy.sql import and_
from fastapi.exceptions import HTTPException
from fastapi import status
from db_models import cpu, storage, storages_set, host, vm_reservation, account
from schemas import HostStatus, ReservationStatus, Storage, LoadsHost, VmReservation, Host


async def add_new_host(db, host_schema):
    if await host_exists(db, host_schema.sku):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sku must be unique.")

    cpu_id = await add_cpu_if_not_exists(db, host_schema.cpu)
    await add_storages_set(db, host_schema.storage, host_schema.sku)
    query = host.insert().values(sku=host_schema.sku,
                                 status=host_schema.status,
                                 ram=host_schema.ram,
                                 cpu_id=cpu_id,
                                 storage_id=host_schema.sku,
                                 network=host_schema.network,
                                 data_center=host_schema.data_center,
                                 hypervizor=host_schema.hypervizor)
    result = await db.execute(query)
    return result


async def revision_tasks(db, host_item):
    query = vm_reservation.update().where(vm_reservation.c.assigned_to_host == host_item.sku).values(
        status=ReservationStatus.in_consideration, assigned_to_host=None)
    await db.execute(query)


async def add_task(db, schema, user_login):
    query = vm_reservation.insert().values(cpu_cores=schema.cpu_cores,
                                           storage_size=schema.storage_size,
                                           storage_type=schema.storage_type,
                                           ram=schema.ram,
                                           hypervizor=schema.hypervizor,
                                           data_center=schema.data_center,
                                           network=schema.network,
                                           user_login=user_login,
                                           status=ReservationStatus.created)
    result = await db.execute(query)
    return result


async def change_my_request_status(db, request_id, new_status):
    query = vm_reservation.update().where(vm_reservation.c.id == request_id).values(status=new_status)
    await db.execute(query)


async def remove_host_storage(db, host_item, sata_port):
    storages = await get_host_storages(db, host_item)

    for store in storages:
        if sata_port == store.sata_port:
            query1 = storage.delete().where(storage.c.id == store.id)
            query2 = storages_set.delete().where(storages_set.c.storage_id == store.id)
            return [await db.execute(q) for q in (query1, query2)]

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"storage with sata_port: {sata_port} not exists")


async def edit_host_config(db, sku, item):
    host_item = await get_host(db, sku)
    if item.status == HostStatus.purchased:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not allowed status for this host")

    item_dict = json.loads(item.json())
    fields_for_edit = {k: v for k, v in item_dict.items() if v}

    storage_action = fields_for_edit.get('storage_action')
    if storage_action:
        add_disks = storage_action.get('add', [])
        remove_disks = storage_action.get('remove', [])

        if remove_disks:
            [await remove_host_storage(db, host_item, disk) for disk in remove_disks['sata_port'] if remove_disks]
        if add_disks:
            using_ports = {store.sata_port for store in await get_host_storages(db, host_item)}
            new_ports = {store['sata_port'] for store in add_disks}

            if using_ports.intersection(new_ports):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"trying to use a busy sata port")

            await add_storages_set(db, [Storage(**disk) for disk in add_disks], sku)
            fields_for_edit.pop('storage_action')
    await db.execute(host.update().where(host.c.sku == sku).values(**fields_for_edit))

    if item.status == HostStatus.destroyed:
        await revision_tasks(db, host_item)


async def get_host_storages(db, host_item):
    query = storages_set.select().where(storages_set.c.sku == host_item.storage_id)
    storages = await db.fetch_all(query)
    result = []
    for each in storages:
        item = await db.fetch_one(storage.select().where(storage.c.id == each.storage_id))
        result.append(item)

    return result


async def host_exists(db, sku):
    host_obj = await db.fetch_one(host.select().where(host.c.sku == sku))
    return True if host_obj else False


async def get_host(db, sku):
    host_obj = await db.fetch_one(host.select().where(host.c.sku == sku))
    if not host_obj:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"host with sku: {sku} not exists")
    return host_obj


async def get_host_info(db, sku):
    host_obj = await get_host(db, sku)
    cpu_obj = await get_cpu_with_id(db, host_obj.cpu_id)
    storages_obj = await get_host_storages(db, host_obj)

    host_dict = dict(host_obj.items())
    host_dict['cpu'] = dict(cpu_obj.items())
    host_dict['storage'] = [dict(store.items()) for store in storages_obj]
    return Host(**host_dict)


async def get_cpu_with_id(db, cpu_id):
    query = cpu.select().where(cpu.c.id == cpu_id)
    return await db.fetch_one(query)


async def add_storage(db, disk):
    query = storage.insert().values(storage_type=disk.storage_type, size=disk.size, sata_port=disk.sata_port)
    storage_id = await db.execute(query)
    return storage_id


async def add_storages_set(db, adding_storages, sku):
    for adding_storage in adding_storages:
        storage_id = await add_storage(db, adding_storage)
        await db.execute(storages_set.insert().values(sku=sku, storage_id=storage_id))


async def add_cpu_if_not_exists(db, schema):
    query = cpu.select().where(and_(cpu.c.cpu_type == schema.cpu_type, cpu.c.cores == schema.cores))
    exists = await db.fetch_all(query)
    if not exists:
        query = cpu.insert().values(cpu_type=schema.cpu_type, cores=schema.cores)
        cpu_id = await db.execute(query)
    else:
        cpu_id, _, _ = exists[0]
    return cpu_id


async def get_user_from_db(db, username):
    return await db.fetch_one(account.select().where(account.c.login == username))


async def get_my_vps_requests(db, username):
    my_requests = await db.fetch_all(vm_reservation.select().where(vm_reservation.c.user_login == username))
    requests_data = [dict(req.items()) for req in my_requests]
    return [VmReservation(**item) for item in requests_data]


async def get_pending_requests_list(db):
    query = vm_reservation.select().where(vm_reservation.c.status == ReservationStatus.in_consideration)
    pending_requests = await db.fetch_all(query)
    return pending_requests


async def reject_requests(db, request_id, description):
    query = vm_reservation.update().where(vm_reservation.c.id == request_id).values(
        status=ReservationStatus.rejected,
        description=description
    )
    return await db.execute(query)


async def get_assigned_requests(db, host_obj):
    query = vm_reservation.select().where(
        and_(vm_reservation.c.status == ReservationStatus.completed,
             vm_reservation.c.assigned_to_host == host_obj.sku))
    return await db.fetch_all(query)


async def get_resources_info(db, host_obj):
    requests_assigned_to_host = await get_assigned_requests(db, host_obj)

    storages_info = {}
    for store in await get_host_storages(db, host_obj):
        result = {'total': store.size, 'free': store.size - sum(
            [request.storage_size for request in requests_assigned_to_host if
             request.storage_type == store.storage_type])}
        if not storages_info.get(store.storage_type):
            storages_info[store.storage_type] = result
        else:
            storages_info[store.storage_type] = Counter(storages_info[store.storage_type]) + Counter(result)

    free_ram = host_obj.ram - sum([request.ram for request in requests_assigned_to_host])

    host_cpu = await get_cpu_with_id(db, host_obj.cpu_id)
    used_cores = sum([request.cpu_cores for request in requests_assigned_to_host])
    cpu_cores = {'total': host_cpu.cores, 'used': used_cores}
    return free_ram, storages_info, cpu_cores


async def verify_requirements(db, client_request, host_obj):
    if host_obj.status != HostStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"host is not active")

    free_ram, storages_info, cpu_cores = await get_resources_info(db, host_obj)

    errors = []
    storage_type = storages_info.get(client_request.storage_type)
    if storage_type and storage_type['free'] < client_request.storage_size:
        errors.append('insufficient STORAGE value')
    if free_ram < client_request.ram:
        errors.append('insufficient RAM')
    if cpu_cores['total'] < client_request.cpu_cores:
        errors.append('discrepancy CPU')
    if client_request.hypervizor != host_obj.hypervizor:
        errors.append('discrepancy HYPERVIZOR')
    if client_request.network and client_request.network != host_obj.network:
        errors.append('discrepancy NETWORK')
    if client_request.data_center and client_request.data_center != host_obj.data_center:
        errors.append('discrepancy DATACENTER')
    return (False, errors) if errors else (True, errors)


async def assign_task_to_host(db, task_id, host_sku):
    return await db.execute(
        vm_reservation.update().where(vm_reservation.c.id == task_id).values(assigned_to_host=host_sku,
                                                                             status=ReservationStatus.completed))


async def assign_host_with_verification(db, request_id, host_sku):
    client_request = await db.fetch_one(vm_reservation.select().where(vm_reservation.c.id == request_id))
    host_obj = await get_host(db, host_sku)

    passed, msg = await verify_requirements(db, client_request, host_obj)
    if passed:
        return await assign_task_to_host(db, client_request.id, host_obj.sku)
    else:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=", ".join(msg))


def get_loads(total, free, round_val=2):
    used = total - free
    return round(used * 100 / total, round_val)


async def get_active_hosts(db):
    active_hosts = await db.fetch_all(host.select().where(host.c.status == HostStatus.active))
    return active_hosts


async def get_hosts_and_loads(db):
    stat = []
    active_hosts = await get_active_hosts(db)
    for active_host in active_hosts:
        free_ram, storages_stat, cpu_cores = await get_resources_info(db, active_host)

        storage_info = {}
        for storage_type, storage_values in storages_stat.items():
            storage_info[storage_type] = {'total': storage_values['total'],
                                          'free': storage_values['free'],
                                          'loads_perc': get_loads(storage_values['total'], storage_values['free'])}

        res = LoadsHost(sku=active_host.sku, ram_status={'total': active_host.ram,
                                                         'free': free_ram,
                                                         'loads_perc': get_loads(active_host.ram, free_ram)},
                        storage_status=storage_info,
                        cpu_cores=cpu_cores)
        stat.append(res)

    return stat


async def auto_allocate_requests(db):
    tasks = await get_pending_requests_list(db)
    active_hosts = await get_active_hosts(db)

    success = 0
    for active_host in active_hosts:
        for task in tasks:
            passed, msg = await verify_requirements(db, task, active_host)
            if passed:
                await assign_task_to_host(db, task.id, active_host.sku)
                success += 1

    return {'await': len(tasks), 'approved': success}
