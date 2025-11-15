import os
import asyncio
from highrise import BaseBot, User, Position
import random
import time
from flask import Flask
import threading
import requests

# ===== إعدادات البوت =====
ROOM_ID = "68e7e3d7dc5306e315d2289b"
API_TOKEN = "6c10af66df88f04e1d68189135dc82a79ad3604aed82d539277e1a2c382852f1"
ADMIN_USERNAME = "Yonnki_HB"
ADMINS = ["Yonnki_HB", "0.OI"]  # قائمة المشرفين

# ===== نظام التشغيل الدائم لـ Render =====
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 البوت شغال بشكل دائم على Render!"

@app.route('/ping')
def ping():
    return "pong"

@app.route('/status')
def status():
    return {
        "status": "online",
        "bot": "running", 
        "platform": "Render",
        "time": time.strftime('%Y-%m-%d %H:%M:%S')
    }

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """بدء سيرفر ويب للحفاظ على التشغيل"""
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    print(f"🚀 بدأ سيرفر الويب على port {os.environ.get('PORT', 8080)}")

# ===== البوت الرئيسي =====
class SimpleBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.is_running = True
        self.welcomed_users = set()
        self.returning_users = set()
        self.follow_target = None
        self.follow_task = None
        self.bot_id = None
        self.frozen_users = {}
        self.bad_words = ["كس", "شرموط", "عاهر", "قحبة", "زبالة", "كلب", "حيوان", "خرا", "طيز", "نيك", "منيك", "منيوك"]
        self.authorized_users = set()  # المستخدمين المخولين باستخدام أوامر هات/روح
        self.protected_users = set()  # المستخدمين المحميين من السحب

    async def on_start(self, session_metadata):
        print("[BOT] ✅ متصل بالغرفة على Render")
        self.bot_id = session_metadata.user_id
        await self.highrise.chat("🤖 البوت شغال بشكل دائم على Render!")
        
        # بدء المهام
        asyncio.create_task(self.auto_welcome())
        asyncio.create_task(self.welcome_new_users())
        asyncio.create_task(self.keep_alive_task())

    async def keep_alive_task(self):
        """مهمة للحفاظ على التشغيل الدائم"""
        while self.is_running:
            try:
                print(f"[BOT] 🟢 البوت شغال على Render - {time.strftime('%H:%M:%S')}")
                await asyncio.sleep(300)  # كل 5 دقائق
            except Exception as e:
                print(f"[BOT] ❌ خطأ في مهمة الحفاظ: {e}")
                await asyncio.sleep(60)

    async def welcome_new_users(self):
        """يرحب بالمستخدمين الجدد والعائدين"""
        while self.is_running:
            try:
                room_users = await self.highrise.get_room_users()
                current_users = {user.id for user, pos in room_users.content}
                
                # المستخدمين الجدد (لم يتم ترحيبهم من قبل)
                new_users = current_users - self.welcomed_users
                
                # المستخدمين العائدين (كانوا في الغرفة من قبل وتركوا وعادوا)
                returned_users = current_users & self.welcomed_users - self.returning_users
                
                for user_id in new_users:
                    for user_obj, pos in room_users.content:
                        if user_obj.id == user_id:
                            # انتظار ثانية ثم الترحيب بالمستخدم الجديد
                            await asyncio.sleep(1)
                            await self.highrise.chat(f"أهلاً وسهلاً {user_obj.username}! 🌟")
                            self.welcomed_users.add(user_id)
                            self.returning_users.add(user_id)
                            print(f"[BOT] 👋 ترحيب جديد بـ {user_obj.username}")
                            break
                
                for user_id in returned_users:
                    for user_obj, pos in room_users.content:
                        if user_obj.id == user_id:
                            # إرسال رياكشن قلب وترحيب للعائدين
                            try:
                                await self.highrise.react("heart", user_id)
                                await self.highrise.chat(f"💖 أهلاً بعودة {user_obj.username}! نورت الغرفة مرة ثانية!")
                                self.returning_users.add(user_id)
                                print(f"[BOT] 💖 رياكشن قلب وترحيب للعائد {user_obj.username}")
                            except Exception as e:
                                print(f"[BOT] ❌ فشل إرسال رياكشن للعائد: {e}")
                            break
                
                # إزالة المستخدمين الذين غادروا الغرفة من returning_users
                left_users = self.returning_users - current_users
                self.returning_users -= left_users
                
                await asyncio.sleep(1)  # تحقق سريع
                
            except Exception as e:
                print(f"[BOT] ❌ خطأ في الترحيب: {e}")
                await asyncio.sleep(5)

    async def on_chat(self, user: User, message: str):
        message_lower = message.lower()

        # كشف الكلمات السيئة وإرسال تنبيه عام
        found_bad_words = []
        for word in self.bad_words:
            if word in message_lower:
                found_bad_words.append(word)
        
        if found_bad_words:
            # إرسال تنبيه عام للجميع
            await self.highrise.chat(f"🚨 {user.username} استخدم كلمات غير لائقة!")
            await self.highrise.chat(f"🔞 الكلمات: {', '.join(found_bad_words)}")
            print(f"[BOT] 🚨 {user.username} سب: {found_bad_words}")

        # التحقق إذا كان المستخدم مشرف
        is_admin = user.username in ADMINS
        is_authorized = user.id in self.authorized_users or user.username == "Yonnki_HB"

        # أمر الأوامر (للجميع) - رسالة عامة
        if message_lower == "اوامر":
            await self.handle_show_commands(user, is_admin, is_authorized)
            return

        # ===== الأوامر الجديدة الخاصة بالمشرفين و Yonnki_HB =====
        
        # أمر اربح @اسم شخص (للمشرفين و Yonnki_HB فقط)
        elif message_lower.startswith("ارحب @") and (is_admin or user.username == "Yonnki_HB"):
            await self.handle_wave_to_user(user, message)

        # أمر تؤبرني @اسم شخص (للمشرفين و Yonnki_HB فقط)
        elif (message_lower.startswith("تؤبرني @") or message_lower.startswith("تؤبريني @")) and (is_admin or user.username == "Yonnki_HB"):
            await self.handle_wink_to_user(user, message)

        # أمر HB الكل (للمشرفين و Yonnki_HB فقط)
        elif message_lower == "hb الكل" and (is_admin or user.username == "Yonnki_HB"):
            await self.handle_hearts_to_all(user)

        # أمر غمزات (للمشرفين و Yonnki_HB فقط) - بدون رسالة
        elif message_lower == "غمزات" and (is_admin or user.username == "Yonnki_HB"):
            await self.handle_winks_to_all(user)

        # أمر ترحيب جماعي (للمشرفين و Yonnki_HB فقط) - بدون رسالة
        elif message_lower == "ترحيب جماعي" and (is_admin or user.username == "Yonnki_HB"):
            await self.handle_waves_to_all(user)

        # ===== الأوامر الحالية =====

        # أمر إعطاء أوامر @اسم (لـ Yonnki_HB فقط)
        elif message_lower.startswith("اعطيه اوامر @") and user.username == "Yonnki_HB":
            await self.handle_give_commands(user, message)

        # أمر شيل اوامر @اسم (لـ Yonnki_HB فقط)
        elif message_lower.startswith("شيل اوامر @") and user.username == "Yonnki_HB":
            await self.handle_remove_commands(user, message)

        # أمر حماية @اسم (لـ Yonnki_HB فقط)
        elif message_lower.startswith("حماية @") and user.username == "Yonnki_HB":
            await self.handle_protect_user(user, message)

        # أمر شيل حماية @اسم (لـ Yonnki_HB فقط)
        elif message_lower.startswith("شيل حماية @") and user.username == "Yonnki_HB":
            await self.handle_unprotect_user(user, message)

        # أمر يروح @شخص1 @شخص2 (للمشرفين والمخولين فقط)
        elif message_lower.startswith("يروح @") and (is_admin or is_authorized):
            await self.handle_send_user(user, message)

        # أمر بدل @شخص (للمشرفين والمخولين فقط)
        elif message_lower.startswith("بدل @") and (is_admin or is_authorized):
            await self.handle_swap_users(user, message)

        # أمر تعا (لـ Yonnki_HB فقط)
        elif message_lower == "تعا":
            if user.username != "Yonnki_HB":
                try:
                    await self.highrise.whisper(user.id, "❌ هذا الأمر مخصص للمشرف Yonnki_HB فقط!")
                except:
                    pass
                return
                
            if self.follow_target == user.id:
                return
                
            if self.follow_task and not self.follow_task.done():
                self.follow_task.cancel()
                
            self.follow_target = user.id
            self.follow_task = asyncio.create_task(self.follow_user())
            # بدون رسالة تأكيد
            print(f"[BOT] 🎯 البوت يتبع {user.username}")

        # أمر وقف (لـ Yonnki_HB فقط)
        elif message_lower == "وقف":
            if user.username != "Yonnki_HB":
                try:
                    await self.highrise.whisper(user.id, "❌ هذا الأمر مخصص للمشرف Yonnki_HB فقط!")
                except:
                    pass
                return

            if self.follow_target == user.id:
                self.follow_target = None
                if self.follow_task and not self.follow_task.done():
                    self.follow_task.cancel()
                # بدون رسالة تأكيد
                print(f"[BOT] 🛑 البوت توقف عن متابعة {user.username}")

        # أمر فوق (للجميع)
        elif message_lower == "فوق":
            await self.handle_up(user)

        # أمر تحت (للجميع)
        elif message_lower == "تحت":
            await self.handle_down(user)

        # أمر روح @شخص (للمشرفين والمخولين فقط)
        elif message_lower.startswith("روح @") and (is_admin or is_authorized):
            await self.handle_goto(user, message)

        # أمر VIP (للمشرفين والمخولين فقط)
        elif message_lower == "vip" and (is_admin or is_authorized):
            await self.handle_vip(user)

        # أمر هات @اسم (للمشرفين والمخولين فقط)
        elif message_lower.startswith("هات @") and (is_admin or is_authorized):
            await self.handle_teleport(user, message)

        # أمر HB @اسم (للمشرفين والمخولين فقط)
        elif message_lower.startswith("hb @") and (is_admin or is_authorized):
            await self.handle_hearts(user, message)

        # أمر ثبت @اسم (للمشرفين والمخولين فقط)
        elif message_lower.startswith("ثبت @") and (is_admin or is_authorized):
            await self.handle_freeze(user, message)

        # أمر فك @اسم (للمشرفين والمخولين فقط)
        elif message_lower.startswith("فك @") and (is_admin or is_authorized):
            await self.handle_unfreeze(user, message)

        # إذا حاول مستخدم عادي استخدام أوامر المشرفين
        elif any(message_lower.startswith(cmd) for cmd in ["روح @", "هات @", "hb @", "ثبت @", "فك @", "يروح @", "بدل @", "ارحب @", "تؤبرني @", "تؤبريني @", "حماية @", "شيل حماية @"]) and not (is_admin or is_authorized):
            try:
                await self.highrise.whisper(user.id, "❌ هذا الأمر للمشرفين والمخولين فقط!")
                print(f"[BOT] ⚠️ {user.username} حاول استخدام أمر للمشرفين")
            except:
                pass  # إذا فشل الرسالة الخاصة

    # ===== الدوال الجديدة للحماية =====

    async def handle_protect_user(self, user: User, message: str):
        """إضافة مستخدم للحماية من السحب (لـ Yonnki_HB فقط)"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            target_found = False
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    self.protected_users.add(room_user.id)
                    await self.highrise.chat(f"🛡️ تم حماية {target_username} من السحب")
                    print(f"[BOT] 🛡️ {user.username} حمى {target_username} من السحب")
                    target_found = True
                    break
            
            if not target_found:
                await self.highrise.chat(f"❌ لم أجد المستخدم {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر حماية: {e}")

    async def handle_unprotect_user(self, user: User, message: str):
        """إزالة مستخدم من الحماية (لـ Yonnki_HB فقط)"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            target_found = False
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    if room_user.id in self.protected_users:
                        self.protected_users.remove(room_user.id)
                        await self.highrise.chat(f"✅ تم إزالة الحماية عن {target_username}")
                        print(f"[BOT] ✅ {user.username} أزال حماية {target_username}")
                    else:
                        await self.highrise.chat(f"❌ {target_username} ليس محمياً")
                    
                    target_found = True
                    break
            
            if not target_found:
                await self.highrise.chat(f"❌ لم أجد المستخدم {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر شيل حماية: {e}")

    def is_user_protected(self, user_id: str, username: str) -> bool:
        """التحقق إذا كان المستخدم محمياً من السحب"""
        # Yonnki_HB دائماً محمي
        if username.lower() == "yonnki_hb":
            return True
        return user_id in self.protected_users

    # ===== الدوال الجديدة للرياكشنات =====

    async def handle_wave_to_user(self, user: User, message: str):
        """إرسال 👋 لمستخدم معين - بدون رسالة"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            target_found = False
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    await self.highrise.react("wave", room_user.id)
                    # بدون رسالة تأكيد
                    print(f"[BOT] 👋 {user.username} أرسل ترحيب لـ {target_username}")
                    target_found = True
                    break
            
            if not target_found:
                # فقط إذا لم يجد المستخدم
                await self.highrise.chat(f"❌ لم أجد المستخدم {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر اربح: {e}")

    async def handle_wink_to_user(self, user: User, message: str):
        """إرسال 😉 لمستخدم معين - بدون رسالة"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            target_found = False
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    await self.highrise.react("wink", room_user.id)
                    # بدون رسالة تأكيد
                    print(f"[BOT] 😉 {user.username} أرسل غمزة لـ {target_username}")
                    target_found = True
                    break
            
            if not target_found:
                # فقط إذا لم يجد المستخدم
                await self.highrise.chat(f"❌ لم أجد المستخدم {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر تؤبرني: {e}")

    async def handle_hearts_to_all(self, user: User):
        """إرسال قلوب للجميع - بدون رسالة"""
        try:
            room_users = await self.highrise.get_room_users()
            # بدون رسالة تأكيد
            
            for room_user, pos in room_users.content:
                if room_user.id != self.bot_id:  # لا ترسل للبوت نفسه
                    await self.send_multiple_heart_reactions(room_user.id)
                    await asyncio.sleep(0.3)  # تأخير بين كل مستخدم
            
            print(f"[BOT] 💖 {user.username} أرسل قلوب للجميع")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر HB الكل: {e}")

    async def handle_winks_to_all(self, user: User):
        """إرسال 😉 للجميع - بدون رسالة"""
        try:
            room_users = await self.highrise.get_room_users()
            # بدون رسالة تأكيد
            
            for room_user, pos in room_users.content:
                if room_user.id != self.bot_id:  # لا ترسل للبوت نفسه
                    try:
                        await self.highrise.react("wink", room_user.id)
                        await asyncio.sleep(0.2)  # تأخير بين كل مستخدم
                    except Exception:
                        continue
            
            print(f"[BOT] 😉 {user.username} أرسل غمزات للجميع")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر غمزات: {e}")

    async def handle_waves_to_all(self, user: User):
        """إرسال 👋 للجميع - بدون رسالة"""
        try:
            room_users = await self.highrise.get_room_users()
            # بدون رسالة تأكيد
            
            for room_user, pos in room_users.content:
                if room_user.id != self.bot_id:  # لا ترسل للبوت نفسه
                    try:
                        await self.highrise.react("wave", room_user.id)
                        await asyncio.sleep(0.2)  # تأخير بين كل مستخدم
                    except Exception:
                        continue
            
            print(f"[BOT] 👋 {user.username} أرسل ترحيب جماعي")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر ترحيب جماعي: {e}")

    # ===== الدوال الحالية (محدثة بدون رسائل تأكيد) =====

    async def handle_show_commands(self, user: User, is_admin: bool, is_authorized: bool):
        """عرض الأوامر للجميع برسالة عامة"""
        try:
            commands_message = "📋 **أوامر البوت المتاحة:**\n\n"
            
            # الأوامر للجميع
            commands_message += "🎮 **أوامر للجميع:**\n"
            commands_message += "• `فوق` - نقل عشوائي للأعلى\n"
            commands_message += "• `تحت` - نقل عشوائي للأسفل\n"
            commands_message += "• `اوامر` - عرض قائمة الأوامر\n\n"
            
            # الأوامر للمخولين والمشرفين
            if is_authorized or is_admin:
                commands_message += "🔧 **أوامر المخولين والمشرفين:**\n"
                commands_message += "• `هات @اسم` - سحب مستخدم\n"
                commands_message += "• `روح @اسم` - الانتقال لمستخدم\n"
                commands_message += "• `يروح @شخص1 @شخص2` - إرسال شخص لشخص\n"
                commands_message += "• `بدل @اسم` - تبادل الأماكن\n"
                commands_message += "• `vip` - نقل لمنطقة VIP\n"
                commands_message += "• `hb @اسم` - إرسال قلوب\n"
                commands_message += "• `ثبت @اسم` - تثبيت مستخدم\n"
                commands_message += "• `فك @اسم` - فك التثبيت\n\n"
            
            # الأوامر الحصرية لـ Yonnki_HB والمشرفين
            if user.username == "Yonnki_HB" or is_admin:
                commands_message += "👑 **أوامر المشرفين و Yonnki_HB:**\n"
                commands_message += "• `ارحب @اسم` - إرسال 👋 لمستخدم\n"
                commands_message += "• `تؤبرني @اسم` - إرسال 😉 لمستخدم\n"
                commands_message += "• `HB الكل` - إرسال قلوب للجميع\n"
                commands_message += "• `غمزات` - إرسال 😉 للجميع\n"
                commands_message += "• `ترحيب جماعي` - إرسال 👋 للجميع\n\n"
            
            # الأوامر الحصرية لـ Yonnki_HB فقط
            if user.username == "Yonnki_HB":
                commands_message += "⚡ **أوامر Yonnki_HB الحصرية:**\n"
                commands_message += "• `تعا` - البوت يتبعك\n"
                commands_message += "• `وقف` - البوت يتوقف\n"
                commands_message += "• `اعطيه اوامر @اسم` - منح صلاحية هات/روح\n"
                commands_message += "• `شيل اوامر @اسم` - سحب صلاحية هات/روح\n"
                commands_message += "• `حماية @اسم` - حماية مستخدم من السحب\n"
                commands_message += "• `شيل حماية @اسم` - إزالة الحماية عن مستخدم\n\n"
            
            # رسالة للمستخدمين العاديين
            if not is_admin and not is_authorized:
                commands_message += "💡 **ملاحظة:** الأوامر الأخرى للمشرفين والمخولين فقط\n"
                commands_message += "اطلب من Yonnki_HB ليمنحك الصلاحية باستخدام `اعطيه اوامر @اسمك`"
            
            # إرسال الرسالة العامة بدلاً من الخاصة
            await self.highrise.chat(commands_message)
            print(f"[BOT] 📋 {user.username} طلب عرض الأوامر (رسالة عامة)")
            
        except Exception as e:
            print(f"[BOT] ❌ خطأ في عرض الأوامر: {e}")

    async def handle_give_commands(self, user: User, message: str):
        """إعطاء صلاحية أوامر هات/روح لمستخدم"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            target_found = False
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    self.authorized_users.add(room_user.id)
                    # بدون رسالة تأكيد عامة
                    await self.highrise.whisper(room_user.id, "🎉 تم منحك صلاحية استخدام أوامر 'هات' و 'روح' من قبل Yonnki_HB!")
                    print(f"[BOT] ✅ {user.username} منح صلاحية هات/روح لـ {target_username}")
                    target_found = True
                    break
            
            if not target_found:
                await self.highrise.chat(f"❌ لم أجد المستخدم {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في منح الصلاحية: {e}")

    async def handle_remove_commands(self, user: User, message: str):
        """سحب صلاحية أوامر هات/روح من مستخدم"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            target_found = False
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    if room_user.id in self.authorized_users:
                        self.authorized_users.remove(room_user.id)
                        # بدون رسالة تأكيد عامة
                        await self.highrise.whisper(room_user.id, "⚠️ تم سحب صلاحية استخدام أوامر 'هات' و 'روح' منك!")
                        print(f"[BOT] ✅ {user.username} سحب صلاحية هات/روح من {target_username}")
                    else:
                        await self.highrise.chat(f"❌ {target_username} ليس لديه صلاحية أوامر هات/روح")
                    
                    target_found = True
                    break
            
            if not target_found:
                await self.highrise.chat(f"❌ لم أجد المستخدم {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في سحب الصلاحية: {e}")

    async def handle_send_user(self, user: User, message: str):
        """إرسال شخص لشخص آخر (يروح @شخص1 @شخص2) - بدون رسالة"""
        try:
            # استخراج الأسماء من الرسالة
            parts = message.split('@')
            if len(parts) < 3:
                await self.highrise.chat("❌ استخدم: يروح @اسم_الشخص_الأول @اسم_الشخص_الثاني")
                return
            
            source_username = parts[1].split()[0].strip()  # الشخص الأول
            target_username = parts[2].strip()  # الشخص الثاني
            
            room_users = await self.highrise.get_room_users()
            
            source_user_id = None
            target_position = None
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == source_username.lower():
                    # التحقق إذا كان المستخدم محمياً
                    if self.is_user_protected(room_user.id, room_user.username):
                        await self.highrise.chat(f"❌ لا يمكن سحب {source_username} لأنه محمي!")
                        return
                    source_user_id = room_user.id
                if room_user.username.lower() == target_username.lower():
                    target_position = pos
            
            if source_user_id and target_position:
                # إنشاء موقع بجوار الشخص المستهدف
                send_position = Position(
                    target_position.x + 1.0,  # على بعد 1 متر
                    target_position.y,
                    target_position.z,
                    target_position.facing
                )
                await self.highrise.teleport(source_user_id, send_position)
                # بدون رسالة تأكيد
                print(f"[BOT] 🚀 {user.username} أرسل {source_username} لـ {target_username}")
            else:
                await self.highrise.chat("❌ لم أجد أحد المستخدمين المطلوبين")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر يروح: {e}")

    async def handle_swap_users(self, user: User, message: str):
        """تبادل الأماكن بين المستخدم وشخص آخر (بدل @شخص) - بدون رسالة"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            
            user_position = None
            target_user_id = None
            target_position = None
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == user.username.lower():
                    user_position = pos
                if room_user.username.lower() == target_username.lower():
                    # التحقق إذا كان المستخدم محمياً
                    if self.is_user_protected(room_user.id, room_user.username):
                        await self.highrise.chat(f"❌ لا يمكن تبادل الأماكن مع {target_username} لأنه محمي!")
                        return
                    target_user_id = room_user.id
                    target_position = pos
            
            if user_position and target_user_id and target_position:
                # تبادل الأماكن
                await self.highrise.teleport(user.id, target_position)
                await self.highrise.teleport(target_user_id, user_position)
                # بدون رسالة تأكيد
                print(f"[BOT] 🔄 {user.username} بدل مكانه مع {target_username}")
            else:
                await self.highrise.chat(f"❌ لم أجد المستخدم {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في أمر بدل: {e}")

    async def handle_up(self, user: User):
        """نقل المستخدم لأعلى بإحداثيات عشوائية - بدون رسالة"""
        try:
            # إحداثيات عشوائية في الأعلى
            random_x = random.uniform(-5.0, 5.0)
            random_y = random.uniform(8.0, 12.0)  # ارتفاع عشوائي
            random_z = random.uniform(-5.0, 5.0)
            
            up_position = Position(random_x, random_y, random_z)
            await self.highrise.teleport(user.id, up_position)
            print(f"[BOT] 🚀 نقل {user.username} للأعلى")
            
        except Exception as e:
            print(f"[BOT] ❌ خطأ في نقل للأعلى: {e}")

    async def handle_down(self, user: User):
        """نقل المستخدم لأسفل بإحداثيات عشوائية - بدون رسالة"""
        try:
            # إحداثيات عشوائية في الأسفل
            random_x = random.uniform(-5.0, 5.0)
            random_y = random.uniform(0.0, 2.0)  # مستوى منخفض
            random_z = random.uniform(-5.0, 5.0)
            
            down_position = Position(random_x, random_y, random_z)
            await self.highrise.teleport(user.id, down_position)
            print(f"[BOT] 📉 نقل {user.username} للأسفل")
            
        except Exception as e:
            print(f"[BOT] ❌ خطأ في نقل للأسفل: {e}")

    async def handle_goto(self, user: User, message: str):
        """انتقال المستخدم لشخص آخر - بدون رسالة"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            
            target_position = None
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    target_position = pos
                    break
            
            if target_position:
                # إنشاء موقع بجوار الشخص المستهدف
                goto_position = Position(
                    target_position.x + 1.0,  # على بعد 1 متر
                    target_position.y,
                    target_position.z,
                    target_position.facing
                )
                await self.highrise.teleport(user.id, goto_position)
                print(f"[BOT] 🚶 {user.username} انتقل لـ {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في الانتقال: {e}")

    async def handle_vip(self, user: User):
        """نقل المستخدم لمنطقة VIP بإحداثيات عشوائية - بدون رسالة"""
        try:
            # إحداثيات VIP عشوائية
            random_x = random.uniform(8.0, 15.0)  # منطقة خاصة
            random_y = random.uniform(3.0, 6.0)
            random_z = random.uniform(8.0, 15.0)
            
            vip_position = Position(random_x, random_y, random_z)
            await self.highrise.teleport(user.id, vip_position)
            print(f"[BOT] 👑 نقل {user.username} لمنطقة VIP")
            
        except Exception as e:
            print(f"[BOT] ❌ خطأ في نقل لـ VIP: {e}")

    async def handle_teleport(self, user: User, message: str):
        """معالجة أمر السحب - بدون رسالة"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            
            user_position = None
            target_user_id = None
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == user.username.lower():
                    user_position = pos
                if room_user.username.lower() == target_username.lower():
                    # التحقق إذا كان المستخدم محمياً
                    if self.is_user_protected(room_user.id, room_user.username):
                        await self.highrise.chat(f"❌ لا يمكن سحب {target_username} لأنه محمي!")
                        return
                    target_user_id = room_user.id
            
            if user_position and target_user_id:
                await self.highrise.teleport(target_user_id, user_position)
                print(f"[BOT] 📥 {user.username} سحب {target_username}")
                
            elif target_username.lower() in ["البوت", "bot"]:
                if user_position:
                    await self.highrise.walk_to(user_position)
                    print(f"[BOT] 🤖 {user.username} حرك البوت")
                    
        except Exception as e:
            print(f"[BOT] ❌ خطأ في السحب: {e}")

    async def handle_hearts(self, user: User, message: str):
        """معالجة أمر HB - بدون رسالة"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            
            target_user_id = None
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    target_user_id = room_user.id
                    break
            
            if target_user_id:
                # إرسال 10 رياكشن قلب بدون رسائل
                await self.send_multiple_heart_reactions(target_user_id)
                print(f"[BOT] 💖 {user.username} أرسل قلوب لـ {target_username}")
                    
        except Exception as e:
            print(f"[BOT] ❌ خطأ في القلوب: {e}")

    async def send_multiple_heart_reactions(self, target_user_id: str):
        """إرسال 10 رياكشن قلب بدون رسائل"""
        for i in range(10):
            try:
                await self.highrise.react("heart", target_user_id)
                if i < 9:
                    await asyncio.sleep(0.2)
            except Exception:
                continue

    async def handle_freeze(self, user: User, message: str):
        """معالجة أمر التثبيت - بدون رسالة"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            
            target_user_id = None
            target_position = None
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    target_user_id = room_user.id
                    target_position = pos
                    break
            
            if target_user_id:
                self.frozen_users[target_user_id] = target_position
                print(f"[BOT] ⛔ {user.username} ثبت {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في التثبيت: {e}")

    async def handle_unfreeze(self, user: User, message: str):
        """معالجة أمر فك التثبيت - بدون رسالة"""
        try:
            target_username = message.split("@")[1].strip()
            
            room_users = await self.highrise.get_room_users()
            
            target_user_id = None
            
            for room_user, pos in room_users.content:
                if room_user.username.lower() == target_username.lower():
                    target_user_id = room_user.id
                    break
            
            if target_user_id and target_user_id in self.frozen_users:
                del self.frozen_users[target_user_id]
                print(f"[BOT] ✅ {user.username} فك تثبيت {target_username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في فك التثبيت: {e}")

    async def on_user_move(self, user: User, pos: Position):
        """يمنع الحركة للمستخدمين المثبتين"""
        if user.id in self.frozen_users:
            saved_pos = self.frozen_users[user.id]
            await self.highrise.teleport(user.id, saved_pos)

    async def on_moderation(self, action: str, moderator: User, target: User, reason: str = None):
        """يتعامل مع أحداث الإدارة ويرسل تنبيه خاص"""
        try:
            if action in ["kick", "ban", "mute"]:
                alert_message = f"🚨 تنبيه إدارة:\n👮 المشرف: {moderator.username}\n🎯 المستخدم: {target.username}\n🔧 الإجراء: {action}"
                if reason:
                    alert_message += f"\n📝 السبب: {reason}"
                
                # البحث عن المشرف في الغرفة
                room_users = await self.highrise.get_room_users()
                admin_user = None
                
                for room_user, pos in room_users.content:
                    if room_user.username.lower() == ADMIN_USERNAME.lower():
                        admin_user = room_user
                        break
                
                if admin_user:
                    try:
                        # إرسال رسالة خاصة للمشرف
                        await self.highrise.whisper(admin_user.id, alert_message)
                        print(f"[BOT] 📨 تم إرسال تنبيه خاص لـ {ADMIN_USERNAME}")
                    except Exception as whisper_error:
                        print(f"[BOT] ❌ فشل إرسال الرسالة الخاصة: {whisper_error}")
                else:
                    print(f"[BOT] ❌ المشرف {ADMIN_USERNAME} غير موجود في الغرفة")
                
                print(f"[BOT] 🚨 {moderator.username} {action} {target.username}")
                
        except Exception as e:
            print(f"[BOT] ❌ خطأ في معالجة الإدارة: {e}")

    async def follow_user(self):
        """مهمة ملاحقة المستخدم"""
        while self.follow_target and self.is_running:
            try:
                room_users = await self.highrise.get_room_users()
                target_position = None
                
                for room_user, pos in room_users.content:
                    if room_user.id == self.follow_target:
                        target_position = pos
                        break
                
                if target_position:
                    follow_position = Position(
                        target_position.x,
                        target_position.y, 
                        target_position.z,
                        target_position.facing
                    )
                    
                    await self.highrise.walk_to(follow_position)
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"[BOT] ❌ خطأ في الملاحقة: {e}")
                await asyncio.sleep(2)

    async def auto_welcome(self):
        """يرسل ترحيبات عامة كل 15 ثانية"""
        messages = [
            "✨ أهلاً وسهلاً بالجميع!",
            "🌹 نورتوا الغرفة!",
            "💫 تشرفنا بوجودكم!",
            "🌟 يا هلا بالطيبين!",
            "🎉 أهلاً بالحلوين!"
        ]
        
        while self.is_running:
            message = random.choice(messages)
            await self.highrise.chat(message)
            await asyncio.sleep(15)

# ===== التشغيل الرئيسي =====
if __name__ == "__main__":
    # بدء جميع الخدمات
    keep_alive()
    
    print("🚀 بدأ تشغيل البوت بشكل دائم على Render...")
    print("🌐 سيرفر الويب شغال للحفاظ على التشغيل")
    
    # تشغيل البوت
    os.system(f"highrise main:SimpleBot {ROOM_ID} {API_TOKEN}")
