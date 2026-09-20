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
    # Render স্বয়ংক্রিয়ভাবে PORT এনভায়রনমেন্ট ভ্যারিয়েবল প্রোভাইড করে
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

# ==================== CONFIGURATION ====================
API_ID = 38564455
API_HASH = "e3c8798942e870d34d34fd35b53ef8be"

# Bot Credentials
BOT_TOKEN = "8747426655:AAG94P6HWK81vEGWyL4hyT7892J230a9z1I"
ADMIN_ID = 7488697341  # শুধুমাত্র আপনার আইডি এডমিন হিসেবে কাজ করবে

# Channels for Force Join (বটকে অবশ্যই এই ২টি চ্যানেলে এডমিন বানাতে হবে)
CHANNEL_1 = "hsmoviehub"   # Username without @
CHANNEL_2 = "Hs_Shadowx"   # Username without @

# Firebase Realtime Database URL
DATABASE_URL = "https://hs-movies-app-default-rtdb.firebaseio.com"
# =======================================================

# Initialize Pyrogram Bot Client
app = Client(
    "hs_movie_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# In-Memory Storage for Admin Session & Dynamic Commands Data
admin_state = {}
commands_data = {}  # Format: {"cmd_1": {"title": "Movie 1", "file_id": "...", "type": "video"}}


# Helper Function: Save User Info to Firebase via REST API
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


# Helper Function: Check Channel Membership via Telegram HTTP API
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


# Main Check Joined Function
async def check_joined(user_id):
    # এডমিন হলে Force Join স্কিপ হবে
    if user_id == ADMIN_ID:
        return True
    
    check_ch1 = is_user_member_of_channel(CHANNEL_1, user_id)
    check_ch2 = is_user_member_of_channel(CHANNEL_2, user_id)
    
    return check_ch1 and check_ch2


# User: /start Command
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    save_user_to_firebase(user_id, first_name, message.from_user.username)
    
    is_joined = await check_joined(user_id)
    
    if not is_joined:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNEL_1}"),
             InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNEL_2}")],
            [InlineKeyboardButton("✅ Check / Joined", callback_data="check_join")]
        ])
        text = (
            f"👋 <b>হ্যালো {first_name}!</b>\n\n"
            f"বটটি ব্যবহার করতে এবং আপনার কাঙ্ক্ষিত ভিডিও গ্রহণ করতে আপনাকে অবশ্যই আমাদের নিচের ২টি চ্যানেলে জয়েন করতে হবে:\n\n"
            f"১. <b>Hs Movie Hub</b>\n"
            f"২. <b>Hs Shadowx</b>\n\n"
            f"👇 জয়েন করার পর নিচের <b>'Check / Joined'</b> বাটনে ক্লিক করুন।"
        )
        await message.reply_text(text, reply_markup=keyboard)
    else:
        await send_welcome_menu(message)


# Send Welcome Menu with Dynamic Inline Buttons
async def send_welcome_menu(message_or_callback):
    buttons = []
    for key, data in commands_data.items():
        buttons.append([InlineKeyboardButton(data['title'], callback_data=f"getfile_{key}")])
    
    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    text = "🎉 <b>স্বাগতম!</b>\n\nনিচে প্রদত্ত বাটনগুলো থেকে আপনার প্রয়োজনীয় ভিডিওটি সংগ্রহ করুন:"
    
    if hasattr(message_or_callback, "reply_text"):
        await message_or_callback.reply_text(text, reply_markup=reply_markup)
    else:
        await message_or_callback.message.edit_text(text, reply_markup=reply_markup)


