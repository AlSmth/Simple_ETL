"""Воронка мастера — основного клиента сервиса: знакомство с сервисом → анкета
(специализации, районы, телефон, согласие на напоминания) → одобрение менеджером.
Каждый шаг меняет лида в CRM: статус, следующий контакт, причину отказа."""

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, User

from ..config import Config
from ..db import Database
from ..texts import CATEGORIES, DISTRICTS, REFUSAL_REASONS, t
from . import keyboards as kb
from ..phone import normalize_phone
from .common import esc, notify_managers, send_lead_card, user_lang
from .keyboards import REFUSAL_RU

router = Router(name="onboarding")

SELECT_FIELDS = {
    # поле анкеты -> (варианты, префикс текста кнопки, вопрос)
    "cats": (CATEGORIES, "cat_", "ask_specialties"),
    "dists": (tuple(DISTRICTS), "dist_", "ask_districts"),
}


class MasterForm(StatesGroup):
    cats = State()
    dists = State()
    phone = State()
    consent = State()
    confirm = State()


async def open_master_path(message: Message, user: User, db: Database, config: Config,
                           *, edit: bool) -> None:
    lang = await user_lang(db, user.id)
    lead = await db.leads.by_tg(user.id)
    master = await db.get_master(user.id)
    if lead and lead["status"] == "connected" and master and master["is_active"]:
        text, markup = t(lang, "already_master"), None
    elif lead and lead["status"] == "registration" and lead["registration_done_at"]:
        text, markup = t(lang, "pending_master"), None
    else:
        await db.leads.ensure_bot_lead(user.id, user.full_name, user.username, lang,
                                       config.script_version)
        text, markup = t(lang, "master_about"), kb.master_about_kb(lang)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "role:master")
async def role_master(callback: CallbackQuery, state: FSMContext, db: Database, config: Config):
    await state.clear()
    await open_master_path(callback.message, callback.from_user, db, config, edit=True)
    await callback.answer()


@router.message(Command("master"))
async def cmd_master(message: Message, state: FSMContext, db: Database, config: Config):
    await state.clear()
    await open_master_path(message, message.from_user, db, config, edit=False)


# ---------- «Хочу подробности» и «Не сейчас» ----------

@router.callback_query(F.data == "minfo")
async def wants_info(callback: CallbackQuery, db: Database, bot: Bot, config: Config):
    lang = await user_lang(db, callback.from_user.id)
    lead = await db.leads.by_tg(callback.from_user.id)
    if lead is None:
        await callback.answer(t(lang, "expired"), show_alert=True)
        return
    lead = await db.leads.request_info(lead["lead_id"])
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(t(lang, "info_requested"))
    await callback.answer()
    await send_lead_card(bot, config, lead, "❓ Мастер просит подробности")


@router.callback_query(F.data == "mlater")
async def not_now(callback: CallbackQuery, db: Database):
    lang = await user_lang(db, callback.from_user.id)
    await callback.message.edit_text(t(lang, "later_question"), reply_markup=kb.later_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "mthink")
async def think_later(callback: CallbackQuery, db: Database):
    lang = await user_lang(db, callback.from_user.id)
    lead = await db.leads.by_tg(callback.from_user.id)
    if lead:
        await db.leads.decide_later(lead["lead_id"])
    await callback.message.edit_text(t(lang, "later_thanks"))
    await callback.answer()


@router.callback_query(F.data.startswith("mrefuse:"))
async def refuse(callback: CallbackQuery, db: Database, bot: Bot, config: Config):
    reason = callback.data.split(":", 1)[1]
    lang = await user_lang(db, callback.from_user.id)
    lead = await db.leads.by_tg(callback.from_user.id)
    if reason not in REFUSAL_REASONS or lead is None:
        await callback.answer()
        return
    lead = await db.leads.refuse(lead["lead_id"], reason, via="lead")
    await callback.message.edit_text(t(lang, "refused_thanks"))
    await callback.answer()
    await notify_managers(bot, config, f"🚫 {esc(lead['full_name'])} (лид №{lead['lead_id']}) "
                                       f"отказался: {esc(REFUSAL_RU[reason])}")


# ---------- анкета ----------

@router.callback_query(F.data == "mjoin")
async def join(callback: CallbackQuery, state: FSMContext, db: Database, config: Config):
    lang = await user_lang(db, callback.from_user.id)
    user = callback.from_user
    lead = await db.leads.by_tg(user.id) or await db.leads.ensure_bot_lead(
        user.id, user.full_name, user.username, lang, config.script_version)
    if lead["status"] == "connected":
        await callback.message.edit_text(t(lang, "already_master"))
        await callback.answer()
        return
    lead = await db.leads.start_registration(lead)
    await state.clear()
    await state.update_data(lead_id=lead["lead_id"], cats=list(lead["categories"]),
                            dists=list(lead["districts"]))
    await state.set_state(MasterForm.cats)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(t(lang, "ask_specialties"), reply_markup=kb.multiselect_kb(
        lang, "cats", CATEGORIES, "cat_", list(lead["categories"])))
    await callback.answer()


