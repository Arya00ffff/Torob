from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import time, re, os, json, sys
from datetime import datetime
from jinja2 import Template

# --- Helper functions ---
def persian_to_english(num_str):
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    trans = str.maketrans(persian_digits, english_digits)
    return num_str.translate(trans)

def extract_number(text):
    numbers = re.findall(r"\d+", persian_to_english(text))
    if numbers:
        return int("".join(numbers))
    return None

def load_history():
    """Load price history from JSON file"""
    if os.path.exists("price_history.json"):
        with open("price_history.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    """Save price history to JSON file"""
    with open("price_history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def update_price_history(history, product_name, link, lowest_price, current_price):
    """Update price history for a product with both lowest and current price"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if link not in history:
        history[link] = {
            "name": product_name,
            "prices": []
        }
    
    # Check if we already have an entry for today
    existing_dates = [entry["date"] for entry in history[link]["prices"]]
    
    if today not in existing_dates:
        history[link]["prices"].append({
            "date": today,
            "lowest_price": lowest_price,
            "current_price": current_price
        })
    else:
        # Update today's prices
        for entry in history[link]["prices"]:
            if entry["date"] == today:
                entry["lowest_price"] = lowest_price
                entry["current_price"] = current_price
                break
    
    return history

def smooth_scroll(driver, pause_time=2):
    """Scroll smoothly and wait for content to load"""
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_attempts = 10
        
        while scroll_attempts < max_attempts:
            # Scroll down in smaller increments
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(pause_time)
            
            # Calculate new scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            # Check if we've reached the bottom
            current_position = driver.execute_script("return window.pageYOffset + window.innerHeight")
            
            if current_position >= new_height:
                # Try one more time to see if more content loads
                time.sleep(3)
                final_height = driver.execute_script("return document.body.scrollHeight")
                if final_height == new_height:
                    break
                new_height = final_height
            
            last_height = new_height
            scroll_attempts += 1
    except Exception as e:
        print(f"  ⚠️ Scroll error: {e}")

def safe_get(driver, url, max_retries=3, timeout=60):
    """Safely load a URL with retries"""
    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}/{max_retries}: Loading {url[:80]}...")
            driver.set_page_load_timeout(timeout)
            driver.get(url)
            return True
        except TimeoutException:
            print(f"  ⚠️ Timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return False
        except WebDriverException as e:
            print(f"  ⚠️ WebDriver error: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return False
    return False

# --- Selenium setup with better error handling ---
options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-extensions")
options.add_argument("--dns-prefetch-disable")
options.add_argument("--disable-setuid-sandbox")
options.add_argument("--disable-software-rasterizer")
options.add_argument("--disable-background-networking")
options.add_argument("--disable-background-timer-throttling")
options.add_argument("--disable-backgrounding-occluded-windows")
options.add_argument("--disable-breakpad")
options.add_argument("--disable-component-extensions-with-background-pages")
options.add_argument("--disable-features=TranslateUI,BlinkGenPropertyTrees")
options.add_argument("--disable-ipc-flooding-protection")
options.add_argument("--disable-renderer-backgrounding")
options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
options.add_argument("--force-color-profile=srgb")
options.add_argument("--hide-scrollbars")
options.add_argument("--metrics-recording-only")
options.add_argument("--mute-audio")
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
options.add_experimental_option('useAutomationExtension', False)
options.page_load_strategy = 'eager'

try:
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(90)
    driver.set_script_timeout(30)
    print("✅ WebDriver initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize WebDriver: {e}")
    sys.exit(1)

url = "https://torob.com/shop/58933/%D8%AA%D8%AC%D9%87%DB%8C%D8%B2%D8%A7%D8%AA-%D8%AA%D9%88%D8%A7%D9%86%D8%A8%D8%AE%D8%B4%DB%8C-%DA%A9%D9%88%D8%B4%D8%A7/%D9%85%D8%AD%D8%B5%D9%88%D9%84%D8%A7%D8%AA/"

products = []
history = load_history()

try:
    print("🌐 Loading main page...")
    
    if not safe_get(driver, url, max_retries=3, timeout=90):
        print("❌ Failed to load main page after retries")
        if history:
            print("📦 Using cached data from previous run")
        else:
            driver.quit()
            sys.exit(1)
    else:
        time.sleep(8)
        
        print("📜 Scrolling to load all products...")
        smooth_scroll(driver, pause_time=3)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_links = soup.select("a[href*='/p/']")
        
        unique_links = {}
        for a in product_links:
            link = "https://torob.com" + a.get("href", "")
            if link not in unique_links:
                unique_links[link] = a
        
        print(f"✅ Found {len(unique_links)} unique products")
        
        is_ci = os.getenv('CI', 'false').lower() == 'true'
        max_products = 20 if is_ci else len(unique_links)
        
        if is_ci and len(unique_links) > max_products:
            print(f"⚠️ CI mode: Processing only first {max_products} products")
            unique_links = dict(list(unique_links.items())[:max_products])
        
        for idx, (link, a) in enumerate(unique_links.items(), 1):
            print(f"Processing {idx}/{len(unique_links)}: {link[:80]}...")
            
            name_tag = a.select_one("h2[class*='ProductCard_desktop_product-name']")
            name = name_tag.get_text(strip=True) if name_tag else "N/A"
            price_tag = a.select_one("div[class*='ProductCard_desktop_product-price-text']")
            current_price_text = price_tag.get_text(strip=True) if price_tag else "N/A"
            current_price_num = extract_number(current_price_text) if current_price_text != "N/A" else None
        
            try:
                if not safe_get(driver, link, max_retries=2, timeout=60):
                    print(f"  ⚠️ Skipping product due to load failure")
                    continue
                    
                time.sleep(3)
                inner_soup = BeautifulSoup(driver.page_source, "html.parser")
        
                price_elems = inner_soup.select("a.price.seller-element")
                all_prices = []
        
                for p in price_elems:
                    txt = p.get_text(strip=True)
                    num = extract_number(txt)
                    if num:
                        all_prices.append(num)
        
                lowest_price_num = min(all_prices) if all_prices else current_price_num
                lowest_price = f"{lowest_price_num:,} تومان" if lowest_price_num else "N/A"
                
                if lowest_price_num and current_price_num:
                    history = update_price_history(history, name, link, lowest_price_num, current_price_num)
                
                price_history = history.get(link, {}).get("prices", [])
        
                products.append({
                    "name": name,
                    "price": current_price_text,
                    "lowest_price": lowest_price,
                    "link": link,
                    "price_history": price_history
                })
            except Exception as e:
                print(f"  ⚠️ Error processing product: {e}")
                continue
    
except Exception as e:
    print(f"❌ Fatal error: {e}")
    print("🔄 Attempting to generate output from existing history...")

finally:
    driver.quit()
    print("✅ WebDriver closed")

save_history(history)
print(f"💾 Price history saved!")

if not products and history:
    print("📦 No new products scraped, generating pages from history...")
    for link, data in history.items():
        prices = data.get("prices", [])
        if prices:
            latest = prices[-1]
            products.append({
                "name": data["name"],
                "price": f"{latest['current_price']:,} تومان",
                "lowest_price": f"{latest['lowest_price']:,} تومان",
                "link": link,
                "price_history": prices
            })

# Generate HTML templates
template_html = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Torob Products - Price Tracker</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Vazir', 'Segoe UI', Tahoma, sans-serif; background: #fafafa; color: #222; }
.header { text-align: center; padding: 30px 20px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.header h1 { margin: 0 0 20px 0; color: #333; font-size: 28px; }
.stats { 
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
  color: white;
  padding: 15px; 
  margin: 0 auto; 
  border-radius: 10px; 
  max-width: 600px;
  font-size: 14px;
  text-align: center;
}
.container { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; padding: 20px; max-width: 1400px; margin: 0 auto; }
.card { background: white; border-radius: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); padding: 15px; transition: 0.2s; }
.card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.name { font-weight: bold; font-size: 16px; margin-bottom: 10px; line-height: 1.4; color: #333; }
.price { color: #009688; font-weight: bold; margin: 5px 0; }
.lowest { color: #e91e63; font-size: 14px; margin: 5px 0; }
.chart-container { margin-top: 15px; display: none; background: #f8f9fa; padding: 15px; border-radius: 8px; }
.chart-container.active { display: block; }
.toggle-chart { 
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
  color: white; 
  border: none; 
  padding: 10px 15px; 
  border-radius: 8px; 
  cursor: pointer; 
  margin-top: 10px; 
  font-size: 13px; 
  width: 100%;
  transition: 0.3s;
  font-weight: bold;
}
.toggle-chart:hover { transform: scale(1.02); box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3); }
.toggle-chart.active { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
a { text-decoration: none; color: inherit; }
.chart-title { text-align: center; font-size: 14px; color: #666; margin-bottom: 10px; font-weight: bold; }
.legend-custom { display: flex; justify-content: center; gap: 20px; margin-top: 10px; font-size: 12px; }
.legend-item { display: flex; align-items: center; gap: 5px; }
.legend-color { width: 20px; height: 3px; border-radius: 2px; }
</style>
</head>
<body>
<div class="header">
  <h1>🛍️ محصولات فروشگاه ترب</h1>
  <div class="stats">
    <strong>تعداد محصولات:</strong> {{ products|length }} | 
    <strong>آخرین بروزرسانی:</strong> {{ update_time }}
  </div>
</div>
<div class="container">
{% for p in products %}
<div class="card">
  <a href="{{ p.link }}" target="_blank">
    <div class="name">{{ p.name }}</div>
    <div class="price">💰 قیمت فعلی: {{ p.price }}</div>
    <div class="lowest">🏷️ کمترین قیمت: {{ p.lowest_price }}</div>
  </a>
  {% if p.price_history|length > 1 %}
  <button class="toggle-chart" onclick="toggleChart('chart-{{ loop.index }}', this)">📊 نمایش تاریخچه قیمت</button>
  <div id="chart-{{ loop.index }}" class="chart-container">
    <div class="chart-title">تاریخچه تغییرات قیمت</div>
    <canvas id="canvas-{{ loop.index }}"></canvas>
    <div class="legend-custom">
      <div class="legend-item"><div class="legend-color" style="background: #4CAF50;"></div><span>کمترین قیمت</span></div>
      <div class="legend-item"><div class="legend-color" style="background: #2196F3;"></div><span>میانگین قیمت</span></div>
    </div>
  </div>
  <script>
  (function() {
    var ctx = document.getElementById('canvas-{{ loop.index }}').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: {{ p.price_history | map(attribute='date') | list | tojson }},
        datasets: [{
          label: 'کمترین قیمت',
          data: {{ p.price_history | map(attribute='lowest_price') | list | tojson }},
          borderColor: '#4CAF50',
          backgroundColor: 'rgba(76, 175, 80, 0.1)',
          tension: 0.4,
          fill: true,
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#4CAF50'
        }, {
          label: 'میانگین قیمت',
          data: {{ p.price_history | map(attribute='current_price') | list | tojson }},
          borderColor: '#2196F3',
          backgroundColor: 'rgba(33, 150, 243, 0.1)',
          tension: 0.4,
          fill: true,
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#2196F3'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                return context.dataset.label + ': ' + context.parsed.y.toLocaleString('fa-IR') + ' تومان';
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: false,
            ticks: { callback: function(value) { return value.toLocaleString('fa-IR'); } },
            grid: { color: 'rgba(0, 0, 0, 0.05)' }
          },
          x: { grid: { display: false } }
        }
      }
    });
  })();
  </script>
  {% endif %}
</div>
{% endfor %}
</div>
<script>
function toggleChart(chartId, button) {
  var chart = document.getElementById(chartId);
  chart.classList.toggle('active');
  button.classList.toggle('active');
  button.textContent = chart.classList.contains('active') ? '📈 مخفی کردن نمودار' : '📊 نمایش تاریخچه قیمت';
}
</script>
</body>
</html>"""

template = Template(template_html)
output = template.render(products=products, update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

with open("index.html", "w", encoding="utf-8") as f:
    f.write(output)

# Generate price history dashboard
products_with_history = []
for link, data in history.items():
    if len(data.get("prices", [])) > 1:
        prices = data["prices"]
        first_price = prices[0]["lowest_price"]
        latest_price = prices[-1]["lowest_price"]
        price_change = ((latest_price - first_price) / first_price) * 100 if first_price > 0 else 0
        
        products_with_history.append({
            "name": data["name"],
            "link": link,
            "price_history": prices,
            "latest_lowest": prices[-1]["lowest_price"],
            "latest_current": prices[-1]["current_price"],
            "price_change": price_change
        })

history_template = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>تاریخچه قیمت‌ها - Torob Price History</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Vazir', 'Segoe UI', Tahoma, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #222; padding: 20px; min-height: 100vh; }
.header { text-align: center; padding: 30px 20px; background: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 15px; margin-bottom: 30px; }
.header h1 { margin: 0 0 20px 0; color: #333; font-size: 32px; }
.stats { background: rgba(255,255,255,0.2); color: white; padding: 15px; margin: 0 auto; border-radius: 10px; max-width: 800px; font-size: 16px; backdrop-filter: blur(10px); text-align: center; }
.container { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; max-width: 1400px; margin: 0 auto; }
.product-card { background: white; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 20px; transition: 0.3s; }
.product-card:hover { transform: translateY(-5px); box-shadow: 0 8px 16px rgba(0,0,0,0.2); }
.product-name { font-weight: bold; font-size: 16px; margin-bottom: 15px; color: #333; line-height: 1.5; }
.price-info { display: flex; justify-content: space-between; margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 8px; }
.price-box { text-align: center; flex: 1; }
.price-label { font-size: 11px; color: #666; margin-bottom: 5px; }
.price-value { font-size: 14px; font-weight: bold; }
.price-value.lowest { color: #4CAF50; }
.price-value.current { color: #2196F3; }
.price-value.change { color: #FF9800; }
.price-value.change.up { color: #f44336; }
.price-value.change.down { color: #4CAF50; }
.chart-wrapper { margin-top: 15px; background: #f8f9fa; padding: 15px; border-radius: 10px; }
.view-product { display: inline-block; margin-top: 10px; padding: 8px 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 8px; font-size: 13px; transition: 0.3s; }
.view-product:hover { transform: scale(1.05); box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3); }
.no-history { text-align: center; padding: 50px; background: white; border-radius: 15px; color: #999; font-size: 18px; }
.legend-custom { display: flex; justify-content: center; gap: 20px; margin-top: 10px; font-size: 12px; }
.legend-item { display: flex; align-items: center; gap: 5px; }
.legend-color { width: 25px; height: 3px; border-radius: 2px; }
</style>
</head>
<body>
<div class="header">
  <h1>📊 داشبورد تاریخچه قیمت‌ها</h1>
  <div class="stats">
    <strong>تعداد محصولات:</strong> {{ products_with_history|length }} | 
    <strong>آخرین بروزرسانی:</strong> {{ update_time }}
  </div>
</div>
<div class="container">
{% for p in products_with_history %}
<div class="product-card">
  <div class="product-name">{{ p.name }}</div>
  <div class="price-info">
    <div class="price-box">
      <div class="price-label">کمترین قیمت</div>
      <div class="price-value lowest">{{ "{:,}".format(p.latest_lowest) }} تومان</div>
    </div>
    <div class="price-box">
      <div class="price-label">قیمت میانگین</div>
      <div class="price-value current">{{ "{:,}".format(p.latest_current) }} تومان</div>
    </div>
    <div class="price-box">
      <div class="price-label">تغییر قیمت</div>
      <div class="price-value change {{ 'up' if p.price_change > 0 else 'down' if p.price_change < 0 else '' }}">
        {{ "+" if p.price_change > 0 else "" }}{{ "{:.1f}".format(p.price_change) }}%
      </div>
    </div>
  </div>
  <div class="chart-wrapper">
    <canvas id="chart-{{ loop.index }}"></canvas>
    <div class="legend-custom">
      <div class="legend-item"><div class="legend-color" style="background: #4CAF50;"></div><span>کمترین قیمت</span></div>
      <div class="legend-item"><div class="legend-color" style="background: #2196F3;"></div><span>میانگین قیمت</span></div>
    </div>
  </div>
  <a href="{{ p.link }}" target="_blank" class="view-product">🔗 مشاهده در ترب</a>
  <script>
  (function() {
    var ctx = document.getElementById('chart-{{ loop.index }}').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: {{ p.price_history | map(attribute='date') | list | tojson }},
        datasets: [{
          label: 'کمترین قیمت',
          data: {{ p.price_history | map(attribute='lowest_price') | list | tojson }},
          borderColor: '#4CAF50',
          backgroundColor: 'rgba(76, 175, 80, 0.1)',
          tension: 0.4,
          fill: true,
          borderWidth: 2.5,
          pointRadius: 4,
          pointBackgroundColor: '#4CAF50',
          pointBorderColor: '#fff',
          pointBorderWidth: 2
        }, {
          label: 'میانگین قیمت',
          data: {{ p.price_history | map(attribute='current_price') | list | tojson }},
          borderColor: '#2196F3',
          backgroundColor: 'rgba(33, 150, 243, 0.1)',
          tension: 0.4,
          fill: true,
          borderWidth: 2.5,
          pointRadius: 4,
          pointBackgroundColor: '#2196F3',
          pointBorderColor: '#fff',
          pointBorderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(0,0,0,0.8)',
            padding: 12,
            callbacks: {
              label: function(context) {
                return context.dataset.label + ': ' + context.parsed.y.toLocaleString('fa-IR') + ' تومان';
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: false,
            ticks: { callback: function(value) { return value.toLocaleString('fa-IR'); } },
            grid: { color: 'rgba(0, 0, 0, 0.05)' }
          },
          x: { grid: { display: false } }
        }
      }
    });
  })();
  </script>
</div>
{% endfor %}
{% if products_with_history|length == 0 %}
<div class="no-history">
  <h2>😔 هنوز تاریخچه قیمتی ثبت نشده است</h2>
  <p>اسکریپت را چند بار در روزهای مختلف اجرا کنید</p>
</div>
{% endif %}
</div>
</body>
</html>"""

history_template_obj = Template(history_template)
history_output = history_template_obj.render(
    products_with_history=products_with_history,
    update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)

with open("price_history.html", "w", encoding="utf-8") as f:
    f.write(history_output)

print(f"✅ Done! Saved {len(products)} products to index.html")
print(f"📊 Price history dashboard saved to price_history.html")
print(f"📈 Tracking {len(products_with_history)} products with price history")

if sys.platform.startswith('win'):
    os.startfile("index.html")