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

# CRM: воронка мастера. Коды совпадают с CHECK-ограничениями в таблице leads.
LEAD_STATUSES = ("new", "contacted", "negotiation", "registration", "connected", "refused")
REFUSAL_REASONS = ("conditions", "price", "few_orders", "complex_registration",
                   "unclear_value", "missing_feature", "other")
FOLLOW_UP_REASONS = ("first_contact", "send_info", "call", "decide_later", "no_response",
                     "finish_registration", "check_activity")

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
        "role_question": "Чем могу помочь?",
        "role_master": "🧰 Я мастер — хочу получать заказы",
        "role_customer": "🏠 Мне нужен мастер",
        "master_about": (
            "Сервис помогает мастерам в Ереване получать заказы: заявки от заказчиков вашего "
            "района приходят прямо в Telegram, а вы сами выбираете, какие брать.\n\n"
            "Чтобы подключиться, ответьте на 4 вопроса — это займёт пару минут."
        ),
        "btn_master_join": "✅ Подключиться",
        "btn_master_info": "❓ Хочу подробности",
        "btn_master_later": "Не сейчас",
        "info_requested": "Хорошо! Менеджер напишет вам в ближайшее время.",
        "later_question": "Подскажите, почему не сейчас? Это поможет нам стать лучше.",
        "later_think": "🕓 Подумаю и вернусь позже",
        "later_thanks": "Договорились, напомню о себе через пару дней. Не хотите напоминаний — /stop.",
        "refused_thanks": "Спасибо за ответ! Если передумаете, просто нажмите /start.",
        "reason_conditions": "Не подходят условия",
        "reason_price": "Дорого",
        "reason_few_orders": "Мало заказов в моём районе",
        "reason_complex_registration": "Сложная регистрация",
        "reason_unclear_value": "Не понимаю, зачем мне это",
        "reason_missing_feature": "Не хватает нужной функции",
        "reason_other": "Другое",
        "ask_specialties": "Какие работы вы выполняете? Можно выбрать несколько, затем нажмите «Готово».",
        "ask_districts": "В каких районах готовы работать? Можно выбрать несколько.",
        "btn_done": "Готово ✅",
        "need_choice": "Выберите хотя бы один вариант.",
        "ask_consent": (
            "Можно присылать вам напоминания и новости сервиса? "
            "О ваших заказах бот будет писать в любом случае."
        ),
        "btn_yes": "Да",
        "btn_no": "Нет",
        "yes": "да",
        "no": "нет",
        "master_summary_title": "📋 Проверьте анкету:",
        "label_name": "Имя",
        "label_specialties": "Специализации",
        "label_districts": "Районы",
        "label_consent": "Напоминания и новости",
        "master_sent": (
            "✅ Анкета отправлена! Менеджер проверит её и подключит вас — "
            "обычно это занимает до одного рабочего дня."
        ),
        "master_approved": (
            "🎉 Вы подключены! Новые заказы будут приходить сюда.\n\n"
            "/new — свободные заявки\n/my — ваши заявки в работе"
        ),
        "master_rejected": (
            "К сожалению, сейчас мы не можем вас подключить. "
            "Менеджер свяжется с вами, если ситуация изменится."
        ),
        "already_master": "Вы уже в команде мастеров 👷\n/new — свободные заявки\n/my — ваши заявки в работе",
        "pending_master": "Ваша анкета на проверке у менеджера. Как только её одобрят, я напишу.",
        "reminder_finish": (
            "Вы начали подключение к сервису, но не закончили. Это займёт пару минут 🙂\n"
            "Не хотите напоминаний — /stop."
        ),
        "btn_continue": "Продолжить",
        "stopped": (
            "Хорошо, больше не будем присылать напоминания и новости. "
            "Уведомления о ваших заказах продолжат приходить."
        ),
        "cmd_stop": "Не присылать новости",
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
        "role_question": "How can I help?",
        "role_master": "🧰 I'm a handyman and want to get jobs",
        "role_customer": "🏠 I need a handyman",
        "master_about": (
            "We help handymen in Yerevan get jobs: requests from customers in your district come "
            "straight to Telegram, and you choose which ones to take.\n\n"
            "To join, answer 4 questions — it takes a couple of minutes."
        ),
        "btn_master_join": "✅ Join",
        "btn_master_info": "❓ Tell me more",
        "btn_master_later": "Not now",
        "info_requested": "Sure! A manager will message you shortly.",
        "later_question": "Could you tell us why not now? It helps us get better.",
        "later_think": "🕓 I'll think and come back later",
        "later_thanks": "Deal, I'll remind you in a couple of days. Don't want reminders? /stop.",
        "refused_thanks": "Thanks for your answer! If you change your mind, just press /start.",
        "reason_conditions": "The terms don't suit me",
        "reason_price": "Too expensive",
        "reason_few_orders": "Too few jobs in my district",
        "reason_complex_registration": "Registration is too complicated",
        "reason_unclear_value": "I don't see why I need it",
        "reason_missing_feature": "A feature I need is missing",
        "reason_other": "Other",
        "ask_specialties": "What kind of work do you do? Pick one or more, then press «Done».",
        "ask_districts": "Which districts are you ready to work in? You can pick several.",
        "btn_done": "Done ✅",
        "need_choice": "Please pick at least one option.",
        "ask_consent": (
            "May we send you reminders and service news? "
            "The bot will message you about your jobs either way."
        ),
        "btn_yes": "Yes",
        "btn_no": "No",
        "yes": "yes",
        "no": "no",
        "master_summary_title": "📋 Please check your profile:",
        "label_name": "Name",
        "label_specialties": "Specialties",
        "label_districts": "Districts",
        "label_consent": "Reminders and news",
        "master_sent": (
            "✅ Profile sent! A manager will review it and connect you — "
            "usually within one business day."
        ),
        "master_approved": (
            "🎉 You're connected! New jobs will come here.\n\n"
            "/new — open requests\n/my — your requests in progress"
        ),
        "master_rejected": (
            "Unfortunately, we can't connect you right now. "
            "A manager will contact you if things change."
        ),
        "already_master": "You're already on the team 👷\n/new — open requests\n/my — your requests in progress",
        "pending_master": "Your profile is being reviewed by a manager. I'll message you once it's approved.",
        "reminder_finish": (
            "You started joining the service but didn't finish. It takes a couple of minutes 🙂\n"
            "Don't want reminders? /stop."
        ),
        "btn_continue": "Continue",
        "stopped": (
            "OK, we won't send reminders or news anymore. "
            "Notifications about your jobs will keep coming."
        ),
        "cmd_stop": "Stop news and reminders",
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
        "role_question": "Ինչո՞վ կարող եմ օգնել։",
        "role_master": "🧰 Ես վարպետ եմ, ուզում եմ պատվերներ ստանալ",
        "role_customer": "🏠 Ինձ վարպետ է պետք",
        "master_about": (
            "Ծառայությունն օգնում է Երևանի վարպետներին պատվերներ ստանալ․ Ձեր թաղամասի "
            "հաճախորդների հայտերը գալիս են անմիջապես Telegram, և Դուք ինքներդ եք ընտրում, "
            "թե որոնք վերցնել։\n\n"
            "Միանալու համար պատասխանեք 4 հարցի․ դա կտևի ընդամենը մի քանի րոպե։"
        ),
        "btn_master_join": "✅ Միանալ",
        "btn_master_info": "❓ Ուզում եմ մանրամասներ",
        "btn_master_later": "Ոչ հիմա",
        "info_requested": "Լավ։ Մենեջերը շուտով կգրի Ձեզ։",
        "later_question": "Խնդրում ենք նշել, թե ինչու ոչ հիմա։ Դա կօգնի մեզ դառնալ ավելի լավը։",
        "later_think": "🕓 Կմտածեմ և կվերադառնամ ավելի ուշ",
        "later_thanks": "Պայմանավորվեցինք, մի քանի օրից կհիշեցնեմ։ Եթե չեք ուզում հիշեցումներ՝ /stop։",
        "refused_thanks": "Շնորհակալություն պատասխանի համար։ Եթե մտափոխվեք, պարզապես սեղմեք /start։",
        "reason_conditions": "Պայմանները չեն համապատասխանում",
        "reason_price": "Թանկ է",
        "reason_few_orders": "Իմ թաղամասում քիչ պատվերներ կան",
        "reason_complex_registration": "Գրանցումը բարդ է",
        "reason_unclear_value": "Չեմ հասկանում, թե ինչու է ինձ պետք",
        "reason_missing_feature": "Պակասում է անհրաժեշտ գործառույթը",
        "reason_other": "Այլ",
        "ask_specialties": (
            "Ի՞նչ աշխատանքներ եք կատարում։ Կարող եք ընտրել մի քանիսը, հետո սեղմեք «Պատրաստ է»։"
        ),
        "ask_districts": "Ո՞ր թաղամասերում եք պատրաստ աշխատել։ Կարող եք ընտրել մի քանիսը։",
        "btn_done": "Պատրաստ է ✅",
        "need_choice": "Ընտրեք առնվազն մեկ տարբերակ։",
        "ask_consent": (
            "Կարո՞ղ ենք Ձեզ ուղարկել հիշեցումներ և ծառայության նորություններ։ "
            "Ձեր պատվերների մասին բոտը կգրի ամեն դեպքում։"
        ),
        "btn_yes": "Այո",
        "btn_no": "Ոչ",
        "yes": "այո",
        "no": "ոչ",
        "master_summary_title": "📋 Ստուգեք հարցաթերթիկը՝",
        "label_name": "Անուն",
        "label_specialties": "Մասնագիտացումներ",
        "label_districts": "Թաղամասեր",
        "label_consent": "Հիշեցումներ և նորություններ",
        "master_sent": (
            "✅ Հարցաթերթիկն ուղարկված է։ Մենեջերը կստուգի այն և կմիացնի Ձեզ․ "
            "սովորաբար դա տևում է մինչև մեկ աշխատանքային օր։"
        ),
        "master_approved": (
            "🎉 Դուք միացված եք։ Նոր պատվերները կգան այստեղ։\n\n"
            "/new — ազատ հայտեր\n/my — Ձեր հայտերը, որոնք կատարման մեջ են"
        ),
        "master_rejected": (
            "Ցավոք, այս պահին չենք կարող Ձեզ միացնել։ "
            "Մենեջերը կկապվի Ձեզ հետ, եթե իրավիճակը փոխվի։"
        ),
        "already_master": (
            "Դուք արդեն վարպետների թիմում եք 👷\n"
            "/new — ազատ հայտեր\n/my — Ձեր հայտերը, որոնք կատարման մեջ են"
        ),
        "pending_master": "Ձեր հարցաթերթիկը մենեջերի մոտ ստուգման է։ Հենց հաստատեն, կգրեմ։",
        "reminder_finish": (
            "Դուք սկսել էիք միանալ ծառայությանը, բայց չավարտեցիք։ Դա կտևի ընդամենը մի քանի րոպե 🙂\n"
            "Եթե չեք ուզում հիշեցումներ՝ /stop։"
        ),
        "btn_continue": "Շարունակել",
        "stopped": (
            "Լավ, այլևս չենք ուղարկի հիշեցումներ և նորություններ։ "
            "Ձեր պատվերների մասին ծանուցումները կշարունակեն գալ։"
        ),
        "cmd_stop": "Չուղարկել նորություններ",
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
