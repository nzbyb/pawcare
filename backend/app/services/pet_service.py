from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.pet import Pet, WeightRecord
from app.models.user import User
from app.schemas.pet import PetCreate, PetUpdate, WeightCreate


def _get_pet(db: Session, user: User, pet_id: int, write: bool = False) -> Pet:
    pet = db.get(Pet, pet_id)
    if not pet or pet.status == "deleted":
        raise BusinessException(message="宠物不存在")

    if user.role == "pet_owner" and pet.owner_id != user.id:
        raise BusinessException(message="无权访问该宠物", code=403)
    if write and user.role == "boarding_staff":
        raise BusinessException(message="寄养员不能修改宠物档案", code=403)
    return pet


def get_pet(db: Session, user: User, pet_id: int) -> Pet:
    return _get_pet(db, user, pet_id, write=False)


def get_pet_for_write(db: Session, user: User, pet_id: int) -> Pet:
    return _get_pet(db, user, pet_id, write=True)


def create_pet(db: Session, user: User, data: PetCreate) -> Pet:
    if user.role != "pet_owner":
        raise BusinessException(message="只有宠物主可以建立宠物档案", code=403)

    pet = Pet(owner_id=user.id, **data.model_dump())
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def list_pets(db: Session, user: User) -> list[Pet]:
    query = db.query(Pet).filter(Pet.status != "deleted")
    if user.role == "pet_owner":
        query = query.filter(Pet.owner_id == user.id)
    return query.order_by(Pet.create_time.desc()).all()


def update_pet(db: Session, user: User, pet_id: int, data: PetUpdate) -> Pet:
    pet = _get_pet(db, user, pet_id, write=True)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(pet, field, value)
    db.commit()
    db.refresh(pet)
    return pet


def delete_pet(db: Session, user: User, pet_id: int) -> None:
    pet = _get_pet(db, user, pet_id, write=True)
    pet.status = "deleted"
    db.commit()


def add_weight(
    db: Session, user: User, pet_id: int, data: WeightCreate
) -> WeightRecord:
    pet = _get_pet(db, user, pet_id, write=True)
    record = WeightRecord(pet_id=pet.id, **data.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_weights(db: Session, user: User, pet_id: int) -> list[WeightRecord]:
    pet = _get_pet(db, user, pet_id)
    return (
        db.query(WeightRecord)
        .filter(WeightRecord.pet_id == pet.id)
        .order_by(WeightRecord.record_date.asc())
        .all()
    )
