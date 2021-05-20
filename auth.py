# -*- coding: utf-8 -*-
import hashlib

from fastapi import Depends, HTTPException, APIRouter
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from starlette import status

from db_helper import get_user_from_db
from db_models import database
from schemas import User


auth_router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SALT = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"


def get_password_hash(password: str):
    return hashlib.sha512((SALT + password).encode('utf-8')).hexdigest()


async def get_token_owner(token):
    username = token.split('.')[0]
    return await get_user_from_db(database, username)


def create_access_token(user):
    token = '.'.join([user.username, user.password, 'token'])
    return {"access_token": token, "token_type": "bearer"}


async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = await get_token_owner(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def is_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


@auth_router.post("/token", tags=['login'])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await get_user_from_db(database, form_data.username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    hashed_password = get_password_hash(form_data.password)
    if not hashed_password == user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    return create_access_token(form_data)
