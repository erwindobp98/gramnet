import os
import json
import random
import asyncio
import sqlite3
import urllib.parse
import time
import requests
from telethon import TelegramClient
from telethon.tl.functions.messages import RequestWebViewRequest

# =====================================================================
# 🛠️ DAFTAR URUTAN AKUN KAMU
# =====================================================================
DAFTAR_AKUN = [
    "ween", "nana", "nanik", "ulan", "yani", "lilis", "sae", 
    "susi", "budi", "ferry", "telo"
]

# =====================================================================
# ⚙️ PENGATURAN UTAMA GRAM NETWORK
# =====================================================================
START_PARAM = "917401265"  
TARGET_BOT = "Gramnetwork_bot"
TARGET_URL = "https://app.gramnetwork.online/"
FILE_CACHE = "gram_cache.json"  

# Pengaturan Jeda (Detik)
DELAY_MIN = 5   
DELAY_MAX = 15  

# API ID & Hash bawaan Telegram Android resmi
API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

# =====================================================================
# 🛡️ FUNGSI PEMBERSIHAN DATABASE (DARURAT)
# =====================================================================
def murnikan_tabel(cursor, nama_tabel, kolom_asli_str, buat_tabel_sql):
    try:
        cursor.execute(f"PRAGMA table_info({nama_tabel})")
        kolom_info = cursor.fetchall()
        if not kolom_info:
            cursor.execute(buat_tabel_sql)
            return
        kolom_sekarang = [k[1] for k in kolom_info]  
        jumlah_kolom_asli = len(kolom_asli_str.split(", "))  
        if "number" in kolom_sekarang or len(kolom_sekarang) != jumlah_kolom_asli:  
            try: 
                # Diberi try-except internal agar jika kolom tidak cocok, tidak melempar eror keluar
                cursor.execute(f"SELECT {kolom_asli_str} FROM {nama_tabel}")  
                data_asli = cursor.fetchall()  
            except Exception: 
                data_asli = []  
                
            cursor.execute(f"DROP TABLE IF EXISTS {nama_tabel}")  
            cursor.execute(buat_tabel_sql)  
            if data_asli:  
                placeholders = ", ".join(["?"] * jumlah_kolom_asli)  
                try:
                    cursor.executemany(f"INSERT INTO {nama_tabel} VALUES ({placeholders})", data_asli)  
                except Exception: pass
    except Exception: pass

