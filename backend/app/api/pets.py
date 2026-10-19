from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.pet import PetCreate, PetResponse, PetUpdate, WeightCreate, WeightResponse
from app.services import pet_service

router = APIRouter(prefix="/pets", tags=["宠物档案"])


@router.post("", response_model=Response)
def create_pet(
    data: PetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pet = pet_service.create_pet(db, current_user, data)
    return Response.success(
        message="宠物档案已建立", data=PetResponse.model_validate(pet).model_dump()
    )


@router.get("", response_model=Response)
def list_pets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pets = pet_service.list_pets(db, current_user)
    return Response.success(
        data=[PetResponse.model_validate(pet).model_dump() for pet in pets]
    )


@router.get("/{pet_id}", response_model=Response)
def get_pet(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pet = pet_service.get_pet(db, current_user, pet_id)
    return Response.success(data=PetResponse.model_validate(pet).model_dump())


@router.put("/{pet_id}", response_model=Response)
def update_pet(
    pet_id: int,
    data: PetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pet = pet_service.update_pet(db, current_user, pet_id, data)
    return Response.success(
        message="宠物档案已更新", data=PetResponse.model_validate(pet).model_dump()
    )


@router.delete("/{pet_id}", response_model=Response)
def delete_pet(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pet_service.delete_pet(db, current_user, pet_id)
    return Response.success(message="宠物档案已删除")


@router.post("/{pet_id}/weights", response_model=Response)
def add_weight(
    pet_id: int,
    data: WeightCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = pet_service.add_weight(db, current_user, pet_id, data)
    return Response.success(
        message="体重已记录", data=WeightResponse.model_validate(record).model_dump()
    )


@router.get("/{pet_id}/weights", response_model=Response)
def list_weights(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = pet_service.list_weights(db, current_user, pet_id)
    return Response.success(
        data=[WeightResponse.model_validate(record).model_dump() for record in records]
    )
