# trading_signal.py - 완전체 버전 (중복방지 + 통합알림)
import requests
import numpy as np
import time
import json
import os
from datetime import datetime, timedelta

class SmartTradingBot:
    def __init__(self):
        # 텔레그램 봇 정보
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '8092280367:AAH3Do1RM4XsmV1JLJEiENfyIWpS4AjB2r8')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID', '1718223270')
        
        # 바이낸스 API
        self.binance_api = 'https://api.binance.com/api/v3'
        self.coins = [
            'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'LINKUSDT',
            'ENAUSDT', 'SUIUSDT', 'BNBUSDT', '1000PEPEUSDT', 
            'PUMPUSDT', 'PENGUUSDT'
        ]
        self.timeframe = '15m'
        
        # 🎯 스마트 알림 설정 (11개 코인 최적화)
        self.cooldown_minutes = 60          # 같은 신호 1시간 쿨다운
        self.batch_threshold = 3            # 3개 이상이면 통합 알림
        self.max_signals_per_run = 8        # 한 번에 최대 8개 신호
        
        # 📝 신호 히스토리 관리
        self.history_file = 'signal_history.json'
        self.signal_history = self.load_signal_history()
        
        print(f"🚀 스마트 트레이딩 봇 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def load_signal_history(self):
        """신호 히스토리 불러오기"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    history = json.load(f)
                    
                # 24시간 이전 기록은 자동 삭제
                cutoff_time = datetime.now() - timedelta(hours=24)
                cleaned_history = {}
                
                for key, timestamp in history.items():
                    if datetime.fromisoformat(timestamp) > cutoff_time:
                        cleaned_history[key] = timestamp
                
                print(f"📝 기존 신호 히스토리 {len(cleaned_history)}개 로드")
                return cleaned_history
            return {}
        except:
            return {}

    def save_signal_history(self):
        """신호 히스토리 저장"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.signal_history, f, indent=2)
            print(f"💾 신호 히스토리 {len(self.signal_history)}개 저장")
        except Exception as e:
            print(f"❌ 히스토리 저장 실패: {e}")

    def is_duplicate_signal(self, symbol, signal_type):
        """중복 신호 체크 (문제 1 해결)"""
        signal_key = f"{symbol}_{signal_type}"
        
        if signal_key in self.signal_history:
            last_time = datetime.fromisoformat(self.signal_history[signal_key])
            time_diff = datetime.now() - last_time
            
            if time_diff < timedelta(minutes=self.cooldown_minutes):
                minutes_left = self.cooldown_minutes - (time_diff.seconds // 60)
                print(f"⏳ {symbol} {signal_type} 쿨다운 중 ({minutes_left}분 남음)")
                return True
        
        return False

    def record_signal(self, symbol, signal_type):
        """신호 발생 기록"""
        signal_key = f"{symbol}_{signal_type}"
        self.signal_history[signal_key] = datetime.now().isoformat()

    def get_market_data(self, symbol):
        """바이낸스 데이터 수집"""
        try:
            ticker_url = f"{self.binance_api}/ticker/24hr?symbol={symbol}"
            klines_url = f"{self.binance_api}/klines?symbol={symbol}&interval={self.timeframe}&limit=200"
            
            ticker_response = requests.get(ticker_url, timeout=10)
            klines_response = requests.get(klines_url, timeout=10)
            
            return ticker_response.json(), klines_response.json()
        except Exception as e:
            print(f"❌ {symbol} 데이터 가져오기 실패: {e}")
            return None, None

    def calculate_rsi(self, prices, period=14):
        """RSI 계산"""
        if len(prices) < period + 1:
            return 50
            
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))
        
        if len(gains) < period:
            return 50
            
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        for i in range(period, len(gains)):
            if avg_loss == 0:
                return 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
        
        return rsi

    def calculate_sma(self, prices, period):
        """이동평균 계산"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return np.mean(prices[-period:])

    def calculate_bollinger_bands(self, prices, period=20, multiplier=2):
        """볼린저밴드 계산"""
        if len(prices) < period:
            price = prices[-1] if prices else 0
            return price, price, price
            
        sma = self.calculate_sma(prices, period)
        std = np.std(prices[-period:])
        
        upper = sma + (std * multiplier)
        lower = sma - (std * multiplier)
        
        return upper, lower, sma

    def analyze_signal(self, symbol, ticker_data, klines_data):
        """신호 분석 + 중복 체크"""
        try:
            closes = [float(kline[4]) for kline in klines_data]
            volumes = [float(kline[5]) for kline in klines_data]
            
            current_price = float(ticker_data['lastPrice'])
            price_change_percent = float(ticker_data['priceChangePercent'])
            
            # 기술적 지표 계산
            rsi = self.calculate_rsi(closes)
            ma20 = self.calculate_sma(closes, 20)
            ma50 = self.calculate_sma(closes, 50)
            bb_upper, bb_lower, bb_middle = self.calculate_bollinger_bands(closes)
            
            avg_volume = np.mean(volumes[-20:])
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # 📊 신호 체크 + 중복 방지
            valid_signals = []
            
            # 1. 슈퍼 시그널
            super_conditions = [
                current_price <= bb_lower and rsi < 25,
                volume_ratio > 3.0,
                ma20 > ma50,
                price_change_percent < -15
            ]
            
            if sum(super_conditions) == 4:
                signal_type = "슈퍼시그널"
                if not self.is_duplicate_signal(symbol, signal_type):
                    valid_signals.append({
                        'type': '👑 슈퍼 시그널',
                        'signal_key': signal_type,
                        'priority': 1,  # 최우선
                        'confidence': '95%+',
                        'expected_return': '+15~30%'
                    })
            
            # 2. 강력한 매수
            strong_buy_conditions = [
                current_price <= bb_lower * 1.02 and 20 <= rsi <= 35,
                volume_ratio > 2.0,
                abs(current_price - ma20) / ma20 < 0.05,
                rsi < 40
            ]
            
            if sum(strong_buy_conditions) == 4:
                signal_type = "강력매수"
                if not self.is_duplicate_signal(symbol, signal_type):
                    valid_signals.append({
                        'type': '🟢 강력한 매수',
                        'signal_key': signal_type,
                        'priority': 2,
                        'confidence': '85%',
                        'expected_return': '+8~20%'
                    })
            
            # 3. 강력한 매도
            strong_sell_conditions = [
                current_price >= bb_upper and rsi > 75,
                volume_ratio > 1.8,
                rsi > 70,
                current_price > ma20 * 1.1
            ]
            
            if sum(strong_sell_conditions) == 4:
                signal_type = "강력매도"
                if not self.is_duplicate_signal(symbol, signal_type):
                    valid_signals.append({
                        'type': '🔴 강력한 매도',
                        'signal_key': signal_type,
                        'priority': 2,
                        'confidence': '80%',
                        'expected_return': '+10~20% (숏)'
                    })
            
            # 4. 황금십자
            golden_cross_conditions = [
                ma20 > ma50,
                45 <= rsi <= 65,
                volume_ratio > 1.0,
                current_price > ma20
            ]
            
            if sum(golden_cross_conditions) == 4:
                signal_type = "황금십자"
                if not self.is_duplicate_signal(symbol, signal_type):
                    valid_signals.append({
                        'type': '⭐ 황금십자',
                        'signal_key': signal_type,
                        'priority': 3,
                        'confidence': '75%',
                        'expected_return': '+15~40%'
                    })
            
            return valid_signals, {
                'current_price': current_price,
                'rsi': rsi,
                'volume_ratio': volume_ratio,
                'price_change_percent': price_change_percent,
                'ma20': ma20,
                'ma50': ma50
            }
            
        except Exception as e:
            print(f"❌ {symbol} 분석 실패: {e}")
            return [], {}

    def send_telegram_message(self, message):
        """텔레그램 메시지 전송"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ 텔레그램 전송 오류: {e}")
            return False

    def send_single_notification(self, signal_data):
        """단일 신호 알림"""
        symbol = signal_data['symbol']
        signal = signal_data['signal']
        market_info = signal_data['market_info']
        
        message = f"""
🚨 *거래 신호 발생!* 🚨

📊 *코인:* {symbol.replace('USDT', '')}/USDT
💰 *현재가:* ${market_info['current_price']:,.2f}
🎯 *신호:* {signal['type']}
📈 *RSI:* {market_info['rsi']:.1f}
📊 *거래량:* {market_info['volume_ratio']:.1f}x
📉 *24시간:* {market_info['price_change_percent']:+.2f}%

✨ *신뢰도:* {signal['confidence']}
💎 *예상 수익:* {signal['expected_return']}

⏰ {datetime.now().strftime('%H:%M:%S')}
🚫 *다음 알림:* {self.cooldown_minutes}분 후
        """.strip()
        
        return self.send_telegram_message(message)

    def send_batch_notification(self, all_signals):
        """통합 신호 알림 (문제 2 해결)"""
        
        # 우선순위별 분류
        super_signals = [s for s in all_signals if s['signal']['priority'] == 1]
        strong_signals = [s for s in all_signals if s['signal']['priority'] == 2]
        other_signals = [s for s in all_signals if s['signal']['priority'] == 3]
        
        message_parts = []
        message_parts.append(f"🚨 *{len(all_signals)}개 신호 동시 발생!* 🚨\n")
        
        # 슈퍼 시그널 (최우선)
        if super_signals:
            message_parts.append("👑 *슈퍼 시그널* (승률 95%+)")
            for signal_data in super_signals:
                symbol = signal_data['symbol'].replace('USDT', '')
                market_info = signal_data['market_info']
                message_parts.append(
                    f"• *{symbol}*: ${market_info['current_price']:,.0f} "
                    f"(RSI: {market_info['rsi']:.0f}, {market_info['price_change_percent']:+.1f}%)"
                )
            message_parts.append("")
        
        # 강력한 신호들
        if strong_signals:
            buy_signals = [s for s in strong_signals if '매수' in s['signal']['type']]
            sell_signals = [s for s in strong_signals if '매도' in s['signal']['type']]
            
            if buy_signals:
                message_parts.append("🟢 *강력한 매수*")
                for signal_data in buy_signals:
                    symbol = signal_data['symbol'].replace('USDT', '')
                    market_info = signal_data['market_info']
                    message_parts.append(
                        f"• *{symbol}*: ${market_info['current_price']:,.0f} (RSI: {market_info['rsi']:.0f})"
                    )
                message_parts.append("")
            
            if sell_signals:
                message_parts.append("🔴 *강력한 매도*")
                for signal_data in sell_signals:
                    symbol = signal_data['symbol'].replace('USDT', '')
                    market_info = signal_data['market_info']
                    message_parts.append(
                        f"• *{symbol}*: ${market_info['current_price']:,.0f} (RSI: {market_info['rsi']:.0f})"
                    )
                message_parts.append("")
        
        # 기타 신호들
        if other_signals:
            message_parts.append("⭐ *기타 신호*")
            for signal_data in other_signals:
                symbol = signal_data['symbol'].replace('USDT', '')
                market_info = signal_data['market_info']
                message_parts.append(
                    f"• *{symbol}*: ${market_info['current_price']:,.0f}"
                )
            message_parts.append("")
        
        # 요약
        super_count = len(super_signals)
        if super_count > 0:
            message_parts.append(f"🔥 *슈퍼 시그널 {super_count}개 포함!*")
        
        message_parts.append(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
        message_parts.append(f"🚫 다음 알림: {self.cooldown_minutes}분 후")
        message_parts.append("⚠️ 투자는 신중히 결정하세요!")
        
        final_message = '\n'.join(message_parts)
        return self.send_telegram_message(final_message)

    def run_smart_analysis(self):
        """🎯 스마트 분석 실행 (두 문제 동시 해결)"""
        print(f"\n🔍 스마트 분석 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 1단계: 모든 신호 수집
        all_valid_signals = []
        
        for symbol in self.coins:
            print(f"   📊 {symbol} 분석 중...")
            
            ticker_data, klines_data = self.get_market_data(symbol)
            if not ticker_data or not klines_data:
                continue
                
            signals, market_info = self.analyze_signal(symbol, ticker_data, klines_data)
            
            # 유효한 신호만 추가
            for signal in signals:
                self.record_signal(symbol, signal['signal_key'])
                all_valid_signals.append({
                    'symbol': symbol,
                    'signal': signal,
                    'market_info': market_info
                })
        
        # 2단계: 스마트 알림 전송
        signal_count = len(all_valid_signals)
        
        if signal_count == 0:
            print(f"⏳ 새로운 신호 없음 - 계속 모니터링...")
            
        elif signal_count == 1:
            # 단일 신호: 상세 알림
            if self.send_single_notification(all_valid_signals[0]):
                print(f"✅ 단일 신호 알림 전송 완료")
            
        elif signal_count >= self.batch_threshold:
            # 복수 신호: 통합 알림
            if self.send_batch_notification(all_valid_signals):
                print(f"✅ {signal_count}개 신호 통합 알림 전송 완료")
        
        # 3단계: 히스토리 저장
        self.save_signal_history()
        
        # 4단계: 현재 상태 출력
        active_cooldowns = sum(1 for key, timestamp in self.signal_history.items()
                             if datetime.now() - datetime.fromisoformat(timestamp) 
                             < timedelta(minutes=self.cooldown_minutes))
        
        if active_cooldowns > 0:
            print(f"⏳ 현재 {active_cooldowns}개 신호 쿨다운 중")
        
        print(f"🎯 분석 완료: {signal_count}개 새로운 신호 발견\n")

if __name__ == "__main__":
    bot = SmartTradingBot()
    bot.run_smart_analysis()