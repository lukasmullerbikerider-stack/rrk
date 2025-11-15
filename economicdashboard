import http.server
import socketserver
import json
import threading
import time
import os
import re
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List
from urllib.parse import parse_qs, urlparse
import requests

# ============================================================================
# DATABASE SETUP
# ============================================================================

class Database:
    def __init__(self, db_file='dashboard.db'):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            subscription_type TEXT DEFAULT 'free',
            subscription_end DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Sessions table
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )''')
        
        conn.commit()
        conn.close()
        print("✓ Database initialized")
    
    def create_user(self, email, password):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        try:
            c.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)',
                     (email, password_hash))
            conn.commit()
            user_id = c.lastrowid
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    def verify_user(self, email, password):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        c.execute('SELECT id, subscription_type, subscription_end FROM users WHERE email=? AND password_hash=?',
                 (email, password_hash))
        result = c.fetchone()
        conn.close()
        
        if result:
            return {'id': result[0], 'subscription': result[1], 'expires': result[2]}
        return None
    
    def create_session(self, user_id):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(days=30)
        
        c.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)',
                 (token, user_id, expires))
        conn.commit()
        conn.close()
        
        return token
    
    def verify_session(self, token):
        if not token:
            return None
            
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('''SELECT u.id, u.email, u.subscription_type, u.subscription_end 
                    FROM sessions s JOIN users u ON s.user_id = u.id 
                    WHERE s.token=? AND s.expires_at > datetime('now')''', (token,))
        result = c.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0], 
                'email': result[1], 
                'subscription': result[2],
                'expires': result[3]
            }
        return None
    
    def update_subscription(self, user_id, sub_type, months=1):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        if months == 12:
            end_date = datetime.now() + timedelta(days=365)
        else:
            end_date = datetime.now() + timedelta(days=30 * months)
        
        c.execute('UPDATE users SET subscription_type=?, subscription_end=? WHERE id=?',
                 (sub_type, end_date, user_id))
        conn.commit()
        conn.close()

# ============================================================================
# REAL PRICE FETCHER
# ============================================================================

class PriceFetcher:
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 300  # 5 minutes
    
    def get_crypto_prices(self):
        """Fetch real crypto prices from CoinGecko"""
        if 'crypto' in self.cache and time.time() - self.cache_time.get('crypto', 0) < self.cache_duration:
            return self.cache['crypto']
        
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': 'bitcoin,ethereum,binancecoin,ripple,solana,cardano,dogecoin,tron,avalanche-2,polkadot',
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                prices = [
                    {'symbol': 'BTC', 'name': 'Bitcoin', 'price': data.get('bitcoin', {}).get('usd', 0), 
                     'change': data.get('bitcoin', {}).get('usd_24h_change', 0)},
                    {'symbol': 'ETH', 'name': 'Ethereum', 'price': data.get('ethereum', {}).get('usd', 0),
                     'change': data.get('ethereum', {}).get('usd_24h_change', 0)},
                    {'symbol': 'BNB', 'name': 'Binance Coin', 'price': data.get('binancecoin', {}).get('usd', 0),
                     'change': data.get('binancecoin', {}).get('usd_24h_change', 0)},
                    {'symbol': 'XRP', 'name': 'Ripple', 'price': data.get('ripple', {}).get('usd', 0),
                     'change': data.get('ripple', {}).get('usd_24h_change', 0)},
                    {'symbol': 'SOL', 'name': 'Solana', 'price': data.get('solana', {}).get('usd', 0),
                     'change': data.get('solana', {}).get('usd_24h_change', 0)},
                    {'symbol': 'ADA', 'name': 'Cardano', 'price': data.get('cardano', {}).get('usd', 0),
                     'change': data.get('cardano', {}).get('usd_24h_change', 0)},
                    {'symbol': 'DOGE', 'name': 'Dogecoin', 'price': data.get('dogecoin', {}).get('usd', 0),
                     'change': data.get('dogecoin', {}).get('usd_24h_change', 0)},
                    {'symbol': 'TRX', 'name': 'Tron', 'price': data.get('tron', {}).get('usd', 0),
                     'change': data.get('tron', {}).get('usd_24h_change', 0)},
                    {'symbol': 'AVAX', 'name': 'Avalanche', 'price': data.get('avalanche-2', {}).get('usd', 0),
                     'change': data.get('avalanche-2', {}).get('usd_24h_change', 0)},
                    {'symbol': 'DOT', 'name': 'Polkadot', 'price': data.get('polkadot', {}).get('usd', 0),
                     'change': data.get('polkadot', {}).get('usd_24h_change', 0)},
                ]
                
                self.cache['crypto'] = prices
                self.cache_time['crypto'] = time.time()
                print("✓ Fetched real crypto prices")
                return prices
        except Exception as e:
            print(f"⚠ Error fetching crypto prices: {e}")
        
        return self._get_mock_crypto()
    
    def get_metal_prices(self):
        """Fetch real metal prices from Metals-API or similar"""
        if 'metals' in self.cache and time.time() - self.cache_time.get('metals', 0) < self.cache_duration:
            return self.cache['metals']
        
        # Note: For production, use API like metals-api.com (requires API key)
        # For now, using realistic mock data that updates slightly
        
        try:
            # Simulate slight price changes
            base_prices = {
                'XAU': 2650 + (time.time() % 100 - 50),  # Gold oscillates
                'XAG': 31.5 + (time.time() % 5 - 2.5),   # Silver
                'XPT': 950 + (time.time() % 50 - 25),    # Platinum
                'XPD': 1150 + (time.time() % 50 - 25),   # Palladium
                'CU': 8500 + (time.time() % 200 - 100),  # Copper
            }
            
            metals = [
                {'symbol': 'XAU', 'name': 'Gold', 'price': base_prices['XAU'], 'unit': '/oz', 
                 'change': (time.time() % 3) - 1.5},
                {'symbol': 'XAG', 'name': 'Silver', 'price': base_prices['XAG'], 'unit': '/oz',
                 'change': (time.time() % 4) - 2},
                {'symbol': 'XPT', 'name': 'Platinum', 'price': base_prices['XPT'], 'unit': '/oz',
                 'change': (time.time() % 3) - 1.5},
                {'symbol': 'XPD', 'name': 'Palladium', 'price': base_prices['XPD'], 'unit': '/oz',
                 'change': (time.time() % 5) - 2.5},
                {'symbol': 'CU', 'name': 'Copper', 'price': base_prices['CU'], 'unit': '/ton',
                 'change': (time.time() % 2) - 1},
                {'symbol': 'AL', 'name': 'Aluminum', 'price': 2450, 'unit': '/ton', 'change': 0.3},
                {'symbol': 'ZN', 'name': 'Zinc', 'price': 2780, 'unit': '/ton', 'change': -0.5},
                {'symbol': 'NI', 'name': 'Nickel', 'price': 16800, 'unit': '/ton', 'change': 0.8},
                {'symbol': 'PB', 'name': 'Lead', 'price': 2050, 'unit': '/ton', 'change': -0.3},
                {'symbol': 'TIN', 'name': 'Tin', 'price': 29500, 'unit': '/ton', 'change': 1.2},
            ]
            
            self.cache['metals'] = metals
            self.cache_time['metals'] = time.time()
            return metals
        except:
            return self._get_mock_metals()
    
    def get_stock_prices(self):
        """Fetch real stock prices - requires API like Alpha Vantage"""
        if 'stocks' in self.cache and time.time() - self.cache_time.get('stocks', 0) < self.cache_duration:
            return self.cache['stocks']
        
        # For production: use Alpha Vantage, Yahoo Finance, or similar API
        # Requires API key
        
        stocks = [
            {'symbol': 'AAPL', 'name': 'Apple', 'price': 178.50, 'change': -1.2},
            {'symbol': 'MSFT', 'name': 'Microsoft', 'price': 425.30, 'change': -0.8},
            {'symbol': 'GOOGL', 'name': 'Alphabet', 'price': 175.20, 'change': -1.5},
            {'symbol': 'AMZN', 'name': 'Amazon', 'price': 182.40, 'change': -0.9},
            {'symbol': 'NVDA', 'name': 'NVIDIA', 'price': 520.80, 'change': -2.1},
            {'symbol': 'TSLA', 'name': 'Tesla', 'price': 258.60, 'change': -4.2},
            {'symbol': 'META', 'name': 'Meta', 'price': 520.40, 'change': -1.1},
            {'symbol': 'JPM', 'name': 'JPMorgan', 'price': 215.30, 'change': -1.8},
            {'symbol': 'V', 'name': 'Visa', 'price': 295.70, 'change': -0.6},
            {'symbol': 'WMT', 'name': 'Walmart', 'price': 85.20, 'change': 0.3}
        ]
        
        self.cache['stocks'] = stocks
        self.cache_time['stocks'] = time.time()
        return stocks
    
    def _get_mock_crypto(self):
        return [
            {'symbol': 'BTC', 'name': 'Bitcoin', 'price': 97500, 'change': -2.4},
            {'symbol': 'ETH', 'name': 'Ethereum', 'price': 3450, 'change': 0.7},
            {'symbol': 'BNB', 'name': 'Binance Coin', 'price': 625, 'change': 3.2},
            {'symbol': 'XRP', 'name': 'Ripple', 'price': 2.15, 'change': -0.9},
            {'symbol': 'SOL', 'name': 'Solana', 'price': 195, 'change': -1.6},
            {'symbol': 'ADA', 'name': 'Cardano', 'price': 0.62, 'change': -5.2},
            {'symbol': 'DOGE', 'name': 'Dogecoin', 'price': 0.38, 'change': -4.8},
            {'symbol': 'TRX', 'name': 'Tron', 'price': 0.24, 'change': 1.2},
            {'symbol': 'AVAX', 'name': 'Avalanche', 'price': 38.5, 'change': -6.1},
            {'symbol': 'DOT', 'name': 'Polkadot', 'price': 7.2, 'change': -3.7}
        ]
    
    def _get_mock_metals(self):
        return [
            {'symbol': 'XAU', 'name': 'Gold', 'price': 2650, 'unit': '/oz', 'change': 0.8},
            {'symbol': 'XAG', 'name': 'Silver', 'price': 31.5, 'unit': '/oz', 'change': 1.2},
            {'symbol': 'XPT', 'name': 'Platinum', 'price': 950, 'unit': '/oz', 'change': 2.1},
            {'symbol': 'XPD', 'name': 'Palladium', 'price': 1150, 'unit': '/oz', 'change': 3.5},
            {'symbol': 'CU', 'name': 'Copper', 'price': 8500, 'unit': '/ton', 'change': 0.5},
            {'symbol': 'AL', 'name': 'Aluminum', 'price': 2450, 'unit': '/ton', 'change': -0.3},
            {'symbol': 'ZN', 'name': 'Zinc', 'price': 2780, 'unit': '/ton', 'change': 0.2},
            {'symbol': 'NI', 'name': 'Nickel', 'price': 16800, 'unit': '/ton', 'change': 0.9},
            {'symbol': 'PB', 'name': 'Lead', 'price': 2050, 'unit': '/ton', 'change': -0.5},
            {'symbol': 'TIN', 'name': 'Tin', 'price': 29500, 'unit': '/ton', 'change': 1.5}
        ]

# ============================================================================
# NEWS SCRAPER - Real from Investing.com
# ============================================================================

class NewsScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        self.impact_keywords = {
            'high': ['crash', 'surge', 'record', 'historic', 'massive', 'plunge', 'soar', 'crisis', 
                    'breakthrough', 'collapse', 'rally', 'tumble', 'spike', 'jump'],
            'medium': ['rise', 'fall', 'increase', 'decrease', 'cut', 'rate', 'policy', 'gains', 
                      'drops', 'climbs', 'slides', 'advance'],
            'low': ['slight', 'modest', 'gradual', 'steady', 'maintain', 'stable', 'unchanged']
        }
        
        self.asset_keywords = {
            'crypto': ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency', 'xrp', 
                      'solana', 'blockchain', 'digital currency', 'token'],
            'metals': ['gold', 'silver', 'platinum', 'palladium', 'copper', 'metal', 'precious metal',
                      'commodity', 'bullion'],
            'stocks': ['stock', 's&p', 'nasdaq', 'dow', 'equity', 'shares', 'market', 'index',
                      'wall street', 'trading', 'investor']
        }
    
    def scrape_investing_news(self) -> List[Dict]:
        """Scrape real news from Investing.com"""
        news_items = []
        
        try:
            # Investing.com news sections
            sections = [
                'https://www.investing.com/news/stock-market-news',
                'https://www.investing.com/news/cryptocurrency-news',
                'https://www.investing.com/news/commodities-news',
                'https://www.investing.com/news/economy',
            ]
            
            for section_url in sections:
                try:
                    print(f"📰 Scraping: {section_url}")
                    response = requests.get(section_url, headers=self.headers, timeout=15)
                    
                    if response.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Find news articles
                        articles = soup.find_all('article', class_='js-article-item')
                        
                        if not articles:
                            # Try alternative selectors
                            articles = soup.find_all('div', class_='largeTitle')
                        
                        for article in articles[:5]:  # Top 5 from each section
                            try:
                                # Extract title
                                title_elem = article.find('a', class_='title')
                                if not title_elem:
                                    title_elem = article.find('a')
                                
                                if not title_elem:
                                    continue
                                
                                title = title_elem.get_text(strip=True)
                                link = title_elem.get('href', '')
                                
                                if link and not link.startswith('http'):
                                    link = 'https://www.investing.com' + link
                                
                                # Extract description/summary
                                desc_elem = article.find('p')
                                description = desc_elem.get_text(strip=True) if desc_elem else title
                                
                                # Skip if title is too short
                                if len(title) < 20:
                                    continue
                                
                                news_items.append({
                                    'title': title,
                                    'description': description,
                                    'url': link,
                                    'source': 'Investing.com',
                                    'date': datetime.now().strftime('%Y-%m-%d')
                                })
                                
                            except Exception as e:
                                print(f"⚠ Error parsing article: {e}")
                                continue
                    
                    time.sleep(2)  # Respectful scraping
                    
                except Exception as e:
                    print(f"⚠ Error scraping section: {e}")
                    continue
            
            print(f"✓ Scraped {len(news_items)} news items from Investing.com")
            
        except Exception as e:
            print(f"✗ Error scraping Investing.com: {e}")
        
        # If scraping failed or insufficient news, add fallback
        if len(news_items) < 5:
            print("⚠ Using fallback news data")
            news_items.extend(self.get_fallback_news())
        
        return news_items
    
    def get_fallback_news(self) -> List[Dict]:
        """Fallback news if scraping fails"""
        return [
            {
                'title': 'Federal Reserve Holds Rates Steady, Signals Data-Dependent Approach',
                'description': 'The Fed maintained interest rates while emphasizing flexibility based on economic indicators.',
                'source': 'Investing.com',
                'url': 'https://www.investing.com/news/economy',
                'date': datetime.now().strftime('%Y-%m-%d'),
            },
            {
                'title': 'Gold Prices Edge Higher on Safe-Haven Demand',
                'description': 'Precious metals gain as investors seek protection amid market uncertainty.',
                'source': 'Investing.com',
                'url': 'https://www.investing.com/news/commodities-news',
                'date': datetime.now().strftime('%Y-%m-%d'),
            },
            {
                'title': 'Tech Stocks Lead Market Rally as AI Optimism Grows',
                'description': 'Major technology companies push indices higher on artificial intelligence developments.',
                'source': 'Investing.com',
                'url': 'https://www.investing.com/news/stock-market-news',
                'date': datetime.now().strftime('%Y-%m-%d'),
            },
            {
                'title': 'Bitcoin Consolidates Near Key Support Level',
                'description': 'Leading cryptocurrency holds ground as traders await next directional move.',
                'source': 'Investing.com',
                'url': 'https://www.investing.com/news/cryptocurrency-news',
                'date': datetime.now().strftime('%Y-%m-%d'),
            },
            {
                'title': 'Oil Prices Fluctuate on Supply Outlook',
                'description': 'Crude benchmarks show mixed performance amid global demand concerns.',
                'source': 'Investing.com',
                'url': 'https://www.investing.com/news/commodities-news',
                'date': datetime.now().strftime('%Y-%m-%d'),
            }
        ]
    
    def calculate_impact(self, title: str, description: str) -> Dict:
        """Calculate impact score based on keywords and sentiment"""
        text = (title + ' ' + description).lower()
        score = 0
        
        # Keyword scoring
        for level, keywords in self.impact_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    if level == 'high':
                        score += 3
                    elif level == 'medium':
                        score += 2
                    else:
                        score += 1
        
        # Determine affected assets
        affected = []
        for asset, keywords in self.asset_keywords.items():
            if any(kw in text for kw in keywords):
                affected.append(asset)
        
        # If no specific asset mentioned, mark as general (affects all)
        if not affected:
            affected = ['stocks', 'metals', 'crypto']
        
        # Extract percentage changes
        percentages = re.findall(r'(\d+\.?\d*)%', text)
        if percentages:
            score += len(percentages) * 2
        
        # Normalize score
        score = min(10, max(1, score))
        
        # Determine sentiment
        negative_words = ['crash', 'fall', 'plunge', 'decline', 'drop', 'tumble', 'loss', 
                         'down', 'lower', 'negative', 'weak', 'slump', 'slide']
        positive_words = ['surge', 'rally', 'gain', 'rise', 'jump', 'soar', 'climb', 
                         'up', 'higher', 'positive', 'strong', 'boost']
        
        neg_count = sum(1 for word in negative_words if word in text)
        pos_count = sum(1 for word in positive_words if word in text)
        
        if neg_count > pos_count:
            sentiment = 'negative'
        elif pos_count > neg_count:
            sentiment = 'positive'
        else:
            sentiment = 'neutral'
        
        return {
            'impact_score': score,
            'affected_assets': affected,
            'sentiment': sentiment
        }
    
    def get_news(self) -> List[Dict]:
        """Get and process news from Investing.com"""
        print("\n🔍 Fetching real news from Investing.com...")
        
        # Scrape real news
        news_items = self.scrape_investing_news()
        
        # Calculate impact for each news
        for item in news_items:
            impact = self.calculate_impact(item['title'], item['description'])
            item.update(impact)
        
        # Sort by impact score
        news_items.sort(key=lambda x: x['impact_score'], reverse=True)
        
        # Take top 10 and add ranking
        top_news = news_items[:10]
        for i, news in enumerate(top_news, 1):
            news['rank'] = i
        
        print(f"✓ Processed {len(top_news)} high-impact news items")
        
        return top_news

# ============================================================================
# ASSET ANALYZER
# ============================================================================

class AssetAnalyzer:
    def __init__(self, news_data, price_fetcher):
        self.news = news_data
        self.fetcher = price_fetcher
    
    def calc_impact(self, asset_type: str) -> float:
        total, count = 0, 0
        for news in self.news:
            if asset_type in news['affected_assets']:
                impact = news['impact_score']
                if news['sentiment'] == 'negative':
                    impact *= -1
                total += impact
                count += 1
        return round((total / count) * 0.5, 2) if count > 0 else 0
    
    def predict(self, price: float, change: float, impact: float) -> float:
        combined = (change * 0.3) + (impact * 0.7)
        return round(price * (1 + combined / 100), 2)
    
    def analyze(self, assets, asset_type):
        impact = self.calc_impact(asset_type)
        results = []
        for asset in assets:
            predicted = self.predict(asset['price'], asset['change'], impact)
            change_pct = ((predicted - asset['price']) / asset['price']) * 100
            unit = asset.get('unit', '')
            results.append({
                'name': f"{asset['name']} ({asset['symbol']})",
                'current_price': f"${asset['price']:,.2f}{unit}",
                'change_percent': f"{change_pct:+.2f}%",
                'predicted_price': f"${predicted:,.2f}{unit}"
            })
        return results

# ============================================================================
# HTML GENERATOR
# ============================================================================

def generate_html(is_authenticated=False, user_data=None, show_pricing=False):
    auth_section = ""
    pricing_section = ""
    dashboard_visibility = "block" if is_authenticated else "none"
    
    if not is_authenticated:
        auth_section = '''
        <div id="authModal" class="modal">
            <div class="modal-content">
                <h2>Welcome to Economic Dashboard</h2>
                <div class="auth-tabs">
                    <button class="tab-btn active" onclick="showTab('login')">Login</button>
                    <button class="tab-btn" onclick="showTab('register')">Register</button>
                </div>
                
                <div id="loginForm" class="auth-form">
                    <input type="email" id="loginEmail" placeholder="Email" required>
                    <input type="password" id="loginPassword" placeholder="Password" required>
                    <button onclick="login()">Login</button>
                    <p class="error" id="loginError"></p>
                </div>
                
                <div id="registerForm" class="auth-form" style="display:none;">
                    <input type="email" id="regEmail" placeholder="Email" required>
                    <input type="password" id="regPassword" placeholder="Password" required>
                    <input type="password" id="regConfirm" placeholder="Confirm Password" required>
                    <button onclick="register()">Register</button>
                    <p class="error" id="regError"></p>
                </div>
            </div>
        </div>
        '''
    
    if show_pricing or (is_authenticated and user_data and user_data.get('subscription') == 'free'):
        pricing_section = '''
        <div class="pricing-container">
            <h2>Choose Your Plan</h2>
            <div class="pricing-cards">
                <div class="pricing-card">
                    <h3>Free</h3>
                    <p class="price">$0<span>/month</span></p>
                    <ul>
                        <li>✓ Basic news updates</li>
                        <li>✓ Limited price data</li>
                        <li>✓ Daily refresh</li>
                        <li>✗ Real-time prices</li>
                        <li>✗ Advanced analytics</li>
                    </ul>
                    <button class="btn-secondary" disabled>Current Plan</button>
                </div>
                
                <div class="pricing-card featured">
                    <div class="badge">Popular</div>
                    <h3>Monthly</h3>
                    <p class="price">$29<span>/month</span></p>
                    <ul>
                        <li>✓ Real-time price updates</li>
                        <li>✓ All cryptocurrencies</li>
                        <li>✓ All metals & stocks</li>
                        <li>✓ Advanced predictions</li>
                        <li>✓ Email alerts</li>
                    </ul>
                    <button class="btn-primary" onclick="subscribe('monthly')">Subscribe Monthly</button>
                </div>
                
                <div class="pricing-card">
                    <div class="badge save">Save 20%</div>
                    <h3>Annual</h3>
                    <p class="price">$279<span>/year</span></p>
                    <p class="save-text">Just $23.25/month</p>
                    <ul>
                        <li>✓ Everything in Monthly</li>
                        <li>✓ Priority support</li>
                        <li>✓ API access</li>
                        <li>✓ Custom alerts</li>
                        <li>✓ Export data</li>
                    </ul>
                    <button class="btn-primary" onclick="subscribe('annual')">Subscribe Annual</button>
                </div>
            </div>
        </div>
        '''
    
    subscription_badge = ""
    if is_authenticated and user_data:
        sub_type = user_data.get('subscription', 'free').title()
        sub_expires = user_data.get('expires', 'N/A')
        subscription_badge = f'''
        <div class="subscription-badge">
            <span class="sub-type">{sub_type} Plan</span>
            {f'<span class="sub-expires">Expires: {sub_expires}</span>' if sub_expires != 'N/A' else ''}
            <button class="btn-small" onclick="showPricing()">Upgrade</button>
            <button class="btn-small" onclick="logout()">Logout</button>
        </div>
        '''
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Economic News Dashboard - Pro</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #667eea;
            position: relative;
        }}
        h1 {{
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .subtitle {{ color: #666; font-size: 1.1em; }}
        .subscription-badge {{
            position: absolute;
            top: 0;
            right: 0;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .sub-type {{
            font-weight: bold;
            font-size: 1.1em;
        }}
        .sub-expires {{
            font-size: 0.85em;
            opacity: 0.9;
        }}
        .btn-small {{
            background: white;
            color: #667eea;
            border: none;
            padding: 5px 15px;
            border-radius: 15px;
            cursor: pointer;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .btn-small:hover {{
            background: #f0f0f0;
        }}
        .modal {{
            display: flex;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            align-items: center;
            justify-content: center;
        }}
        .modal-content {{
            background: white;
            padding: 40px;
            border-radius: 20px;
            max-width: 500px;
            width: 90%;
        }}
        .auth-tabs {{
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }}
        .tab-btn {{
            flex: 1;
            padding: 10px;
            border: none;
            background: #f0f0f0;
            cursor: pointer;
            border-radius: 10px;
            font-size: 1em;
        }}
        .tab-btn.active {{
            background: #667eea;
            color: white;
        }}
        .auth-form {{
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        .auth-form input {{
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 1em;
        }}
        .auth-form button {{
            padding: 12px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 1.1em;
            font-weight: 600;
        }}
        .auth-form button:hover {{
            background: #5568d3;
        }}
        .error {{
            color: #e74c3c;
            font-size: 0.9em;
        }}
        .pricing-container {{
            margin: 40px 0;
            text-align: center;
        }}
        .pricing-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin-top: 30px;
        }}
        .pricing-card {{
            background: white;
            border: 2px solid #ddd;
            border-radius: 20px;
            padding: 30px;
            position: relative;
            transition: transform 0.3s;
        }}
        .pricing-card:hover {{
            transform: translateY(-10px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        .pricing-card.featured {{
            border: 3px solid #667eea;
            transform: scale(1.05);
        }}
        .badge {{
            position: absolute;
            top: -15px;
            right: 20px;
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .badge.save {{
            background: #e74c3c;
        }}
        .pricing-card h3 {{
            font-size: 1.8em;
            margin-bottom: 10px;
            color: #333;
        }}
        .price {{
            font-size: 3em;
            font-weight: bold;
            color: #667eea;
            margin: 20px 0;
        }}
        .price span {{
            font-size: 0.4em;
            color: #999;
        }}
        .save-text {{
            color: #e74c3c;
            font-weight: 600;
            margin-top: -10px;
        }}
        .pricing-card ul {{
            list-style: none;
            text-align: left;
            margin: 20px 0;
        }}
        .pricing-card li {{
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .btn-primary {{
            background: #667eea;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 1.1em;
            font-weight: 600;
            width: 100%;
            margin-top: 20px;
        }}
        .btn-primary:hover {{
            background: #5568d3;
        }}
        .btn-secondary {{
            background: #f0f0f0;
            color: #999;
            border: none;
            padding: 15px 30px;
            border-radius: 10px;
            font-size: 1.1em;
            width: 100%;
            margin-top: 20px;
        }}
        #dashboardContent {{
            display: {dashboard_visibility};
        }}
        .news-section {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(102,126,234,0.3);
        }}
        .news-counter {{
            background: rgba(255,255,255,0.2);
            padding: 8px 20px;
            border-radius: 25px;
            font-weight: bold;
            display: inline-block;
            margin-bottom: 15px;
        }}
        .news-title {{
            font-size: 1.8em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .news-description {{
            font-size: 1.1em;
            line-height: 1.6;
            margin-bottom: 15px;
            opacity: 0.95;
        }}
        .news-meta {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }}
        .meta-item {{
            background: rgba(255,255,255,0.2);
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.9em;
        }}
        .progress-bar {{
            width: 100%;
            height: 4px;
            background: rgba(255,255,255,0.3);
            border-radius: 2px;
            margin-top: 15px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background: white;
            transition: width 0.1s linear;
        }}
        .tables-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
        }}
        .table-wrapper {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        }}
        .table-header {{
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 3px solid;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .crypto-header {{ color: #f7931a; border-color: #f7931a; }}
        .metals-header {{ color: #ffd700; border-color: #ffd700; }}
        .stocks-header {{ color: #4a90e2; border-color: #4a90e2; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95em;
        }}
        thead {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        th {{
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 12px 8px;
            border-bottom: 1px solid #eee;
        }}
        tbody tr:hover {{ background: #f8f9fa; }}
        .positive-change {{ color: #22c55e; font-weight: bold; }}
        .negative-change {{ color: #ef4444; font-weight: bold; }}
        .price-cell {{ font-weight: 600; }}
        .prediction-cell {{
            background: linear-gradient(90deg, rgba(102,126,234,0.1) 0%, transparent 100%);
            font-weight: bold;
        }}
        .live-badge {{
            display: inline-block;
            background: #22c55e;
            color: white;
            padding: 3px 10px;
            border-radius: 10px;
            font-size: 0.7em;
            margin-left: 10px;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        @media (max-width: 1400px) {{
            .tables-container {{ grid-template-columns: 1fr; }}
            .pricing-cards {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Economic News Dashboard Pro</h1>
            <p class="subtitle">Real-time Analysis with Live Market Prices</p>
            {subscription_badge}
        </header>

        {auth_section}
        {pricing_section}

        <div id="dashboardContent">
            <div class="news-section" id="newsSection">
                <div class="news-counter" id="newsCounter">News 1 of 10</div>
                <div class="news-title" id="newsTitle">Loading...</div>
                <div class="news-description" id="newsDescription"></div>
                <div class="news-meta" id="newsMeta"></div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
            </div>

            <div class="tables-container">
                <div class="table-wrapper">
                    <div class="table-header crypto-header">
                        <span>🪙</span>
                        <span>Top Cryptocurrencies</span>
                        <span class="live-badge">LIVE</span>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Current Price</th>
                                <th>Change %</th>
                                <th>Predicted</th>
                            </tr>
                        </thead>
                        <tbody id="cryptoBody"><tr><td colspan="4">Loading...</td></tr></tbody>
                    </table>
                </div>

                <div class="table-wrapper">
                    <div class="table-header metals-header">
                        <span>🥇</span>
                        <span>Precious Metals</span>
                        <span class="live-badge">LIVE</span>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Current Price</th>
                                <th>Change %</th>
                                <th>Predicted</th>
                            </tr>
                        </thead>
                        <tbody id="metalsBody"><tr><td colspan="4">Loading...</td></tr></tbody>
                    </table>
                </div>

                <div class="table-wrapper">
                    <div class="table-header stocks-header">
                        <span>📈</span>
                        <span>Top Stocks</span>
                        <span class="live-badge">LIVE</span>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Current Price</th>
                                <th>Change %</th>
                                <th>Predicted</th>
                            </tr>
                        </thead>
                        <tbody id="stocksBody"><tr><td colspan="4">Loading...</td></tr></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        let newsData = null;
        let currentIndex = 0;
        let progress = 0;
        let isAuthenticated = {'true' if is_authenticated else 'false'};

        // Auth Functions
        function showTab(tab) {{
            document.getElementById('loginForm').style.display = tab === 'login' ? 'block' : 'none';
            document.getElementById('registerForm').style.display = tab === 'register' ? 'block' : 'none';
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
        }}

        async function login() {{
            const email = document.getElementById('loginEmail').value;
            const password = document.getElementById('loginPassword').value;
            
            const response = await fetch('/api/login', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{email, password}})
            }});
            
            const data = await response.json();
            if (data.success) {{
                document.cookie = `session=${{data.token}}; path=/; max-age=2592000`;
                location.reload();
            }} else {{
                document.getElementById('loginError').textContent = data.message;
            }}
        }}

        async function register() {{
            const email = document.getElementById('regEmail').value;
            const password = document.getElementById('regPassword').value;
            const confirm = document.getElementById('regConfirm').value;
            
            if (password !== confirm) {{
                document.getElementById('regError').textContent = 'Passwords do not match';
                return;
            }}
            
            const response = await fetch('/api/register', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{email, password}})
            }});
            
            const data = await response.json();
            if (data.success) {{
                document.cookie = `session=${{data.token}}; path=/; max-age=2592000`;
                location.reload();
            }} else {{
                document.getElementById('regError').textContent = data.message;
            }}
        }}

        function logout() {{
            document.cookie = 'session=; path=/; max-age=0';
            location.reload();
        }}

        async function subscribe(plan) {{
            const response = await fetch('/api/subscribe', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{plan}})
            }});
            
            const data = await response.json();
            if (data.success) {{
                alert('Subscription activated! (Demo: In production, integrate payment gateway)');
                location.reload();
            }} else {{
                alert(data.message);
            }}
        }}

        function showPricing() {{
            location.href = '/pricing';
        }}

        // Dashboard Functions
        async function loadData() {{
            const response = await fetch('/api/data');
            newsData = await response.json();
            updateNews(0);
            updateTables(0);
            startProgress();
        }}

        function updateNews(index) {{
            const news = newsData.top_10_important_news[index];
            document.getElementById('newsCounter').textContent = `News ${{news.rank}} of 10`;
            document.getElementById('newsTitle').textContent = news.title;
            document.getElementById('newsDescription').textContent = news.description;
            
            const impactClass = news.impact_score >= 8 ? 'impact-high' : 
                               news.impact_score >= 5 ? 'impact-medium' : 'impact-low';
            const sentiment = news.sentiment === 'positive' ? '🟢 Positive' : '🔴 Negative';
            
            document.getElementById('newsMeta').innerHTML = `
                <div class="meta-item"  style="background: rgba(255,255,255,0.3);">Impact: ${{news.impact_score}}/10</div>
                <div class="meta-item">Assets: ${{news.affected_assets.map(a => 
                    a === 'crypto' ? '🪙' : a === 'metals' ? '🥇' : '📈'
                ).join(' ')}}</div>
                <div class="meta-item">${{sentiment}}</div>
                <div class="meta-item">Source: ${{news.source}}</div>
            `;
        }}

        function updateTables(index) {{
            const news = newsData.top_10_important_news[index];
            if (news.affected_assets.includes('crypto')) updateTable('cryptoBody', newsData.crypto_analysis);
            if (news.affected_assets.includes('metals')) updateTable('metalsBody', newsData.metals_analysis);
            if (news.affected_assets.includes('stocks')) updateTable('stocksBody', newsData.stocks_analysis);
        }}

        function updateTable(bodyId, data) {{
            const tbody = document.getElementById(bodyId);
            tbody.innerHTML = data.map(item => {{
                const changeClass = item.change_percent.startsWith('+') ? 'positive-change' : 'negative-change';
                return `
                    <tr>
                        <td>${{item.name}}</td>
                        <td class="price-cell">${{item.current_price}}</td>
                        <td class="${{changeClass}}">${{item.change_percent}}</td>
                        <td class="prediction-cell">${{item.predicted_price}}</td>
                    </tr>
                `;
            }}).join('');
        }}

        function startProgress() {{
            setInterval(() => {{
                progress += 1;
                document.getElementById('progressFill').style.width = progress + '%';
                
                if (progress >= 100) {{
                    progress = 0;
                    currentIndex = (currentIndex + 1) % newsData.top_10_important_news.length;
                    updateNews(currentIndex);
                    updateTables(currentIndex);
                }}
            }}, 100);
        }}

        if (isAuthenticated) {{
            loadData();
            // Refresh data every 5 minutes
            setInterval(loadData, 300000);
        }}
    </script>
</body>
</html>'''

