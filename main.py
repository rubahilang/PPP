from telegram import Update, constants
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging
import requests
from telegram.ext import ContextTypes
import os
import requests
from bs4 import BeautifulSoup
import shutil
import json
from typing import List, Dict, Optional
import httpx

USAGE_FILE = 'usage_counts.json'
ADMIN_FILE = 'admin.md'
BANNED_FILE = 'user.md'


# Menambahkan job queue untuk menjalankan pemeriksaan setiap 10 menit
def schedule_jobs(application: Application) -> None:
    application.job_queue.run_repeating(check_all_users, interval=600, first=10)

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

async def is_user(user_id: int) -> bool:
    """Cek apakah user_id ada di user.md."""
    try:
        with open('user.md', 'r') as banned_file:
            banned_users = banned_file.read().strip().splitlines()  # Membaca file per baris
            # Memeriksa apakah user_id ada dalam daftar user
            return str(user_id) in banned_users
    except FileNotFoundError:
        # Jika file user.md tidak ditemukan, anggap tidak ada user yang terdaftar
        return False


async def check_all_users(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Mendapatkan semua file .txt di direktori saat ini
    txt_files = [file for file in os.listdir() if file.endswith('.txt')]

    for file_name in txt_files:
        user_id = file_name.split('.')[0]  # Mengambil user_id dari nama file
        try:
            with open(file_name, 'r') as file:
                domains = file.read().strip()  # Membaca semua domain dalam file

                if domains:
                    # Kirim permintaan GET ke URL
                    url = 'https://check.skiddle.id/'
                    params = {'domains': domains}
                    response = requests.get(url, params=params)

                    if response.status_code == 200:
                        try:
                            # Memparsing respons JSON
                            data = response.json()
                            blocked_domains = []

                            for domain_name, status_info in data.items():
                                if status_info.get('blocked') == True:
                                    blocked_domains.append(domain_name)

                            # Jika ada domain yang diblokir, kirim pesan ke user
                            if blocked_domains:
                                # Menyiapkan pesan yang diformat
                                output_lines = ["⚠️ Domain berikut terblokir oleh Kominfo ⚠️:"]
                                output_lines.extend(blocked_domains)
                                output_lines.append("\n✨Agar tidak mendapatkan pesan ini lagi, silakan gunakan perintah /ipos lalu hapus domain dengan mengirimkan Y ✨")
                                output_text = "\n".join(output_lines)

                                await context.bot.send_message(
                                    chat_id=int(user_id),
                                    text=output_text
                                )
                        except Exception as e:
                            logger.error(f"Error memparsing respons JSON untuk file {file_name}: {e}")
                    else:
                        logger.error(f"Error: Menerima status kode {response.status_code} untuk file {file_name}")
                else:
                    logger.info(f"Tidak ada domain yang ditemukan dalam file {file_name}")
        except Exception as e:
            logger.error(f"Error memeriksa file {file_name}: {e}")


# Fungsi untuk menambahkan domain ke file khusus pengguna
async def add_to(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
        
        # Cek apakah pengirim adalah admin
        if not await is_admin(user_id):
            await update.message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
            return
        
        if context.args:
            if len(context.args) < 2:  # Memeriksa apakah user memberikan user_id dan domain
                await update.message.reply_text("Gunakan format: /add_to <user_id> <domain1> <domain2> ...")
                return

            target_user_id = context.args[0]  # user_id yang dituju
            domains = " ".join(context.args[1:])  # Gabungkan domain menjadi satu string
            file_name = f'{target_user_id}.txt'  # Nama file berdasarkan target_user_id

            # Ganti spasi antar domain dengan koma
            domains = domains.replace(' ', ',')
            new_domains = domains.split(',')

            try:
                # Memeriksa apakah file untuk target_user_id sudah ada
                try:
                    with open(file_name, 'r') as file:
                        existing_domains = file.read().strip().split(',')
                except FileNotFoundError:
                    existing_domains = []

                # Filter hanya domain yang belum ada
                unique_domains = [domain for domain in new_domains if domain not in existing_domains]

                if unique_domains:
                    with open(file_name, 'a') as file:
                        if existing_domains:
                            file.write(f',{",".join(unique_domains)}')
                        else:
                            file.write(f'{",".join(unique_domains)}')

                    await update.message.reply_text(f"Domain(s) {','.join(unique_domains)} telah ditambahkan ke list user {target_user_id}. 🎉")
                else:
                    await update.message.reply_text(f"Semua domain yang Anda masukkan sudah ada dalam list user {target_user_id}. 😕")
            
            except Exception as e:
                await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")
        else:
            await update.message.reply_text("Harap masukkan user_id dan domain yang ingin ditambahkan setelah /add_to. 💡")
    else:
        await update.message.reply_text("Pesan tidak valid! ❌")

async def cek_domain(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

        # Cek apakah user ter-banned
        if not await is_user(user_id):
            await update.message.reply_text(
                "🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬"
            )
            return

        file_name = f'{user_id}.txt'  # Nama file berdasarkan user_id

        # Memeriksa apakah file pengguna ada
        try:
            with open(file_name, 'r') as file:
                domains = file.read().strip()  # Membaca semua domain dalam file

                if domains:
                    # Kirim permintaan GET ke URL
                    url = 'https://check.skiddle.id/'
                    params = {'domains': domains}
                    response = requests.get(url, params=params)

                    # Menangani respons
                    if response.status_code == 200:
                        try:
                            # Memparsing respons JSON
                            data = response.json()
                            # Menyiapkan daftar untuk output
                            output_lines = ["🔍Hasil Pemeriksaan🔍:"]
                            for domain_name, status_info in data.items():
                                if status_info.get('blocked') == True:
                                    output_lines.append(f"{domain_name}: ❌DIBLOKIR❌")
                                else:
                                    output_lines.append(f"{domain_name}: ✅AMAN✅")
                            # Menggabungkan output dan mengirimkan ke pengguna
                            output_text = "\n".join(output_lines) + " 🚀"
                            await update.message.reply_text(output_text)
                        except Exception as e:
                            # Menangani kesalahan parsing JSON
                            await update.message.reply_text(f"Terjadi kesalahan saat memproses data: {e}")
                    else:
                        await update.message.reply_text(f"Error: {response.status_code} ⚠️")
                else:
                    await update.message.reply_text("Tambahkan domain terlebih dahulu, baru bisa dicek. 😉👌")
        except FileNotFoundError:
            await update.message.reply_text("Tambahkan domain terlebih dahulu, baru bisa dicek. 😉👌")
        except Exception as e:
            await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")
    else:
        await update.message.reply_text("Pesan tidak valid! ❌")

# Fungsi untuk menampilkan list domain
async def list_domains(update: Update, context: CallbackContext) -> None:
    # Mendapatkan user_id pengirim
    user_id = update.message.from_user.id

    # Cek apakah user ter-banned
    if not await is_user(user_id):
        await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
        return
    
    # Menentukan file berdasarkan apakah ada argumen atau tidak
    if context.args:
        # Jika ada argumen, gunakan argumen tersebut (misalnya, /list 123123)
        file_name = f'{context.args[0]}.txt'
    else:
        # Jika tidak ada argumen, gunakan user_id
        file_name = f'{user_id}.txt'

    # Memeriksa apakah file pengguna ada
    try:
        with open(file_name, 'r') as file:
            domains = file.read().strip()  # Membaca semua domain dalam file

            if domains:
                # Menampilkan domain dalam format list
                domains_list = domains.split(',')
                await update.message.reply_text(f"Daftar domain Anda: 📜\n" + "\n".join(domains_list))
            else:
                await update.message.reply_text("Tambahin Domain Dulu Cuy, Baru Bisa Di Cek. 😉👌")
    except FileNotFoundError:
        await update.message.reply_text(f"File {file_name} tidak ditemukan. Tambahin Domain Dulu Cuy, Baru Bisa Di Cek. 😉👌")
    except Exception as e:
        await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")

# Fungsi untuk menampilkan list user
async def list_user(update: Update, context: CallbackContext) -> None:
    # Mendapatkan user_id pengirim
    user_id = update.message.from_user.id

    # Cek apakah pengirim adalah admin
    if not await is_admin(user_id):
        await update.message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return
    
    file_name = 'user.md'

    # Memeriksa apakah file pengguna ada
    try:
        with open(file_name, 'r') as file:
            domains = file.read().strip()  # Membaca semua domain dalam file

            if domains:
                # Menampilkan domain dalam format list
                domains_list = domains.split('\n')
                await update.message.reply_text(f"Daftar List User: 📜\n" + "\n".join(domains_list))
            else:
                await update.message.reply_text("Tambahin User Dulu Cuy, Baru Bisa Di Cek. 😉👌")
    except FileNotFoundError:
        await update.message.reply_text(f"File {file_name} tidak ditemukan. Pastikan file sudah ada. 🔍")
    except Exception as e:
        await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")

# Fungsi untuk menampilkan list admin
async def list_admin(update: Update, context: CallbackContext) -> None:
    # Mendapatkan user_id pengirim
    user_id = update.message.from_user.id

    # Cek apakah pengirim adalah admin
    if not await is_admin(user_id):
        await update.message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return
    
    file_name = 'admin.md'

    # Memeriksa apakah file pengguna ada
    try:
        with open(file_name, 'r') as file:
            domains = file.read().strip()  # Membaca semua domain dalam file

            if domains:
                # Menampilkan domain dalam format list
                domains_list = domains.split('\n')
                await update.message.reply_text(f"Daftar List Admin: 📜\n" + "\n".join(domains_list))
            else:
                await update.message.reply_text("Tambahin Admin Dulu Cuy, Baru Bisa Di Cek. 😉👌")
    except FileNotFoundError:
        await update.message.reply_text(f"File {file_name} tidak ditemukan. Pastikan file sudah ada. 🔍")
    except Exception as e:
        await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")



# Fungsi untuk memeriksa domain dan menghapus jika perlu
async def ipos(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

        # Cek apakah user ter-banned
        if not await is_user(user_id):
            await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
            return
        
        file_name = f'{user_id}.txt'  # Nama file berdasarkan user_id

        # Memeriksa apakah file pengguna ada
        try:
            with open(file_name, 'r') as file:
                domains = file.read().strip()  # Membaca semua domain dalam file

                if domains:
                    # Kirim permintaan GET ke URL
                    url = 'https://check.skiddle.id/'
                    params = {'domains': domains}
                    response = requests.get(url, params=params)

                    if response.status_code == 200:
                        try:
                            # Parse respons JSON
                            data = response.json()
                            blocked_domains = []

                            for domain_name, status_info in data.items():
                                if status_info.get('blocked') == True:
                                    blocked_domains.append(domain_name)

                            # Jika ada domain yang diblokir, minta konfirmasi untuk menghapus
                            if blocked_domains:
                                await update.message.reply_text(
                                    f"⚠️ Domain berikut diblokir oleh Kominfo ⚠️:\n" +
                                    "\n".join(blocked_domains) +
                                    "\n\nApakah Anda ingin menghapus domain-domain tersebut dari daftar? (Y/N) ❓"
                                )
                                # Simpan domain yang terblokir untuk referensi selanjutnya
                                context.user_data['blocked_domains'] = blocked_domains
                            else:
                                await update.message.reply_text("✅ Semua domain aman. ✅")
                        except ValueError:
                            await update.message.reply_text("Gagal memparsing respons JSON. ⚠️")
                    else:
                        await update.message.reply_text(f"Error: {response.status_code} ⚠️")    
                else:
                    await update.message.reply_text("Tambahkan domain terlebih dahulu untuk melakukan pengecekan. 😉👌")
        except FileNotFoundError:
            await update.message.reply_text("Tambahin Domain Dulu Cuy, Baru Bisa Di Cek. 😉👌")
        except Exception as e:
            await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")
    else:
        await update.message.reply_text("Ngetik Ap Km Dek❓❗ Maaf Tidak Bisa Yh❌")

# Fungsi untuk menghapus domain jika konfirmasi diterima
async def remove_domain(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

        # Cek apakah user ter-banned
        if not await is_user(user_id):
            await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
            return
        
        file_name = f'{user_id}.txt'  # Nama file berdasarkan user_id

        # Memeriksa jika ada domain terblokir yang perlu dihapus
        if 'blocked_domains' in context.user_data:
            blocked_domains = context.user_data['blocked_domains']
            if update.message.text.lower() == 'y':  # Jika user konfirmasi dengan Y/y
                try:
                    with open(file_name, 'r') as file:
                        domains = file.read().strip()  # Membaca semua domain dalam file
                    for domain in blocked_domains:
                        domains = domains.replace(domain, '').replace(',,', ',').strip(',')  # Menghapus domain terblokir

                    with open(file_name, 'w') as file:
                        file.write(domains)  # Menulis ulang daftar domain tanpa yang terblokir

                    await update.message.reply_text(f"Domain ini IPOS❌ dan telah dihapus cuy😁👍:\n" + "\n".join(blocked_domains))
                except Exception as e:
                    await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")
            else:
                await update.message.reply_text("Dah IPOS Masi Aja Disimpen😒")
            del context.user_data['blocked_domains']  # Hapus data sementara blocked_domains
        else:
            await update.message.reply_text("Ngetik Ap Dek🤷‍♂️, Salah Itu Mending Ketik /help 😎")

# Fungsi untuk /start command
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Selamat Datang! 🎉\n\n"
        "List Command Yang Tersedia:\n\n"
        "/tes digunakan untuk mengecek domain langsung tanpa perlu di add! 🌐\n"
        "Pemakaian: /tes link1.com link2.com dst... \n❌❌TANPA HTTPS://❌❌\n\n"
        "/hapus dapat digunakan untuk menghapus domain yang sudah ditambahkan 🚮\n"
        "Pemakaian: /hapus link1.com link2.com dst... \n❌❌TANPA HTTPS://❌❌\n\n"
        "/add digunakan untuk menambahkan domain anda ✨\n"
        "Pemakaian: /add link1.com link2.com dst... \n❌❌TANPA HTTPS://❌❌\n\n"
        "/list untuk melihat daftar domain yang sudah ditambahkan 📜\n\n"
        "/cek untuk memeriksa dan menampilkan status semua domain 🔍\n\n"
        "/ipos untuk memeriksa dan menampilkan domain yang ipos ⭐\n\n"
        "/rank untuk memeriksa dan menampilkan Rank Domain ⭐\n"
        "Pemakaian: /rank rubah4d\n\n"
    )

# Fungsi untuk /dev menu
async def dev(update: Update, context: CallbackContext) -> None:

    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

    # Cek apakah pengirim adalah admin
    if not await is_user(user_id):
        await update.message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return
        
    await update.message.reply_text(
        "Selamat Datang DEV! 🎉\n\n"
        "List Command Yang Tersedia:\n\n"
        "/active 👉 Untuk Melihat Total User 👈\n"
        "/hapus domain * 👉 Untuk Menghapus Domain Dari Semua User 👈\n"
        "/hapus all  👉 Untuk Menghapus Semua Domain 👈\n"
        "/hapus all userid 👉 Untuk Menghapus Semua Domain Untuk User Spesifik👈\n"
        "/add domain * 👉 Untuk Menambah Domain Dari Semua User 👈\n"
        "/add_to userid domain1 👉 Untuk Menambah Domain ke Spesifik User 👈\n"
        "/balas userid 👉 Untuk Chat UserId 👈\n"
        "/show 👉 Untuk Show Username User 👈\n"
        "/list userid 👉 Untuk Melihat Domain Milik User Spesifik 👈\n"
        "/wl 👉 Untuk White List User 👈\n"
        "/unwl 👉 Untuk Hapus White List User 👈\n"
        "/admin 👉 Untuk Menambah Admin 👈\n"
        "/unadmin 👉 Untuk Menghapus Admin 👈\n"
        "/show_user 👉 Untuk Melihat Seluruh User 👈\n"
        "/show_admin 👉 Untuk Melihat Seluruh Admin 👈\n"
        "/rm userid 👉 Untuk Menghapus File Domain User 👈\n"
        "/undo userid 👉 Untuk Mengembalikan File Domain User Yang Terhapus 👈\n"
        "/trash👉 Untuk Melihat File Domain User Yang Terhapus 👈\n"
    )


# Fungsi untuk /help command
async def help(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Bantuan Datang! 🆘\n\n"
        "List Command Yang Tersedia:\n\n"
        "/tes digunakan untuk mengecek domain langsung tanpa perlu di add! 🌐\n"
        "Pemakaian: /tes link1.com link2.com dst... \n❌❌TANPA HTTPS://❌❌\n\n"
        "/hapus dapat digunakan untuk menghapus domain yang sudah ditambahkan 🚮\n"
        "Pemakaian: /hapus link1.com link2.com dst... \n❌❌TANPA HTTPS://❌❌\n\n"
        "/add digunakan untuk menambahkan domain anda ✨\n"
        "Pemakaian: /add link1.com link2.com dst... \n❌❌TANPA HTTPS://❌❌\n\n"
        "/list untuk melihat daftar domain yang sudah ditambahkan 📜\n\n"
        "/cek untuk memeriksa dan menampilkan status semua domain 🔍\n\n"
        "/ipos untuk memeriksa dan menampilkan domain yang ipos ⭐\n\n"
        "/rank untuk memeriksa dan menampilkan Rank Domain ⭐\n"
        "Pemakaian: /rank rubah4d\n\n"
    )

# Fungsi untuk menangani perintah /tes
async def tes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Gunakan format: /tes domain1 domain2")
        return

    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

    # Cek apakah user ter-banned
    if not await is_user(user_id):
        await update.message.reply_text(
            "🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬"
        )
        return

    # Menggabungkan argumen dan mengganti spasi dengan koma
    domains = ",".join(context.args)

    # URL dan parameter
    url = 'https://check.skiddle.id/'
    params = {'domains': domains}

    try:
        # Mengirimkan request ke API
        response = requests.get(url, params=params)
        if response.status_code == 200:
            try:
                # Memparsing respons JSON
                data = response.json()
                # Menyiapkan daftar untuk output
                output_lines = ["🔍Hasil Pemeriksaan🔍:"]
                for domain_name, status_info in data.items():
                    if status_info.get('blocked') == True:
                        output_lines.append(f"{domain_name}: ❌DIBLOKIR❌")
                    else:
                        output_lines.append(f"{domain_name}: ✅AMAN✅")
                # Menggabungkan output dan mengirimkan ke pengguna
                output_text = "\n".join(output_lines) + " 🚀"
                await update.message.reply_text(output_text)
            except Exception as e:
                # Menangani kesalahan parsing JSON
                await update.message.reply_text(f"Terjadi kesalahan saat memproses data: {e}")
        else:
            await update.message.reply_text(f"Error dari API: {response.status_code}")
    except Exception as e:
        # Menangani kesalahan jaringan atau lainnya
        await update.message.reply_text(f"Terjadi kesalahan: {e}")


async def hapus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Gunakan format: /hapus <domain1 domain2 ...> | /hapus all | /hapus all <user_id>")
        return

    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
    
    # Cek apakah user ter-banned
    if not await is_user(user_id):
        await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
        return

    args = context.args
    if args[0] == "all":
        # Jika hanya "all", hapus isi file user_id.txt
        target_user_id = user_id if len(args) == 1 else args[1]

        file_name = f"{target_user_id}.txt"

        # Cek apakah file ada
        if not os.path.exists(file_name):
            await update.message.reply_text(f"File {file_name} tidak ditemukan.")
            return

        try:
            # Kosongkan isi file
            with open(file_name, "w") as file:
                file.write("")  # Kosongkan file

            await update.message.reply_text(
                f"✅ Semua domain berhasil dihapus dari file `{file_name}`."
            )
        except Exception as e:
            await update.message.reply_text(f"Terjadi kesalahan saat menghapus isi file `{file_name}`: {e}")
        return

    # Jika bukan "all", proses penghapusan domain tertentu
    to_remove = set(args[:-1])  # Ambil semua argumen kecuali yang terakhir
    remove_all = args[-1] == '*'  # Cek apakah argumen terakhir adalah '*'

    try:
        if remove_all:
            # Ambil semua file .txt di direktori
            txt_files = [f for f in os.listdir('.') if f.endswith('.txt')]

            if not txt_files:
                await update.message.reply_text("Tidak ada User ditemukan.")
                return

            removed_from_files = []  # Menyimpan nama file yang domain berhasil dihapus
            not_found_in_files = []  # Menyimpan nama file yang tidak ditemukan domain yang ingin dihapus

            for file_name in txt_files:
                with open(file_name, "r") as file:
                    data = file.read().strip()
                domains = data.split(",")

                # Menghapus domain yang diminta
                updated_domains = [domain for domain in domains if domain not in to_remove]

                # Jika domain dihapus, simpan perubahan ke file
                if len(updated_domains) < len(domains):
                    with open(file_name, "w") as file:
                        file.write(",".join(updated_domains))
                    # Menghilangkan ekstensi .txt sebelum menambahkannya ke list
                    removed_from_files.append(file_name.replace(".txt", ""))
                else:
                    not_found_in_files.append(file_name)

            # Mengirimkan pesan ke pengguna tanpa ekstensi .txt
            if removed_from_files:
                await update.message.reply_text(
                    f"✅ Domain berhasil dihapus Cuy dari User berikut: \n" + "\n".join(removed_from_files)
                )
            if not_found_in_files:
                await update.message.reply_text(
                    f"Domain yang diminta tidak ditemukan di User berikut: \n" + "\n".join(not_found_in_files)
                )

        else:
            # Menangani kasus penghapusan domain untuk file pengguna spesifik
            file_name = f"{user_id}.txt"

            # Periksa apakah file pengguna ada
            if not os.path.exists(file_name):
                await update.message.reply_text("Tidak ada data domain yang disimpan.")
                return

            try:
                # Membaca file dan memisahkan domain
                with open(file_name, "r") as file:
                    data = file.read().strip()
                domains = data.split(",")

                # Menghapus domain yang diminta
                to_remove = set(args)  # Gunakan set untuk memastikan tidak ada duplikat di input
                updated_domains = [domain for domain in domains if domain not in to_remove]

                if len(updated_domains) == len(domains):
                    await update.message.reply_text("Tidak ada domain yang cocok untuk dihapus.")
                    return

                # Menyimpan kembali data yang sudah dihapus
                with open(file_name, "w") as file:
                    file.write(",".join(updated_domains))

                # Mengirimkan pesan dengan format rapi
                await update.message.reply_text(
                    f"✅ Domain berhasil dihapus Cuy. 🚮 \n🌐 Domain Tersisa 🌐:\n" +
                    ("\n".join(updated_domains) if updated_domains else "Tidak ada domain tersisa.")
                )
            except Exception as e:
                await update.message.reply_text(f"Terjadi kesalahan: {e}")

    except Exception as e:
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

# Fungsi untuk /help command
async def userid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"Selamat Datang! 🎉\n\n"
        f"User ID Kamu Adalah: {user_id} 👤"
    )

async def active(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
    
    # Cek apakah user ter-banned
    if not await is_user(user_id):
        await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
        return
    
    try:
        # Mendapatkan daftar semua file .txt di direktori saat ini
        txt_files = [f[:-4] for f in os.listdir('.') if f.endswith('.txt')]

        if not txt_files:
            await update.message.reply_text("Tidak ada UserID yang aktif.")
        else:
            user_list = "\n".join(txt_files)
            await update.message.reply_text(f"UserID yang aktif:\n{user_list}")
    except Exception as e:
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

# Fungsi untuk memulai percakapan /chat
async def balas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 2:  # Jika argumen kurang dari 2 (user_id dan pesan)
        await update.message.reply_text(
            "Gunakan format: /chat <user_id> <pesan>\nContoh: /chat 12345678 Halo!"
        )
        return

    # Ambil user_id dan pesan dari argumen
    user_id = args[0]
    message = " ".join(args[1:])

    try:
        # Kirim pesan ke user_id yang ditentukan
        await context.bot.send_message(chat_id=user_id, text=message)
        await update.message.reply_text(f"✅ Pesan berhasil dikirim ke {user_id}.")
    except Exception as e:
        # Logging error jika gagal mengirim
        logger.error(f"Error mengirim pesan ke {user_id}: {e}")
        await update.message.reply_text(f"⚠️ Gagal mengirim pesan: {e}")

# Fungsi untuk memulai percakapan /chat
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if len(args) < 1:  # Jika argumen kurang dari 1 (pesan)
        await update.message.reply_text(
            "Gunakan format: /chat <pesan>\nContoh: /chat Halo!"
        )
        return

    # Ambil user_id dan pesan dari argumen
    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
    dev = "6895581386"
    message = f"Pesan dari {user_id}: {' '.join(args)}"

    try:
        # Kirim pesan ke user_id yang ditentukan
        await context.bot.send_message(chat_id=dev, text=message)
        await update.message.reply_text(f"✅ Pesan berhasil dikirim ke Developer.")
    except Exception as e:
        # Logging error jika gagal mengirim
        logger.error(f"Error mengirim pesan ke Developer: {e}")
        await update.message.reply_text(f"⚠️ Gagal mengirim pesan: {e}")


# Fungsi untuk menampilkan username dari user_id
async def show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
    
    # Cek apakah user ter-banned
    if not await is_user(user_id):
        await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
        return

    args = context.args
    if len(args) < 1:  # Jika tidak ada user_id yang dimasukkan
        await update.message.reply_text("Gunakan format: /show <user_id>\nContoh: /show 12345678")
        return

    user_id = args[0]
    try:
        # Mendapatkan informasi pengguna berdasarkan user_id
        user = await context.bot.get_chat(chat_id=user_id)
        username = user.username if user.username else "Tidak memiliki username"
        full_name = f"{user.first_name} {user.last_name or ''}".strip()
        
        # Mengirimkan informasi ke pengirim perintah
        await update.message.reply_text(
            f"✅ Informasi Pengguna:\n"
            f"- User ID: {user.id}\n"
            f"- Username: @{username}\n"
            f"- Nama Lengkap: {full_name}"
        )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Gagal mendapatkan informasi pengguna: {e}"
        )

# Fungsi untuk pengecekan rank
# Fungsi untuk Membagi Pesan jika Terlalu Panjang
def split_message(message: str, max_length: int = 4096) -> List[str]:
    """Memecah pesan menjadi beberapa bagian yang tidak melebihi max_length."""
    messages = []
    while len(message) > max_length:
        # Cari posisi pemisah terbaik sebelum batas max_length
        split_pos = message.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        messages.append(message[:split_pos])
        message = message[split_pos:]
    messages.append(message)
    return messages

# Handler untuk Perintah /rank
async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Gunakan format: /rank {keyword}\nContoh: /rank AI tools")
        return

    # Gabungkan argumen menjadi keyword
    keyword = " ".join(context.args)
    
    url = "https://api.serphouse.com/serp/live"
    payload = {
        "data": {
            "q": keyword,
            "domain": "google.com",
            "loc": "Indonesia",
            "lang": "en",
            "device": "mobile",
            "serp_type": "web",
            "page": "1",
            "verbatim": "0"
        }
    }
    headers = {
        'accept': "application/json",
        'content-type': "application/json",
        'authorization': "Bearer 63664a65e5615342dea5b731db1fd12858aac25f427a54c5114a8f041df8c07d"
    }

    try:
        # Kirim permintaan POST ke API
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            # Parse respons JSON
            data = response.json()

            # Simpan JSON ke file rank.json
            with open('./rank.json', 'w') as file:
                json.dump(data, file, indent=4)

            # Akses bagian "results" -> "results" -> "organic"
            organic_results = data.get("results", {}).get("results", {}).get("organic", [])
            if organic_results:
                # Mengumpulkan hasil
                result_text = []
                for item in organic_results:
                    position = item.get("position")
                    site_title = item.get("site_title")
                    link = item.get("link")
                    result_text.append(f"Position: {position}\nSite Title: {site_title}\nLink: {link}\n{'-' * 50}\n")
                
                # Mengirim hasil dalam chunk (4096 karakter per pesan)
                chunk_size = 4000  # Sedikit di bawah batas Telegram
                current_chunk = ""
                for line in result_text:
                    if len(current_chunk) + len(line) > chunk_size:
                        await update.message.reply_text(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += line
                if current_chunk:  # Kirim chunk terakhir
                    await update.message.reply_text(current_chunk)
            else:
                await update.message.reply_text("Bagian 'organic' tidak ditemukan dalam 'results'.")
        else:
            await update.message.reply_text(f"Gagal mengambil data. Status Code: {response.status_code}\nResponse: {response.text}")
    except Exception as e:
        await update.message.reply_text(f"Terjadi kesalahan: {e}")

# Handler untuk Perintah /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Halo! Saya adalah bot pengecek ranking.\n"
        "Gunakan perintah /rank <keyword> untuk memulai pengecekan."
    )

# Handler Global untuk Error
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to notify the user."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # Jangan mengirim pesan error kepada user di produksi
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ Terjadi kesalahan pada bot.")
        except Exception as e:
            logger.error(f"Gagal mengirim pesan error kepada user: {e}")


# Handler untuk Perintah /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Halo! Saya adalah bot pengecek ranking.\n"
        "Gunakan perintah /rank <keyword> untuk memulai pengecekan."
    )

# Handler Global untuk Error
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to notify the user."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # Jangan mengirim pesan error kepada user di produksi
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("⚠️ Terjadi kesalahan pada bot.")
        except Exception as e:
            logger.error(f"Gagal mengirim pesan error kepada user: {e}")


# Fungsi untuk mengecek apakah user ada di admin.md
async def is_admin(user_id: int) -> bool:
    try:
        with open('admin.md', 'r') as admin_file:
            admin_users = admin_file.read().strip().splitlines()
            return str(user_id) in admin_users
    except FileNotFoundError:
        return False

# Fungsi untuk menambahkan ID ke file admin.md
async def add_to_admin(user_id: int) -> None:
    with open('admin.md', 'a') as admin_file:
        admin_file.write(f'{user_id}\n')

# Fungsi untuk menghapus ID dari file admin.md
async def remove_from_admin(user_id: int) -> None:
    try:
        with open('admin.md', 'r') as admin_file:
            admin_users = admin_file.read().strip().splitlines()

        admin_users = [id for id in admin_users if id != str(user_id)]  # Menghapus ID

        with open('admin.md', 'w') as admin_file:
            admin_file.write("\n".join(admin_users))  # Menulis ulang file
    except FileNotFoundError:
        pass  # File tidak ada, tidak perlu diproses lebih lanjut

# Fungsi untuk menambahkan ID ke file user.md
async def add_to_banned(user_id: int) -> None:
    with open('user.md', 'a') as banned_file:
        banned_file.write(f'{user_id}\n')

# Fungsi untuk menghapus ID dari file user.md
async def remove_from_banned(user_id: int) -> None:
    try:
        with open('user.md', 'r') as banned_file:
            banned_users = banned_file.read().strip().splitlines()

        banned_users = [id for id in banned_users if id != str(user_id)]  # Menghapus ID

        with open('user.md', 'w') as banned_file:
            banned_file.write("\n".join(banned_users))  # Menulis ulang file
    except FileNotFoundError:
        pass  # File tidak ada, tidak perlu diproses lebih lanjut

# Fungsi untuk menangani perintah /admin dan /unadmin
async def admin(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

    # Cek apakah pengirim adalah admin
    if not await is_admin(user_id):
        await update.message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    # Cek apakah ada ID yang diberikan
    if context.args:
        for target_id in context.args:
            await add_to_admin(target_id)
        await update.message.reply_text(f"ID {', '.join(context.args)} telah ditambahkan ke admin.")
    else:
        await update.message.reply_text("Harap masukkan ID yang ingin ditambahkan ke admin.")

# Fungsi untuk menangani perintah /unadmin
async def unadmin(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

    # Cek apakah pengirim adalah admin
    if not await is_admin(user_id):
        await update.message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    # Cek apakah ada ID yang diberikan
    if context.args:
        for target_id in context.args:
            await remove_from_admin(target_id)
        await update.message.reply_text(f"ID {', '.join(context.args)} telah dihapus dari admin.")
    else:
        await update.message.reply_text("Harap masukkan ID yang ingin dihapus dari admin.")

# Fungsi untuk menangani perintah /banned
async def banned(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

    # Cek apakah pengirim adalah admin
    if not await is_admin(user_id):
        await update.message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    # Cek apakah ada ID yang diberikan
    if context.args:
        for target_id in context.args:
            await add_to_banned(target_id)
        await update.message.reply_text(f"ID {', '.join(context.args)} telah Ditambahkan.")
    else:
        await update.message.reply_text("Harap masukkan ID yang ingin Ditambahkan.")

# Fungsi untuk menangani perintah /unbanned
async def unbanned(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim

    # Cek apakah pengirim adalah admin
    if not await is_admin(user_id):
        await update.message.reply_text("Anda tidak memiliki akses untuk menggunakan perintah ini.")
        return

    # Cek apakah ada ID yang diberikan
    if context.args:
        for target_id in context.args:
            await remove_from_banned(target_id)
        await update.message.reply_text(f"ID {', '.join(context.args)} telah dihapus dari user.")
    else:
        await update.message.reply_text("Harap masukkan ID yang ingin dihapus dari user.")

# Fungsi untuk menambahkan domain ke file khusus pengguna
# Fungsi untuk memeriksa apakah pengguna adalah admin
def load_admin_list() -> List[str]:
    if not os.path.exists(ADMIN_FILE):
        return []
    with open(ADMIN_FILE, 'r') as file:
        admins = [line.strip() for line in file if line.strip()]
    return admins

# Fungsi untuk memeriksa apakah pengguna ter-banned
async def is_user(user_id: int) -> bool:
    """Cek apakah user_id ada di user.md (banned users)."""
    try:
        with open(BANNED_FILE, 'r') as banned_file:
            banned_users = banned_file.read().strip().splitlines()
            return str(user_id) in banned_users
    except FileNotFoundError:
        # Jika file user.md tidak ditemukan, anggap tidak ada user yang ter-banned
        return False

# Fungsi untuk memuat hitungan penggunaan
def load_usage_counts() -> Dict[str, Dict[str, int]]:
    if not os.path.exists(USAGE_FILE):
        return {}
    with open(USAGE_FILE, 'r') as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}

# Fungsi untuk menyimpan hitungan penggunaan
def save_usage_counts(data: Dict[str, Dict[str, int]]) -> None:
    with open(USAGE_FILE, 'w') as file:
        json.dump(data, file, indent=4)

# Fungsi untuk memeriksa dan meningkatkan hitungan penggunaan
def check_and_increment_usage(user_id: int, feature: str, max_usage: int) -> bool:
    usage_data = load_usage_counts()
    user_id_str = str(user_id)
    
    if user_id_str not in usage_data:
        usage_data[user_id_str] = {}
    
    if feature not in usage_data[user_id_str]:
        usage_data[user_id_str][feature] = 0
    
    if usage_data[user_id_str][feature] >= max_usage:
        return False  # Sudah mencapai batas
    
    usage_data[user_id_str][feature] += 1
    save_usage_counts(usage_data)
    return True

# Fungsi untuk menambahkan ID ke file admin.md
async def add_to_admin(target_id: str) -> None:
    with open(ADMIN_FILE, 'a') as admin_file:
        admin_file.write(f'{target_id}\n')

# Fungsi untuk menghapus ID dari file admin.md
async def remove_from_admin(target_id: str) -> None:
    try:
        with open(ADMIN_FILE, 'r') as admin_file:
            admin_users = admin_file.read().strip().splitlines()
        admin_users = [id for id in admin_users if id != target_id]
        with open(ADMIN_FILE, 'w') as admin_file:
            admin_file.write("\n".join(admin_users))
    except FileNotFoundError:
        pass  # File tidak ada, tidak perlu diproses lebih lanjut

# Fungsi untuk menambahkan ID ke file user.md (banned users)
async def add_to_banned(target_id: str) -> None:
    with open(BANNED_FILE, 'a') as banned_file:
        banned_file.write(f'{target_id}\n')

# Fungsi untuk menghapus ID dari file user.md (banned users)
async def remove_from_banned(target_id: str) -> None:
    try:
        with open(BANNED_FILE, 'r') as banned_file:
            banned_users = banned_file.read().strip().splitlines()
        banned_users = [id for id in banned_users if id != target_id]
        with open(BANNED_FILE, 'w') as banned_file:
            banned_file.write("\n".join(banned_users))
    except FileNotFoundError:
        pass  # File tidak ada, tidak perlu diproses lebih lanjut

# Fungsi untuk memuat daftar admin (dari cache untuk efisiensi)
ADMIN_LIST: List[str] = []

def load_admins() -> None:
    global ADMIN_LIST
    ADMIN_LIST = load_admin_list()

# Fungsi untuk menambahkan domain ke file khusus pengguna
async def add_domain(update: Update, context: CallbackContext) -> None:
    if update.message:
        user = update.message.from_user
        user_id: int = user.id  # Mendapatkan user_id pengirim
        username: Optional[str] = user.username.lower() if user.username else None  # Mendapatkan username pengirim (jika ada)
        
        # Cek apakah user ter-banned
        if not await is_user(user_id):
            await update.message.reply_text(
                "🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n"
                "💬 Silahkan Hubungi Developer Dengan Command /chat 💬"
            )
            return
        
        # Tentukan apakah pengguna adalah admin
        is_admin: bool = str(user_id) in ADMIN_LIST
        
        if context.args:
            # Cek dan tingkatkan hitungan penggunaan jika bukan admin
            if not is_admin:
                FEATURE = 'add_domain'
                MAX_USAGE = 5  # Batas penggunaan dalam Mode Trial
                if not check_and_increment_usage(user_id, FEATURE, MAX_USAGE):
                    await update.message.reply_text(
                        "Dalam Mode Trial Hanya Dapat Memakai Fitur Ini Sebanyak 5x!"
                    )
                    return
            
            # Gabungkan semua argumen yang dimasukkan oleh user
            domains_str: str = " ".join(context.args)  # Gabungkan menjadi satu string
            file_name: str = f'{user_id}.txt'  # Nama file berdasarkan user_id

            # Memeriksa apakah argumen terakhir adalah '*'
            add_to_all_files: bool = context.args[-1] == '*'  
            if add_to_all_files:
                domains_str = " ".join(context.args[:-1])  # Hilangkan '*' dari daftar domain yang akan ditambahkan

            # Ganti spasi antar domain dengan koma
            domains_str = domains_str.replace(' ', ',')
            new_domains: List[str] = [domain.strip() for domain in domains_str.split(',') if domain.strip()]

            try:
                if add_to_all_files:
                    # Menambahkan domain ke semua file .txt di direktori
                    txt_files: List[str] = [f for f in os.listdir('.') if f.endswith('.txt')]

                    if not txt_files:
                        await update.message.reply_text("Tidak ada User ditemukan.")
                        return

                    for file_name in txt_files:
                        # Membaca file dan menambahkan domain baru
                        with open(file_name, 'r') as file:
                            existing_domains: List[str] = [domain.strip() for domain in file.read().strip().split(',') if domain.strip()]

                        # Menambahkan domain baru yang belum ada
                        unique_domains: List[str] = [domain for domain in new_domains if domain not in existing_domains]

                        if unique_domains:
                            with open(file_name, 'a') as file:
                                if existing_domains:
                                    file.write(f',{",".join(unique_domains)}')
                                else:
                                    file.write(f'{",".join(unique_domains)}')

                    await update.message.reply_text(f"Domain(s) {', '.join(new_domains)} telah ditambahkan ke semua User. 🎉")
                
                else:
                    # Menambahkan domain hanya ke file user_id.txt
                    try:
                        with open(file_name, 'r') as file:
                            existing_domains: List[str] = [domain.strip() for domain in file.read().strip().split(',') if domain.strip()]
                    except FileNotFoundError:
                        existing_domains = []

                    if not is_admin:
                        # Cek jumlah domain yang sudah ada
                        if len(existing_domains) >= 3:
                            await update.message.reply_text(
                                f"Dalam Mode Trial Hanya Dapat Menambahkan MAX 3 domain! "
                                f"Silahkan hapus salah satu domain: {', '.join(existing_domains)}"
                            )
                            return

                        # Filter hanya domain yang belum ada
                        unique_domains = [domain for domain in new_domains if domain not in existing_domains]

                        # Cek apakah penambahan akan melebihi batas 3 domain
                        if len(existing_domains) + len(unique_domains) > 3:
                            allowed_add = 3 - len(existing_domains)
                            unique_domains = unique_domains[:allowed_add]
                            await update.message.reply_text(
                                f"Dalam Mode Trial Hanya Dapat Menambahkan MAX 3 domain! "
                                f"Sekarang hanya dapat menambahkan {allowed_add} domain: {', '.join(unique_domains)}"
                            )
                    else:
                        # Jika admin, tidak ada batasan
                        unique_domains = [domain for domain in new_domains if domain not in existing_domains]

                    if unique_domains:
                        with open(file_name, 'a') as file:
                            if existing_domains:
                                file.write(f',{",".join(unique_domains)}')
                            else:
                                file.write(f'{",".join(unique_domains)}')

                        if not is_admin:
                            await update.message.reply_text(
                                f"Domain(s) {', '.join(unique_domains)} telah ditambahkan ke list Anda. 🎉"
                            )
                        else:
                            await update.message.reply_text(
                                f"Domain(s) {', '.join(unique_domains)} telah ditambahkan ke list Anda tanpa batasan. 🎉"
                            )
                    else:
                        if not is_admin:
                            await update.message.reply_text("Semua domain yang Anda masukkan sudah ada dalam list Anda atau melebihi batas maksimal. 😕")
                        else:
                            await update.message.reply_text("Semua domain yang Anda masukkan sudah ada dalam list Anda. 😕")
            
            except Exception as e:
                await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")
        else:
            await update.message.reply_text("Harap masukkan domain yang ingin ditambahkan setelah /add. 💡")

# Fungsi untuk memindahkan file ke folder /trash
async def move(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
        
        # Cek apakah user ter-banned
        if not await is_user(user_id):
            await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
            return
        
        if context.args:
            target_user_id = context.args[0]  # user_id yang dituju
            file_name = f'{target_user_id}.txt'  # Nama file berdasarkan target_user_id
            trash_folder = './trash'  # Folder trash

            # Membuat folder trash jika belum ada
            if not os.path.exists(trash_folder):
                os.makedirs(trash_folder)

            # Cek apakah file ada di direktori utama
            if os.path.exists(file_name):
                # Memindahkan file ke folder trash
                shutil.move(file_name, os.path.join(trash_folder, file_name))
                await update.message.reply_text(f"File {file_name} telah Dihapus. ✅")
            else:
                await update.message.reply_text(f"File {file_name} tidak ditemukan. ❌")
        else:
            await update.message.reply_text("Harap masukkan user_id setelah /move untuk Menghapus file. 💡")

# Fungsi untuk mengembalikan file dari folder /trash
async def undo(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
        
        # Cek apakah user ter-banned
        if not await is_user(user_id):
            await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
            return
        
        if context.args:
            target_user_id = context.args[0]  # user_id yang dituju
            file_name = f'{target_user_id}.txt'  # Nama file berdasarkan target_user_id
            trash_folder = './trash'  # Folder trash

            # Cek apakah file ada di folder trash
            if os.path.exists(os.path.join(trash_folder, file_name)):
                # Mengembalikan file ke direktori utama
                shutil.move(os.path.join(trash_folder, file_name), file_name)
                await update.message.reply_text(f"File {file_name} telah dikembalikan . ✅")
            else:
                await update.message.reply_text(f"File {file_name} tidak ditemukan di Tempat Sampah. ❌")
        else:
            await update.message.reply_text("Harap masukkan user_id setelah /undo untuk mengembalikan file. 💡")

# Fungsi untuk melihat isi folder /trash
async def trash(update: Update, context: CallbackContext) -> None:
    trash_folder = './trash'  # Folder trash

    # Cek apakah folder trash ada
    if os.path.exists(trash_folder):
        files = os.listdir(trash_folder)
        if files:
            await update.message.reply_text(f"List File Terhapus:\n" + "\n".join(files))
        else:
            await update.message.reply_text("Tempat Sampah kosong. ❌")
    else:
        await update.message.reply_text("Tempat Sampah tidak ditemukan. ❌")

# Ganti dengan API Key Google Safe Browsing Anda
GOOGLE_API_KEY = "AIzaSyAb4MlukiqcUftRR86SRcA18iQLGsvSy5Q"

def report_phishing_manual(api_key: str, url_to_report: str) -> dict:
    """
    Melaporkan URL phishing ke Google Safe Browsing API secara manual menggunakan HTTP POST.

    Args:
        api_key (str): API Key Google Cloud Anda.
        url_to_report (str): URL yang ingin dilaporkan sebagai phishing.

    Returns:
        dict: Respons dari Google Safe Browsing API.
    """
    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    body = {
        "client": {
            "clientId": "reportphishing-443815",
            "clientVersion": "1.5.2"
        },
        "threatInfo": {
            "threatTypes": ["SOCIAL_ENGINEERING", "MALWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [
                {"url": url_to_report}
            ]
        }
    }
    
    response = requests.post(endpoint, headers=headers, data=json.dumps(body))
    
    if response.status_code == 200:
        result = response.json()
        return result
    else:
        return {"error": f"Terjadi kesalahan: {response.status_code}", "details": response.text}

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler untuk perintah /report. Mengambil URL dari argumen dan melaporkannya.

    Args:
        update (Update): Update dari Telegram.
        context (ContextTypes.DEFAULT_TYPE): Konteks callback dari Telegram.
    """
    if context.args:
        urls = context.args
        responses = []
        for url in urls:
            result = report_phishing_manual(GOOGLE_API_KEY, url)
            if "error" in result:
                responses.append(f"*URL:* `{url}`\n*Status:* ❌ Gagal\n*Error:* {result['error']}")
            else:
                responses.append(f"*URL:* `{url}`\n*Status:* ✅ Berhasil dikirim")
        response_message = "\n\n".join(responses)
        await update.message.reply_text(response_message, parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            "Silakan berikan setidaknya satu URL untuk dilaporkan.\n"
            "Contoh penggunaan: /report https://example.com/phishing1 https://example.com/phishing2"
        )

# Fungsi untuk memeriksa apakah domain diindeks oleh Google
def check_domain_indexed(domain):
    """
    Check if a domain is indexed by Google using Serphouse API.

    :param domain: The domain to check (e.g., 'example.com').
    :return: True if indexed, False otherwise.
    """
    url = "https://api.serphouse.com/serp/live"
    payload = {
        "data": {
            "q": f"site:{domain}",
            "domain": "google.com",
            "loc": "Indonesia",
            "lang": "en",
            "device": "mobile",
            "serp_type": "web",
            "page": "1",
            "verbatim": "0"
        }
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": "Bearer RO7H9zb9tea0RTgTloYBqNMqsT7qGM5ygQo3biCwGNPT4ubUMoBbPpcwla63"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Check if there are results in the response
        if "results" in data and len(data["results"]) > 0:
            return True
        else:
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error while checking domain: {e}")
        return False

# Fungsi untuk menangani perintah /index
async def index_domains(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
        
        # Periksa apakah ada domain yang diberikan
        if context.args:
            domains = context.args
            result_messages = []

            for domain in domains:
                is_indexed = check_domain_indexed(domain.strip())
                if is_indexed:
                    result_messages.append(f"Status Untuk: '{domain}' INDEX ✅")
                else:
                    result_messages.append(f"Status Untuk: '{domain}' NOT INDEX ❌")

            # Gabungkan hasil untuk semua domain dan kirimkan pesan
            await update.message.reply_text("\n".join(result_messages))
        else:
            await update.message.reply_text("Harap masukkan domain yang ingin diperiksa. Contoh: /index example.com")
    else:
        await update.message.reply_text("Perintah tidak valid! ❌")

# Fungsi utama
def main() -> None:
    # Inisialisasi bot dengan token
    application = Application.builder().token('7657800138:AAESC3n08oyC2AqHFn3oxa6qWInprwKADLo').build()

    # Menjadwalkan pemeriksaan domain untuk setiap pengguna
    schedule_jobs(application)

    # Menambahkan handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("add", add_domain))
    application.add_handler(CommandHandler("list", list_domains))
    application.add_handler(CommandHandler("cek", cek_domain))
    application.add_handler(CommandHandler("ipos", ipos))
    application.add_handler(CommandHandler("tes", tes))
    application.add_handler(CommandHandler("hapus", hapus))
    application.add_handler(CommandHandler("rm", move))
    application.add_handler(CommandHandler("undo", undo))
    application.add_handler(CommandHandler("trash", trash))
    application.add_handler(CommandHandler("userid", userid))
    application.add_handler(CommandHandler("active", active))
    application.add_handler(CommandHandler("dev", dev))
    application.add_handler(CommandHandler("chat", chat))
    application.add_handler(CommandHandler("show", show))
    application.add_handler(CommandHandler("rank", rank))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("unadmin", unadmin))
    application.add_handler(CommandHandler("wl", banned))
    application.add_handler(CommandHandler("unwl", unbanned))
    application.add_handler(CommandHandler("show_user", list_user))
    application.add_handler(CommandHandler("show_admin", list_admin))
    application.add_handler(CommandHandler("balas", balas))
    application.add_handler(CommandHandler("add_to", add_to))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("index", index_domains))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, remove_domain))  # Untuk konfirmasi penghapusan

    # Menjalankan bot
    application.run_polling()
     # Tambahkan Handler Global untuk Error
    application.add_error_handler(error_handler)

if __name__ == "__main__":
    main()
