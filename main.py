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
longpoll = VkLongPoll(vk_session, mode=2)

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
ALLOWED = ["разработчик", "тех.администратор", "администратор"]

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
                for chat in chats:
                    send_msg(chat[0], t)
        time.sleep(get_interval())

threading.Thread(target=piar_loop, daemon=True).start()
print("бот пиара запущен")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        peer_id = event.peer_id
        uid = event.user_id
        text = event.text
        role = get_role(uid)
        print(f"[{uid}|{role}] {text}")

        text_lower = text.lower().strip()

        if text_lower in ["начать", "меню", "привет", "старт"]:
            send_msg(peer_id, "бот для пиара. выберите действие:", keyboard=get_main_keyboard())
            continue

        if text in ["Помощь", ".помощь"]:
            help_text = "команды:\n\nпиар (текст) - добавить\nсписок - тексты\nудалить (номер)\nинтервал (секунды)\nинфо - информация\nстоп/старт\nчат - добавить чат\nстата - статистика\nзапросы - запросы\n+доступ/-доступ (ID)\n//rang (ID) (ранг)\nпомощь"
            send_msg(peer_id, help_text)
            continue

        if text == "Статистика":
            chats_count = conn.execute("SELECT COUNT(*) FROM chats WHERE active=1").fetchone()[0]
            texts_count = conn.execute("SELECT COUNT(*) FROM texts").fetchone()[0]
            active_status = "запущен" if get_active() else "остановлен"
            send_msg(peer_id, f"чатов: {chats_count}\nтекстов: {texts_count}\nстатус: {active_status}\nинтервал: {get_interval()}с")
            continue

        if text == "Запросить доступ":
            if role in ALLOWED:
                send_msg(peer_id, "у вас уже есть доступ")
                continue
            req = (conn.execute("SELECT requests FROM users WHERE user_id=?", (uid,)).fetchone() or [0])[0]
            if req > 0:
                send_msg(peer_id, "вы уже отправили запрос")
                continue
            req = 1
            conn.execute("INSERT OR REPLACE INTO users (user_id, requests, role) VALUES (?, ?, COALESCE((SELECT role FROM users WHERE user_id=?), 'пользователь'))", (uid, req, uid))
            conn.commit()
            send_msg(827888215, f"запрос доступа от [id{uid}|пользователя] (ID: {uid}). +доступ {uid} или -доступ {uid}")
            send_msg(peer_id, "запрос отправлен разработчику")
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

        if text.startswith("+доступ") and role == "разработчик":
            try:
                target_id = int(parts[0]) if parts[0].isdigit() else None
                if target_id:
                    if get_role(target_id) in ALLOWED:
                        send_msg(peer_id, "уже есть доступ")
                    else:
                        set_role(target_id, "пользователь")
                        conn.execute("UPDATE users SET requests=0 WHERE user_id=?", (target_id,))
                        conn.commit()
                        send_msg(target_id, "разработчик успешно одобрил вам доступ к пиар боту")
                        send_msg(peer_id, f"вы одобрили доступ [id{target_id}|пользователю]")
            except:
                send_msg(peer_id, "ошибка")
            continue

        if text.startswith("-доступ") and role == "разработчик":
            try:
                target_id = int(parts[0]) if parts[0].isdigit() else None
                if target_id:
                    if get_role(target_id) in ALLOWED:
                        send_msg(peer_id, "нельзя отклонить доступ у администратора")
                    else:
                        conn.execute("UPDATE users SET requests=0 WHERE user_id=?", (target_id,))
                        conn.commit()
                        send_msg(target_id, "к сожалению, разработчик отклонил вам доступ к боту")
                        send_msg(peer_id, f"вы отклонили доступ [id{target_id}|пользователю]")
            except:
                send_msg(peer_id, "ошибка")
            continue

        if role not in ALLOWED:
            send_msg(peer_id, "нет доступа. нажмите 'запросить доступ'")
            continue

        if first == "//chatid" or first == "chatid":
            send_msg(peer_id, f"ID: {peer_id}")
            continue

        if first == "чаты":
            chats = conn.execute("SELECT id FROM chats WHERE active=1").fetchall()
            if chats:
                ids = ", ".join([str(c[0]) for c in chats])
                send_msg(peer_id, "чаты: " + ids)
            else:
                send_msg(peer_id, "нет чатов")
            continue

            active_status = "запущен" if get_active() else "остановлен"
            chats_list = conn.execute("SELECT id FROM chats WHERE active=1").fetchall()
            chat_ids = ", ".join([str(c[0]) for c in chats_list]) if chats_list else "нет"
            send_msg(peer_id, f"статус: {active_status}\nинтервал: {interval}с\nчатов: {chats_count} ({chat_ids})\nтекстов: {texts_count}")
            continue

        if first == "пиар" and len(parts) > 1:
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
        elif first == "удалить" and len(parts) > 1:
            try:
                tid = int(parts[1])
                conn.execute("DELETE FROM texts WHERE id=?", (tid,))
                conn.commit()
                send_msg(peer_id, "удалено")
            except:
                send_msg(peer_id, "ошибка")
        elif first == "интервал" and len(parts) > 1:
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
            if len(parts) > 1:
                try:
                    chat_id = int(parts[1])
                    conn.execute("INSERT OR REPLACE INTO chats (id, active) VALUES (?, 1) ON CONFLICT(id) DO UPDATE SET active=1", (chat_id,))
                    conn.commit()
                    send_msg(peer_id, f"чат {chat_id} добавлен")
                except:
                    send_msg(peer_id, "чат (ID)")
            elif peer_id > 2000000000:
                conn.execute("INSERT OR REPLACE INTO chats (id, active) VALUES (?, 1) ON CONFLICT(id) DO UPDATE SET active=1", (peer_id,))
                conn.commit()
                send_msg(peer_id, "чат добавлен")
            else:
                send_msg(peer_id, "чат (ID) - укажите ID")
        elif first == "стата":
            target_uid = uid
            if len(parts) > 1:
                try:
                    target_uid = int(parts[1]) if parts[1].isdigit() else uid
                except:
                    pass
            target_role = get_role(target_uid)
            reqs = conn.execute("SELECT requests FROM users WHERE user_id=?", (target_uid,)).fetchone()
            req_count = reqs[0] if reqs else 0
            send_msg(peer_id, f"ID: {target_uid}\nроль: {target_role}\nзапросов: {req_count}")
        elif first == "помощь":
            help_text = "команды:\n\nпиар (текст) - добавить\nсписок - тексты\nудалить (номер)\nинтервал (секунды)\nинфо - информация\nстоп/старт\nчат - добавить чат\nстата - статистика\nзапросы - запросы\n+доступ/-доступ (ID)\n//rang (ID) (ранг)\nпомощь"
            send_msg(peer_id, help_text)
        elif first == "//rang" and len(parts) >= 3:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            target_text = parts[1]
            try:
                rank = int(parts[2])
            except:
                send_msg(peer_id, "ранги: -1 блок, 1 пользователь, 2 админ, 3 тех.админ, 4 разраб")
                continue
            if rank not in ROLES:
                send_msg(peer_id, "ранги: -1 блок, 1 пользователь, 2 админ, 3 тех.админ, 4 разраб")
                continue
            target_id = None
            if target_text.isdigit():
                target_id = int(target_text)
            elif '[id' in target_text:
                match = re.search(r'\[id(\d+)', target_text)
                if match:
                    target_id = int(match.group(1))
            if target_id:
                set_role(target_id, ROLES[rank])
                send_msg(peer_id, f"выдана роль: {ROLES[rank]}")
            else:
                send_msg(peer_id, "укажите ID или @user")
