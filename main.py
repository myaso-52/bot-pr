import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import sqlite3
import time
import threading
import random
import re
import json

def parse_user_id(text):
    """Парсит ID из ссылки, упоминания, скриннейма или числа"""
    text = text.strip()
    # vk.com/ или vk.ru/
    if 'vk.com/' in text or 'vk.ru/' in text:
        text = text.split('/')[-1].strip().replace(']', '').replace('[', '')
    # @user
    if text.startswith('@'):
        text = text[1:]
    # [id123|...]
    if '[id' in text:
        match = re.search(r'\[id(\d+)', text)
        if match: return int(match.group(1))
    # Просто число
    if text.isdigit():
        return int(text)
    # Скриннейм
    try:
        res = vk.utils.resolveScreenName(screen_name=text)
        if res and res['type'] == 'user':
            return res['object_id']
    except:
        pass
    return None
import config
from datetime import datetime, timezone, timedelta as td

vk_session = vk_api.VkApi(token=config.TOKEN, api_version="5.199")
vk = vk_session.get_api()
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, 240839587)

conn = sqlite3.connect("pr.db", check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY, active INTEGER DEFAULT 1)")
conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, role TEXT DEFAULT 'нет_доступа', requests INTEGER DEFAULT 0, ban_until REAL DEFAULT 0, ban_reason TEXT, ban_by TEXT, reg_date TEXT)")
conn.execute("CREATE TABLE IF NOT EXISTS user_texts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)")
try:
    conn.execute("ALTER TABLE users ADD COLUMN ban_until REAL DEFAULT 0")
except: pass
try:
    conn.execute("ALTER TABLE users ADD COLUMN ban_reason TEXT")
except: pass
try:
    conn.execute("ALTER TABLE users ADD COLUMN ban_by TEXT")
except: pass
try:
    conn.execute("ALTER TABLE users ADD COLUMN reg_date TEXT")
except: pass
conn.commit()

conn.execute("INSERT OR IGNORE INTO users (user_id, role) VALUES (827888215, 'разработчик')")
conn.execute("INSERT OR IGNORE INTO users (user_id, role) VALUES (864686414, 'разработчик')")
conn.commit()

ALLOWED = ["разработчик", "тех.администратор", "администратор", "пользователь"]

def get_role(uid):
    row = conn.execute("SELECT role, ban_until FROM users WHERE user_id=?", (uid,)).fetchone()
    if row:
        if row[1] and row[1] > time.time():
            return "заблокирован"
        return row[0]
    return "нет_доступа"

def set_role(uid, role):
    conn.execute("INSERT OR REPLACE INTO users (user_id, role) VALUES (?, ?)", (uid, role))
    conn.commit()

def get_interval():
    row = conn.execute("SELECT value FROM settings WHERE key='interval'").fetchone()
    return int(row[0]) if row else 3600

def get_active():
    row = conn.execute("SELECT value FROM settings WHERE key='active'").fetchone()
    if row:
        return row[0] == '1'
    return False

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
            user_texts = conn.execute("SELECT user_id, text FROM user_texts ORDER BY RANDOM()").fetchall()
            chats = conn.execute("SELECT id FROM chats WHERE active=1").fetchall()
            if user_texts and chats:
                for uid_text, t in user_texts:
                    kb = VkKeyboard(inline=True)
                    kb.add_openlink_button("Откликнуться", link="https://vk.ru/write-240839587?ref=827888215")
                    for chat in chats:
                        send_msg(chat[0], t, keyboard=kb.get_keyboard())
                    time.sleep(1)
        time.sleep(get_interval())

