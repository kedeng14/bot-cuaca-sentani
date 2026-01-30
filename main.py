import requests
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import os
import datetime

# --- KONFIGURASI DARI GITHUB SECRETS ---
TOKEN_BOT = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# --- 1. FUNGSI PENDUKUNG ---
def dapatkan_hari_indo(date_obj):
    hari_map = {
        'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
        'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'
    }
    bulan_map = {
        'January': 'Januari', 'February': 'Februari', 'March': 'Maret', 'April': 'April',
        'May': 'Mei', 'June': 'Juni', 'July': 'Juli', 'August': 'Agustus',
        'September': 'September', 'October': 'Oktober', 'November': 'November', 'December': 'Desember'
    }
    hari = hari_map.get(date_obj.strftime('%A'))
    tgl = date_obj.strftime('%d')
    bulan = bulan_map.get(date_obj.strftime('%B'))
    tahun = date_obj.strftime('%Y')
    return f"{hari}, {tgl} {bulan} {tahun}"

def terjemahkan_arah(kode):
    kamus_arah = {
        'N': 'Utara', 'NNE': 'U. Timur Laut', 'NE': 'Timur Laut', 'ENE': 'T. Timur Laut', 
        'E': 'Timur', 'ESE': 'T. Tenggara', 'SE': 'Tenggara', 'SSE': 'S. Tenggara', 
        'S': 'Selatan', 'SSW': 'S. Barat Daya', 'SW': 'Barat Daya', 'WSW': 'B. Barat Daya', 
        'W': 'Barat', 'WNW': 'B. Barat Laut', 'NW': 'Barat Laut', 'NNW': 'U. Barat Laut', 
        'VARIABLE': 'Berubah-ubah', 'CALM': 'Tenang'
    }
    return kamus_arah.get(str(kode).upper(), kode)

def ambil_kondisi_terburuk(series):
    prioritas = ['Petir', 'Lebat', 'Sedang', 'Hujan', 'Kabut', 'Berawan', 'Cerah']
    kondisi_tersedia = series.unique().tolist()
    for p in prioritas:
        for k in kondisi_tersedia:
            if p.lower() in k.lower(): return k
    return kondisi_tersedia[0]

