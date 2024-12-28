from aiogram.fsm.state import StatesGroup, State

class AddClient(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    phone_code_hash = State()
    otp = State()
    password = State()
    

class AddPyroAccount(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    code = State()
    password = State()