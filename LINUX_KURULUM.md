# Linux Kurulum ve Kullanım Rehberi

Bu rehber Debian/Ubuntu tabanlı dağıtımlar içindir. Diğer dağıtımlarda Python 3, `venv`, `pip` ve CUPS paket adları farklı olabilir.

## 1. Gereksinimler

Terminali açıp aşağıdaki araçları kurun:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

Python sürümünü doğrulayın:

```bash
python3 --version
```

Python 3.10 veya üstü önerilir. Proje Python 3.13 üzerinde çalıştırılarak test edilmiştir.

## 2. Projeyi indirme

GitHub deposunu bilgisayara klonlayın. `KULLANICI_ADI` ve `DEPO_ADI` alanlarını kendi GitHub kullanıcı adınız ve depo adınızla değiştirin:

```bash
git clone https://github.com/KULLANICI_ADI/DEPO_ADI.git
cd DEPO_ADI
```

Alternatif olarak GitHub’daki **Code → Download ZIP** seçeneğiyle indirdiğiniz ZIP dosyasını çıkarın ve terminalde proje klasörüne geçin.

## 3. Python sanal ortamı ve paketler

Proje klasöründeyken:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Kurulum bittiğinde uygulamayı başlatın:

```bash
python fisv9.py
```

Uygulama `http://127.0.0.1:5000` adresinde açılır; sistemin varsayılan tarayıcısını otomatik başlatmayı dener. Tarayıcı açılmazsa bu adresi kendiniz açın. Terminal penceresini uygulama çalışırken kapatmayın. Uygulamayı durdurmak için terminalde `Ctrl+C` tuşlarına basın.

Her yeni terminal oturumunda proje klasörüne geçip sanal ortamı etkinleştirin:

```bash
cd DEPO_ADI
source .venv/bin/activate
python fisv9.py
```

## 4. Excel dosyasını yükleme

1. **Excel dosyası** düğmesiyle `.xlsx` dosyanızı seçin.
2. **Excel Yükle** düğmesine basın.
3. Uygulama en az barkod, ürün adı ve satış fiyatı sütunlarını arar. Alış fiyatı ve kalan stok sütunları isteğe bağlıdır.
4. Yükleme özetinde ürün grubu, fiyatı değişen ve tek fiyatlı ürün sayıları görünür.

İlk açılışta **Yalnızca fiyatı değişenleri göster** filtresi açıktır. Tek fiyatlı ürünleri görmek için kutunun işaretini kaldırın veya kategori listesinden **Tek fiyatlı** seçin. Ürünleri ada veya fiyata göre sıralayabilir, barkod/ürün adıyla arayabilirsiniz.

### Tekrar eden barkodlar ve fiyat partileri

Dosyada ayrı bir eski/yeni fiyat sütunu yoktur. Bu nedenle aynı barkod ve ürün adı altındaki farklı satış fiyatları ayrı partiler olarak gösterilir; en düşük fiyat eski, en yüksek fiyat yeni kabul edilir. Aynı fiyattan gelen tekrar satırlarının stok adetleri birleştirilir. Üç ayrı fiyatı bulunan ürünlerde ara fiyatı da etiket fiyatı menüsünden seçebilirsiniz. Yazdırmadan önce seçimi kontrol edin.

## 5. Yazdırma seçenekleri

### Tarayıcı ve CUPS ile yazdırma

Çoğu Linux masaüstü yazıcısı için önerilen yöntem:

1. Yazıcıyı Linux’a kurun ve sistem yazıcılarında göründüğünü doğrulayın.
2. Uygulamada ürünleri seçip **Önizle** düğmesine basın.
3. Önizleme penceresinden **Yazdır** seçeneğini seçin.
4. Yazdırma penceresinde doğru yazıcıyı, etiket/kağıt boyutunu ve ölçeklendirmeyi kontrol edin. Etiket tasarımı 80 × 40 mm ölçüsündedir.

Yazıcı görünmüyorsa dağıtımınızın yazıcı ayarları veya CUPS yönetim arayüzü üzerinden yazıcıyı ekleyin. Yazıcı sürücüsü, bağlantı ve CUPS kurulumu dağıtıma ve yazıcı modeline göre değişir.

### Wi‑Fi/Ethernet yazıcıya doğrudan gönderme

Bu yöntem sadece yazıcının doğrudan ağ üzerinden uygun komutları kabul ettiği modellerde çalışır:

1. **Ayarlar** bölümünde **Wi‑Fi / Ethernet (TCP/IP)** seçin.
2. Yazıcının IP adresini ve desteklediği TCP portunu girin. Port `9100` yaygın bir varsayılandır; yazıcı kılavuzundan doğrulayın.
3. Yazıcının desteklediği ZPL, TSPL veya ESC/POS dilini seçin.
4. Ayarları kaydedin; ürünleri seçip **Yazıcıya Gönder** düğmesini kullanın.

Bilgisayar ile yazıcı aynı ağa erişebilmeli ve seçilen port açık olmalıdır. Bu özellik her marka/modelde çalışacağı garanti edilen evrensel bir bağlantı değildir; gerçek etiket basmadan önce tek bir etiketle deneyin.

### USB, seri port ve Bluetooth

Mevcut doğrudan seri yazdırma seçeneği Windows `COM3` benzeri port adlarını bekler. Linux’taki `/dev/ttyUSB0`, `/dev/ttyACM0` ve `/dev/rfcomm0` portları şu an desteklenmez. Bu bağlantı türleri yerine Linux’ta kurulu yazıcı sürücüsü üzerinden tarayıcı yazdırmasını veya uyumluysa Wi‑Fi yazdırmasını kullanın.

## 6. Sık karşılaşılan durumlar

- **Port 5000 kullanımda:** Başka bir uygulama bu portu kullanıyor olabilir. Uygulamayı kapatın veya portu kullanan süreci bulup durdurun; uygulama adresi ayarlarda sabit `127.0.0.1:5000` olarak kullanılır.
- **Paket kurulumu başarısız:** Sanal ortamın etkin olduğundan emin olun (`source .venv/bin/activate`) ve `python -m pip install -r requirements.txt` komutunu yeniden çalıştırın.
- **Excel sütunu bulunamadı:** Barkod, ürün adı ve satış fiyatı sütun başlıklarını kontrol edin.
- **Önizlemede barkod yok:** Uygulama kendi barkod kütüphanesini yerelden sunar; sayfayı yenileyip Excel’i yeniden yükleyin. Tarayıcı konsolunda başka bir hata varsa ayrıntısıyla inceleyin.
- **Doğrudan Wi‑Fi baskısı başarısız:** Yazıcı IP’sini, portunu, aynı ağda olmayı ve yazıcı komut dilini doğrulayın. Alternatif olarak CUPS/tarayıcı yazdırmasını kullanın.

## 7. Veri ve güvenlik

Uygulama web sunucusunu yalnızca yerel bilgisayarda (`127.0.0.1`) açar; başka cihazlardan erişim sağlamak üzere yapılandırılmamıştır. Yüklenen ürün verisi bir veritabanına yazılmaz ve uygulama durduğunda bellekten silinir. Gerçek mağaza Excel dosyalarını herkese açık GitHub deposuna yüklemeyin.
