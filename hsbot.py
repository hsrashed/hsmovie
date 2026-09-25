import os
import threading
import requests
import json
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ==================== FLASK SERVER FOR RENDER ====================
flask_app = Flask(__name__)

@flask_app.route('/')
@flask_app.route('/ping')
def ping():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# ==================== CONFIGURATION ====================
API_ID = 38564455
API_HASH = "e3c8798942e870d34d34fd35b53ef8be"

BOT_TOKEN = "8747426655:AAEWHgvI38lz6EPksouXTWHtEs96F38VUNk"
ADMIN_ID = 7488697341

CHANNEL_1 = "hsmoviehub"   
CHANNEL_2 = "Hs_Shadowx"   

DATABASE_URL = "https://hs-movies-app-default-rtdb.firebaseio.com"
# =======================================================

app = Client(
    "hs_movie_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

admin_state = {}
commands_data = {}

def save_user_to_firebase(user_id, first_name, username):
    try:
        url = f"{DATABASE_URL}/users/{user_id}.json"
        data = {
            'user_id': user_id,
            'first_name': first_name,
            'username': username or ""
        }
        requests.put(url, json=data, timeout=5)
    except Exception as e:
        print(f"Firebase Save Error: {e}")

def is_user_member_of_channel(channel_username, user_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        params = {"chat_id": f"@{channel_username}", "user_id": user_id}
        res = requests.get(url, params=params, timeout=5).json()
        if res.get("ok"):
            status = res["result"]["status"]
            if status in ["creator", "administrator", "member"]:
                return True
        return False
    except Exception as e:
        print(f"API Check Error for {channel_username}: {e}")
        return False

async def check_joined(user_id):
    if user_id == ADMIN_ID:
        return True
    return is_user_member_of_channel(CHANNEL_1, user_id) and is_user_member_of_channel(CHANNEL_2, user_id)

# ==================== USER HANDLERS ====================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    save_user_to_firebase(user_id, first_name, message.from_user.username)
    
    if not await check_joined(user_id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNEL_1}"),
             InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNEL_2}")],
            [InlineKeyboardButton("✅ Check / Joined", callback_data="check_join")]
        ])
        text = (
            f"👋 <b>হ্যালো {first_name}!</b>\n\n"
            f"বটটি ব্যবহার করতে আমাদের ২টি চ্যানেলে জয়েন করতে হবে:\n\n"
            f"১. <b>Hs Movie Hub</b>\n"
            f"২. <b>Hs Shadowx</b>\n\n"
            f"👇 জয়েন করার পর <b>'Check / Joined'</b> বাটনে ক্লিক করুন।"
        )
        await message.reply_text(text, reply_markup=keyboard)
    else:
        await send_welcome_menu(message)

async def send_welcome_menu(message_or_callback):
    buttons = []
    for key, data in commands_data.items():
        buttons.append([InlineKeyboardButton(data['title'], callback_data=f"mc_{key}")])
    
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    text = "🎉 <b>স্বাগতম!</b>\n\nনিচে প্রদত্ত বাটনগুলো থেকে আপনার প্রয়োজনীয় কন্টেন্ট নির্বাচন করুন:"
    
    if hasattr(message_or_callback, "reply_text"):
        await message_or_callback.reply_text(text, reply_markup=reply_markup)
    else:
        await message_or_callback.message.edit_text(text, reply_markup=reply_markup)

async def send_file_list(client, user_id, file_list):
    for item in file_list:
        f_id = item['id']
        f_type = item['type']
        try:
            if f_type == "video":
                await client.send_video(user_id, f_id)
            elif f_type == "photo":
                await client.send_photo(user_id, f_id)
            elif f_type == "document":
                await client.send_document(user_id, f_id)
            elif f_type == "audio":
                await client.send_audio(user_id, f_id)
        except Exception as e:
            print(f"Error sending file: {e}")

