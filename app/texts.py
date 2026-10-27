"""Тексты для заказчиков на трёх языках. Мастера и менеджеры работают на русском,
их тексты лежат рядом с хендлерами."""

LANGS = ("ru", "en", "hy")
DEFAULT_LANG = "en"

LANG_BUTTONS = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "hy": "🇦🇲 Հայերեն",
}

# Порядок = порядок кнопок. Коды совпадают с categories.code в базе.
CATEGORIES = ("plumbing", "electrical", "installation", "furniture", "repair", "appliances", "other")

CONTACT_METHODS = ("telegram", "whatsapp", "phone")

ORDER_STATUSES = ("new", "assigned", "done", "cancelled")

# Районы Еревана: код в базе -> (ru, en, hy). Последний — «другой».
DISTRICTS = {
    "ajapnyak": ("Аджапняк", "Ajapnyak", "Աջափնյակ"),
    "arabkir": ("Арабкир", "Arabkir", "Արաբկիր"),
    "avan": ("Аван", "Avan", "Ավան"),
    "davtashen": ("Давташен", "Davtashen", "Դավթաշեն"),
    "erebuni": ("Эребуни", "Erebuni", "Էրեբունի"),
    "kanaker_zeytun": ("Канакер-Зейтун", "Kanaker-Zeytun", "Քանաքեռ-Զեյթուն"),
    "kentron": ("Кентрон", "Kentron", "Կենտրոն"),
    "malatia_sebastia": ("Малатия-Себастия", "Malatia-Sebastia", "Մալաթիա-Սեբաստիա"),
    "nork_marash": ("Норк-Мараш", "Nork-Marash", "Նորք-Մարաշ"),
    "nor_nork": ("Нор-Норк", "Nor Nork", "Նոր Նորք"),
    "nubarashen": ("Нубарашен", "Nubarashen", "Նուբարաշեն"),
    "shengavit": ("Шенгавит", "Shengavit", "Շենգավիթ"),
    "other": ("Другой / за городом", "Other / outside Yerevan", "Այլ / Երևանից դուրս"),
}

