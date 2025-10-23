from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time, re, os, json
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
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
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

# --- Selenium setup ---
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

driver = webdriver.Chrome(options=options)

url = "https://torob.com/shop/58933/%D8%AA%D8%AC%D9%87%DB%8C%D8%B2%D8%A7%D8%AA-%D8%AA%D9%88%D8%A7%D9%86%D8%A8%D8%AE%D8%B4%DB%8C-%DA%A9%D9%88%D8%B4%D8%A7/%D9%85%D8%AD%D8%B5%D9%88%D9%84%D8%A7%D8%AA/"
print("🌐 Loading page...")
driver.get(url)

# Wait for initial content to load
time.sleep(5)

print("📜 Scrolling to load all products...")
smooth_scroll(driver, pause_time=2)

soup = BeautifulSoup(driver.page_source, "html.parser")
product_links = soup.select("a[href*='/p/']")

# Remove duplicates
unique_links = {}
for a in product_links:
    link = "https://torob.com" + a.get("href", "")
    if link not in unique_links:
        unique_links[link] = a

print(f"✅ Found {len(unique_links)} unique products")

# Load existing price history
history = load_history()
products = []

for idx, (link, a) in enumerate(unique_links.items(), 1):
    print(f"Processing {idx}/{len(unique_links)}: {link}")
    
    name_tag = a.select_one("h2[class*='ProductCard_desktop_product-name']")
    name = name_tag.get_text(strip=True) if name_tag else "N/A"
    price_tag = a.select_one("div[class*='ProductCard_desktop_product-price-text']")
    current_price_text = price_tag.get_text(strip=True) if price_tag else "N/A"
    current_price_num = extract_number(current_price_text) if current_price_text != "N/A" else None

    # Fetch lowest price from product page
    try:
        driver.get(link)
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
        
        # Update price history with both prices
        if lowest_price_num and current_price_num:
            history = update_price_history(history, name, link, lowest_price_num, current_price_num)
        
        # Get price history for this product
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

driver.quit()

# Save updated history
save_history(history)
print(f"💾 Price history saved!")

