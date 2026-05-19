from fastapi import Header, HTTPException, Depends, Query
from sqlalchemy import select 
from app.core.telegram_auth import verify_init_data
from app.core.config import settings
from app.models.user import User
from app.db.session import get_session

async def get_current_user(
        x_telegram_init_data: str| None = Header(default=None),
        db = Depends(get_session), 
        telegram_id: int | None = Query(default=None)) -> User:
    # DEV BYPASS ONLY! REMOVE THIS IN PRODUCTION!
    if settings.debug==True and telegram_id is not None:
        tg_id = telegram_id
    else:
        # checks if init is there or not, if not, raises 401 error.
        if x_telegram_init_data is None:
            raise HTTPException(status_code=401, detail="missing init data")
        # gatekeeps
        try:
            tg_user = verify_init_data(x_telegram_init_data, settings.TELEGRAM_BOT_TOKEN)
        except ValueError:
            raise HTTPException(status_code=401, detail="invalid init data")
        tg_id = tg_user["id"]            

    # lookup the user by TG id. runs the query on the database and returns a Result object:
    result = await db.execute(select(User).where(User.telegram_id == tg_id))

    #   - None        if no rows matched
    #   - the value   if exactly one row matched
    #   - it RAISES   if two or more rows matched (a "should be unique" violation)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return user

