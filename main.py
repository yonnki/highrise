import os
import asyncio
from highrise import BaseBot, User, Position
import time

class RailwayBot(BaseBot):
    def __init__(self):
        super().__init__()
        self.clicks = {}
        
    async def on_start(self, session_metadata):
        print("🟢 البوت شغال على Railway!")
        await self.highrise.chat("🎮 انقر نقرتين سريعتين على أي مكان!")
        
    async def on_user_click(self, user: User, pos: Position, obj_id: str = None):
        try:
            current_time = time.time()
            user_id = user.id
            
            print(f"🎯 {user.username} نقر على: ({pos.x:.1f}, {pos.y:.1f}, {pos.z:.1f})")
            
            if user_id in self.clicks:
                last_time = self.clicks[user_id]
                if current_time - last_time < 1.0:
                    print(f"🚀 نقرة مزدوجة! بتنقل {user.username}")
                    await self.highrise.teleport(user.id, pos)
                    await self.highrise.whisper(user.id, "🎯 انتقلت!")
                    del self.clicks[user_id]
                    return
            
            self.clicks[user_id] = current_time
            
        except Exception as e:
            print(f"❌ خطأ: {e}")

if __name__ == "__main__":
    # المتغيرات مباشرة في الكود
    ROOM_ID = "65ec8ba1a11c3c2221a7c1a8"
    API_TOKEN = "6c10af66df88f04e1d68189135dc82a79ad3604aed82d539277e1a2c382852f1"
    
    os.system(f"highrise main:RailwayBot {ROOM_ID} {API_TOKEN}")