# --- Generate HTML with price charts ---
template_html = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Torob Products - Price Tracker</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
<style>
* { box-sizing: border-box; }
body { font-family: 'Vazir', 'Segoe UI', Tahoma, sans-serif; background: #fafafa; color: #222; margin: 0; padding: 0; }
.container { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; padding: 20px; }
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
.header { text-align: center; padding: 30px 20px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.header h1 { margin: 0; color: #333; font-size: 28px; }
.stats { 
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
  color: white;
  padding: 15px; 
  margin: 20px auto; 
  border-radius: 10px; 
  max-width: 600px;
  font-size: 14px;
}
.chart-title { 
  text-align: center; 
  font-size: 14px; 
  color: #666; 
  margin-bottom: 10px;
  font-weight: bold;
}
.legend-custom {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 10px;
  font-size: 12px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.legend-color {
  width: 20px;
  height: 3px;
  border-radius: 2px;
}
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
  <button class="toggle-chart" onclick="toggleChart('chart-{{ loop.index }}', this)">
    📊 نمایش تاریخچه قیمت
  </button>
  <div id="chart-{{ loop.index }}" class="chart-container">
    <div class="chart-title">لیست تغییرات قیمت</div>
    <canvas id="canvas-{{ loop.index }}"></canvas>
    <div class="legend-custom">
      <div class="legend-item">
        <div class="legend-color" style="background: #4CAF50;"></div>
        <span>کمترین قیمت</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #2196F3;"></div>
        <span>میانگین قیمت</span>
      </div>
    </div>
  </div>
  <script>
  (function() {
    var dates = {{ p.price_history | map(attribute='date') | list | tojson }};
    var lowestPrices = {{ p.price_history | map(attribute='lowest_price') | list | tojson }};
    var currentPrices = {{ p.price_history | map(attribute='current_price') | list | tojson }};
    
    var ctx = document.getElementById('canvas-{{ loop.index }}').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: [
          {
            label: 'کمترین قیمت',
            data: lowestPrices,
            borderColor: '#4CAF50',
            backgroundColor: 'rgba(76, 175, 80, 0.1)',
            tension: 0.4,
            fill: true,
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: '#4CAF50'
          },
          {
            label: 'میانگین قیمت',
            data: currentPrices,
            borderColor: '#2196F3',
            backgroundColor: 'rgba(33, 150, 243, 0.1)',
            tension: 0.4,
            fill: true,
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: '#2196F3'
          }
        ]
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
            ticks: {
              callback: function(value) {
                return value.toLocaleString('fa-IR');
              }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.05)'
            }
          },
          x: {
            grid: {
              display: false
            }
          }
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
  
  if (chart.classList.contains('active')) {
    button.textContent = '📈 مخفی کردن نمودار';
  } else {
    button.textContent = '📊 نمایش تاریخچه قیمت';
  }
}
</script>
</body>
</html>
"""

template = Template(template_html)
output = template.render(
    products=products,
    update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(output)

# --- Generate Price History Dashboard ---
history_template = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تاریخچه قیمت‌ها - Torob Price History</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
<style>
* { box-sizing: border-box; }
body { 
  font-family: 'Vazir', 'Segoe UI', Tahoma, sans-serif; 
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #222; 
  margin: 0; 
  padding: 20px;
  min-height: 100vh;
}
.header { 
  text-align: center; 
  padding: 30px 20px; 
  background: white; 
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  border-radius: 15px;
  margin-bottom: 30px;
}
.header h1 { margin: 0; color: #333; font-size: 32px; }
.stats { 
  background: rgba(255,255,255,0.2);
  color: white;
  padding: 15px; 
  margin: 20px auto; 
  border-radius: 10px; 
  max-width: 800px;
  font-size: 16px;
  backdrop-filter: blur(10px);
  text-align: center;
}
.filters {
  background: white;
  padding: 20px;
  border-radius: 15px;
  margin-bottom: 20px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.filter-row {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
}
.filter-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.filter-item label {
  font-size: 13px;
  font-weight: bold;
  color: #666;
}
.filter-item input, .filter-item select {
  padding: 10px 15px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: 0.3s;
}
.filter-item input:focus, .filter-item select:focus {
  border-color: #667eea;
}
.container { 
  display: grid; 
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); 
  gap: 20px; 
}
.product-card { 
  background: white; 
  border-radius: 15px; 
  box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
  padding: 20px; 
  transition: 0.3s;
}
.product-card:hover { 
  transform: translateY(-5px); 
  box-shadow: 0 8px 16px rgba(0,0,0,0.2); 
}
.product-name { 
  font-weight: bold; 
  font-size: 16px; 
  margin-bottom: 15px; 
  color: #333;
  line-height: 1.5;
}
.price-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 8px;
}
.price-box {
  text-align: center;
}
.price-label {
  font-size: 11px;
  color: #666;
  margin-bottom: 5px;
}
.price-value {
  font-size: 14px;
  font-weight: bold;
}
.price-value.lowest { color: #4CAF50; }
.price-value.current { color: #2196F3; }
.price-value.change { color: #FF9800; }
.price-value.change.up { color: #f44336; }
.price-value.change.down { color: #4CAF50; }
.chart-wrapper {
  margin-top: 15px;
  background: #f8f9fa;
  padding: 15px;
  border-radius: 10px;
}
.view-product {
  display: inline-block;
  margin-top: 10px;
  padding: 8px 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  text-decoration: none;
  border-radius: 8px;
  font-size: 13px;
  transition: 0.3s;
}
.view-product:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
}
.no-history {
  text-align: center;
  padding: 50px;
  background: white;
  border-radius: 15px;
  color: #999;
  font-size: 18px;
}
.legend-custom {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 10px;
  font-size: 12px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.legend-color {
  width: 25px;
  height: 3px;
  border-radius: 2px;
}
</style>
</head>
<body>
<div class="header">
  <h1>📊 داشبورد تاریخچه قیمت‌ها</h1>
</div>

<div class="stats">
  <strong>تعداد محصولات ردیابی شده:</strong> {{ products_with_history|length }} | 
  <strong>آخرین بروزرسانی:</strong> {{ update_time }}
</div>

<div class="filters">
  <div class="filter-row">
    <div class="filter-item">
      <label>🔍 جستجو:</label>
      <input type="text" id="searchInput" placeholder="نام محصول را جستجو کنید..." onkeyup="filterProducts()">
    </div>
    <div class="filter-item">
      <label>📈 مرتب‌سازی:</label>
      <select id="sortSelect" onchange="sortProducts()">
        <option value="name">نام محصول</option>
        <option value="priceAsc">قیمت (کم به زیاد)</option>
        <option value="priceDesc">قیمت (زیاد به کم)</option>
        <option value="changeDesc">بیشترین تغییر قیمت</option>
      </select>
    </div>
  </div>
</div>

<div class="container" id="productsContainer">
{% for p in products_with_history %}
<div class="product-card" data-name="{{ p.name|lower }}" data-price="{{ p.latest_lowest }}" data-change="{{ p.price_change }}">
  <div class="product-name">{{ p.name }}</div>
  
  <div class="price-info">
    <div class="price-box">
      <div class="price-label">کمترین قیمت فعلی</div>
      <div class="price-value lowest">{{ "{:,}".format(p.latest_lowest) }} تومان</div>
    </div>
    <div class="price-box">
      <div class="price-label">قیمت میانگین فعلی</div>
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
      <div class="legend-item">
        <div class="legend-color" style="background: #4CAF50;"></div>
        <span>کمترین قیمت</span>
      </div>
      <div class="legend-item">
        <div class="legend-color" style="background: #2196F3;"></div>
        <span>میانگین قیمت</span>
      </div>
    </div>
  </div>
  
  <a href="{{ p.link }}" target="_blank" class="view-product">🔗 مشاهده محصول در ترب</a>
  
  <script>
  (function() {
    var dates = {{ p.price_history | map(attribute='date') | list | tojson }};
    var lowestPrices = {{ p.price_history | map(attribute='lowest_price') | list | tojson }};
    var currentPrices = {{ p.price_history | map(attribute='current_price') | list | tojson }};
    
    var ctx = document.getElementById('chart-{{ loop.index }}').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: dates,
        datasets: [
          {
            label: 'کمترین قیمت',
            data: lowestPrices,
            borderColor: '#4CAF50',
            backgroundColor: 'rgba(76, 175, 80, 0.1)',
            tension: 0.4,
            fill: true,
            borderWidth: 2.5,
            pointRadius: 4,
            pointBackgroundColor: '#4CAF50',
            pointBorderColor: '#fff',
            pointBorderWidth: 2
          },
          {
            label: 'میانگین قیمت',
            data: currentPrices,
            borderColor: '#2196F3',
            backgroundColor: 'rgba(33, 150, 243, 0.1)',
            tension: 0.4,
            fill: true,
            borderWidth: 2.5,
            pointRadius: 4,
            pointBackgroundColor: '#2196F3',
            pointBorderColor: '#fff',
            pointBorderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(0,0,0,0.8)',
            padding: 12,
            titleFont: { size: 14 },
            bodyFont: { size: 13 },
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
            ticks: {
              callback: function(value) {
                return value.toLocaleString('fa-IR');
              }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.05)'
            }
          },
          x: {
            grid: {
              display: false
            }
          }
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
  <p>لطفاً اسکریپت را چند بار در روزهای مختلف اجرا کنید تا تاریخچه قیمت ساخته شود.</p>
</div>
{% endif %}
</div>

<script>
function filterProducts() {
  const searchValue = document.getElementById('searchInput').value.toLowerCase();
  const cards = document.querySelectorAll('.product-card');
  
  cards.forEach(card => {
    const name = card.getAttribute('data-name');
    if (name.includes(searchValue)) {
      card.style.display = 'block';
    } else {
      card.style.display = 'none';
    }
  });
}

function sortProducts() {
  const sortValue = document.getElementById('sortSelect').value;
  const container = document.getElementById('productsContainer');
  const cards = Array.from(container.querySelectorAll('.product-card'));
  
  cards.sort((a, b) => {
    switch(sortValue) {
      case 'name':
        return a.getAttribute('data-name').localeCompare(b.getAttribute('data-name'));
      case 'priceAsc':
        return parseFloat(a.getAttribute('data-price')) - parseFloat(b.getAttribute('data-price'));
      case 'priceDesc':
        return parseFloat(b.getAttribute('data-price')) - parseFloat(a.getAttribute('data-price'));
      case 'changeDesc':
        return Math.abs(parseFloat(b.getAttribute('data-change'))) - Math.abs(parseFloat(a.getAttribute('data-change')));
      default:
        return 0;
    }
  });
  
  cards.forEach(card => container.appendChild(card));
}
</script>
</body>
</html>
"""

# Prepare data for history dashboard
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
os.startfile("index.html")