TEXTS = {
    "ru": {
        "choose_language": "🌐 Выберите язык · Choose your language · Ընտրեք լեզուն",
        "welcome": (
            "Здравствуйте! 👋 Я помогу оставить заявку на мелкий ремонт и бытовые работы в Ереване.\n\n"
            "Выберите, что нужно:"
        ),
        "ask_description": (
            "Коротко опишите проблему: что случилось и что нужно сделать.\n"
            "Можно приложить фото 📷"
        ),
        "ask_district": "В каком районе? 📍",
        "ask_address": "Укажите адрес: улица, дом, квартира 🏠",
        "ask_contact": "Как вам удобнее связаться?",
        "ask_phone": "Введите номер телефона (например, +374 91 123456) или нажмите кнопку ниже.",
        "share_phone_btn": "📱 Отправить мой номер",
        "bad_phone": "Это не похоже на номер телефона. Попробуйте ещё раз, например: +374 91 123456",
        "need_description": "Пожалуйста, отправьте текстовое описание или фото с подписью.",
        "need_text": "Пожалуйста, отправьте ответ текстом.",
        "description_too_long": "Слишком длинный текст. Сократите, пожалуйста, до {limit} символов.",
        "summary_title": "📋 Проверьте заявку:",
        "summary_confirm": "Отправить мастерам?",
        "has_photo": "фото приложено",
        "btn_send": "✅ Отправить",
        "btn_cancel": "❌ Отменить",
        "sent": (
            "✅ Заявка №{id} отправлена!\n"
            "Как только мастер возьмёт её, я сообщу. Способ связи: {contact}.\n"
            "Ваши заявки: /orders"
        ),
        "cancelled": "Заявка отменена. Чтобы создать новую, нажмите /start.",
        "expired": "Сессия устарела. Начните заново: /start",
        "label_category": "Категория",
        "label_problem": "Проблема",
        "label_district": "Район",
        "label_address": "Адрес",
        "label_contact": "Способ связи",
        "label_phone": "Телефон",
        "my_orders_title": "📋 Ваши заявки:",
        "no_orders": "У вас пока нет заявок. Создать: /start",
        "status_new": "🟢 Ищем мастера",
        "status_assigned": "👷 Мастер назначен",
        "status_done": "✅ Выполнена",
        "status_cancelled": "⚪️ Отменена",
        "btn_cancel_order": "❌ Отменить №{id}",
        "order_cancelled": "Заявка №{id} отменена.",
        "cannot_cancel": (
            "Эту заявку уже нельзя отменить: мастер взял её в работу. Свяжитесь с ним напрямую."
        ),
        "notify_assigned": "👷 Мастер {master} взял вашу заявку №{id} и скоро свяжется с вами.",
        "notify_released": "Мастер не сможет выполнить заявку №{id}. Ищем другого мастера.",
        "notify_done": "✅ Заявка №{id} выполнена. Спасибо, что обратились!",
        "cat_plumbing": "🚰 Сантехника",
        "cat_electrical": "💡 Электрика",
        "cat_installation": "🔧 Установка и монтаж",
        "cat_furniture": "🪑 Сборка мебели",
        "cat_repair": "🛠 Мелкий ремонт",
        "cat_appliances": "🔌 Бытовая техника",
        "cat_other": "📦 Другое",
        "contact_telegram": "✈️ Telegram",
        "contact_whatsapp": "💬 WhatsApp",
        "contact_phone": "📞 Звонок",
        "cmd_start": "Новая заявка",
        "cmd_orders": "Мои заявки",
        "cmd_language": "Сменить язык",
        "cmd_cancel": "Отменить заполнение",
    },
    "en": {
        "choose_language": "🌐 Choose your language · Выберите язык · Ընտրեք լեզուն",
        "welcome": (
            "Hello! 👋 I'll help you request a handyman for repairs and household jobs in Yerevan.\n\n"
            "What do you need?"
        ),
        "ask_description": (
            "Briefly describe the problem: what happened and what needs to be done.\n"
            "You can attach a photo 📷"
        ),
        "ask_district": "Which district? 📍",
        "ask_address": "Send the address: street, building, apartment 🏠",
        "ask_contact": "How would you like to be contacted?",
        "ask_phone": "Enter your phone number (e.g. +374 91 123456) or tap the button below.",
        "share_phone_btn": "📱 Share my number",
        "bad_phone": "That doesn't look like a phone number. Please try again, e.g. +374 91 123456",
        "need_description": "Please send a text description or a photo with a caption.",
        "need_text": "Please reply with text.",
        "description_too_long": "The text is too long. Please shorten it to {limit} characters.",
        "summary_title": "📋 Please check your request:",
        "summary_confirm": "Send it to the handymen?",
        "has_photo": "photo attached",
        "btn_send": "✅ Send",
        "btn_cancel": "❌ Cancel",
        "sent": (
            "✅ Request #{id} has been sent!\n"
            "I'll let you know as soon as a handyman takes it. Contact method: {contact}.\n"
            "Your requests: /orders"
        ),
        "cancelled": "Request cancelled. Press /start to create a new one.",
        "expired": "Session expired. Please start again: /start",
        "label_category": "Category",
        "label_problem": "Problem",
        "label_district": "District",
        "label_address": "Address",
        "label_contact": "Contact method",
        "label_phone": "Phone",
        "my_orders_title": "📋 Your requests:",
        "no_orders": "You have no requests yet. Create one: /start",
        "status_new": "🟢 Looking for a handyman",
        "status_assigned": "👷 Handyman assigned",
        "status_done": "✅ Done",
        "status_cancelled": "⚪️ Cancelled",
        "btn_cancel_order": "❌ Cancel #{id}",
        "order_cancelled": "Request #{id} has been cancelled.",
        "cannot_cancel": (
            "This request can't be cancelled anymore: a handyman is already on it. "
            "Please contact them directly."
        ),
        "notify_assigned": "👷 Handyman {master} has taken your request #{id} and will contact you soon.",
        "notify_released": "The handyman can't do request #{id} after all. We're looking for another one.",
        "notify_done": "✅ Request #{id} is done. Thank you for choosing us!",
        "cat_plumbing": "🚰 Plumbing",
        "cat_electrical": "💡 Electrical",
        "cat_installation": "🔧 Installation & mounting",
        "cat_furniture": "🪑 Furniture assembly",
        "cat_repair": "🛠 Minor repairs",
        "cat_appliances": "🔌 Home appliances",
        "cat_other": "📦 Other",
        "contact_telegram": "✈️ Telegram",
        "contact_whatsapp": "💬 WhatsApp",
        "contact_phone": "📞 Phone call",
        "cmd_start": "New request",
        "cmd_orders": "My requests",
        "cmd_language": "Change language",
        "cmd_cancel": "Stop filling in",
    },
    "hy": {
        "choose_language": "🌐 Ընտրեք լեզուն · Выберите язык · Choose your language",
        "welcome": (
            "Բարև Ձեզ։ 👋 Ես կօգնեմ Երևանում թողնել հայտ մանր վերանորոգման և կենցաղային աշխատանքների համար։\n\n"
            "Ընտրեք, թե ինչ է պետք՝"
        ),
        "ask_description": (
            "Համառոտ նկարագրեք խնդիրը՝ ինչ է պատահել և ինչ է պետք անել։\n"
            "Կարող եք կցել նաև լուսանկար 📷"
        ),
        "ask_district": "Ո՞ր վարչական շրջանում։ 📍",
        "ask_address": "Նշեք հասցեն՝ փողոց, շենք, բնակարան 🏠",
        "ask_contact": "Ինչպե՞ս է Ձեզ հարմար կապ հաստատել։",
        "ask_phone": "Մուտքագրեք հեռախոսահամարը (օր.՝ +374 91 123456) կամ սեղմեք ներքևի կոճակը։",
        "share_phone_btn": "📱 Ուղարկել իմ համարը",
        "bad_phone": "Սա հեռախոսահամարի նման չէ։ Փորձեք նորից, օրինակ՝ +374 91 123456",
        "need_description": "Խնդրում եմ ուղարկեք տեքստային նկարագրություն կամ լուսանկար՝ ստորագրությամբ։",
        "need_text": "Խնդրում եմ պատասխանեք տեքստով։",
        "description_too_long": "Տեքստը չափազանց երկար է։ Խնդրում եմ կրճատեք մինչև {limit} նիշ։",
        "summary_title": "📋 Ստուգեք հայտը՝",
        "summary_confirm": "Ուղարկե՞լ վարպետներին։",
        "has_photo": "լուսանկարը կցված է",
        "btn_send": "✅ Ուղարկել",
        "btn_cancel": "❌ Չեղարկել",
        "sent": (
            "✅ Հայտ №{id}-ը ուղարկված է։\n"
            "Հենց վարպետը վերցնի այն, կտեղեկացնեմ։ Կապի եղանակ՝ {contact}։\n"
            "Ձեր հայտերը՝ /orders"
        ),
        "cancelled": "Հայտը չեղարկված է։ Նորը ստեղծելու համար սեղմեք /start։",
        "expired": "Սեսիան ավարտվել է։ Սկսեք նորից՝ /start",
        "label_category": "Կատեգորիա",
        "label_problem": "Խնդիր",
        "label_district": "Շրջան",
        "label_address": "Հասցե",
        "label_contact": "Կապի եղանակ",
        "label_phone": "Հեռախոս",
        "my_orders_title": "📋 Ձեր հայտերը՝",
        "no_orders": "Դուք դեռ հայտեր չունեք։ Ստեղծել՝ /start",
        "status_new": "🟢 Վարպետ ենք փնտրում",
        "status_assigned": "👷 Վարպետը նշանակված է",
        "status_done": "✅ Կատարված է",
        "status_cancelled": "⚪️ Չեղարկված է",
        "btn_cancel_order": "❌ Չեղարկել №{id}",
        "order_cancelled": "№{id} հայտը չեղարկված է։",
        "cannot_cancel": (
            "Այս հայտն այլևս հնարավոր չէ չեղարկել՝ վարպետն արդեն զբաղվում է դրանով։ "
            "Կապվեք նրա հետ անմիջապես։"
        ),
        "notify_assigned": "👷 Վարպետ {master}-ը վերցրել է Ձեր №{id} հայտը և շուտով կկապվի Ձեզ հետ։",
        "notify_released": "Վարպետը չի կարող կատարել №{id} հայտը։ Փնտրում ենք այլ վարպետ։",
        "notify_done": "✅ №{id} հայտը կատարված է։ Շնորհակալություն, որ դիմեցիք մեզ։",
        "cat_plumbing": "🚰 Սանտեխնիկա",
        "cat_electrical": "💡 Էլեկտրականություն",
        "cat_installation": "🔧 Տեղադրում և մոնտաժ",
        "cat_furniture": "🪑 Կահույքի հավաքում",
        "cat_repair": "🛠 Մանր վերանորոգում",
        "cat_appliances": "🔌 Կենցաղային տեխնիկա",
        "cat_other": "📦 Այլ",
        "contact_telegram": "✈️ Telegram",
        "contact_whatsapp": "💬 WhatsApp",
        "contact_phone": "📞 Հեռախոսազանգ",
        "cmd_start": "Նոր հայտ",
        "cmd_orders": "Իմ հայտերը",
        "cmd_language": "Փոխել լեզուն",
        "cmd_cancel": "Դադարեցնել լրացումը",
    },
}

for _code, _names in DISTRICTS.items():
    for _lang, _name in zip(LANGS, _names):
        TEXTS[_lang][f"dist_{_code}"] = _name


def t(lang: str, key: str, **kwargs) -> str:
    text = TEXTS.get(lang, TEXTS[DEFAULT_LANG])[key]
    return text.format(**kwargs) if kwargs else text