def buat_dan_kirim():
    try:
        # 1. AMBIL DATA API
        KODE_ADM4 = "91.03.01.1001"
        URL_API = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={KODE_ADM4}"
        response = requests.get(URL_API).json()
        raw_list = response["data"][0]["cuaca"]
        flat_list = [item for sublist in raw_list for item in sublist] if isinstance(raw_list[0], list) else raw_list
        df = pd.json_normalize(flat_list)
        
        df['Waktu_DT'] = pd.to_datetime(df['local_datetime'])
        df['t'] = pd.to_numeric(df['t'])
        df['hu'] = pd.to_numeric(df['hu'])
        df['ws'] = pd.to_numeric(df['ws'])
        
        # 2. LOGIKA ROLLING WINDOW (WIT)
        sekarang = datetime.datetime.now() + datetime.timedelta(hours=9)
        df_filtered = df[(df['Waktu_DT'] >= sekarang - datetime.timedelta(hours=3)) & 
                         (df['Waktu_DT'] <= sekarang + datetime.timedelta(hours=28))].copy()

        def kategori_waktu(hour):
            if 6 <= hour < 12: return 'Pagi'
            elif 12 <= hour < 18: return 'Siang'
            elif 18 <= hour < 24: return 'Malam'
            else: return 'Dini Hari'

        df_filtered['Kategori'] = df_filtered['Waktu_DT'].dt.hour.apply(kategori_waktu)
        urutan_auto = df_filtered.drop_duplicates(subset=['Kategori'])['Kategori'].tolist()[:4]
        
        ringkasan = df_filtered.groupby('Kategori').agg({
            't': ['min', 'max'], 'hu': ['min', 'max'], 'ws': 'max',
            'wd': 'first', 'weather_desc': ambil_kondisi_terburuk, 'Waktu_DT': 'first'
        }).reindex(urutan_auto).dropna().reset_index()
        ringkasan.columns = ['Kategori', 'Suhu_Min', 'Suhu_Max', 'Hum_Min', 'Hum_Max', 'Angin_Max', 'Arah', 'Kondisi', 'Waktu_Ref']

        # 3. VISUALISASI
        img = Image.new('RGB', (1200, 800), color='#1c2833')
        draw = ImageDraw.Draw(img)
        f_path = "Roboto-Bold.ttf"
        
        # Load Ikon & Logo
        i_temp = Image.open("temp.png").convert("RGBA").resize((35, 35))
        i_rh = Image.open("RH.png").convert("RGBA").resize((35, 35))
        i_wind = Image.open("wind.png").convert("RGBA").resize((35, 35))
        
        try:
            logo = Image.open("bmkg.png").convert("RGBA")
            logo.thumbnail((100, 100))
            img.paste(logo, (50, 45), logo)
        except:
            pass

        # Load Font
        f_judul = ImageFont.truetype(f_path, 48)
        f_tgl = ImageFont.truetype(f_path, 26)
        f_kat = ImageFont.truetype(f_path, 36)
        f_suhu = ImageFont.truetype(f_path, 52)
        f_label = ImageFont.truetype(f_path, 20)
        f_val = ImageFont.truetype(f_path, 24)
        f_ref = ImageFont.truetype(f_path, 18)
        f_copy = ImageFont.truetype(f_path, 16) # Font khusus copyright

        # Header Bahasa Indonesia
        tgl_indo = dapatkan_hari_indo(sekarang)
        draw.text((600, 70), "PREDIKSI CUACA SENTANI", font=f_judul, fill='#FEE715', anchor="mm")
        draw.text((600, 115), tgl_indo.upper(), font=f_tgl, fill='#BDC3C7', anchor="mm")
        draw.line((400, 145, 800, 145), fill="#FEE715", width=2)

        x_pos = 50
        for _, row in ringkasan.iterrows():
            # Panel
            draw.rectangle([x_pos, 190, x_pos + 260, 760], outline="#34495e", width=2)
            
            # Kategori & Tanggal
            draw.text((x_pos+30, 225), row['Kategori'].upper(), font=f_kat, fill='#FEE715')
            draw.text((x_pos+30, 262), row['Waktu_Ref'].strftime('%d %b'), font=f_ref, fill='#95a5a6')
            
            # Suhu
            img.paste(i_temp, (x_pos+25, 300), i_temp)
            draw.text((x_pos+70, 295), f"{int(row['Suhu_Min'])}-{int(row['Suhu_Max'])}°C", font=f_suhu, fill='white')
            
            # Kondisi Cuaca
            kondisi = str(row['Kondisi'])
            warna = '#E67E22' if 'Hujan' in kondisi or 'Petir' in kondisi else '#48dbfb'
            draw.text((x_pos+30, 375), kondisi, font=f_val, fill=warna)
            draw.line((x_pos+30, 440, x_pos+230, 440), fill="#34495e", width=1)
            
            # KELEMBABAN
            img.paste(i_rh, (x_pos+25, 480), i_rh)
            draw.text((x_pos+70, 475), "Kelembaban:", font=f_label, fill='#BDC3C7')
            draw.text((x_pos+70, 503), f"{int(row['Hum_Min'])}-{int(row['Hum_Max'])}%", font=f_val, fill='white')
            
            # ANGIN
            img.paste(i_wind, (x_pos+25, 580), i_wind)
            draw.text((x_pos+70, 575), "Angin Max:", font=f_label, fill='#BDC3C7')
            draw.text((x_pos+70, 603), f"{int(round(row['Angin_Max']))} km/j", font=f_val, fill='white')
            
            # ARAH ANGIN
            arah_nama = terjemahkan_arah(row['Arah'])
            draw.text((x_pos+70, 640), f"Arah: {arah_nama}", font=f_ref, fill='#FEE715')
            
            x_pos += 285

        # COPYRIGHT BY KEDENG V (Posisi tengah bawah)
        draw.text((600, 785), "Copyright © 2026 by Kedeng V", font=f_copy, fill='#5d6d7e', anchor="mm")

        nama_file = "output.png"
        img.save(nama_file)

        # 4. KIRIM KE TELEGRAM
        url_tele = f"https://api.telegram.org/bot{TOKEN_BOT}/sendPhoto"
        with open(nama_file, 'rb') as photo:
            requests.post(url_tele, data={'chat_id': CHAT_ID, 'caption': f"📊 Update Cuaca Sentani\n📅 {tgl_indo}"}, files={'photo': photo})

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    buat_dan_kirim()