# User & Admin Callback Query Handler
@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    
    # Check Force Join Callback
    if data == "check_join":
        is_joined = await check_joined(user_id)
        if is_joined:
            await callback_query.answer("ধন্যবাদ! আপনি সফলভাবে চ্যানেলগুলোতে জয়েন করেছেন।", show_alert=True)
            await send_welcome_menu(callback_query)
        else:
            await callback_query.answer("⚠️ আপনি এখনও ২টি চ্যানেলে জয়েন করেননি! অনুগ্রহ করে আগে জয়েন করুন।", show_alert=True)
            
    # Send Selected File to User
    elif data.startswith("getfile_"):
        is_joined = await check_joined(user_id)
        if not is_joined:
            await callback_query.answer("⚠️ ফাইলটি পেতে আপনাকে অবশ্যই চ্যানেলগুলোতে জয়েন করতে হবে!", show_alert=True)
            return

        cmd_key = data.split("getfile_")[1]
        if cmd_key in commands_data:
            file_info = commands_data[cmd_key]
            file_id = file_info['file_id']
            file_type = file_info['type']
            
            if file_type == "video":
                await client.send_video(user_id, file_id)
            elif file_type == "photo":
                await client.send_photo(user_id, file_id)
            elif file_type == "document":
                await client.send_document(user_id, file_id)
            elif file_type == "audio":
                await client.send_audio(user_id, file_id)
            await callback_query.answer()
        else:
            await callback_query.answer("ফাইলটি খুঁজে পাওয়া যায়নি বা ডিলিট করা হয়েছে!", show_alert=True)

    # ------------------- ADMIN CALLBACKS -------------------
    elif user_id == ADMIN_ID:
        if data == "admin_add_file":
            admin_state[ADMIN_ID] = {"step": "WAITING_FOR_MEDIA"}
            await callback_query.message.reply_text("আপনি যে ফাইল, ভিডিও, অডিও বা ইমেজ যোগ করতে চান তা পাঠান।")
            await callback_query.answer()
            
        elif data == "admin_manage_cmds":
            if not commands_data:
                await callback_query.answer("এখনও কোনো কমান্ড যুক্ত করা হয়নি!", show_alert=True)
            else:
                buttons = []
                for k, v in commands_data.items():
                    buttons.append([InlineKeyboardButton(f"⚙️ {v['title']}", callback_data=f"manage_{k}")])
                
                buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="admin_menu_home")])
                await callback_query.message.edit_text(
                    "<b>ম্যানেজ বাটন/কমান্ড:</b>\nনিচ থেকে যেকোনো বাটনের নাম এডিট বা ডিলিট করতে সেটি নির্বাচন করুন:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                await callback_query.answer()

        elif data == "admin_menu_home":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Movie / File", callback_data="admin_add_file")],
                [InlineKeyboardButton("📋 Manage / Edit / Delete Commands", callback_data="admin_manage_cmds")]
            ])
            await callback_query.message.edit_text("স্বাগতম এডমিন প্যানেলে! আপনার করণীয় অপশন বেছে নিন:", reply_markup=keyboard)
            await callback_query.answer()

        elif data.startswith("manage_"):
            cmd_key = data.split("manage_")[1]
            if cmd_key in commands_data:
                v = commands_data[cmd_key]
                buttons = [
                    [InlineKeyboardButton("✏️ Edit Title", callback_data=f"edit_title_{cmd_key}"),
                     InlineKeyboardButton("🗑️ Delete Command", callback_data=f"del_cmd_{cmd_key}")],
                    [InlineKeyboardButton("🔙 Back", callback_data="admin_manage_cmds")]
                ]
                await callback_query.message.edit_text(
                    f"<b>কমান্ড বিবরণী:</b>\n\n<b>Title:</b> {v['title']}\n<b>Type:</b> {v['type']}\n\nআপনি এটি দিয়ে কি করতে চান?",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                await callback_query.answer("এই কমান্ডটি পাওয়া যায়নি!", show_alert=True)

        elif data.startswith("edit_title_"):
            cmd_key = data.split("edit_title_")[1]
            if cmd_key in commands_data:
                admin_state[ADMIN_ID] = {"step": "WAITING_FOR_EDIT_TITLE", "edit_key": cmd_key}
                await callback_query.message.reply_text(f"<b>'{commands_data[cmd_key]['title']}'</b>-এর জন্য নতুন নামটি লিখে পাঠান:")
                await callback_query.answer()

        elif data.startswith("del_cmd_"):
            cmd_key = data.split("del_cmd_")[1]
            if cmd_key in commands_data:
                deleted_title = commands_data[cmd_key]['title']
                del commands_data[cmd_key]
                await callback_query.answer(f"'{deleted_title}' সফলভাবে ডিলিট করা হয়েছে!", show_alert=True)
                
                if not commands_data:
                    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="admin_menu_home")]])
                    await callback_query.message.edit_text("সব কমান্ড ডিলিট করা হয়েছে। কোনো ফাইল যুক্ত নেই।", reply_markup=keyboard)
                else:
                    buttons = []
                    for k, v in commands_data.items():
                        buttons.append([InlineKeyboardButton(f"⚙️ {v['title']}", callback_data=f"manage_{k}")])
                    buttons.append([InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="admin_menu_home")])
                    await callback_query.message.edit_text("কমান্ড সফলভাবে ডিলিট করা হয়েছে!\n\nবর্তমান তালিকা:", reply_markup=InlineKeyboardMarkup(buttons))


