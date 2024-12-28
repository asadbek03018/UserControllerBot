from aiogram.fsm.state import StatesGroup, State

class CreateAdvertisementStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_text = State()
    selecting_duration = State()
    selecting_groups = State()