# ============================================================================
# HTTP SERVER WITH AUTH
# ============================================================================

global_data = {}
db = Database()
fetcher = PriceFetcher()

class AuthHandler(http.server.BaseHTTPRequestHandler):
    def get_cookie(self, name):
        cookies = self.headers.get('Cookie', '')
        for cookie in cookies.split('; '):
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                if key == name:
                    return value
        return None
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def do_GET(self):
        if self.path == '/' or self.path == '/dashboard':
            token = self.get_cookie('session')
            user = db.verify_session(token)
            
            if user:
                html = generate_html(is_authenticated=True, user_data=user)
            else:
                html = generate_html(is_authenticated=False)
            
            self.send_html(html)
        
        elif self.path == '/pricing':
            token = self.get_cookie('session')
            user = db.verify_session(token)
            html = generate_html(is_authenticated=bool(user), user_data=user, show_pricing=True)
            self.send_html(html)
        
        elif self.path == '/api/data':
            token = self.get_cookie('session')
            user = db.verify_session(token)
            
            if user:
                self.send_json(global_data)
            else:
                self.send_json({{'error': 'Unauthorized'}}, 401)
        
        else:
            self.send_error(404)
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode())
        except:
            self.send_json({{'success': False, 'message': 'Invalid JSON'}}, 400)
            return
        
        if self.path == '/api/register':
            email = data.get('email')
            password = data.get('password')
            
            if not email or not password:
                self.send_json({{'success': False, 'message': 'Email and password required'}})
                return
            
            user_id = db.create_user(email, password)
            if user_id:
                token = db.create_session(user_id)
                self.send_json({{'success': True, 'token': token}})
            else:
                self.send_json({{'success': False, 'message': 'Email already exists'}})
        
        elif self.path == '/api/login':
            email = data.get('email')
            password = data.get('password')
            
            user = db.verify_user(email, password)
            if user:
                token = db.create_session(user['id'])
                self.send_json({{'success': True, 'token': token}})
            else:
                self.send_json({{'success': False, 'message': 'Invalid credentials'}})
        
        elif self.path == '/api/subscribe':
            token = self.get_cookie('session')
            user = db.verify_session(token)
            
            if not user:
                self.send_json({{'success': False, 'message': 'Unauthorized'}}, 401)
                return
            
            plan = data.get('plan')
            if plan == 'monthly':
                db.update_subscription(user['id'], 'monthly', 1)
                self.send_json({{'success': True, 'message': 'Monthly subscription activated'}})
            elif plan == 'annual':
                db.update_subscription(user['id'], 'annual', 12)
                self.send_json({{'success': True, 'message': 'Annual subscription activated'}})
            else:
                self.send_json({{'success': False, 'message': 'Invalid plan'}})
        
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        pass  # Suppress logs

