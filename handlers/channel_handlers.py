import html
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from database.db import (
    get_user_channel_schedules,
    add_channel_schedule,
    delete_channel_schedule,
)
from utils.states import ChannelScheduleState

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("channel", "channels"))
@router.callback_query(F.data == "menu:channels")
async def handle_menu_channels(event: Message | CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Kanallarga avtomatik test rejalashtirish boshqaruvi."""
    await state.clear()
    user = event.from_user
    if not user:
        return
    user_id = user.id
    schedules = await get_user_channel_schedules(user_id)
    bot_info = await bot.get_me()

    text = (
        "📢 <b>Guruh va Kanallar bilan ishlash</b>\n\n"
        "👥 <b>Guruhlarda viktorina (Musobaqa):</b>\n"
        f"1. Botni guruhingizga qo'shing (@{bot_info.username}).\n"
        "2. Guruhda <code>/poll</code> buyrug'ini yuboring va testni tanlang — bot taymerli sinxron o'yin o'tkazib beradi!\n\n"
        "📢 <b>Kanallarga avtomatik test joylash:</b>\n"
        "Bot har kuni yoki har 12 soatda kanalingizga yangi, takrorlanmagan testlarni avtomatik joylab borishi mumkin.\n"
        "• Botni kanalingizga Administrator qilib qo'shing va quyidagi tugma orqali kanalni ulang:\n\n"
    )

    rows = []
    if schedules:
        text += "📋 <b>Sizning faol jadvallaringiz:</b>\n"
        for s in schedules:
            ch_title = html.escape(s["channel_title"] or s["channel_id"], quote=False)
            top = html.escape(s["topic"], quote=False)
            hrs = s["interval_hours"]
            cnt = s["question_count"]
            text += f"• <b>{ch_title}</b>: <i>{top}</i> (Har {hrs} soatda {cnt} ta savol)\n"
            rows.append([
                InlineKeyboardButton(
                    text=f"🗑 O'chirish: {ch_title[:15]}",
                    callback_data=f"ch_del:{s['id']}",
                )
            ])
        text += "\n"
    else:
        text += "<i>Sizda hali birorta ham rejalashtirilgan kanal yo'q.</i>\n\n"

    rows.append([
        InlineKeyboardButton(text="➕ Yangi kanal rejalashtirish", callback_data="ch_add:start")
    ])
    rows.append([
        InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu:home")
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "ch_add:start")
async def handle_channel_add_start(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Kanal qo'shish jarayonini boshlash."""
    bot_info = await bot.get_me()
    await state.set_state(ChannelScheduleState.waiting_channel)
    text = (
        "📢 <b>1-qadam: Kanalingiz manzilini yuboring</b>\n\n"
        f"Avval botni (@{bot_info.username}) kanalingizga admin qilib qo'shganingizga ishonch hosil qiling.\n\n"
        "So'ngra kanalingiz username yoki havolasini yozing:\n"
        "<i>(Masalan: @mening_kanalim yoki https://t.me/mening_kanalim)</i>"
    )
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu:channels")]])
    if callback.message:
        await callback.message.edit_text(text, reply_markup=cancel_kb, parse_mode="HTML")
    await callback.answer()


@router.message(ChannelScheduleState.waiting_channel, F.text)
async def process_channel_input(message: Message, state: FSMContext, bot: Bot) -> None:
    """Kanal username yoki ID sini tekshirish."""
    raw_channel = message.text.strip().replace("https://t.me/", "@")
    if not raw_channel.startswith("@") and not raw_channel.startswith("-100"):
        raw_channel = f"@{raw_channel}"

    # Bot kanalda admin ekanligini tekshirish
    try:
        chat = await bot.get_chat(raw_channel)
        channel_id = str(chat.id)
        channel_title = chat.title or raw_channel
    except Exception as e:
        logger.warning("Kanal tekshirishda xatolik: %s", e)
        bot_info = await bot.get_me()
        await message.answer(
            f"❌ <b>Bot kanaldan topilmadi yoki admin emas!</b>\n\n"
            f"Iltimos, @{bot_info.username} ni kanalingizga <b>Admin</b> qilib qo'shing va username'ni qayta yuboring.",
            parse_mode="HTML",
        )
        return

    await state.update_data(channel_id=channel_id, channel_title=channel_title)
    await state.set_state(ChannelScheduleState.waiting_topic)

    text = (
        f"✅ <b>{html.escape(channel_title, quote=False)}</b> kanali muvaffaqiyatli ulandi!\n\n"
        "📌 <b>2-qadam:</b> Qaysi mavzu yoki fandan testlar tashlab borilsin?\n"
        "<i>(Masalan: Ingliz tili B2 grammatika, O'zbekiston tarixi, DTM Matematika...)</i>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(ChannelScheduleState.waiting_topic, F.text)
async def process_topic_input(message: Message, state: FSMContext) -> None:
    """Mavzuni qabul qilish va interval tanlash."""
    topic = message.text.strip()
    await state.update_data(topic=topic)
    await state.set_state(ChannelScheduleState.waiting_interval)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏰ Har 12 soatda (2 ta savol)", callback_data="ch_int:12:2"),
                InlineKeyboardButton(text="⏰ Har 24 soatda (3 ta savol)", callback_data="ch_int:24:3"),
            ],
            [
                InlineKeyboardButton(text="⏰ Har 24 soatda (5 ta savol)", callback_data="ch_int:24:5"),
                InlineKeyboardButton(text="⏰ Har 6 soatda (1 ta savol)", callback_data="ch_int:6:1"),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu:channels"),
            ],
        ]
    )

    text = (
        f"🎯 <b>Mavzu:</b> <i>{html.escape(topic, quote=False)}</i>\n\n"
        "⏱ <b>3-qadam:</b> Qancha vaqt oralig'ida yangi testlar kanalga tashlab turilsin?"
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("ch_int:"))
async def process_interval_callback(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Intervalni saqlash va jadvalni ishga tushirish."""
    parts = callback.data.split(":")
    hours = int(parts[1])
    count = int(parts[2])

    data = await state.get_data()
    channel_id = data.get("channel_id")
    channel_title = data.get("channel_title", "Kanal")
    topic = data.get("topic", "Umumiy bilimlar")

    if not channel_id:
        await callback.answer("Ma'lumotlar topilmadi, qaytadan boshlang", show_alert=True)
        return

    await add_channel_schedule(
        user_id=callback.from_user.id,
        channel_id=channel_id,
        channel_title=channel_title,
        topic=topic,
        question_count=count,
        interval_hours=hours,
    )
    await state.clear()
    await callback.answer("Jadval muvaffaqiyatli saqlandi! 🚀", show_alert=True)

    text = (
        f"🎉 <b>Avtoposting muvaffaqiyatli rejalashtirildi!</b>\n\n"
        f"📢 <b>Kanal:</b> {html.escape(channel_title, quote=False)}\n"
        f"📌 <b>Mavzu:</b> {html.escape(topic, quote=False)}\n"
        f"⏱ <b>Davriylik:</b> Har {hours} soatda {count} ta yangi AI testi\n\n"
        f"<i>Bot belgilangan vaqtda o'zi yangi testlar tuzib, kanalingizga chiroyli Quiz Poll qilib tashlab boradi!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Kanallar bo'limi", callback_data="menu:channels")]])
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("ch_del:"))
async def handle_channel_delete(callback: CallbackQuery) -> None:
    """Kanal jadvalini o'chirish."""
    schedule_id = int(callback.data.split(":")[1])
    await delete_channel_schedule(schedule_id, callback.from_user.id)
    await callback.answer("Jadval o'chirildi ✅")
    # Kanallar menyusini yangilash
    await handle_menu_channels(callback, None, callback.bot)