@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    if data == "check_join":
        if await check_joined(user_id):
            await callback_query.answer("ধন্যবাদ! আপনি সফলভাবে জয়েন করেছেন।", show_alert=True)
            await send_welcome_menu(callback_query)
        else:
            await callback_query.answer("⚠️ আপনি এখনও ২টি চ্যানেলে জয়েন করেননি!", show_alert=True)
            return

    # User Selection: Main Title Clicked
    elif data.startswith("mc_"):
        if not await check_joined(user_id):
            await callback_query.answer("⚠️ ফাইল পেতে চ্যানেলে জয়েন করুন!", show_alert=True)
            return

        cmd_key = data.replace("mc_", "")
        if cmd_key in commands_data:
            item = commands_data[cmd_key]
            if item.get("is_episodic"):
                buttons = []
                episodes = item.get("episodes", {})
                for ep_key, ep_val in episodes.items():
                    # Format: ge_cmdKey_epKey
                    buttons.append([InlineKeyboardButton(ep_val['title'], callback_data=f"ge_{cmd_key}_{ep_key}")])
                
                buttons.append([InlineKeyboardButton("🔙 Back Main Menu", callback_data="back_user_main")])
                await callback_query.message.edit_text(
                    f"🎬 <b>{item['title']}</b> - পর্বসমূহ:\nনিচ থেকে কাঙ্ক্ষিত পর্ব বেছে নিন:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                await callback_query.answer("ফাইল পাঠানো হচ্ছে...")
                await send_file_list(client, user_id, item.get("files", []))
        else:
            await callback_query.answer("কন্টেন্ট খুঁজে পাওয়া যায়নি!", show_alert=True)

    # User Selection: Episode Clicked
    elif data.startswith("ge_"):
        if not await check_joined(user_id):
            await callback_query.answer("⚠️ ফাইল পেতে চ্যানেলে জয়েন করুন!", show_alert=True)
            return

        parts = data.split("_")
        if len(parts) >= 3:
            cmd_key, ep_key = parts[1], parts[2]
            if cmd_key in commands_data and ep_key in commands_data[cmd_key].get("episodes", {}):
                ep_data = commands_data[cmd_key]["episodes"][ep_key]
                await callback_query.answer("পর্বের ভিডিও পাঠানো হচ্ছে...")
                await send_file_list(client, user_id, ep_data.get("files", []))
                return
        
        await callback_query.answer("পর্বটি খুঁজে পাওয়া যায়নি!", show_alert=True)

    elif data == "back_user_main":
        await send_welcome_menu(callback_query)

    # ------------------- ADMIN CALLBACKS -------------------
    elif user_id == ADMIN_ID:
        if data == "admin_add_content":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("হ্যাঁ (Yes)", callback_data="add_type_series"),
                 InlineKeyboardButton("না (No)", callback_data="add_type_single")]
            ])
            await callback_query.message.edit_text("আপনি যে কন্টেন্টটি যোগ করছেন তার কি কোনো **পর্ব/এপিসোড** আছে?", reply_markup=keyboard)
            await callback_query.answer()

        elif data in ["add_type_series", "add_type_single"]:
            is_episodic = (data == "add_type_series")
            admin_state[ADMIN_ID] = {
                "step": "WAITING_FOR_MAIN_TITLE",
                "is_episodic": is_episodic
            }
            txt = "সিরিজ/নাটকের প্রধান **টাইটেল** লিখে পাঠান:" if is_episodic else "মুভি/কন্টেন্টের **টাইটেল** লিখে পাঠান:"
            await callback_query.message.edit_text(txt)
            await callback_query.answer()

        elif data == "admin_manage_cmds":
            await show_admin_manage_menu(callback_query)

        elif data == "admin_menu_home":
            await send_admin_home(callback_query)

        elif data.startswith("admin_manage_"):
            cmd_key = data.replace("admin_manage_", "")
            if cmd_key in commands_data:
                item = commands_data[cmd_key]
                buttons = []
                if item.get("is_episodic"):
                    buttons.append([InlineKeyboardButton("➕ Add Episode", callback_data=f"ae_{cmd_key}")])
                    buttons.append([InlineKeyboardButton("📋 Manage Episodes", callback_data=f"me_{cmd_key}")])
                
                buttons.append([InlineKeyboardButton("🗑️ Delete Whole Content", callback_data=f"del_cmd_{cmd_key}")])
                buttons.append([InlineKeyboardButton("🔙 Back", callback_data="admin_manage_cmds")])
                
                txt = f"<b>কন্টেন্ট:</b> {item['title']}\n<b>টাইপ:</b> {'Episodic' if item['is_episodic'] else 'Single'}"
                await callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(buttons))

        elif data.startswith("ae_"):
            cmd_key = data.replace("ae_", "")
            admin_state[ADMIN_ID] = {
                "step": "WAITING_FOR_EP_TITLE",
                "cmd_key": cmd_key
            }
            await callback_query.message.reply_text("নতুন পর্বের নাম লিখে পাঠান (যেমন: Episode 1):")
            await callback_query.answer()

        elif data.startswith("me_"):
            cmd_key = data.replace("me_", "")
            if cmd_key in commands_data:
                episodes = commands_data[cmd_key].get("episodes", {})
                buttons = []
                for ep_k, ep_v in episodes.items():
                    buttons.append([InlineKeyboardButton(f"🗑️ Delete {ep_v['title']}", callback_data=f"de_{cmd_key}_{ep_k}")])
                buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"admin_manage_{cmd_key}")])
                await callback_query.message.edit_text("পর্ব ম্যানেজমেন্ট:", reply_markup=InlineKeyboardMarkup(buttons))

        elif data.startswith("de_"):
            parts = data.split("_")
            if len(parts) >= 3:
                cmd_key, ep_key = parts[1], parts[2]
                if cmd_key in commands_data and ep_key in commands_data[cmd_key]["episodes"]:
                    del commands_data[cmd_key]["episodes"][ep_key]
                    await callback_query.answer("পর্বটি সফলভাবে মুছে ফেলা হয়েছে!", show_alert=True)
                    await show_admin_manage_menu(callback_query)
                    return

        elif data.startswith("del_cmd_"):
            cmd_key = data.replace("del_cmd_", "")
            if cmd_key in commands_data:
                del commands_data[cmd_key]
                await callback_query.answer("কন্টেন্ট সম্পূর্ণ ডিলিট করা হয়েছে!", show_alert=True)
                await show_admin_manage_menu(callback_query)

