from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import ctypes
import ipaddress
import logging
import os
import re
import socket
import sys
import unicodedata
import webbrowser

import pandas as pd
from flask import Flask, jsonify, render_template_string, request
import serial
from werkzeug.serving import make_server

APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, static_folder=os.path.join(APP_DIR, "static"))
VERI_HAZIR = {"ham_veri": []}
MAX_ETIKET_ADEDI = 500
SERVER_PORT = 5000


def _normalize(value):
    value = str(value or "").replace("ı", "i").replace("İ", "i")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _money(value):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return Decimal("0.00")
    text = str(value).strip().replace("₺", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise ValueError(f"Geçersiz fiyat değeri: {value}") from error


def _number(value, default=0):
    if value is None or pd.isna(value) or str(value).strip() == "":
        return default
    try:
        return max(0, int(Decimal(str(value).replace(",", "."))))
    except (InvalidOperation, ValueError):
        return default


def _column_map(columns):
    aliases = {
        "Barkod": {"barkod", "barkodu", "barcode"},
        "Urun_Adi": {"urunadi", "urun", "productname", "ad"},
        "Alis_Fiyati": {"alisfiyati", "alis", "purchaseprice"},
        "Yeni_Fiyat": {"satisfiyati", "satis", "saleprice", "yenifiyat"},
        "Kalan": {"kalan", "stok", "mevcut", "remaining"},
    }
    normalized = {_normalize(column): column for column in columns}
    result = {}
    for field, names in aliases.items():
        match = next((normalized[name] for name in names if name in normalized), None)
        if match is not None:
            result[field] = match
    missing = {"Barkod", "Urun_Adi", "Yeni_Fiyat"} - result.keys()
    if missing:
        raise ValueError(
            "Excel'de gerekli sütunlar bulunamadı: "
            + ", ".join(sorted(missing))
            + ". Barkod, Ürün Adı ve Satış Fiyatı sütunları gereklidir."
        )
    return result


def _group_products(dataframe):
    columns = _column_map(dataframe.columns)
    groups = {}
    for _, row in dataframe.iterrows():
        barcode = str(row.get(columns["Barkod"], "") or "").strip()
        name = re.sub(r"\s+", " ", str(row.get(columns["Urun_Adi"], "") or "")).strip()
        if not barcode or not name:
            continue
        group_key = (barcode, _normalize(name))
        product = groups.setdefault(
            group_key,
            {"Barkod": barcode, "Urun_Adi": name, "fiyatlar": {}},
        )
        price = _money(row.get(columns["Yeni_Fiyat"]))
        batch = product["fiyatlar"].setdefault(
            str(price),
            {"fiyat": price, "adet": 0, "alis_toplam": Decimal("0.00")},
        )
        quantity = _number(row.get(columns.get("Kalan")), default=1)
        buy_price = _money(row.get(columns.get("Alis_Fiyati")))
        batch["adet"] += quantity
        batch["alis_toplam"] += buy_price * quantity

    products = []
    for index, product in enumerate(groups.values()):
        batches = sorted(product["fiyatlar"].values(), key=lambda batch: batch["fiyat"])
        prices = [batch["fiyat"] for batch in batches]
        old_price, new_price = prices[0], prices[-1]
        for batch in batches:
            batch["alis_fiyati"] = (
                batch["alis_toplam"] / batch["adet"]
                if batch["adet"]
                else Decimal("0.00")
            )
        products.append(
            {
                "_id": index,
                "Barkod": product["Barkod"],
                "Urun_Adi": product["Urun_Adi"],
                "Eski_Fiyat": float(old_price),
                "Yeni_Fiyat": float(new_price),
                "Alis_Fiyati": float(batches[-1]["alis_fiyati"]),
                "Parti_Durumu": "Fiyatı değişen" if len(prices) > 1 else "Tek fiyat",
                "Fiyat_Sayisi": len(prices),
                "Fiyatlar": [
                    {
                        "fiyat": float(batch["fiyat"]),
                        "adet": batch["adet"],
                        "alis_fiyati": float(batch["alis_fiyati"]),
                    }
                    for batch in batches
                ],
            }
        )
    return products

HTML_SAY = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Evrensel Fiş & Raf Etiketi Sistemi</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="{{ url_for('static', filename='JsBarcode.all.min.js') }}"></script>
    <style>
        :root { color-scheme: light; --bg: #f4f6f9; --surface: #fff; --text: #202734; --muted: #64748b; --border: #d7dee8; --soft: #eef2f7; }
        body { font-family: Arial, sans-serif; margin: 0; padding: 15px; background: var(--bg); color: var(--text); }
        body.dark { color-scheme: dark; --bg: #111827; --surface: #1f2937; --text: #f3f4f6; --muted: #b6c2d2; --border: #475569; --soft: #263449; }
        .container { max-width: 1250px; margin: auto; background: var(--surface); padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h2 { color: #333; margin-top: 0; font-size: 20px; }
        body.dark h2 { color: var(--text); }
        .btn { background: #0052cc; color: white; padding: 10px 15px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold; }
        .btn-preview { background: #6554c0; }
        .btn-success { background: #00875a; }
        .btn-warning { background: #ffab00; color: black; }
        .btn-danger { background: #de350b; color: white; padding: 8px 12px; font-size: 13px; }
        .arama-kutu, .row-actions { margin: 15px 0; padding: 10px; background: var(--soft); border-radius: 5px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .arama-kutu input, select, .settings input { box-sizing: border-box; padding: 9px; font-size: 14px; border: 1px solid var(--border); border-radius: 4px; background: var(--surface); color: var(--text); }
        .arama-kutu input { width: min(280px, 100%); }
        .table-wrap { width: 100%; overflow-x: auto; }
        table { width: 100%; min-width: 900px; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid var(--border); padding: 8px; text-align: center; font-size: 13px; }
        th { background: var(--soft); }
        .settings { margin: 10px 0; padding: 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--soft); }
        .settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; align-items: end; }
        .settings label { display: flex; flex-direction: column; gap: 5px; font-size: 13px; }
        .settings-help { color: var(--muted); font-size: 12px; line-height: 1.5; }
        .fiyat-detay { display: block; color: var(--muted); font-size: 11px; margin-top: 3px; }
        .mobile-note { color: var(--muted); font-size: 12px; }
        @media (max-width: 650px) {
            body { padding: 8px; }
            .container { padding: 12px; }
            .row-actions .btn { flex: 1 1 145px; }
            .arama-kutu > * { max-width: 100%; }
            .arama-kutu input { flex: 1 1 100%; width: 100%; }
        }
        .radio-group { display: flex; gap: 10px; justify-content: center; align-items: center; }

        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.6); overflow-y: auto; }
        .modal-content { background-color: #e9ecef; margin: 3% auto; padding: 20px; border-radius: 8px; width: 90%; max-width: 850px; }
        .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #ccc; padding-bottom: 10px; margin-bottom: 15px; }
        .etiket-listesi { display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; }

        .raf-etiketi {
            width: 320px;
            height: 135px;
            background: #ffffff;
            border: 1px solid #999;
            padding: 8px 12px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            font-family: 'Arial', sans-serif;
            color: #111;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
            page-break-inside: avoid;
            break-inside: avoid;
        }
        .etiket-ust { font-weight: bold; font-size: 13px; text-transform: uppercase; line-height: 1.2; text-align: left; }
        .etiket-kod { font-weight: bold; font-size: 13px; margin-top: 2px; text-align: left; }
        .etiket-orta { display: flex; justify-content: space-between; align-items: center; margin-top: 2px; }
        .barkod-alani { width: 52%; text-align: center; }
        .barkod-alani svg { width: 100%; height: 42px; }
        .fiyat-alani { width: 48%; text-align: right; display: flex; flex-direction: column; justify-content: center; }
        .alis-fiyat { font-size: 11px; font-weight: bold; color: #333; margin-bottom: 4px; }
        .satis-fiyat { font-size: 13px; font-weight: bold; }
        .satis-rakam { font-size: 21px; font-weight: 900; letter-spacing: -0.5px; }
        .etiket-alt { font-size: 10px; color: #333; text-align: left; font-weight: bold; }

        @media print {
            @page {
                size: 80mm 40mm;
                margin: 0;
            }
            body * { visibility: hidden; }
            #onizlemeAlani, #onizlemeAlani * { visibility: visible; }
            #onizlemeAlani { 
                position: absolute; 
                left: 0; 
                top: 0; 
                width: 100%; 
                background: white; 
                margin: 0;
                padding: 0;
            }
            .no-print { display: none !important; }
            .raf-etiketi { 
                box-shadow: none; 
                border: none; 
                margin: 0; 
                page-break-after: always;
                break-after: page;
            }
        }
    </style>
</head>
<body>
<div class="container">
    <h2>Evrensel Fiş & Raf Etiketi Sistemi</h2>
    
    <div class="row-actions">
        <input type="file" id="excelFile" accept=".xlsx, .xls" />
        <button class="btn" onclick="dosyaYukle()">1. Excel Yükle</button>
        <button class="btn btn-preview" onclick="onizlemeAc()">👁️ Önizle</button>
        <button class="btn btn-success" onclick="onizlemeAc(true)">🖨️ Önizle ve Yazdır</button>
        <button class="btn btn-warning" onclick="yaziciyaGonder()">⚙️ Yazıcıya Gönder</button>
        <button class="btn" onclick="temayiDegistir()">🌙 Tema</button>
    </div>

    <details class="settings">
        <summary><strong>⚙️ Ayarlar</strong></summary>
        <div class="settings-grid" style="margin-top:12px;">
            <label>Yazıcı marka / model
                <input id="printerModel" type="text" placeholder="Örn. Zebra, TSC, Xprinter">
            </label>
            <label>Bağlantı
                <select id="printerTransport" onchange="yaziciAlanlariniGoster()">
                    <option value="browser">Windows / tarayıcı yazdırması (önerilen)</option>
                    <option value="wifi">Wi-Fi / Ethernet (TCP/IP)</option>
                    <option value="serial">COM / Bluetooth sanal COM</option>
                </select>
            </label>
            <label>Yazıcı dili (doğrudan bağlantıda)
                <select id="printerLanguage">
                    <option value="zpl">ZPL</option>
                    <option value="tspl">TSPL</option>
                    <option value="escpos">ESC/POS</option>
                </select>
            </label>
            <label class="wifi-setting">Yazıcı IP adresi
                <input id="printerHost" type="text" placeholder="192.168.1.50">
            </label>
            <label class="wifi-setting">TCP portu
                <input id="printerPort" type="number" min="1" max="65535" value="9100">
            </label>
            <label class="serial-setting">COM portu (Bluetooth için eşleştirilmiş sanal COM)
                <input id="printerCom" type="text" placeholder="COM3">
            </label>
            <label class="serial-setting">Baud hızı
                <input id="printerBaud" type="number" min="1200" value="9600">
            </label>
        </div>
        <p class="settings-help">Ayarlar bu tarayıcıda saklanır. En geniş uyumluluk için “Windows / tarayıcı yazdırması” seçin; bu seçenek kurulu Windows yazıcı sürücüsünü kullanır. Wi‑Fi ve COM/Bluetooth sanal COM doğrudan yazdırma için Flask sunucusunun yazıcıya erişen bilgisayarda çalışması gerekir. Bluetooth cihazını önce Windows’ta eşleştirip sanal COM portunu seçin. Doğrudan yazdırmada yazıcı dili (ZPL/TSPL/ESC/POS) cihazla aynı olmalıdır.</p>
        <button class="btn" onclick="ayarlariKaydet()">Ayarları Kaydet</button>
    </details>

    <div class="arama-kutu">
        <strong>🔍 Ürün Ara:</strong>
        <input type="search" id="aramaGirdisi" oninput="urunleriFiltrele()" placeholder="Barkod veya ürün adı yazın...">
        <label><input type="checkbox" id="sadeceGerekliler" checked onchange="urunleriFiltrele()"> Yalnızca fiyatı değişenleri göster</label>
        <select id="kategoriFiltresi" onchange="kategoriFiltresiDegisti()" aria-label="Fiyat kategorisi">
            <option value="hepsi">Tüm kategoriler</option>
            <option value="Fiyatı değişen">Fiyatı değişen</option>
            <option value="Tek fiyat">Tek fiyatlı</option>
        </select>
        <select id="sirala" onchange="urunleriFiltrele()" aria-label="Ürünleri sırala">
            <option value="name">Ada göre sırala</option>
            <option value="price-asc">Fiyata göre (artan)</option>
            <option value="price-desc">Fiyata göre (azalan)</option>
        </select>
        <button class="btn btn-danger" onclick="filtreleriTemizle()">Filtreyi Temizle</button>
        <span id="aramaBilgi" style="color: #666; font-size: 13px;"></span>
    </div>

    <div id="durum" style="margin-bottom: 10px; font-weight: bold;">Durum: Excel bekleniyor...</div>

    <!-- Sınırlandırma kaldırıldı, liste dikeyde serbestçe akacak -->
    <div class="table-wrap">
        <table id="urunTablosu">
            <thead>
                <tr>
                    <th><input type="checkbox" onclick="tumunuSec(this)"> Seç</th>
                    <th>Barkod</th>
                    <th>Ürün Adı</th>
                    <th>Fiyat Grubu</th>
                    <th>Eski Fiyat</th>
                    <th>Yeni Fiyat</th>
                    <th>Etiket fiyatı</th>
                    <th>Adet</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    </div>
</div>

<div id="onizlemeModal" class="modal">
    <div class="modal-content">
        <div class="modal-header no-print">
            <h3 style="margin:0;">Etiket Önizlemesi (<span id="onizlemeSayisi">0</span> Adet)</h3>
            <div>
                <button class="btn btn-success" onclick="window.print()">🖨️ Yazdır</button>
                <button class="btn" style="background:#d9534f;" onclick="onizlemeKapat()">Kapat</button>
            </div>
        </div>
        <div id="onizlemeAlani" class="etiket-listesi"></div>
    </div>
</div>

<script>
let tumUrunlerVeri = [];
const urunDurumlari = {};
const BUGUN_TARIH = "{{ bugun }}";

function htmlGuvenli(metin) {
    return String(metin == null ? "" : metin).replace(/[&<>"']/g, karakter => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[karakter]);
}

function fiyatYaz(fiyat) {
    return Number(fiyat || 0).toFixed(2).replace(".", ",") + " ₺";
}

function temaUygula() {
    document.body.classList.toggle("dark", localStorage.getItem("gfis-dark") === "true");
}

function temayiDegistir() {
    localStorage.setItem("gfis-dark", document.body.classList.toggle("dark") ? "true" : "false");
}

function yaziciAlanlariniGoster() {
    const wifi = document.getElementById("printerTransport").value === "wifi";
    const serialMode = document.getElementById("printerTransport").value === "serial";
    document.querySelectorAll(".wifi-setting").forEach(el => el.style.display = wifi ? "flex" : "none");
    document.querySelectorAll(".serial-setting").forEach(el => el.style.display = serialMode ? "flex" : "none");
}

function ayarlariKaydet() {
    const ayarlar = {};
    ["printerModel", "printerTransport", "printerLanguage", "printerHost", "printerPort", "printerCom", "printerBaud"]
        .forEach(id => ayarlar[id] = document.getElementById(id).value);
    localStorage.setItem("gfis-printer", JSON.stringify(ayarlar));
    yaziciAlanlariniGoster();
    alert("Yazıcı ayarları bu tarayıcıya kaydedildi.");
}

function ayarlariYukle() {
    try {
        const ayarlar = JSON.parse(localStorage.getItem("gfis-printer") || "{}");
        Object.keys(ayarlar).forEach(id => {
            const alan = document.getElementById(id);
            if (alan) alan.value = ayarlar[id];
        });
    } catch (error) {
        console.error("Yazıcı ayarları okunamadı:", error);
    }
    temaUygula();
    yaziciAlanlariniGoster();
}

async function dosyaYukle() {
    let fileInput = document.getElementById('excelFile');
    if (fileInput.files.length === 0) {
        alert("Lütfen önce bir Excel dosyası seçin.");
        return;
    }

    let formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        document.getElementById('durum').innerText = "Excel okunuyor...";
        let response = await fetch('/upload', { method: 'POST', body: formData });
        let result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.error || "Excel yüklenemedi.");
        tumUrunlerVeri = result.veriler;
        Object.keys(urunDurumlari).forEach(key => delete urunDurumlari[key]);
        document.getElementById('durum').innerText =
            `Ürün: ${result.toplam} · Fiyatı değişen: ${result.degisen} · Tek fiyatlı: ${result.tek_fiyat}`;
        urunleriFiltrele();
    } catch (error) {
        document.getElementById('durum').innerText = "Yükleme başarısız.";
        alert("Excel yükleme hatası: " + error.message);
    }
}

function tabloyuDoldur(veriler) {
    let tbody = document.getElementById('urunTablosu').querySelector('tbody');
    tbody.replaceChildren();
    veriler.forEach(item => {
        const id = item._id;
        const state = urunDurumlari[id] || {};
        const changed = item.Parti_Durumu === "Fiyatı değişen";
        const checked = state.selected === undefined ? changed : state.selected;
        const choice = state.choice || "new";
        const chosenIndex = state.priceIndex === undefined ? item.Fiyatlar.length - 1 : Number(state.priceIndex);
        const priceInfo = item.Fiyatlar.map(parti =>
            `${fiyatYaz(parti.fiyat)} × ${parti.adet} adet`).join(" · ");
        const priceControl = item.Fiyatlar.length > 2
            ? `<select class="fiyat-secimi" data-index="${id}" aria-label="Etiket fiyatı">${item.Fiyatlar.map((parti, index) => {
                const label = index === 0 ? "Eski" : index === item.Fiyatlar.length - 1 ? "Yeni" : `Ara ${index}`;
                return `<option value="${index}" ${index === chosenIndex ? "selected" : ""}>${label}: ${fiyatYaz(parti.fiyat)} · ${parti.adet} adet</option>`;
            }).join("")}</select>`
            : `<div class="radio-group">
                <label><input type="radio" name="karar_${id}" value="old" ${choice === "old" ? "checked" : ""} ${changed ? "" : "disabled"}> Eski</label>
                <label><input type="radio" name="karar_${id}" value="new" ${choice === "new" ? "checked" : ""} ${changed ? "" : "disabled"}> Yeni</label>
            </div>`;
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><input type="checkbox" class="secim-chx" data-index="${id}" ${checked ? "checked" : ""} aria-label="Ürünü seç"></td>
            <td>${htmlGuvenli(item.Barkod)}</td>
            <td style="text-align:left;padding-left:10px;">${htmlGuvenli(item.Urun_Adi)}</td>
            <td>${htmlGuvenli(item.Parti_Durumu)}<span class="fiyat-detay">${priceInfo}</span></td>
            <td>${fiyatYaz(item.Eski_Fiyat)}</td>
            <td>${fiyatYaz(item.Yeni_Fiyat)}</td>
            <td>${priceControl}</td>
            <td><input type="number" class="adet-girdisi" data-index="${id}" value="${state.quantity || 1}" min="1" max="${MAX_ETIKET_JS}" style="width:60px;text-align:center" aria-label="Etiket adedi"></td>`;
        tbody.appendChild(tr);
    });
    tbody.querySelectorAll(".secim-chx").forEach(input => input.addEventListener("change", () => {
        urunDurumlari[input.dataset.index] = urunDurumlari[input.dataset.index] || {};
        urunDurumlari[input.dataset.index].selected = input.checked;
    }));
    tbody.querySelectorAll("input[type=radio]").forEach(input => input.addEventListener("change", () => {
        const id = input.name.replace("karar_", "");
        urunDurumlari[id] = urunDurumlari[id] || {};
        urunDurumlari[id].choice = input.value;
        const product = tumUrunlerVeri.find(item => String(item._id) === id);
        urunDurumlari[id].priceIndex = input.value === "old" ? 0 : product.Fiyatlar.length - 1;
    }));
    tbody.querySelectorAll(".fiyat-secimi").forEach(input => input.addEventListener("change", () => {
        const id = input.dataset.index;
        urunDurumlari[id] = urunDurumlari[id] || {};
        urunDurumlari[id].priceIndex = Number(input.value);
    }));
    tbody.querySelectorAll(".adet-girdisi").forEach(input => input.addEventListener("change", () => {
        const id = input.dataset.index;
        const quantity = Math.min({{ max_etiket }}, Math.max(1, Number(input.value) || 1));
        input.value = quantity;
        urunDurumlari[id] = urunDurumlari[id] || {};
        urunDurumlari[id].quantity = quantity;
    }));
    document.getElementById('aramaBilgi').innerText = `Gösterilen: ${veriler.length} / ${tumUrunlerVeri.length} ürün`;
}

function tumunuSec(kaynak) {
    document.querySelectorAll('.secim-chx').forEach(chx => {
        chx.checked = kaynak.checked;
        urunDurumlari[chx.dataset.index] = urunDurumlari[chx.dataset.index] || {};
        urunDurumlari[chx.dataset.index].selected = kaynak.checked;
    });
}

function urunleriFiltrele() {
    let arananMetin = document.getElementById('aramaGirdisi').value.toLowerCase();
    const sadeceGerekliler = document.getElementById("sadeceGerekliler").checked;
    const kategori = document.getElementById("kategoriFiltresi").value;
    let filtrelenmis = tumUrunlerVeri.filter(item =>
        (!sadeceGerekliler || item.Parti_Durumu === "Fiyatı değişen") &&
        (kategori === "hepsi" || item.Parti_Durumu === kategori) &&
        (String(item.Barkod).toLowerCase().includes(arananMetin) ||
         String(item.Urun_Adi).toLowerCase().includes(arananMetin))
    );
    const siralama = document.getElementById("sirala").value;
    filtrelenmis.sort((a, b) => siralama === "price-asc" ? a.Yeni_Fiyat - b.Yeni_Fiyat :
        siralama === "price-desc" ? b.Yeni_Fiyat - a.Yeni_Fiyat :
        a.Urun_Adi.localeCompare(b.Urun_Adi, "tr"));
    tabloyuDoldur(filtrelenmis);
}

function kategoriFiltresiDegisti() {
    const kategori = document.getElementById("kategoriFiltresi").value;
    const gerekliKutusu = document.getElementById("sadeceGerekliler");
    if (kategori === "Tek fiyat") {
        gerekliKutusu.checked = false;
        gerekliKutusu.disabled = true;
    } else {
        gerekliKutusu.disabled = false;
    }
    urunleriFiltrele();
}

function filtreleriTemizle() {
    document.getElementById('aramaGirdisi').value = "";
    document.getElementById("kategoriFiltresi").value = "hepsi";
    document.getElementById("sirala").value = "name";
    document.getElementById("sadeceGerekliler").checked = false;
    document.getElementById("sadeceGerekliler").disabled = false;
    urunleriFiltrele();
}

function secilenUrunleriHazirla() {
    const visibleSelections = new Set(
        Array.from(document.querySelectorAll(".secim-chx:checked")).map(input => input.dataset.index)
    );
    return tumUrunlerVeri.filter(item => visibleSelections.has(String(item._id))).map(item => {
        const state = urunDurumlari[item._id] || {};
        const selectedIndex = state.priceIndex === undefined
            ? (state.choice === "old" ? 0 : item.Fiyatlar.length - 1)
            : Number(state.priceIndex);
        const parti = item.Fiyatlar[selectedIndex];
        return {
            barkod: item.Barkod,
            ad: item.Urun_Adi,
            fiyat: parti.fiyat,
            alis_fiyati: parti.alis_fiyati,
            quantity: state.quantity || 1,
            tarih: BUGUN_TARIH
        };
    });
}

async function yaziciyaGonder() {
    const secilenler = secilenUrunleriHazirla();
    if (!secilenler.length) {
        alert("Yazdırmak için en az bir ürün seçin.");
        return;
    }
    const ayarlar = JSON.parse(localStorage.getItem("gfis-printer") || "{}");
    if (!ayarlar.printerTransport || ayarlar.printerTransport === "browser") {
        onizlemeAc(true);
        return;
    }
    const labels = secilenler.map(item => ({
        barcode: item.barkod, name: item.ad, price: item.fiyat, quantity: item.quantity
    }));
    const config = {
        transport: ayarlar.printerTransport,
        language: ayarlar.printerLanguage || "zpl",
        host: ayarlar.printerHost,
        port: ayarlar.printerPort,
        com: ayarlar.printerCom,
        baud: ayarlar.printerBaud
    };
    try {
        const response = await fetch("/print", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ labels, config })
        });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.error || "Yazdırma başarısız.");
        alert(`${result.count} etiket yazıcıya gönderildi.`);
    } catch (error) {
        alert("Yazdırma hatası: " + error.message);
    }
}

function onizlemeAc(direktYazdir = false) {
    let secilenler = secilenUrunleriHazirla();
    if (secilenler.length === 0) {
        alert("Önizlemek veya yazdırmak için en az bir ürün seçmelisiniz.");
        return;
    }

    let onizlemeAlani = document.getElementById('onizlemeAlani');
    onizlemeAlani.innerHTML = "";
    const toplamEtiket = secilenler.reduce((sum, item) => sum + item.quantity, 0);
    document.getElementById('onizlemeSayisi').innerText = toplamEtiket;
    let barcodeIndex = 0;
    secilenler.forEach(item => {
        for (let copy = 0; copy < item.quantity; copy++) {
            const i = barcodeIndex++;
            onizlemeAlani.insertAdjacentHTML("beforeend", `
                <div class="raf-etiketi">
                    <div>
                        <div class="etiket-ust">${htmlGuvenli(item.ad)}</div>
                        <div class="etiket-kod">${htmlGuvenli(item.barkod)}</div>
                    </div>
                    <div class="etiket-orta">
                        <div class="barkod-alani"><svg id="barcode_${i}"></svg></div>
                        <div class="fiyat-alani">
                            <div class="alis-fiyat">ALIŞ: &nbsp; ${fiyatYaz(item.alis_fiyati)}</div>
                            <div class="satis-fiyat">SATIŞ: <span class="satis-rakam">${fiyatYaz(item.fiyat)}</span></div>
                        </div>
                    </div>
                    <div class="etiket-alt">TARİHİ: &nbsp;${htmlGuvenli(item.tarih)}</div>
                </div>`);
            if (!window.JsBarcode) throw new Error("Barkod kütüphanesi yüklenemedi; internet bağlantısını kontrol edin.");
            JsBarcode(`#barcode_${i}`, String(item.barkod), {
                format: "CODE128", width: 1.5, height: 32, displayValue: true, fontSize: 11, margin: 0
            });
        }
    });

    document.getElementById('onizlemeModal').style.display = "block";

    if (direktYazdir) {
        setTimeout(() => { window.print(); }, 400);
    }
}

function onizlemeKapat() {
    document.getElementById('onizlemeModal').style.display = "none";
}

const MAX_ETIKET_JS = {{ max_etiket }};
ayarlariYukle();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    bugun = datetime.now().strftime("%d.%m.%Y")
    return render_template_string(HTML_SAY, bugun=bugun, max_etiket=MAX_ETIKET_ADEDI)

@app.route("/upload", methods=["POST"])
def upload():
    try:
        file = request.files.get("file")
        if file is None or not file.filename:
            return jsonify({"success": False, "error": "Excel dosyası seçilmedi."}), 400
        dataframe = pd.read_excel(file, dtype=str)
        products = _group_products(dataframe)
        if not products:
            return jsonify({"success": False, "error": "Excel'de okunabilir ürün satırı bulunamadı."}), 400
        VERI_HAZIR["ham_veri"] = products
        changed = sum(item["Parti_Durumu"] == "Fiyatı değişen" for item in products)
        return jsonify({
            "success": True,
            "toplam": len(products),
            "degisen": changed,
            "tek_fiyat": len(products) - changed,
            "veriler": products,
        })
    except Exception as e:
        logging.exception("Excel dosyası işlenemedi")
        return jsonify({"success": False, "error": str(e)}), 400


def _printer_bytes(labels, language):
    if not isinstance(labels, list) or not labels:
        raise ValueError("En az bir etiket seçilmelidir.")
    total = 0
    commands = []
    for label in labels:
        if not isinstance(label, dict):
            raise ValueError("Etiket verisi geçersiz.")
        barcode = str(label.get("barcode", "")).strip()
        name = str(label.get("name", "")).strip()
        price = _money(label.get("price"))
        quantity = _number(label.get("quantity"), default=1)
        if not barcode or not name:
            raise ValueError("Ürün adı ve barkod boş olamaz.")
        if quantity < 1:
            raise ValueError("Etiket adedi en az 1 olmalıdır.")
        total += quantity
        if total > MAX_ETIKET_ADEDI:
            raise ValueError(f"Tek seferde en fazla {MAX_ETIKET_ADEDI} etiket gönderilebilir.")
        safe_name = re.sub(r"[\r\n\x00-\x1f]", " ", name).replace('"', "'")
        safe_barcode = re.sub(r"[\r\n\x00-\x1f]", "", barcode)
        if language == "zpl":
            safe_name = safe_name.replace("^", " ").replace("~", " ")
            safe_barcode = safe_barcode.replace("^", " ").replace("~", " ")
            command = (
                "^XA^CI28^PW640^LL320"
                f"^FO20,20^A0N,28,28^FB600,2,2,L,0^FD{safe_name}^FS"
                f"^FO20,95^A0N,22,22^FD{safe_barcode}^FS"
                f"^FO20,135^BCN,65,Y,N,N^FD{safe_barcode}^FS"
                f"^FO360,145^A0N,24,24^FDSATIS: {price} TL^FS^XZ"
            )
        elif language == "tspl":
            safe_name = safe_name.replace("\\", " ").replace('"', "'")
            safe_barcode = safe_barcode.replace("\\", " ").replace('"', "'")
            command = (
                "SIZE 80 mm,40 mm\r\nGAP 2 mm,0 mm\r\nCLS\r\n"
                f'TEXT 20,15,"TSS24.BF2",0,1,1,"{safe_name}"\r\n'
                f'BARCODE 20,85,"128",65,1,0,2,2,"{safe_barcode}"\r\n'
                f'TEXT 360,140,"3",0,1,1,"{price} TL"\r\nPRINT 1,1\r\n'
            )
        elif language == "escpos":
            text = f"{safe_name}\n{safe_barcode}\nSATIS: {price} TL\n".encode("cp1254", errors="replace")
            # ESC/POS uses GS k m=73 for Code 128 on compatible printers.
            barcode_bytes = safe_barcode.encode("ascii", errors="replace")
            if not barcode_bytes or len(barcode_bytes) > 255:
                raise ValueError("ESC/POS Code 128 barkodu 1 ile 255 ASCII karakter arasında olmalıdır.")
            command = b"\x1b@" + text + b"\x1dH\x02\x1dkI" + bytes([len(barcode_bytes)]) + barcode_bytes + b"\n\n"
            commands.extend([command] * quantity)
            continue
        else:
            raise ValueError("Yazıcı dili ZPL, TSPL veya ESC/POS olmalıdır.")
        commands.extend([command.encode("utf-8")] * quantity)
    return b"".join(commands), total


@app.route("/print", methods=["POST"])
def print_labels():
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return jsonify({
            "success": False,
            "error": "Doğrudan yazıcı bağlantısı yalnızca yazıcı sunucusunun çalıştığı bilgisayardan kullanılabilir.",
        }), 403
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ValueError("Yazdırma isteği geçersiz; ayarları kontrol edip tekrar deneyin.")
        config = payload.get("config", {}) if isinstance(payload, dict) else {}
        labels = payload.get("labels") if isinstance(payload, dict) else None
        if not isinstance(config, dict):
            raise ValueError("Yazıcı ayarları geçersiz.")
        language = str(config.get("language", "zpl")).lower()
        data, count = _printer_bytes(labels, language)
        transport = str(config.get("transport", "")).lower()
        if transport == "wifi":
            host = str(config.get("host", "")).strip()
            try:
                address = ipaddress.ip_address(host)
            except ValueError as error:
                raise ValueError("Yazıcı için geçerli bir IP adresi girin.") from error
            port = _number(config.get("port"), default=9100)
            if not 1 <= port <= 65535:
                raise ValueError("TCP portu 1 ile 65535 arasında olmalıdır.")
            with socket.create_connection((str(address), port), timeout=5) as printer:
                printer.sendall(data)
        elif transport == "serial":
            port_name = str(config.get("com", "")).strip()
            baudrate = _number(config.get("baud"), default=9600)
            if not re.fullmatch(r"COM\d+", port_name, re.IGNORECASE):
                raise ValueError("Geçerli bir COM portu girin (ör. COM3). Bluetooth için Windows sanal COM portunu seçin.")
            if baudrate < 1200:
                raise ValueError("Baud hızı en az 1200 olmalıdır.")
            with serial.Serial(port_name.upper(), baudrate=baudrate, timeout=2, write_timeout=5) as printer:
                printer.write(data)
                printer.flush()
        else:
            raise ValueError("Doğrudan yazdırma için Wi-Fi veya COM bağlantısını seçin.")
        return jsonify({"success": True, "count": count})
    except (ValueError, OSError, serial.SerialException) as error:
        logging.exception("Etiketler yazıcıya gönderilemedi")
        return jsonify({"success": False, "error": str(error)}), 400

def run_desktop_app():
    try:
        server = make_server("127.0.0.1", SERVER_PORT, app, threaded=True)
    except OSError as error:
        logging.exception("Uygulama sunucusu başlatılamadı")
        message = f"Uygulama başlatılamadı. {SERVER_PORT} portu kullanımda olabilir.\n{error}"
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(0, message, "Yamaç Etiket", 0x10)
        else:
            print(message, file=sys.stderr)
        return

    url = f"http://127.0.0.1:{server.server_port}"
    if not webbrowser.open_new_tab(url):
        message = f"Tarayıcı otomatik açılamadı. Bu adresi tarayıcıya yazın: {url}"
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(0, message, "Yamaç Etiket", 0x40)
        else:
            print(message, file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_desktop_app()