@router.callback_query(F.data.startswith("msel:"))
async def toggle(callback: CallbackQuery, state: FSMContext, db: Database):
    _, field, code = callback.data.split(":", 2)
    if field not in SELECT_FIELDS or await state.get_state() != getattr(MasterForm, field).state:
        await callback.answer()
        return
    codes, prefix, _ = SELECT_FIELDS[field]
    if code not in codes:
        await callback.answer()
        return
    lang = await user_lang(db, callback.from_user.id)
    selected = (await state.get_data()).get(field, [])
    selected = [c for c in selected if c != code] if code in selected else selected + [code]
    await state.update_data({field: selected})
    await callback.message.edit_reply_markup(
        reply_markup=kb.multiselect_kb(lang, field, codes, prefix, selected))
    await callback.answer()


@router.callback_query(F.data.startswith("mdone:"))
async def done_select(callback: CallbackQuery, state: FSMContext, db: Database):
    field = callback.data.split(":", 1)[1]
    if field not in SELECT_FIELDS or await state.get_state() != getattr(MasterForm, field).state:
        await callback.answer()
        return
    lang = await user_lang(db, callback.from_user.id)
    selected = (await state.get_data()).get(field, [])
    if not selected:
        await callback.answer(t(lang, "need_choice"), show_alert=True)
        return
    codes, prefix, _ = SELECT_FIELDS[field]
    labels = ", ".join(t(lang, prefix + c) for c in codes if c in selected)
    await callback.message.edit_text(f"<b>{esc(labels)}</b>")
    await callback.answer()
    if field == "cats":
        await state.set_state(MasterForm.dists)
        await callback.message.answer(t(lang, "ask_districts"), reply_markup=kb.multiselect_kb(
            lang, "dists", tuple(DISTRICTS), "dist_", (await state.get_data()).get("dists", [])))
    else:
        await state.set_state(MasterForm.phone)
        await callback.message.answer(t(lang, "ask_phone"), reply_markup=kb.phone_kb(lang))


@router.message(MasterForm.phone)
async def got_phone(message: Message, state: FSMContext, db: Database):
    lang = await user_lang(db, message.from_user.id)
    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw) if raw else None
    if phone is None:
        await message.answer(t(lang, "bad_phone"))
        return
    await state.update_data(phone=phone)
    await message.answer(f"📞 +{phone}", reply_markup=ReplyKeyboardRemove())
    await state.set_state(MasterForm.consent)
    await message.answer(t(lang, "ask_consent"), reply_markup=kb.consent_kb(lang))


@router.callback_query(MasterForm.consent, F.data.startswith("mconsent:"))
async def got_consent(callback: CallbackQuery, state: FSMContext, db: Database):
    lang = await user_lang(db, callback.from_user.id)
    consent = callback.data == "mconsent:yes"
    await state.update_data(consent=consent)
    await state.set_state(MasterForm.confirm)
    await callback.message.edit_text(f"<b>{t(lang, 'label_consent')}:</b> {t(lang, 'yes' if consent else 'no')}")
    await callback.answer()

    data = await state.get_data()
    lines = [
        f"<b>{t(lang, 'master_summary_title')}</b>",
        "",
        f"<b>{t(lang, 'label_name')}:</b> {esc(callback.from_user.full_name)}",
        f"<b>{t(lang, 'label_specialties')}:</b> "
        + esc(", ".join(t(lang, "cat_" + c) for c in CATEGORIES if c in data["cats"])),
        f"<b>{t(lang, 'label_districts')}:</b> "
        + esc(", ".join(t(lang, "dist_" + d) for d in DISTRICTS if d in data["dists"])),
        f"<b>{t(lang, 'label_phone')}:</b> +{data['phone']}",
        f"<b>{t(lang, 'label_consent')}:</b> {t(lang, 'yes' if consent else 'no')}",
    ]
    await callback.message.answer("\n".join(lines), reply_markup=kb.master_confirm_kb(lang))


@router.callback_query(MasterForm.confirm, F.data.startswith("mconfirm:"))
async def confirm(callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot,
                  config: Config):
    lang = await user_lang(db, callback.from_user.id)
    data = await state.get_data()
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    if callback.data != "mconfirm:send":
        # анкета брошена — лид остаётся в регистрации, бот напомнит позже
        await callback.message.answer(t(lang, "cancelled"))
        return
    lead = await db.leads.save_registration(
        data["lead_id"], full_name=callback.from_user.full_name, phone=data["phone"],
        categories=[c for c in CATEGORIES if c in data["cats"]],
        districts=[d for d in DISTRICTS if d in data["dists"]], consent=data["consent"],
    )
    await callback.message.answer(t(lang, "master_sent"))
    await send_lead_card(bot, config, lead, "📝 Анкета мастера — подключить?")