# Admin Panel: /admin Command
@app.on_message(filters.command("admin") & filters.user(ADMIN_ID) & filters.private)
async def admin_panel(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Movie / File", callback_data="admin_add_file")],
        [InlineKeyboardButton("📋 Manage / Edit / Delete Commands", callback_data="admin_manage_cmds")]
    ])
    await message.reply_text("স্বাগতম এডমিন প্যানেলে! আপনার করণীয় অপশন বেছে নিন:", reply_markup=keyboard)


# Admin Message Handler (Add / Edit input handling)
@app.on_message(filters.user(ADMIN_ID) & filters.private & ~filters.command(["start", "admin"]))
async def admin_message_handler(client, message):
    state = admin_state.get(ADMIN_ID, {}).get("step")
    
    # Step 1: Receiving File/Media from Admin
    if state == "WAITING_FOR_MEDIA":
        file_id = None
        file_type = None
        
        if message.video:
            file_id = message.video.file_id
            file_type = "video"
        elif message.photo:
            file_id = message.photo.file_id
            file_type = "photo"
        elif message.document:
            file_id = message.document.file_id
            file_type = "document"
        elif message.audio:
            file_id = message.audio.file_id
            file_type = "audio"
            
        if file_id:
            admin_state[ADMIN_ID] = {
                "step": "WAITING_FOR_TITLE",
                "temp_file_id": file_id,
                "temp_type": file_type
            }
            await message.reply_text("মিডিয়া পাওয়া গেছে! এখন বাটন বা কমান্ডের নামটি লিখে পাঠান।")
        else:
            await message.reply_text("দয়া করে একটি সঠিক ভিডিও, ছবি বা ফাইল পাঠান।")
            
    # Step 2: Receiving Button Title & Saving Command
    elif state == "WAITING_FOR_TITLE":
        cmd_title = message.text.strip()
        temp_data = admin_state.get(ADMIN_ID, {})
        
        cmd_key = f"cmd_{len(commands_data) + 1}"
        while cmd_key in commands_data:
            cmd_key += "_1"

        commands_data[cmd_key] = {
            "title": cmd_title,
            "file_id": temp_data.get("temp_file_id"),
            "type": temp_data.get("temp_type")
        }
        
        admin_state[ADMIN_ID] = {}
        await message.reply_text(f"✅ সাকসেসফুলি অ্যাড হয়েছে!\n\nবাটনের নাম: <b>{cmd_title}</b>\nইউজারদের ওয়েলকাম মেনুতে এই বাটনটি যুক্ত হয়ে গেছে।")

    # Step 3: Editing Title of existing Command
    elif state == "WAITING_FOR_EDIT_TITLE":
        new_title = message.text.strip()
        edit_key = admin_state.get(ADMIN_ID, {}).get("edit_key")
        
        if edit_key and edit_key in commands_data:
            commands_data[edit_key]["title"] = new_title
            admin_state[ADMIN_ID] = {}
            await message.reply_text(f"✅ বাটনের নাম আপডেট করে <b>'{new_title}'</b> রাখা হয়েছে!")
        else:
            await message.reply_text("আপডেট করতে ব্যর্থ হয়েছে, আবার চেষ্টা করুন।")


if __name__ == "__main__":
    # Start Flask Web Server in Background Thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("Bot is starting...")
    app.run()
