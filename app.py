# -*- coding: utf-8 -*-
import os
from typing import List, Dict

import uvicorn
from fastapi import FastAPI, Query, Depends
from dotenv import load_dotenv

from auth import get_current_user, auth_router, is_admin
from schemas import Host, VmReservation, User, ReservationStatusForUser, EditHost, HostAdd, LoadsHost
from db_models import database
from db_helper import add_new_host, get_host_info, get_my_vps_requests, change_my_request_status, reject_requests, \
    get_pending_requests_list, assign_host_with_verification, edit_host_config, get_hosts_and_loads, auto_allocate_requests, add_task

load_dotenv()
app = FastAPI(description="Веб-сервис для планирования количества ресурсов и "
                          "аппаратных хостов на базе поступающих заявок.", title='Otus. Проектная работа')


@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


@app.post('/add_host', tags=['admin_actions'])
async def add_host(item: HostAdd, current_user: User = Depends(is_admin)):
    """Добавить новый хост"""
    await add_new_host(database, item)
    return {'result': 'success'}


@app.get('/get_host', response_model=Host, tags=['admin_actions'])
async def get_host(sku: int = Query(...), current_user: User = Depends(is_admin)):
    """Получить конфигурацию хоста по его sku"""
    host_data = await get_host_info(database, sku)
    return host_data


@app.post('/edit_existing_host', tags=['admin_actions'])
async def edit_existing_host(item: EditHost, sku: int = Query(...), current_user: User = Depends(is_admin)):
    """Изменить существующий хост"""
    await edit_host_config(database, sku, item)
    return {'result': 'success'}


@app.get('/pending_requests', response_model=Dict[str, List[VmReservation]],
         response_model_exclude_none=True, tags=['admin_actions'])
async def get_pending_requests(current_user: User = Depends(is_admin)):
    """Получить заявки в рассмотрении"""
    pending_requests = await get_pending_requests_list(database)
    result = [VmReservation(**item) for item in pending_requests]
    return {'result': result}


@app.post('/reject_pending_request', tags=['admin_actions'])
async def reject_pending_request(description: str, request_id: int = Query(...), current_user: User = Depends(is_admin)):
    """Отклонить ожидающую заявку"""
    await reject_requests(database, request_id, description)
    return {'result': 'success'}


@app.post('/assign_host_for_request', tags=['admin_actions'])
async def assign_host_for_request(host_sku: int, request_id: int = Query(...), current_user: User = Depends(is_admin)):
    """Назначить хост для заявки"""
    await assign_host_with_verification(database, request_id, host_sku)
    return {'result': 'success'}


@app.post('/get_hosts_load', tags=['admin_actions'], response_model=Dict[str, List[LoadsHost]])
async def get_hosts_load(current_user: User = Depends(is_admin)):
    """Получить хосты и их загруженность"""
    result = await get_hosts_and_loads(database)
    return {'result': result}


@app.post('/auto_allocate', tags=['admin_actions'])
async def auto_allocate(current_user: User = Depends(is_admin)):
    """Автоназначение хостов на заявки"""
    result = await auto_allocate_requests(database)
    return result


@app.post('/reserve_vps', tags=['user_actions'])
async def reserve_vps(item: VmReservation, current_user: User = Depends(get_current_user)):
    """Создать заявку на ВМ"""
    await add_task(database, item, current_user.login)
    return {'result': 'success'}


@app.get('/my_vps_requests', response_model=Dict[str, List[VmReservation]],
         response_model_exclude_none=True, response_model_exclude={"assigned_to_host"}, tags=['user_actions'])
async def get_reservation_requests(current_user: User = Depends(get_current_user)):
    """Получить все свои заявки"""
    requests_data = await get_my_vps_requests(database, current_user.login)
    return {"result": requests_data}


@app.post('/edit_vps_reservation_status', tags=['user_actions'])
async def change_my_vps_request_status(new_status: ReservationStatusForUser, request_id: int = Query(...),
                                       current_user: User = Depends(get_current_user)):
    """Изменить статус своей заявки"""
    await change_my_request_status(database, request_id, new_status)
    return {'result': 'success'}


app.include_router(auth_router)

if __name__ == '__main__':
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('API_PORT', 8000))
    uvicorn.run('app:app', host=API_HOST, port=API_PORT)

