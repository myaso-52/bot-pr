import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import sqlite3
import time
import threading
import random
import re
import config

vk_session = vk_api.VkApi(token=config.TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

conn = sqlite3.connect("pr.db", check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS texts (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, active INTEGER DEFAULT 1)")
conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, role TEXT DEFAULT 'пользователь', requests INTEGER DEFAULT 0)")
conn.commit()

conn.execute("INSERT OR IGNORE INTO users (user_id, role) VALUES (827888215, 'разработчик')")
conn.execute("INSERT OR IGNORE INTO users (user_id, role) VALUES (864686414, 'разработчик')")
conn.commit()

ROLES = {4: "разработчик", 3: "тех.администратор", 2: "администратор", 1: "пользователь", -1: "заблокирован"}
ALLOWED = ["разработчик", "тех.администратор", "администратор", "пользователь"]

def get_role(uid):
    row = conn.execute("SELECT role FROM users WHERE user_id=?", (uid,)).fetchone()
    return row[0] if row else "пользователь"

def set_role(uid, role):
    conn.execute("INSERT OR REPLACE INTO users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit()

def get_interval():
    row = conn.execute("SELECT value FROM settings WHERE key='interval'").fetchone()
    return int(row[0]) if row else 3600

def get_active():
    row = conn.execute("SELECT value FROM settings WHERE key='active'").fetchone()
    return row[0] == '1' if row else True

def send_msg(peer_id, text, keyboard=None):
    try:
        params = {"peer_id": peer_id, "message": text, "random_id": 0}
        if keyboard:
            params["keyboard"] = keyboard
        vk.messages.send(**params)
    except Exception as e:
        err = str(e)
        if "kicked" in err.lower() or "7]" in err:
            print(f"чат {peer_id} недоступен, удаляю")
            conn.execute("DELETE FROM chats WHERE id=?", (peer_id,))
            conn.commit()
        else:
            print(f"ошибка отправки: {e}")

def get_main_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button("Помощь", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Статистика", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Запросить доступ", color=VkKeyboardColor.POSITIVE)
    return kb.get_keyboard()

def piar_loop():
    while True:
        if get_active():
            texts = conn.execute("SELECT text FROM texts").fetchall()
            chats = conn.execute("SELECT id FROM chats WHERE active=1").fetchall()
            if texts and chats:
                t = random.choice(texts)[0]
                kb = VkKeyboard(inline=True)
                kb.add_openlink_button("Залутать", link="https://vk.ru/write-221392393?ref=827888215")
                for chat in chats:
                    send_msg(chat[0], t, keyboard=kb.get_keyboard())
        time.sleep(get_interval())

threading.Thread(target=piar_loop, daemon=True).start()
# Авто-добавление всех чатов где бот есть
try:
    convs = vk.messages.getConversations(count=200)
    added = 0
    for conv in convs['items']:
        peer = conv['conversation']['peer']['id']
        if peer > 2000000000:
            conn.execute("INSERT OR IGNORE INTO chats (id, active) VALUES (?, 1)", (peer,))
            added += 1
    conn.commit()
    print(f"найдено {added} чатов")
except Exception as e:
    print(f"ошибка сканирования: {e}")

print("бот пиара запущен")

last_msg = ("", 0, 0)
for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        # Защита от дублей: одинаковый текст от того же юзера за 1 сек
        now = time.time()
        if event.text == last_msg[0] and event.user_id == last_msg[1] and now - last_msg[2] < 3:
            continue
        last_msg = (event.text, event.user_id, now)
        peer_id = event.peer_id
        uid = event.user_id
        text = event.text
        role = get_role(uid)
        print(f"[{uid}|{role}] {text}")

        text_lower = text.lower().strip()

        if text_lower in ["начать", "меню", "привет", "старт"]:
            if role in ALLOWED:
                send_msg(peer_id, "бот для пиара. выберите действие:", keyboard=get_main_keyboard())
            elif role == "заблокирован":
                send_msg(peer_id, "вы заблокированы")
            else:
                send_msg(peer_id, "нет доступа. добавьте бота в 3 чата от 200 человек и отпишите @dimo4kaenergy")
            continue

        if text in ["Помощь", ".помощь"]:
            if role not in ALLOWED:
                send_msg(peer_id, "нет доступа. чтобы получить - добавьте бота в 3 пиар чата от 200 человек и отпишите @dimo4kaenergy")
                continue
            help_text = "📋 КОМАНДЫ ПИАР БОТА:\n\n📝 пиар (текст) - добавить текст для рассылки\n📋 список - показать все тексты\n🗑 удалить (номер) - удалить текст\n⏱ интервал (сек) - частота постинга\n📊 инфо - статус и кол-во чатов/текстов\n📊 //info - подробная статистика\n⏹ стоп - остановить пиар\n▶️ старт - запустить пиар\n💬 чат (ID) - добавить чат вручную\n📋 чаты - список чатов с названиями\n🔍 scan - найти все доступные чаты\n🗑 //dl - удалить недоступные чаты\n🆔 chatid - узнать ID чата\n👤 стата (ID) - профиль пользователя"
            if role == "разработчик":
                help_text += "\n\n🔧 ДЛЯ РАЗРАБОТЧИКА:\n👥 стафф - список администрации\n👥 users - все пользователи\n📩 запросы - запросы доступа\n🔑 rang (ID) (ранг) - выдать роль\n❌ delacc (ID) - удалить пользователя"
            help_text += "\n\n❓ помощь - это сообщение"
            send_msg(peer_id, help_text)
            continue

        if text == "Статистика":
            if role not in ALLOWED:
                send_msg(peer_id, "нет доступа. чтобы получить - добавьте бота в 3 пиар чата от 200 человек и отпишите @dimo4kaenergy")
                continue
            chats_count = conn.execute("SELECT COUNT(*) FROM chats WHERE active=1").fetchone()[0]
            texts_count = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
            active_status = "запущен" if get_active() else "остановлен"
            send_msg(peer_id, f"чатов: {chats_count}\nтекстов: {texts_count}\nстатус: {active_status}\nинтервал: {get_interval()}с")
            continue

        if text == "Запросить доступ":
            if role in ALLOWED:
                send_msg(peer_id, "у вас уже есть доступ")
            elif role == "заблокирован":
                send_msg(peer_id, "вы заблокированы")
            else:
                req = (conn.execute("SELECT requests FROM users WHERE user_id=?", (uid,)).fetchone() or [0])[0]
                if req > 0:
                    send_msg(peer_id, "запрос уже отправлен. ожидайте")
                    continue
                conn.execute("INSERT OR REPLACE INTO users (user_id, requests, role, reg_date) VALUES (?, 1, 'пользователь', ?)", (uid, time.strftime('%d.%m.%Y')))
                conn.commit()
                send_msg(peer_id, "запрос отправлен разработчику")
                try:
                    u = vk.users.get(user_ids=uid)[0]
                    name = f"{u['first_name']} {u['last_name']}"
                except:
                    name = f"ID {uid}"
                send_msg(827888215, f"{name} запросил доступ\n\nодобрить: rang 1 {uid}\nотказать: rang 0 {uid}")
            continue

        # Команды без префикса
        cmd = text.strip().lower()
        if cmd.startswith("."):
            cmd = cmd[1:]
        parts = cmd.split()
        if not parts:
            continue

        first = parts[0]

        if first == "запросы":
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            reqs = conn.execute("SELECT user_id, requests FROM users WHERE requests > 0 ORDER BY requests DESC LIMIT 10").fetchall()
            if reqs:
                txt = "запросы:\n" + "\n".join([f"[id{r[0]}|ID{r[0]}]: {r[1]}" for r in reqs])
            else:
                txt = "нет запросов"
            send_msg(peer_id, txt)
            continue

        if role == "заблокирован":
            send_msg(peer_id, "вы заблокированы в боте")
            continue
        if role not in ALLOWED:
            send_msg(peer_id, "нет доступа. чтобы получить - добавьте бота в 3 пиар чата от 200 человек и отпишите @dimo4kaenergy")
            continue

        if first == "delacc":
            if len(parts) < 2:
                send_msg(peer_id, "использование: delacc (ID)")
                continue
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            target_id = None
            if parts[1].isdigit():
                target_id = int(parts[1])
            elif '[id' in parts[1]:
                match = re.search(r'\[id(\d+)', parts[1])
                if match: target_id = int(match.group(1))
            if target_id:
                conn.execute("DELETE FROM users WHERE user_id=?", (target_id,))
                conn.commit()
                send_msg(peer_id, f"пользователь {target_id} удален из базы")
            else:
                send_msg(peer_id, "delacc (ID)")
            continue

        if first == "//scan" or first == "scan":
            try:
                convs = vk.messages.getConversations(count=200)
                added = 0
                for conv in convs['items']:
                    peer = conv['conversation']['peer']['id']
                    if peer > 2000000000:
                        exists = conn.execute("SELECT id FROM chats WHERE id=?", (peer,)).fetchone()
                        if not exists:
                            conn.execute("INSERT OR IGNORE INTO chats (id, active) VALUES (?, 1)", (peer,))
                            added += 1
                conn.commit()
                send_msg(peer_id, f"найдено и добавлено {added} чатов")
            except Exception as e:
                send_msg(peer_id, f"ошибка: {e}")
            continue

        if first == "//dl" or first == "dl":
            chats = conn.execute("SELECT id FROM chats WHERE active=1").fetchall()
            removed = 0
            for chat in chats:
                try:
                    vk.messages.send(peer_id=chat[0], message=".", random_id=0)
                except:
                    conn.execute("DELETE FROM chats WHERE id=?", (chat[0],))
                    removed += 1
            conn.commit()
            send_msg(peer_id, f"удалено {removed} недоступных чатов")
            continue

        if first == "//chts" or first == "chts":
            chats = conn.execute("SELECT id FROM chats WHERE active=1").fetchall()
            if chats:
                txt = "чаты (" + str(len(chats)) + "):\n" + "\n".join([str(c[0]) for c in chats])
            else:
                txt = "нет чатов"
            send_msg(peer_id, txt)
            continue

        if first == "//chatid" or first == "chatid":
            send_msg(peer_id, f"ID: {peer_id}")
            continue

        if first in ["стафф", ".стафф", "staff", ".staff", "админы", ".админы"]:
            staff = conn.execute("SELECT user_id, role FROM users WHERE role IN ('разработчик', 'тех.администратор', 'администратор') ORDER BY CASE role WHEN 'разработчик' THEN 1 WHEN 'тех.администратор' THEN 2 WHEN 'администратор' THEN 3 END").fetchall()
            if staff:
                txt = "👥 СТАФФ:\n\n"
                for s in staff:
                    try:
                        u = vk.users.get(user_ids=s[0])[0]
                        name = f"{u['first_name']} {u['last_name']}"
                    except:
                        name = f"ID {s[0]}"
                    emoji = "👑" if s[1] == "разработчик" else "🔧" if s[1] == "тех.администратор" else "🛡"
                    txt += f"{emoji} [id{s[0]}|{name}]: {s[1]}\n"
            else:
                txt = "нет администраторов"
            send_msg(peer_id, txt)
            continue

        if first == "//users" or first == "users":
            users = conn.execute("SELECT user_id, role FROM users WHERE role = 'пользователь' ORDER BY user_id LIMIT 50").fetchall()
            if users:
                txt = "пользователи (" + str(len(users)) + "):\n" + "\n".join([f"[id{u[0]}|ID{u[0]}]" for u in users])
            else:
                txt = "нет пользователей"
            send_msg(peer_id, txt)
            continue

        
        if first == "чаты":
            chats = conn.execute("SELECT id FROM chats WHERE active=1").fetchall()
            if chats:
                txt = "чаты:\n"
                for c in chats:
                    try:
                        info = vk.messages.getConversationsById(peer_ids=c[0])
                        title = info['items'][0]['chat_settings']['title'] if info['items'] else "без названия"
                    except:
                        title = "недоступен"
                    txt += f"{c[0]}: {title}\n"
                send_msg(peer_id, txt)
            else:
                send_msg(peer_id, "нет чатов")
            continue

        if first == "//info" or first == "info":
            chats_count = conn.execute("SELECT COUNT(*) FROM chats WHERE active=1").fetchone()[0]
            texts_count = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
            interval = get_interval()
            sent_total = texts_count * chats_count if texts_count and chats_count else 0
            send_msg(peer_id, f"статус: {'запущен' if get_active() else 'остановлен'}\nинтервал: {interval}с\nчатов: {chats_count}\nтекстов: {texts_count}\nотправлено за цикл: {sent_total}")
            continue

        if first == "инфо":
            chats_count = conn.execute("SELECT COUNT(*) FROM chats WHERE active=1").fetchone()[0]
            texts_count = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
            active_status = "запущен" if get_active() else "остановлен"
            send_msg(peer_id, f"статус: {active_status}\nинтервал: {get_interval()}с\nчатов: {chats_count}\nтекстов: {texts_count}")
            continue

        if first == "пиар":
            if len(parts) < 2:
                send_msg(peer_id, "использование: пиар (текст)")
                continue
            t = " ".join(parts[1:])
            conn.execute("INSERT INTO texts (text) VALUES (?)", (t,))
            conn.commit()
            send_msg(peer_id, "добавлено")
        elif first == "список":
            texts = conn.execute("SELECT id, text FROM texts").fetchall()
            if texts:
                txt = "тексты:\n" + "\n".join([f"{t[0]}. {t[1][:50]}" for t in texts])
            else:
                txt = "нет текстов"
            send_msg(peer_id, txt)
        elif first == "удалить":
            if len(parts) < 2:
                send_msg(peer_id, "использование: удалить (номер)")
                continue
            try:
                tid = int(parts[1])
                conn.execute("DELETE FROM texts WHERE id=?", (tid,))
                conn.commit()
                send_msg(peer_id, "удалено")
            except:
                send_msg(peer_id, "ошибка")
        elif first == "интервал":
            if len(parts) < 2:
                send_msg(peer_id, "использование: интервал (секунды)")
                continue
            try:
                val = int(parts[1])
                conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('interval',?)", (str(val),))
                conn.commit()
                send_msg(peer_id, f"интервал: {parts[1]}с")
            except:
                send_msg(peer_id, "ошибка")
        elif first == "стоп":
            conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('active','0')")
            conn.commit()
            send_msg(peer_id, "пиар остановлен")
        elif first == "старт":
            conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('active','1')")
            conn.commit()
            send_msg(peer_id, "пиар запущен")
        elif first == "чат":
            if len(parts) < 2 and peer_id <= 2000000000:
                send_msg(peer_id, "использование: чат (ID)")
                continue
            if len(parts) > 1:
                try:
                    chat_id = int(parts[1])
                    exists = conn.execute("SELECT id FROM chats WHERE id=?", (chat_id,)).fetchone()
                    if exists:
                        send_msg(peer_id, f"чат {chat_id} уже добавлен")
                        continue
                    try:
                        vk.messages.send(peer_id=chat_id, message=".", random_id=0)
                        conn.execute("INSERT OR REPLACE INTO chats (id, active) VALUES (?, 1) ON CONFLICT(id) DO UPDATE SET active=1", (chat_id,))
                        conn.commit()
                        send_msg(peer_id, f"чат {chat_id} добавлен")
                    except Exception as e:
                        if "kicked" in str(e).lower() or "7]" in str(e):
                            send_msg(peer_id, f"чат {chat_id} недоступен (бота кикнули)")
                        elif "917" in str(e):
                            send_msg(peer_id, f"чат {chat_id} недоступен (бота нет в чате)")
                        else:
                            send_msg(peer_id, f"чат {chat_id} недоступен")
                except:
                    send_msg(peer_id, "чат (ID)")
            elif peer_id > 2000000000:
                exists = conn.execute("SELECT id FROM chats WHERE id=?", (peer_id,)).fetchone()
                if exists:
                    send_msg(peer_id, "чат уже добавлен")
                else:
                    conn.execute("INSERT OR REPLACE INTO chats (id, active) VALUES (?, 1) ON CONFLICT(id) DO UPDATE SET active=1", (peer_id,))
                    conn.commit()
                    send_msg(peer_id, "чат добавлен")
            else:
                send_msg(peer_id, "чат (ID) - укажите ID чата")
        elif first == "стата":
            target_uid = uid
            if len(parts) > 1:
                target_text = parts[1]
                if target_text.isdigit():
                    target_uid = int(target_text)
                elif "[id" in target_text:
                    match = re.search(r"\[id(\d+)", target_text)
                    if match: target_uid = int(match.group(1))
            target_role = get_role(target_uid)
            reqs = conn.execute("SELECT requests, reg_date FROM users WHERE user_id=?", (target_uid,)).fetchone()
            reg_date = reqs[1] if reqs and len(reqs) > 1 else "неизвестно"
            try:
                u = vk.users.get(user_ids=target_uid)[0]
                name = f"{u['first_name']} {u['last_name']}"
            except:
                name = f"ID {target_uid}"
            send_msg(peer_id, f"👤 {name}\n🆔 ID: {target_uid}\n🔰 Роль: {target_role}\n📅 Регистрация: {reg_date}")
        elif first == "помощь":
            send_msg(peer_id, "команды пиар бота:\n\n📝 пиар (текст) — добавить текст\n📋 список — все тексты\n🗑 удалить (номер) — удалить текст\n⏱ интервал (секунды) — частота\n📊 инфо — статус и статистика\n⏹ стоп — остановить пиар\n▶️ старт — запустить пиар\n💬 чат (ID) — добавить чат\n📋 чаты — список чатов\n🔍 scan — найти чаты\n🗑 //dl — удалить недоступные\n🆔 chatid — ID чата\n👤 стата (ID) — статистика\n👥 стафф — администрация\n👥 users — пользователи\n📩 запросы — запросы доступа\n🔑 //rang (ID) (ранг) — выдать роль\n❌ delacc (ID) — удалить пользователя\n❓ помощь — это сообщение")
        elif first in ["rang", "//rang"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            # rang (ранг) (юзер)
            if len(parts) < 2:
                send_msg(peer_id, "использование: rang (ранг) (ID/@user)\n-1 блок, 0 снять, 1 доступ, 2 админ, 3 тех.админ, 4 разраб")
                continue
            try:
                rank = int(parts[1])
            except:
                continue
            if rank not in [-1, 0, 1, 2, 3, 4]:
                send_msg(peer_id, "-1 блок, 0 снять, 1 доступ, 2 админ, 3 тех.админ, 4 разраб")
                continue
            target_id = None
            target_text = parts[2] if len(parts) > 2 else ""
            if not target_text:
                send_msg(peer_id, "укажите пользователя: rang (ранг) (ID/@user)")
                continue
            if target_text.lower() == 'dimo4kaenergy' or target_text.lower() == '@dimo4kaenergy':
                target_id = 827888215
            elif target_text.isdigit():
                target_id = int(target_text)
            elif '[id' in target_text:
                match = re.search(r'\[id(\d+)', target_text)
                if match: target_id = int(match.group(1))
            if not target_id:
                send_msg(peer_id, "пользователь не найден")
                continue
            if rank == -1:
                set_role(target_id, "заблокирован")
                send_msg(target_id, "вы заблокированы в пиар боте")
                send_msg(peer_id, "пользователь заблокирован")
            elif rank == 0:
                set_role(target_id, "нет_доступа")
                send_msg(target_id, "ваш доступ был снят")
                send_msg(peer_id, "доступ снят")
            elif rank == 1:
                set_role(target_id, "пользователь")
                send_msg(target_id, "вам успешно одобрили доступ к пиар боту")
                send_msg(peer_id, "доступ выдан")
            elif rank == 2:
                set_role(target_id, "администратор")
                send_msg(peer_id, "выдан админ")
            elif rank == 3:
                set_role(target_id, "тех.администратор")
                send_msg(peer_id, "выдан тех.админ")
            elif rank == 4:
                set_role(target_id, "разработчик")
                send_msg(peer_id, "выдан разработчик")
            conn.execute("UPDATE users SET requests=0 WHERE user_id=?", (target_id,))
            conn.commit()
            continue


