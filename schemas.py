# -*- coding: utf-8 -*-
from enum import Enum
from datetime import datetime
from typing import List, Optional, Dict, Union

from pydantic import BaseModel, validator, root_validator, Field


class HostStatus(str, Enum):
    active = 'active'
    purchased = 'purchased'
    destroyed = 'destroyed'


class Hypervizor(str, Enum):
    OpenStack = 'OpenStack'
    VmWare = 'VmWare'
    Nutanix = 'Nutanix'


class ReservationStatusForUser(str, Enum):
    created = 'created'
    in_consideration = 'in_consideration'


class ReservationStatus(str, Enum):
    created = 'created'
    in_consideration = 'in_consideration'
    rejected = 'rejected'
    completed = 'completed'


class DataCenter(str, Enum):
    DataLine = 'DataLine'
    DataSpace = 'DataSpace'
    DataPro = 'DataPro'
    ITeco = 'i-Teco'
    STOREDATA = 'STOREDATA'


class Network(str, Enum):
    network_segment1 = 'network_segment1'
    network_segment2 = 'network_segment2'
    network_segment3 = 'network_segment3'
    network_segment4 = 'network_segment4'


class StorageAction(str, Enum):
    add = 'add'
    remove = 'remove'


class CPU(BaseModel):
    cpu_type: str
    cores: int = Field(..., gt=0)

    @validator('cpu_type')
    def validate_cpu_type(cls, value):
        assert value in ['intel', 'amd'], 'must be intel or amd'
        return value


class Storage(BaseModel):
    storage_type: str
    size: int = Field(..., gt=5)
    sata_port: int = Field(..., gt=0, le=10)

    @validator('storage_type')
    def validate_storage_type(cls, value):
        assert value in ['ssd', 'hdd', 'sshd'], 'must be ssd, hdd or sshd'
        return value


class Host(BaseModel):
    sku: int = Field(..., gt=0)
    status: HostStatus = HostStatus.active
    cpu: CPU
    ram: int = Field(..., ge=8)
    storage: List[Storage]
    data_center: DataCenter
    network: Network
    hypervizor: Hypervizor

    @validator('storage')
    def validate_storages(cls, storages):
        if len(storages) > 1:
            ports = [store.sata_port for store in storages]
            assert len(ports) == len(set(ports)), 'ports for storages will be unique'
        return storages

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "sku": 12345,
                "status": "active",
                "cpu": {
                    "cpu_type": "intel",
                    "cores": 32
                },
                "ram": 256,
                "storage": [
                    {
                        "storage_type": "ssd",
                        "size": 5000,
                        "sata_port": 1
                    },
                    {
                        "storage_type": "hdd",
                        "size": 10000,
                        "sata_port": 2
                    }
                ],
                "data_center": "DataLine",
                "network": "network_segment1",
                "hypervizor": "VmWare",
            }}


class HostAdd(Host):

    @validator('storage')
    def validate_storages(cls, storages):
        if len(storages) > 1:
            ports = [store.sata_port for store in storages]
            assert len(ports) == len(set(ports)), 'ports for storages will be unique'
        return storages


class EditHost(BaseModel):
    status:  Optional[HostStatus]
    ram: Optional[int]
    storage_action: Optional[Dict[StorageAction, Union[List[Storage], Dict]]] = None
    data_center: Optional[DataCenter]
    network: Optional[Network]
    hypervizor: Optional[Hypervizor]

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "status": "active",
                "ram": 8,
                "storage_action": {
                    "add": [
                        {
                            "storage_type": "ssd",
                            "size": 500,
                            "sata_port": 7
                        }
                    ],
                    "remove":  {
                            "sata_port": [1, 2]
                        },
                },
                "data_center": "DataLine",
                "network": "network_segment1",
                "hypervizor": "OpenStack"
            }
        }


class LoadsHost(BaseModel):
    sku: int
    cpu_cores: Dict
    ram_status: Dict
    storage_status: Dict


class VmReservation(BaseModel):
    id: Optional[int]
    created_time = datetime.utcnow()
    status: ReservationStatus = ReservationStatus.created
    description: Optional[str] = None
    cpu_cores: Optional[str] = 2
    ram: Optional[int] = 1
    storage_size: Optional[int] = 10
    storage_type: Optional[str] = 'hdd'
    data_center: Optional[DataCenter] = None
    network: Optional[Network] = None
    hypervizor: Hypervizor
    assigned_to_host: Optional[int] = None

    @root_validator
    def check_resourses(cls, values):
        cpu_cores, ram, storage_size, storage_type = values.get('cpu_cores'), values.get('ram'),\
                                                     values.get('storage_size'), values.get('storage_type')
        assert storage_type in ['ssd', 'hdd', 'sshd'], 'must be ssd, hdd or sshd'
        if not any([cpu_cores, ram, storage_size]):
            raise ValueError('at least one parameter of [cpu_cores, ram, storage_size] must be specified')
        return values

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "cpu_cores": 4,
                "ram": 32,
                "storage_size": 10,
                "storage_type": 'hdd',
                "data_center": "DataLine",
                "network": "network_segment1",
                "hypervizor": "VmWare",
            }}


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    username: str
    email: Optional[str] = None
    is_admin: Optional[bool] = None
