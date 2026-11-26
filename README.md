# Yamaç Etiket

Excel ürün listesinden barkodlu raf etiketleri hazırlamak ve yazdırmak için yerel çalışan, Flask tabanlı bir web uygulaması.

## Özellikler

- `.xlsx` ürün listesi yükleme
- Barkod ve ürün adına göre arama
- Fiyatı değişen ürünleri filtreleme; tek fiyatlı ürünleri ayrı gösterme
- Ada veya fiyata göre sıralama
- Tekrarlanan barkod/ürün kayıtlarını fiyat partilerine ayırma ve aynı fiyatlı stokları birleştirme
- Eski/yeni fiyat seçimi; üç fiyatlı ürünlerde ara fiyatı seçebilme
- Barkodlu raf etiketi önizlemesi ve tarayıcı üzerinden yazdırma
- Kurulu yazıcı sürücüsü, uyumlu Wi‑Fi yazıcı ve Windows COM bağlantısı
- Mobil ekranda kullanılabilen arayüz ve koyu tema

## Excel biçimi

Desteklenen ve test edilen biçim `.xlsx` dosyasıdır.

Zorunlu sütunlar:

- Barkod (ör. `Barkodu`)
- Ürün adı (ör. `Ürün Adı`)
- Satış fiyatı (ör. `Satış Fiyatı`)

`Alış Fiyatı` ve `Kalan` sütunları isteğe bağlıdır. `Kalan` yoksa her satır bir adet kabul edilir. Barkod ve normalleştirilmiş ürün adı aynı olan satırlar gruplanır. Aynı satış fiyatındaki satırların adetleri toplanır; farklı fiyatlar ayrı parti olarak korunur. Birden fazla fiyat bulunduğunda en düşük fiyat “eski”, en yüksek fiyat “yeni” olarak gösterilir. İki fiyat arasındaki partiler de listede tutulur.

Bu varsayım, Excel dosyasında eski/yeni fiyatı belirten ayrı bir sütun olmadığı için kullanılır. Etiket basmadan önce ürün ve fiyat seçimlerini kontrol edin.

## Linux kurulumu ve kullanımı

Adım adım rehber: [LINUX_KURULUM.md](LINUX_KURULUM.md)

Özetle, Python ve sanal ortam desteğini kurduktan sonra proje klasöründe:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python fisv9.py
```

Uygulama `http://127.0.0.1:5000` adresinde çalışır ve varsayılan tarayıcıda açılmayı dener. Kapatmak için terminalde `Ctrl+C` kullanın.

### Linux yazıcı desteği

- **Tarayıcıdan yazdırma:** Linux’ta CUPS üzerinden kurulmuş ve sistem tarafından görülen yazıcılarla kullanılabilir.
- **Wi‑Fi/Ethernet:** Uygulama ayarlarında yazıcı IP’sini, portunu (uyumlu cihazlarda çoğunlukla `9100`) ve yazıcı dilini seçin. Yazıcının doğrudan ağdan bu komut dilini kabul etmesi gerekir.
- **USB/seri/Bluetooth seri port:** Doğrudan seri yazdırma şu an Windows `COM` portları içindir; Linux `/dev/ttyUSB*`, `/dev/ttyACM*` veya `/dev/rfcomm*` aygıtları desteklenmiyor.

Hiçbir yazıcı modeli için evrensel doğrudan yazdırma garantisi yoktur. Model, bağlantı ve yazıcı komut dili uyumlu olmalıdır.

## Windows

Python ile çalıştırmak için:

```powershell
python -m pip install -r requirements.txt
python fisv9.py
```

Windows tek dosyalık uygulamasını kaynak koddan üretmek için `build_windows.bat` dosyasını çalıştırın. Çıktı `dist/YamacEtiket.exe` konumuna yazılır. Bu derleme adımı Linux’ta değil, Windows ortamında çalıştırılmalıdır.

## Etiket hazırlama

1. Excel dosyasını seçip **Excel Yükle** düğmesine basın.
2. Varsayılan olarak yalnızca fiyatı değişen ürünler görünür. Tek fiyatlıları görmek için bu filtreyi kapatın veya kategori menüsünden seçin.
3. Yazdırılacak ürünleri işaretleyin. Aynı barkodda birden çok fiyat varsa etiket fiyatını seçin.
4. Etiket adedini girin. Tek seferde en fazla 500 etiket gönderilebilir.
5. **Önizle** ile sonucu kontrol edin; ardından **Yazdır** seçeneğini kullanın.
6. Doğrudan yazıcı bağlantısı için **Ayarlar** bölümünden bağlantı türü, marka/model bilgisi ve yazıcı dilini seçip ayarları kaydedin.

Yazıcı ayarları ve tema tarayıcının yerel depolamasında saklanır. Ürün verileri bir veritabanına kaydedilmez; sunucu kapandığında bellekteki yükleme de silinir.

emircan...

