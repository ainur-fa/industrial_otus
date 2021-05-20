# -*- coding: utf-8 -*-
import os

import databases
from sqlalchemy import Column, Integer, String, ForeignKey, Table, TIMESTAMP, Boolean, create_engine
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func


Base = declarative_base()
DATABASE_URL = os.getenv('DATABASE_URL', "sqlite:///./sqlite_db.db")

database = databases.Database(DATABASE_URL)
metadata = Base.metadata


class CPU(Base):
    __tablename__ = 'cpu'
    id = Column(Integer,  primary_key=True, autoincrement=True)
    cpu_type = Column(String)
    cores = Column(Integer)
    host = relationship("Host", back_populates="cpu")


class Storage(Base):
    __tablename__ = 'storage'
    id = Column(Integer,  primary_key=True, autoincrement=True)
    storage_type = Column(String)
    size = Column(Integer)
    sata_port = Column(Integer)


storages_set = Table('storages_set', metadata,
                     Column('sku', Integer(), ForeignKey('host.sku')),
                     Column('storage_id', Integer(), ForeignKey('storage.id')))


class Host(Base):
    __tablename__ = 'host'
    sku = Column(Integer, primary_key=True, unique=True)
    status = Column(String)
    ram = Column(Integer)
    data_center = Column(String)
    network = Column(String)
    hypervizor = Column(String)

    cpu_id = Column(Integer, ForeignKey('cpu.id'))
    cpu = relationship("CPU", back_populates="host")

    storage_id = Column(Integer, ForeignKey('storage.id'))
    storage = relationship("Storage", secondary=storages_set, backref='host', cascade='all,delete')


class Account(Base):
    __tablename__ = 'account'
    login = Column(String, primary_key=True, unique=True)
    username = Column(String)
    email = Column(String)
    hashed_password = Column(String)
    is_admin = Column(Boolean)


class VmReservation(Base):
    __tablename__ = 'vm_reservation'
    id = Column(Integer,  primary_key=True, autoincrement=True)
    status = Column(String, nullable=False)
    created_time = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    cpu_cores = Column(Integer, nullable=True)
    ram = Column(Integer, nullable=True)
    storage_size = Column(Integer, nullable=True)
    storage_type = Column(String, nullable=True)
    hypervizor = Column(String, nullable=False)
    data_center = Column(String)
    network = Column(String)
    description = Column(String, default=None)

    assigned_to_host = Column(String, ForeignKey('host.sku'))
    host = relationship("Host", back_populates="vm_reservation")

    user_login = Column(Integer, ForeignKey('account.login'))
    account = relationship("Account", back_populates="vm_reservation")


cpu = CPU.__table__
host = Host.__table__
storage = Storage.__table__
vm_reservation = VmReservation.__table__
account = Account.__table__

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata.create_all(engine)