threading.Thread(target=piar_loop, daemon=True).start()

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
    if event.type == VkBotEventType.MESSAGE_NEW and event.obj.message:
        message_obj = event.obj.message
        now_ts = time.time()
        if message_obj['text'] == last_msg[0] and message_obj['from_id'] == last_msg[1] and now_ts - last_msg[2] < 3:
            continue
        last_msg = (message_obj['text'], message_obj['from_id'], now_ts)
        peer_id = message_obj['peer_id']
        uid = message_obj['from_id']
        text = message_obj['text'].strip()
        role = get_role(uid)
        print(f"[{uid}|{role}] {text}")

        text_lower = text.lower()
        if text_lower.startswith("."):
            text_lower = text_lower[1:]
        parts = text_lower.split()
        first = parts[0] if parts else ""

        # Кнопка Запросить доступ
        if text_lower in ["запросить доступ", "запросить"]:
            if role in ALLOWED:
                send_msg(peer_id, "у вас уже есть доступ")
            elif role == "заблокирован":
                send_msg(peer_id, "вы заблокированы")
            else:
                req = (conn.execute("SELECT requests FROM users WHERE user_id=?", (uid,)).fetchone() or [0])[0]
                if req > 0:
                    send_msg(peer_id, "запрос уже отправлен")
                    continue
                conn.execute("INSERT OR REPLACE INTO users (user_id, requests, reg_date, role) VALUES (?, 1, ?, COALESCE((SELECT role FROM users WHERE user_id=?), 'нет_доступа'))", (uid, time.strftime('%d.%m.%Y'), uid))
                conn.commit()
                send_msg(peer_id, "запрос отправлен разработчику")
                try:
                    u = vk.users.get(user_ids=uid)[0]
                    name = f"{u['first_name']} {u['last_name']}"
                except:
                    name = f"ID {uid}"
                send_msg(827888215, f"{name} запросил доступ\n\n✅ Одобрить: rang 1 {uid}\n❌ Отказать: rang 0 {uid}")
            continue

        # Помощь
        if first in ["помощь", "хелп", "help", "начать", "меню", "привет"]:
            if role not in ALLOWED:
                send_msg(peer_id, "чтобы получить доступ к пиар боту нужно добавить это сообщество в 5 пиар чатов (от 200 человек), а потом отписать @dimo4kaenergy и запросить доступ")
                continue
            help_text = "📋 КОМАНДЫ ПИАР БОТА:\n\n📝 пиар (текст) - добавить текст\n📋 список - ваши тексты\n🗑 удалить (номер) - удалить текст\n⏱ интервал (сек) - частота\n📊 инфо - статус\n⏹ стоп - остановить\n▶️ старт - запустить\n💬 чат (ID) - добавить чат\n📋 чаты - список чатов\n🔍 scan - найти чаты\n🗑 //dl - удалить недоступные\n🆔 chatid - ID чата\n👤 стата (ID) - профиль"
            if role == "разработчик":
                help_text += "\n\n🔧 ДЛЯ РАЗРАБОТЧИКА:\n👥 стафф - администрация\n👥 users - пользователи\n📩 запросы - запросы\n🔑 rang (ранг) (ID) - роль\n📨 sms (ссылка) (текст) - смс\n🔨 //ban (срок) (ссылка) (причина)\n📋 //banlist - список банов\n❌ delacc (ID) - удалить"
            send_msg(peer_id, help_text, keyboard=get_main_keyboard())
            continue

        # Статистика
        if first in ["статистика", "stats", "stat"]:
            if role not in ALLOWED:
                send_msg(peer_id, "чтобы получить доступ к пиар боту нужно добавить это сообщество в 5 пиар чатов (от 200 человек), а потом отписать @dimo4kaenergy и запросить доступ")
                continue
            chats_count = conn.execute("SELECT COUNT(*) FROM chats WHERE active=1").fetchone()[0]
            texts_count = conn.execute("SELECT COUNT(*) FROM user_texts").fetchone()[0]
            active_status = "запущен" if get_active() else "остановлен"
            send_msg(peer_id, f"чатов: {chats_count}\nтекстов: {texts_count}\nстатус: {active_status}\nинтервал: {get_interval()}с")
            continue

        # Проверка бана
        if role == "заблокирован":
            ban_info = conn.execute("SELECT ban_until, ban_reason FROM users WHERE user_id=?", (uid,)).fetchone()
            if ban_info and ban_info[0] >= 9999999990:
                send_msg(peer_id, f"вы заблокированы навсегда\nпричина: {ban_info[1]}")
            elif ban_info and ban_info[0] > time.time():
                tz_moscow = timezone(td(hours=3))
                unban = datetime.fromtimestamp(ban_info[0], tz=tz_moscow).strftime('%d.%m.%Y %H:%M')
                send_msg(peer_id, f"вы заблокированы до {unban} МСК\nпричина: {ban_info[1]}")
            else:
                send_msg(peer_id, "вы заблокированы")
            continue

        if role not in ALLOWED:
            send_msg(peer_id, "чтобы получить доступ к пиар боту нужно добавить это сообщество в 5 пиар чатов (от 200 человек), а потом отписать @dimo4kaenergy и запросить доступ")
            continue

        # === КОМАНДЫ ===

        if first in ["запросы"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            reqs = conn.execute("SELECT user_id FROM users WHERE requests > 0 LIMIT 10").fetchall()
            if reqs:
                txt = "запросы:\n" + "\n".join([f"[id{r[0]}|ID{r[0]}]" for r in reqs])
            else:
                txt = "нет запросов"
            send_msg(peer_id, txt)
            continue

        if first in ["delacc"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            target_id = None
            if len(parts) > 1:
                target_id = parse_user_id(parts[1])
            if target_id:
                conn.execute("DELETE FROM users WHERE user_id=?", (target_id,))
                conn.execute("DELETE FROM user_texts WHERE user_id=?", (target_id,))
                conn.commit()
                send_msg(peer_id, f"пользователь {target_id} удалён")
            else:
                send_msg(peer_id, "delacc (ID)")
            continue

        if first in ["//ud", "ud"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            if len(parts) < 2:
                send_msg(peer_id, "//ud (ID текста)\nСписок: список")
                continue
            try:
                tid = int(parts[1])
            except:
                send_msg(peer_id, "ID текста числом")
                continue
            row = conn.execute("SELECT id, user_id, text FROM user_texts WHERE id=?", (tid,)).fetchone()
            if not row:
                send_msg(peer_id, "текст не найден")
                continue
            conn.execute("DELETE FROM user_texts WHERE id=?", (tid,))
            conn.commit()
            send_msg(peer_id, f"удалён текст #{tid}: {row[2][:40]}\nвладелец: [id{row[1]}|ID{row[1]}]")
            continue

        if first in ["//ban", "ban"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            if len(parts) < 3:
                send_msg(peer_id, "использование: //ban (срок) (ссылка/ID) (причина)\n-1 навсегда, 0 разбан, 1-365 дни")
                continue
            try:
                days = int(parts[1])
            except:
                send_msg(peer_id, "срок числом: -1 навсегда, 0 разбан, 1-365 дни")
                continue
            target_id = parse_user_id(parts[2])
            if not target_id:
                send_msg(peer_id, "пользователь не найден")
                continue
            reason = " ".join(parts[3:]) if len(parts) > 3 else "не указана"
            if days == 0:
                conn.execute("UPDATE users SET ban_until=0, ban_reason='', ban_by='' WHERE user_id=?", (target_id,))
                conn.commit()
                try: send_msg(target_id, "вы разблокированы в пиар боте")
                except: pass
                send_msg(peer_id, f"пользователь {target_id} разблокирован")
            elif days == -1:
                conn.execute("UPDATE users SET ban_until=9999999999, ban_reason=?, ban_by=? WHERE user_id=?", (reason, str(uid), target_id))
                conn.commit()
                try: send_msg(target_id, f"вы заблокированы навсегда\nпричина: {reason}")
                except: pass
                send_msg(peer_id, f"пользователь {target_id} заблокирован навсегда")
            elif 1 <= days <= 365:
                ban_until = time.time() + (days * 86400)
                conn.execute("UPDATE users SET ban_until=?, ban_reason=?, ban_by=? WHERE user_id=?", (ban_until, reason, str(uid), target_id))
                conn.commit()
                tz_moscow = timezone(td(hours=3))
                unban_date = datetime.fromtimestamp(ban_until, tz=tz_moscow).strftime('%d.%m.%Y %H:%M')
                try: send_msg(target_id, f"вы заблокированы на {days} дн. до {unban_date} МСК\nпричина: {reason}")
                except: pass
                send_msg(peer_id, f"заблокирован на {days} дн. до {unban_date} МСК")
            else:
                send_msg(peer_id, "срок от 1 до 365, -1 навсегда, 0 разбан")
            continue

        if first in ["//banlist", "banlist"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            now_ts2 = time.time()
            bans = conn.execute("SELECT user_id, ban_until, ban_reason FROM users WHERE ban_until > ? ORDER BY ban_until DESC", (now_ts2,)).fetchall()
            if bans:
                tz_moscow = timezone(td(hours=3))
                txt = "заблокированные:\n\n"
                for b in bans:
                    if b[1] >= 9999999990:
                        until_str = "навсегда"
                    else:
                        until_str = "до " + datetime.fromtimestamp(b[1], tz=tz_moscow).strftime('%d.%m.%Y %H:%M')
                    txt += f"[id{b[0]}|ID{b[0]}]: {until_str} | {b[2]}\n"
            else:
                txt = "нет заблокированных"
            send_msg(peer_id, txt)
            continue

        if first in ["sms"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            if len(parts) < 3:
                send_msg(peer_id, "sms (ссылка/ID) (сообщение)")
                continue
            target_text = parts[1]
            msg_text = " ".join(parts[2:])
            target_id = parse_user_id(target_text)
            if target_id:
                try:
                    vk.messages.send(user_id=target_id, message=msg_text, random_id=0)
                    send_msg(peer_id, f"отправлено {target_id}")
                except Exception as e:
                    send_msg(peer_id, f"ошибка: {e}")
            else:
                send_msg(peer_id, "не найден. укажите ссылку vk.com/имя или ID")
            continue

        if first in ["//scan", "scan"]:
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

        if first in ["//cht", "cht"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            total = conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM chats WHERE active=1").fetchone()[0]
            inactive = total - active
            send_msg(peer_id, f"💬 Всего чатов: {total}\n✅ Активных: {active}\n❌ Удалённых/неактивных: {inactive}")
            continue

        if first in ["//dl", "dl"]:
            chats = conn.execute("SELECT id FROM chats WHERE active=1").fetchall()
            removed = 0
            for chat in chats:
                try:
                    vk.messages.send(peer_id=chat[0], message=".", random_id=0)
                except:
                    conn.execute("UPDATE chats SET active=0 WHERE id=?", (chat[0],))
                    removed += 1
            conn.commit()
            send_msg(peer_id, f"✅ Отключено {removed} недоступных чатов\n\n//cht — посмотреть статистику")
            continue

        if first in ["//chatid", "chatid"]:
            send_msg(peer_id, f"ID: {peer_id}")
            continue

        if first in ["стафф", "staff", "админы"]:
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

        if first in ["users"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            users = conn.execute("SELECT user_id FROM users WHERE role='пользователь' LIMIT 50").fetchall()
            if users:
                txt = "пользователи:\n" + "\n".join([f"[id{u[0]}|ID{u[0]}]" for u in users])
            else:
                txt = "нет пользователей"
            send_msg(peer_id, txt)
            continue

        if first in ["чаты"]:
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

        if first in ["инфо", "info"]:
            chats_count = conn.execute("SELECT COUNT(*) FROM chats WHERE active=1").fetchone()[0]
            texts_count = conn.execute("SELECT COUNT(*) FROM user_texts").fetchone()[0]
            active_status = "запущен" if get_active() else "остановлен"
            send_msg(peer_id, f"статус: {active_status}\nинтервал: {get_interval()}с\nчатов: {chats_count}\nтекстов: {texts_count}")
            continue

        if first in ["стата", "профиль", "проф", "profile"]:
            target_uid = uid
            if len(parts) > 1:
                parsed = parse_user_id(parts[1])
                if parsed: target_uid = parsed
            target_role = get_role(target_uid)
            reqs = conn.execute("SELECT reg_date FROM users WHERE user_id=?", (target_uid,)).fetchone()
            reg_date = reqs[0] if reqs else "неизвестно"
            try:
                u = vk.users.get(user_ids=target_uid)[0]
                name = f"{u['first_name']} {u['last_name']}"
            except:
                name = f"ID {target_uid}"
            send_msg(peer_id, f"👤 {name}\n🆔 ID: {target_uid}\n🔰 Роль: {target_role}\n📅 Регистрация: {reg_date}")
            continue

        if first in ["пиар"]:
            if len(parts) < 2:
                send_msg(peer_id, "пиар (текст)")
                continue
            t = " ".join(parts[1:])
            conn.execute("INSERT INTO user_texts (user_id, text) VALUES (?, ?)", (uid, t))
            conn.commit()
            send_msg(peer_id, "добавлено")
            continue

        if first in ["список"]:
            if role == "разработчик":
                texts = conn.execute("SELECT id, text, user_id FROM user_texts").fetchall()
                if texts:
                    txt = "тексты (все):\n" + "\n".join([f"{t[0]}. [id{t[2]}|ID{t[2]}]: {t[1][:50]}" for t in texts])
                else:
                    txt = "нет текстов"
            else:
                texts = conn.execute("SELECT id, text FROM user_texts WHERE user_id=?", (uid,)).fetchall()
                if texts:
                    txt = "ваши тексты:\n" + "\n".join([f"{t[0]}. {t[1][:50]}" for t in texts])
                else:
                    txt = "нет текстов"
            send_msg(peer_id, txt)
            continue

        if first in ["удалить"]:
            if len(parts) < 2:
                send_msg(peer_id, "удалить (номер)")
                continue
            try:
                tid = int(parts[1])
                if role == "разработчик":
                    conn.execute("DELETE FROM user_texts WHERE id=?", (tid,))
                else:
                    conn.execute("DELETE FROM user_texts WHERE id=? AND user_id=?", (tid, uid))
                conn.commit()
                send_msg(peer_id, "удалено")
            except:
                send_msg(peer_id, "ошибка")
            continue

        if first in ["интервал"]:
            if len(parts) < 2:
                send_msg(peer_id, "интервал (секунды)")
                continue
            try:
                val = int(parts[1])
                conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('interval',?)", (str(val),))
                conn.commit()
                send_msg(peer_id, f"интервал: {val}с")
            except:
                send_msg(peer_id, "ошибка")
            continue

        if first in ["стоп"]:
            conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('active','0')")
            conn.commit()
            send_msg(peer_id, "пиар остановлен")
            continue

        if first in ["старт"]:
            conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('active','1')")
            conn.commit()
            send_msg(peer_id, "пиар запущен")
            continue

        if first in ["чат"]:
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
                send_msg(peer_id, "чат (ID)")
            continue

        if first in ["rang", "//rang"]:
            if role != "разработчик":
                send_msg(peer_id, "только разработчик")
                continue
            if len(parts) < 3:
                send_msg(peer_id, "rang (ранг) (ID/@user)\n-1 блок, 0 снять, 1 доступ, 2 админ, 3 тех.админ, 4 разраб")
                continue
            try:
                rank = int(parts[1])
            except:
                send_msg(peer_id, "ранг числом: -1, 0, 1, 2, 3, 4")
                continue
            if rank not in [-1, 0, 1, 2, 3, 4]:
                send_msg(peer_id, "-1 блок, 0 снять, 1 доступ, 2 админ, 3 тех.админ, 4 разраб")
                continue
            target_id = parse_user_id(parts[2])
            if not target_id:
                send_msg(peer_id, "пользователь не найден")
                continue
            if rank == -1:
                set_role(target_id, "заблокирован")
                conn.execute("UPDATE users SET ban_until=9999999999, ban_reason='заблокирован разработчиком' WHERE user_id=?", (target_id,))
                conn.commit()
                try: send_msg(target_id, "вы заблокированы в пиар боте")
                except: pass
                send_msg(peer_id, "заблокирован")
            elif rank == 0:
                set_role(target_id, "нет_доступа")
                conn.execute("UPDATE users SET requests=0, ban_until=0 WHERE user_id=?", (target_id,))
                conn.commit()
                try: send_msg(target_id, "разработчик отказал вам в доступе")
                except: pass
                send_msg(peer_id, "доступ снят, пользователю отправлен отказ")
            elif rank == 1:
                set_role(target_id, "пользователь")
                conn.execute("UPDATE users SET requests=0, ban_until=0 WHERE user_id=?", (target_id,))
                conn.commit()
                try: send_msg(target_id, "вам одобрили доступ к пиар боту")
                except: pass
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
            continue


