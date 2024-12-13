from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging
import requests
from telegram.ext import ContextTypes
import os
import requests
from bs4 import BeautifulSoup
import shutil

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
                    url = 'https://ppp.foxyx.online/'
                    params = {'domains': domains}
                    response = requests.get(url, params=params)

                    if response.status_code == 200:
                        # Memeriksa respons dan memproses setiap domain
                        domain_status = response.text.strip().split('\n')
                        blocked_domains = []

                        for domain in domain_status:
                            domain_name, status = domain.split(': ')
                            if status.strip() == "Blocked!":
                                blocked_domains.append(domain_name.strip())

                        # Jika ada domain yang terblokir, kirim pesan ke user
                        if blocked_domains:
                            await context.bot.send_message(
                                chat_id=int(user_id),
                                text=f"⚠️ Domain ini terblokir Kominfo Cuy ⚠️:\n" + "\n".join(blocked_domains) + "\n\n ✨Agar Tidak Mendapat Pesan Ini lagi Silahkan /ipos lalu hapus domain dengan mengirimkan Y ✨"
                            )
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

# Fungsi untuk memeriksa domain
async def cek_domain(update: Update, context: CallbackContext) -> None:
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
                    url = 'https://ppp.foxyx.online/'
                    params = {'domains': domains}
                    response = requests.get(url, params=params)

                    # Menangani respons
                    if response.status_code == 200:
                        await update.message.reply_text(f"🔍Hasil Pemeriksaan🔍:\n {response.text} 🚀")
                    else:
                        await update.message.reply_text(f"Error: {response.status_code} ⚠️")
                else:
                    await update.message.reply_text("Tambahin Domain Dulu Cuy, Baru Bisa Di Cek. 😉👌")
        except FileNotFoundError:
            await update.message.reply_text("Tambahin Domain Dulu Cuy, Baru Bisa Di Cek. 😉👌")
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
                    url = 'https://ppp.foxyx.online/'
                    params = {'domains': domains}
                    response = requests.get(url, params=params)

                    if response.status_code == 200:
                        # Memeriksa respons dan memproses setiap domain
                        domain_status = response.text.strip().split('\n')
                        blocked_domains = []

                        for domain in domain_status:
                            # Cek status domain, misalnya example.com: Not Blocked!
                            domain_name, status = domain.split(': ')
                            if status.strip() == "Blocked!":
                                blocked_domains.append(domain_name.strip())

                        # Jika ada domain yang diblokir, minta konfirmasi untuk menghapus
                        if blocked_domains:
                            await update.message.reply_text(f"⚠️ Domain ini Diblok Kominfo Cuy ⚠️:\n" + "\n".join(blocked_domains) +
                                                          "\n\nApakah Anda ingin menghapus domain-domain tersebut dari daftar? (Y/N) ❓")
                            context.user_data['blocked_domains'] = blocked_domains  # Simpan domain yang terblokir untuk referensi selanjutnya
                        else:
                            await update.message.reply_text("✅ Aman Jaya Sentausa Cuy. ✅")
                    else:
                        await update.message.reply_text(f"Error: {response.status_code} ⚠️")
                else:
                    await update.message.reply_text("Tambahin Domain Dulu Cuy, Baru Bisa Di Cek. 😉👌")
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
        await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
        return

    # Menggabungkan argumen dan mengganti spasi dengan koma
    domains = ",".join(context.args)

    # URL dan parameter
    url = 'https://ppp.foxyx.online/'
    params = {'domains': domains}

    try:
        # Mengirimkan request ke API
        response = requests.get(url, params=params)
        if response.status_code == 200:
            # Mengirimkan respons API ke pengguna
            await update.message.reply_text(f"🔍Hasil Pemeriksaan🔍:\n {response.text} 🚀")
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
async def rank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
    
    # Cek apakah user ter-banned
    if not await is_user(user_id):
        await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
        return

    if not context.args:
        await update.message.reply_text("Gunakan format: /rank <keyword>")
        return

    keyword = " ".join(context.args)  # Mengambil keyword setelah /rank
    url = "https://seorch.net/php/ranking/ranking.php"

    headers = {
        "Host": "seorch.net",
        "Cookie": "__gads=ID=ec411790f06ead66:T=1733062797:RT=1733062797:S=ALNI_MbPsZANmo5ApY4VAgwfsuCU04LyRQ; "
                  "__gpi=UID=00000fa543511d96:T=1733062797:RT=1733062797:S=ALNI_Mbvlax5juhij4yGJlpkR47A71SdTQ; "
                  "__eoi=ID=03a0268a63e7cb69:T=1733062797:RT=1733062797:S=AA-AfjbZ180PT6UnTkIktbZS_7SC",
        "Content-Length": "112",
        "Sec-Ch-Ua-Platform": "\"Windows\"",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": "\"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
        "Sec-Ch-Ua-Mobile": "?0",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/131.0.6778.86 Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://seorch.net",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://seorch.net/html/google-rank-checker.html",
        "Accept-Encoding": "gzip, deflate, br",
        "Priority": "u=1, i",
        "Connection": "keep-alive"
    }

    data = {
        "kw": keyword,
        "url": "",
        "lang": "id",
        "device": "mobile",
        "bot": "woodsofypres",
        "loc": "",
        "country": "Indonesia",
        "uule": "false"
    }

    # Kirim pesan "Melakukan Pengecekan..." terlebih dahulu
    sent_message = await update.message.reply_text("🔍 Melakukan Pengecekan...")

    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            rows = soup.find_all("tr")

            # Menyimpan semua hasil dalam satu string
            result_message = "🔎 Pengecekan Selesai 🔍:\n ❗SELALU CEK ULANG MELALUI ROAMING❗\n\n"

            for row in rows:
                cells = row.find_all("td")
                if len(cells) > 3:
                    rank = cells[0].text.strip()
                    link = cells[1].find("a")["href"].strip()
                    description = cells[2].text.strip()
                    site = cells[3].text.strip()

                    # Menambahkan hasil ke dalam message string
                    result_message += f"{rank} {link} - {description} - {site}\n"

            # Hapus pesan "Melakukan Pengecekan..."
            await sent_message.delete()

            # Kirim pesan utuh dalam satu kali kirim
            await update.message.reply_text(result_message)
        else:
            await update.message.reply_text(f"⚠️ Gagal mengambil data. Status Code: {response.status_code}")
    except Exception as e:
        # Hapus pesan "Melakukan Pengecekan..." jika terjadi kesalahan
        await sent_message.delete()
        await update.message.reply_text(f"⚠️ Terjadi kesalahan: {e}")

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
async def add_domain(update: Update, context: CallbackContext) -> None:
    if update.message:
        user_id = update.message.from_user.id  # Mendapatkan user_id pengirim
        
        # Cek apakah user ter-banned
        if not await is_user(user_id):
            await update.message.reply_text("🤖 Anda Tidak Memiliki Akses Untuk Memakai Bot Ini 🤖 \n\n 💬 Silahkan Hubungi Developer Dengan Command /chat 💬")
            return
        
        if context.args:
            # Gabungkan semua argumen yang dimasukkan oleh user
            domains = " ".join(context.args)  # Gabungkan menjadi satu string
            file_name = f'{user_id}.txt'  # Nama file berdasarkan user_id

            # Memeriksa apakah argumen terakhir adalah '*'
            add_to_all_files = context.args[-1] == '*'  
            if add_to_all_files:
                domains = " ".join(context.args[:-1])  # Hilangkan '*' dari daftar domain yang akan ditambahkan

            # Ganti spasi antar domain dengan koma
            domains = domains.replace(' ', ',')
            new_domains = domains.split(',')

            try:
                if add_to_all_files:
                    # Menambahkan domain ke semua file .txt di direktori
                    txt_files = [f for f in os.listdir('.') if f.endswith('.txt')]

                    if not txt_files:
                        await update.message.reply_text("Tidak ada User ditemukan.")
                        return

                    for file_name in txt_files:
                        # Membaca file dan menambahkan domain baru
                        with open(file_name, 'r') as file:
                            existing_domains = file.read().strip().split(',')

                        # Menambahkan domain baru yang belum ada
                        unique_domains = [domain for domain in new_domains if domain not in existing_domains]

                        if unique_domains:
                            with open(file_name, 'a') as file:
                                if existing_domains:
                                    file.write(f',{",".join(unique_domains)}')
                                else:
                                    file.write(f'{",".join(unique_domains)}')

                    await update.message.reply_text(f"Domain(s) {','.join(new_domains)} telah ditambahkan ke semua User. 🎉")
                
                else:
                    # Menambahkan domain hanya ke file user_id.txt
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

                        await update.message.reply_text(f"Domain(s) {','.join(unique_domains)} telah ditambahkan ke list Anda. 🎉")
                    else:
                        await update.message.reply_text("Semua domain yang Anda masukkan sudah ada dalam list Anda. 😕")
            
            except Exception as e:
                await update.message.reply_text(f"Terjadi kesalahan: {e} 😔")
        else:
            await update.message.reply_text("Harap masukkan domain yang ingin ditambahkan setelah /add. 💡")
    else:
        await update.message.reply_text("Pesan tidak valid! ❌")

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

# Fungsi utama
def main() -> None:
    # Inisialisasi bot dengan token
    application = Application.builder().token('').build()

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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, remove_domain))  # Untuk konfirmasi penghapusan

    # Menjalankan bot
    application.run_polling()

if __name__ == "__main__":
    main()