def murnikan_database_telethon(nama_session):
    nama_file = f"{nama_session}.session"
    if not os.path.exists(nama_file): return
    try:
        conn = sqlite3.connect(nama_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")  
        tabel_list = [t[0] for t in cursor.fetchall()]  
        if "session" in tabel_list and "sessions" not in tabel_list:  
            cursor.execute("ALTER TABLE session RENAME TO sessions")  
            conn.commit()  
        murnikan_tabel(cursor, "sessions", "dc_id, server_address, port, auth_key, takeout_id",
                       "CREATE TABLE sessions (dc_id INTEGER PRIMARY KEY, server_address TEXT, port INTEGER, auth_key BLOB, takeout_id INTEGER)")  
        murnikan_tabel(cursor, "entities", "id, hash, username, phone, name, date",
                       "CREATE TABLE entities (id INTEGER PRIMARY KEY, hash INTEGER, username TEXT, phone TEXT, name TEXT, date INTEGER)")  
        cursor.execute("DROP TABLE IF EXISTS peers")  
        conn.commit()  
        conn.close()  
    except Exception: pass

# =====================================================================
# 🔑 INTERAKTIF LOGIN & GENERATE INITDATA VIA TELETHON
# =====================================================================
async def ambil_atau_login_telethon(nama_session, butuh_clean=False):
    if butuh_clean:
        murnikan_database_telethon(nama_session)
        
    nama_file = f"{nama_session}.session"  
    
    # Bersihkan file sampah sqlite
    for suffix in ["-journal", "-wal", "-shm"]:  
        try: os.remove(f"{nama_file}{suffix}")  
        except: pass  

    client = TelegramClient(nama_session, API_ID, API_HASH)
    
    try:  
        await client.connect()
        
        # ✅ DETEKSI OTOMATIS: Jika file tidak ada atau ter-log out (Invalid)
        if not await client.is_user_authorized():
            print(f"   ⚠️ [LOGIN REQUIRED] Session '{nama_session}' belum ada atau sudah INVALID!")
            phone = input(f"   📲 Masukkan Nomor HP untuk [{nama_session}] (Format +62...): ").strip()
            if not phone:
                print("   ❌ Login dibatalkan karena nomor kosong.")
                await client.disconnect()
                return None
                
            await client.send_code_request(phone)
            print("   📩 OTP dikirim ke akun Telegram kamu.")
            code = input("   🔑 Masukkan Kode OTP: ").strip()
            
            try:
                await client.sign_in(phone, code)
            except Exception as e:
                if "Password" in str(e) or "protected" in str(e).lower():
                    password = input("   🔒 Masukkan Password 2FA (Cloud Password) kamu: ").strip()
                    await client.sign_in(password=password)
                else:
                    raise e
            print(f"   ✅ Login sukses! File '{nama_file}' diperbarui.")

        # Ambil query token untuk game
        bot_entity = await client.get_entity(TARGET_BOT)
        bot_peer = await client.get_input_entity(bot_entity)
          
        web_view = await client(RequestWebViewRequest(  
            peer=bot_peer, bot=bot_peer, platform="android",  
            from_bot_menu=False, url=TARGET_URL, start_param=START_PARAM  
        ))  
          
        parsed_url = urllib.parse.unquote(web_view.url)
        await client.disconnect() # Disconnect setelah selesai mengambil token
        
        if "#tgWebAppData=" in parsed_url:  
            return parsed_url.split("#tgWebAppData=")[1].split("&tgWebAppVersion")[0]  
        elif "?tgWebAppData=" in parsed_url:  
            return parsed_url.split("?tgWebAppData=")[1].split("&tgWebAppVersion")[0]  
            
    except Exception as e:  
        print(f"   ❌ Gagal memproses session {nama_session}: {e}")
        try: await client.disconnect()
        except: pass
        
        if not butuh_clean and os.path.exists(nama_file):
            print("   🔄 Database macet? Mencoba memurnikan database dan ulang...")
            return await ambil_atau_login_telethon(nama_session, butuh_clean=True)
    return None

# =====================================================================
# 💾 FUNGSI CACHE JSON
# =====================================================================
def muat_cache_token():
    if os.path.exists(FILE_CACHE):
        try:
            with open(FILE_CACHE, "r") as f: return json.load(f)
        except Exception: return {}
    return {}

def simpan_cache_token(cache):
    try:
        with open(FILE_CACHE, "w") as f: json.dump(cache, f, indent=4)
    except Exception: pass

# =====================================================================
# 🚀 HTTP REQUEST DENGAN RETRY 3X
# =====================================================================
def kirim_request_dengan_retry(url, headers, payload, nama_proses):
    for nomor_try in range(1, 4):
        try:
            res = requests.post(url, headers=headers, data=payload, timeout=15)
            return res
        except Exception as e:
            print(f"   ❌ [Try #{nomor_try}/3] Masalah jaringan saat {nama_proses}...")
            if nomor_try < 3: time.sleep(3) 
    return None

def eksekusi_api(token):
    headers = {  
        "Content-Type": "application/x-www-form-urlencoded",  
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  
        "Origin": "https://app.gramnetwork.online",  
        "Referer": "https://app.gramnetwork.online/"  
    }  
    payload = {"initData": token}  
    
    res_claim = kirim_request_dengan_retry(
        "https://app.gramnetwork.online/api/claim_mining.php", headers, payload, "Claim Mining"
    )
    if res_claim is None: return True, "Network Error" # Biarkan token tetap di cache
        
    res_text = res_claim.text.lower()
    if "unauthorized" in res_text or "expired" in res_text or "invalid" in res_text or res_claim.status_code == 401:
        return False, "Token Expired"
        
    print(f"   💰 Claim Mining -> {res_claim.text.strip()}")  

    res_start = kirim_request_dengan_retry(
        "https://app.gramnetwork.online/api/start_mining.php", headers, payload, "Start Mining"
    )
    if res_start is not None:
        print(f"   🕹️ Start Mining -> {res_start.text.strip()}")  
        
    return True, "Sukses"

# =====================================================================
# 🔄 LOOP UTAMA (CORE ENGINE)
# =====================================================================
async def main():
    print("🚀 Skrip All-In-One Gram Network Berjalan...")
    
    while True:
        try:
            cache_token = muat_cache_token()
            print(f"\n========== 📂 Memproses Antrean {len(DAFTAR_AKUN)} Akun ==========")
            
            for index, nama_session in enumerate(DAFTAR_AKUN, start=1):
                if nama_session == "-": continue
                print(f"\n[Akun #{index} - {nama_session}]")
                
                token_terpakai = cache_token.get(nama_session)
                butuh_token_baru = False
                
                # Cek token lokal di file JSON
                if token_terpakai:
                    print("   🔍 Menguji token lama dari cache JSON...")
                    status_token, pesan = eksekusi_api(token_terpakai)
                    if not status_token:
                        print("   ⚠️ Token Gram kedaluwarsa/invalid!")
                        butuh_token_baru = True
                else:
                    print("   ℹ️ Token belum terdaftar di JSON.")
                    butuh_token_baru = True
                
                # Jika token mati, panggil modul Telethon (Bisa otomatis minta login ulang)
                if butuh_token_baru:
                    print("   🔄 Memeriksa session & mengambil initData baru...")
                    token_baru = await ambil_query_telethon(nama_session, butuh_clean=False)
                    
                    if token_baru:
                        print("   ✅ Token baru didapatkan! Menyimpan ke JSON...")
                        cache_token[nama_session] = token_baru
                        simpan_cache_token(cache_token)
                        
                        print("   🚀 Menjalankan ulang perintah game dengan token baru...")
                        eksekusi_api(token_baru)
                    else:
                        print(f"   ❌ Gagal memproses akun {nama_session} pada giliran ini.")
                
                # Jeda acak antar akun
                jeda_acak = random.randint(DELAY_MIN, DELAY_MAX)
                print(f"   ⏳ Jeda acak {jeda_acak} detik sebelum ke akun berikutnya...")
                await asyncio.sleep(jeda_acak)
            
            print(f"\n🎉 Semua akun sukses dieksekusi!")  
            print("⏳ Menunggu 4 jam sebelum mengulang perulangan...")  
            await asyncio.sleep(14520) 
            
        except Exception as global_error:
            print(f"⚠️ Kendala sistem utama: {global_error}")  
            await asyncio.sleep(30)

# Alias fungsi agar kompatibel dengan pemanggilan di atas
ambil_query_telethon = ambil_atau_login_telethon

if __name__ == "__main__":
    asyncio.run(main())
