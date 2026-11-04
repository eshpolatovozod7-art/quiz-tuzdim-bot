from aiogram.fsm.state import State, StatesGroup


class QuizCreateState(StatesGroup):
    waiting_topic = State()
    waiting_text = State()
    waiting_document = State()
    waiting_video = State()
    waiting_audio = State()
    waiting_image = State()
    waiting_custom_count = State()


class ChannelScheduleState(StatesGroup):
    waiting_channel = State()
    waiting_topic = State()
    waiting_interval = State()