async def send_admin_home(event):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Movie / Series", callback_data="admin_add_content")],
        [InlineKeyboardButton("📋 Manage Content & Episodes", callback_data="admin_manage_cmds")]
    ])
    text = "স্বাগতম এডমিন প্যানেলে! আপনার করণীয় অপশন বেছে নিন:"
    if hasattr(event, "reply_text"):
        await event.reply_text(text, reply_markup=keyboard)
    else:
        await event.message.edit_text(text, reply_markup=keyboard)

async def show_admin_manage_menu(callback_query):
    if not commands_data:
        await callback_query.answer("কোনো কন্টেন্ট যুক্ত নেই!", show_alert=True)
        return
    buttons = []
    for k, v in commands_data.items():
        buttons.append([InlineKeyboardButton(f"⚙️ {v['title']}", callback_data=f"admin_manage_{k}")])
    buttons.append([InlineKeyboardButton("🔙 Back Admin Home", callback_data="admin_menu_home")])
    await callback_query.message.edit_text("ম্যানেজ করতে কন্টেন্ট নির্বাচন করুন:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("admin") & filters.user(ADMIN_ID) & filters.private)
async def admin_panel(client, message):
    await send_admin_home(message)

# ==================== ADMIN STEP-BY-STEP INPUT ====================

@app.on_message(filters.user(ADMIN_ID) & filters.private & ~filters.command(["start", "admin"]))
async def admin_message_handler(client, message):
    state_data = admin_state.get(ADMIN_ID, {})
    step = state_data.get("step")

    # Step 1: Main Title Input
    if step == "WAITING_FOR_MAIN_TITLE":
        title = message.text.strip()
        is_episodic = state_data.get("is_episodic")
        cmd_key = f"c{len(commands_data) + 1}"
        
        if is_episodic:
            commands_data[cmd_key] = {
                "title": title,
                "is_episodic": True,
                "episodes": {}
            }
            admin_state[ADMIN_ID] = {}
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Episode", callback_data=f"ae_{cmd_key}")],
                [InlineKeyboardButton("📋 Manage Content", callback_data=f"admin_manage_{cmd_key}")]
            ])
            await message.reply_text(f"✅ মেইন টাইটেল <b>'{title}'</b> তৈরি হয়েছে!\nএখন পর্ব যোগ করতে নিচের 'Add Episode' বাটনে চাপুন:", reply_markup=keyboard)
        else:
            admin_state[ADMIN_ID] = {
                "step": "WAITING_FOR_FILE_COUNT",
                "temp_cmd_key": cmd_key,
                "temp_title": title,
                "is_episodic": False
            }
            await message.reply_text(f"<b>'{title}'</b>-এর জন্য আপনি কয়টি ভিডিও/ফাইল আপলোড করতে চান? (সংখ্যা লিখে পাঠান, যেমন: 1 বা 2):")

    # Step 2: Episode Title Input
    elif step == "WAITING_FOR_EP_TITLE":
        ep_title = message.text.strip()
        cmd_key = state_data.get("cmd_key")
        
        admin_state[ADMIN_ID] = {
            "step": "WAITING_FOR_FILE_COUNT",
            "temp_cmd_key": cmd_key,
            "temp_ep_title": ep_title,
            "is_episodic": True
        }
        await message.reply_text(f"<b>'{ep_title}'</b> পর্বটির জন্য কয়টি ভিডিও/ফাইল শেয়ার করতে চান? (সংখ্যা লিখে পাঠান):")

    # Step 3: File Count Input
    elif step == "WAITING_FOR_FILE_COUNT":
        if not message.text.isdigit() or int(message.text) <= 0:
            await message.reply_text("⚠️ অনুগ্রহ করে একটি সঠিক সংখ্যা লিখে পাঠান (যেমন: 1, 2, 3):")
            return
            
        count = int(message.text)
        state_data["total_files"] = count
        state_data["received_files"] = []
        state_data["step"] = "WAITING_FOR_FILES"
        admin_state[ADMIN_ID] = state_data
        
        await message.reply_text(f"ঠিক আছে, এখন পর পর **{count} টি** ভিডিও/ফাইল এক এক করে বটকে পাঠান:")

    # Step 4: Video / File Receiving
    elif step == "WAITING_FOR_FILES":
        file_id = None
        file_type = None

        if message.video:
            file_id, file_type = message.video.file_id, "video"
        elif message.photo:
            file_id, file_type = message.photo.file_id, "photo"
        elif message.document:
            file_id, file_type = message.document.file_id, "document"
        elif message.audio:
            file_id, file_type = message.audio.file_id, "audio"

        if not file_id:
            await message.reply_text("⚠️ এটি কোনো বৈধ ফাইল নয়, দয়া করে একটি ফাইল বা ভিডিও পাঠান।")
            return

        received = state_data.get("received_files", [])
        received.append({"id": file_id, "type": file_type})
        total = state_data.get("total_files")

        if len(received) < total:
            await message.reply_text(f"✅ {len(received)}/{total} ফাইল পাওয়া গেছে। বাকিগুলো পাঠান:")
        else:
            cmd_key = state_data.get("temp_cmd_key")
            is_episodic = state_data.get("is_episodic")

            if is_episodic:
                ep_title = state_data.get("temp_ep_title")
                episodes = commands_data[cmd_key].get("episodes", {})
                ep_key = f"e{len(episodes) + 1}"
                
                episodes[ep_key] = {
                    "title": ep_title,
                    "files": received
                }
                commands_data[cmd_key]["episodes"] = episodes
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Another Episode", callback_data=f"ae_{cmd_key}")],
                    [InlineKeyboardButton("📋 Manage Content", callback_data=f"admin_manage_{cmd_key}")]
                ])
                await message.reply_text(f"🎉 <b>'{ep_title}'</b> সফলভাবে সেভ হয়েছে! ({total}টি ফাইল সহ)", reply_markup=keyboard)
            else:
                title = state_data.get("temp_title")
                commands_data[cmd_key] = {
                    "title": title,
                    "is_episodic": False,
                    "files": received
                }
                await message.reply_text(f"🎉 <b>'{title}'</b> কন্টেন্টটি সফলভাবে সেভ হয়েছে! ({total}টি ফাইল সহ)")

            admin_state[ADMIN_ID] = {}

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot starting...")
    app.run()