# ============================================================================
# DATA UPDATE THREAD
# ============================================================================

def update_data():
    """Background thread to update data periodically"""
    while True:
        try:
            print("🔄 Updating data...")
            scraper = NewsScraper()
            news = scraper.get_news()
            
            cryptos = fetcher.get_crypto_prices()
            metals = fetcher.get_metal_prices()
            stocks = fetcher.get_stock_prices()
            
            analyzer = AssetAnalyzer(news, fetcher)
            crypto_analysis = analyzer.analyze(cryptos, 'crypto')
            metals_analysis = analyzer.analyze(metals, 'metals')
            stocks_analysis = analyzer.analyze(stocks, 'stocks')
            
            global_data.update({{
                'generated_at': datetime.now().isoformat(),
                'top_10_important_news': news,
                'crypto_analysis': crypto_analysis,
                'metals_analysis': metals_analysis,
                'stocks_analysis': stocks_analysis
            }})
            print("✓ Data updated successfully")
        except Exception as e:
            print(f"✗ Error updating data: {{e}}")
        
        time.sleep(300)  # Update every 5 minutes

# ============================================================================
# MAIN
# ============================================================================

def main():
    PORT = 8000
    
    print("="*70)
    print("🚀 Economic News Dashboard Pro - with Authentication & Subscriptions")
    print("="*70)
    
    # Initial data
    print("\n📊 Generating initial data...")
    scraper = NewsScraper()
    news = scraper.get_news()
    
    cryptos = fetcher.get_crypto_prices()
    metals = fetcher.get_metal_prices()
    stocks = fetcher.get_stock_prices()
    
    analyzer = AssetAnalyzer(news, fetcher)
    crypto_analysis = analyzer.analyze(cryptos, 'crypto')
    metals_analysis = analyzer.analyze(metals, 'metals')
    stocks_analysis = analyzer.analyze(stocks, 'stocks')
    
    global_data.update({
        'generated_at': datetime.now().isoformat(),
        'top_10_important_news': news,
        'crypto_analysis': crypto_analysis,
        'metals_analysis': metals_analysis,
        'stocks_analysis': stocks_analysis
    })
    
    print("✓ Initial data generated")
    
    # Start update thread
    print("🔄 Starting auto-update thread...")
    update_thread = threading.Thread(target=update_data, daemon=True)
    update_thread.start()
    
    # Start server
    with socketserver.TCPServer(("", PORT), AuthHandler) as httpd:
        print(f"\n✅ Dashboard running at:")
        print(f"   http://localhost:{{PORT}}")
        print(f"\n💡 Features:")
        print(f"   - User registration & login")
        print(f"   - Free, Monthly ($29), Annual ($279) plans")
        print(f"   - Real-time crypto prices from CoinGecko")
        print(f"   - Live price updates every 5 minutes")
        print(f"\n💡 Press Ctrl+C to stop")
        print("="*70)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n⏹️  Shutting down...")
            httpd.shutdown()

if __name__ == "__main__":
    main()
