import tkinter as tk
from tkinter import ttk
import requests
from bs4 import BeautifulSoup
import threading
import time
import logging
from datetime import datetime
import random  # 랜덤 모듈 추가

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ladder_game.log', encoding='utf-8')
    ]
)

class LadderGameGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("파워사다리 게임 분석기")
        self.root.geometry("620x810")
        
        # 자산 및 베팅 정보 초기화
        self.initial_asset = 500000  # 초기 자산 50만원
        self.current_asset = self.initial_asset
        self.base_bet = 30000  # 기본 베팅 금액
        self.current_bet = self.base_bet
        self.total_profit = 0
        self.win_count = 0
        self.lose_count = 0
        
        # 예측 및 베팅 정보
        self.current_round = None  # 현재 회차
        self.next_round = None  # 다음 회차
        self.current_prediction = None  # 현재 회차 예측 (이미 베팅한 예측)
        self.next_prediction = None  # 다음 회차 예측 (새로운 예측)
        
        # HTTP 세션 초기화
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 메인 프레임
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # GUI 컴포넌트 초기화
        self.create_asset_display()  # 자산 정보 표시 영역 추가
        self.create_result_display()
        self.create_stats_display()
        self.create_prediction_display()
        self.create_log_display()  # 로그 표시 영역 추가
        
        # 상태 표시 레이블
        self.status_label = ttk.Label(self.main_frame, text="마지막 업데이트: -")
        self.status_label.grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # 데이터 초기화
        self.game_results = []
        self.last_round = None
        self.previous_prediction = None
        self.update_data()

    def create_asset_display(self):
        # 자산 정보 표시 프레임
        asset_frame = ttk.LabelFrame(self.main_frame, text="내 정보", padding="5")
        asset_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 자산 정보 레이블
        self.asset_labels = {
            '초기자산': ttk.Label(asset_frame, text=f"초기자산: {self.initial_asset:,}원"),
            '현재자산': ttk.Label(asset_frame, text=f"현재자산: {self.current_asset:,}원"),
            '총수익': ttk.Label(asset_frame, text=f"총수익: {self.total_profit:,}원"),
            '승률': ttk.Label(asset_frame, text="승률: 0%"),
            '현재베팅': ttk.Label(asset_frame, text=f"현재 베팅금액: {self.current_bet:,}원")
        }
        
        # 배치
        row = 0
        for label in self.asset_labels.values():
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
            row += 1

    def create_result_display(self):
        # 결과 표시 프레임
        result_frame = ttk.LabelFrame(self.main_frame, text="게임 결과", padding="5")
        result_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 결과 표시 트리뷰
        columns = ('회차', '방향', '줄수', '홀짝')
        self.result_tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=15)
        
        # 컬럼 설정
        for col in columns:
            self.result_tree.heading(col, text=col)
            self.result_tree.column(col, width=100, anchor='center')
        
        # 트리뷰 스타일 설정
        style = ttk.Style()
        style.configure("Winner.Treeview.Row", background="lightgreen")
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        
        # 배치
        self.result_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

    def create_stats_display(self):
        # 통계 표시 프레임
        stats_frame = ttk.LabelFrame(self.main_frame, text="통계", padding="5")
        stats_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 통계 레이블
        self.stats_labels = {
            '좌우비율': ttk.Label(stats_frame, text="좌우 비율: "),
            '줄수비율': ttk.Label(stats_frame, text="3줄/4줄 비율: "),
            '홀짝비율': ttk.Label(stats_frame, text="홀짝 비율: ")
        }
        
        # 배치
        row = 0
        for label in self.stats_labels.values():
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
            row += 1

    def create_prediction_display(self):
        # 예측 표시 프레임
        prediction_frame = ttk.LabelFrame(self.main_frame, text="다음 회차 예측", padding="5")
        prediction_frame.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 예측 레이블
        self.prediction_labels = {
            '방향': ttk.Label(prediction_frame, text="예상 방향: "),
            '줄수': ttk.Label(prediction_frame, text="예상 줄수: "),
            '홀짝': ttk.Label(prediction_frame, text="예상 홀짝: ")
        }
        
        # 배치
        row = 0
        for label in self.prediction_labels.values():
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
            row += 1

    def create_log_display(self):
        # 로그 표시 프레임
        log_frame = ttk.LabelFrame(self.main_frame, text="베팅 내역", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 로그 표시 텍스트 위젯
        self.log_text = tk.Text(log_frame, height=8, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def add_log(self, message):
        current_time = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert('1.0', f"[{current_time}] {message}\n")
        self.log_text.see('1.0')

    def update_result_tree(self):
        # 기존 항목 삭제
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        
        # 새 데이터 추가
        for result in self.game_results:
            round_num, direction, line, parity = result
            
            # 모든 회차에 대해 승리 여부 확인
            correct_count = 0
            # 현재 예측 전략(좌3홀)과 비교
            if direction == '좌':
                correct_count += 1
            if line == '3':
                correct_count += 1
            if parity == '홀':
                correct_count += 1
            
            # 2개 이상 적중시 표시 추가
            if correct_count >= 2:
                result = (f"★{round_num}", direction, line, parity)
            
            item = self.result_tree.insert('', 'end', values=result)
            
            # 적중 결과에 따라 태그 설정
            if correct_count >= 2:
                self.result_tree.tag_configure('winner', foreground='blue')
                self.result_tree.item(item, tags=('winner',))

    def update_stats(self):
        if not self.game_results:
            return
        
        # 최근 20개 결과만 사용
        recent_results = self.game_results[:20]
        
        # 좌우 비율
        left_count = sum(1 for _, dir, _, _ in recent_results if dir == '좌')
        right_count = len(recent_results) - left_count
        self.stats_labels['좌우비율'].config(
            text=f"좌우 비율: 좌 {left_count}회 ({left_count/len(recent_results)*100:.1f}%) / "
                 f"우 {right_count}회 ({right_count/len(recent_results)*100:.1f}%)")
        
        # 줄수 비율
        line3_count = sum(1 for _, _, line, _ in recent_results if line == '3')
        line4_count = len(recent_results) - line3_count
        self.stats_labels['줄수비율'].config(
            text=f"3줄/4줄 비율: 3줄 {line3_count}회 ({line3_count/len(recent_results)*100:.1f}%) / "
                 f"4줄 {line4_count}회 ({line4_count/len(recent_results)*100:.1f}%)")
        
        # 홀짝 비율
        odd_count = sum(1 for _, _, _, par in recent_results if par == '홀')
        even_count = len(recent_results) - odd_count
        self.stats_labels['홀짝비율'].config(
            text=f"홀짝 비율: 홀 {odd_count}회 ({odd_count/len(recent_results)*100:.1f}%) / "
                 f"짝 {even_count}회 ({even_count/len(recent_results)*100:.1f}%)")

    def update_prediction(self):
        # 항상 좌3홀로 고정 예측
        predicted_direction = '좌'
        predicted_line = '3'
        predicted_parity = '홀'
        
        # 다음 회차 예측 저장
        self.next_prediction = (predicted_direction, predicted_line, predicted_parity)
        
        # 예측 표시 업데이트
        self.prediction_labels['방향'].config(text=f"예상 방향: {predicted_direction}")
        self.prediction_labels['줄수'].config(text=f"예상 줄수: {predicted_line}")
        self.prediction_labels['홀짝'].config(text=f"예상 홀짝: {predicted_parity}")

    def check_prediction_result(self, actual_result):
        if not self.current_prediction:
            return
        
        correct_count = 0
        result_details = []
        
        # 방향 체크
        if self.current_prediction[0] == actual_result[1]:
            correct_count += 1
            result_details.append("방향 적중")
        
        # 줄수 체크
        if self.current_prediction[1] == actual_result[2]:
            correct_count += 1
            result_details.append("줄수 적중")
        
        # 홀짝 체크
        if self.current_prediction[2] == actual_result[3]:
            correct_count += 1
            result_details.append("홀짝 적중")
        
        # 베팅 금액 계산
        bet_amount = self.current_bet * 3  # 3곳에 베팅
        
        # 당첨금 계산 및 자산 증가
        win_amount = self.current_bet * 2 * correct_count  # 적중당 2배
        self.current_asset += win_amount  # 당첨금 추가
        
        # 수익 계산
        profit = win_amount - bet_amount
        
        # 승패 기록 및 다음 베팅 금액 설정
        if correct_count >= 2:  # 2개 이상 적중시 승리
            self.win_count += 1
            self.current_bet = self.base_bet  # 승리시 기본 베팅으로 리셋
        else:
            self.lose_count += 1
            # 새로운 베팅 전략: 최대 1.5배까지만 증가하고, 2연패부터는 기본 베팅으로 리셋
            consecutive_losses = 1
            for i in range(len(self.game_results)-1, -1, -1):
                result = self.game_results[i]
                if i >= len(self.game_results) - 5:  # 최근 5게임만 확인
                    # 현재 회차의 예측과 비교하여 승패 확인
                    round_correct_count = 0
                    if self.current_prediction[0] == result[1]:
                        round_correct_count += 1
                    if self.current_prediction[1] == result[2]:
                        round_correct_count += 1
                    if self.current_prediction[2] == result[3]:
                        round_correct_count += 1
                    
                    if round_correct_count < 2:  # 패배
                        consecutive_losses += 1
                    else:  # 승리하면 연패 중단
                        break
            
            if consecutive_losses >= 2:
                self.current_bet = self.base_bet  # 2연패부터는 기본 베팅
            else:
                self.current_bet = int(self.base_bet * 1.5)  # 첫 패배시에만 1.5배
            
            # 현재 자산의 5%를 초과하지 않도록 제한
            max_allowed_bet = max(self.current_asset // 20, self.base_bet)  # 최소 기본 베팅은 보장
            self.current_bet = min(self.current_bet, max_allowed_bet)
        
        # 총 수익 업데이트 (초기 자산과 현재 자산의 차이)
        self.total_profit = self.current_asset - self.initial_asset
        
        # 결과 로깅
        result_str = ", ".join(result_details) if result_details else "모두 미적중"
        win_mark = "🎯 승리! " if correct_count >= 2 else ""  # 2개 이상 적중시 승리 표시
        self.add_log(f"{actual_result[0]}회차 결과: {win_mark}{result_str}")
        self.add_log(f"수익: {profit:,}원 (적중 {correct_count}개, 베팅 {bet_amount:,}원, 당첨 {win_amount:,}원)")
        
        # 자산 정보 업데이트
        total_games = self.win_count + self.lose_count
        win_rate = (self.win_count / total_games * 100) if total_games > 0 else 0
        
        self.asset_labels['현재자산'].config(text=f"현재자산: {self.current_asset:,}원")
        self.asset_labels['총수익'].config(text=f"총수익: {self.total_profit:,}원")
        self.asset_labels['승률'].config(text=f"승률: {win_rate:.1f}% ({self.win_count}승 {self.lose_count}패)")
        self.asset_labels['현재베팅'].config(text=f"현재 베팅금액: {self.current_bet:,}원")

    def update_data(self):
        try:
            logging.info("데이터 업데이트 시작")
            
            # API 호출
            url = "https://ntry.com/data/json/games/power_ladder/result.json"
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            logging.info(f"API 응답: {data}")
            
            if not data:
                logging.warning("결과 데이터가 없습니다")
                return
            
            try:
                round_num = str(data['r'])
                direction = '좌' if data['s'] == 'LEFT' else '우'
                line = str(data['l'])
                parity = '홀' if data['o'] == 'ODD' else '짝'
                
                new_result = (round_num, direction, line, parity)
                logging.info(f"파싱된 결과: {round_num}회차 - {direction}/{line}/{parity}")
                
                is_first_update = self.current_round is None
                
                if is_first_update or self.current_round != round_num:
                    logging.info(f"새로운 회차 발견: {round_num} (이전: {self.current_round})")
                    
                    # 이전 예측 결과 확인 (첫 업데이트가 아닐 경우에만)
                    if not is_first_update and self.current_prediction:
                        self.check_prediction_result(new_result)
                    
                    # 회차 정보 업데이트
                    self.current_round = round_num
                    self.next_round = str(int(round_num) + 1)
                    
                    # 게임 결과 업데이트
                    self.game_results.insert(0, new_result)
                    if len(self.game_results) > 20:
                        self.game_results = self.game_results[:20]
                    
                    self.update_result_tree()
                    self.update_stats()
                    
                    # 예측 정보 업데이트
                    if is_first_update:
                        # 첫 업데이트인 경우 현재 회차와 다음 회차 예측 한번에 처리
                        self.update_prediction()  # 현재 회차 예측
                        self.current_prediction = self.next_prediction
                        self.next_prediction = None
                        self.update_prediction()  # 다음 회차 예측
                        # 다음 회차 베팅 정보 로깅 (한 번만)
                        bet_amount = self.current_bet * 3  # 3곳에 베팅
                        self.current_asset -= bet_amount  # 베팅 금액 즉시 차감
                        self.total_profit = self.current_asset - self.initial_asset  # 총수익 업데이트
                        self.asset_labels['현재자산'].config(text=f"현재자산: {self.current_asset:,}원")
                        self.asset_labels['총수익'].config(text=f"총수익: {self.total_profit:,}원")
                        self.add_log(f"{self.next_round}회차 베팅: 방향({self.next_prediction[0]}), 줄수({self.next_prediction[1]}), 홀짝({self.next_prediction[2]}) - 각 {self.current_bet:,}원")
                    else:
                        # 이전에 예측한 다음 회차 예측을 현재 예측으로
                        self.current_prediction = self.next_prediction
                        self.next_prediction = None
                        self.update_prediction()  # 새로운 다음 회차 예측
                        # 다음 회차 베팅 정보 로깅
                        bet_amount = self.current_bet * 3  # 3곳에 베팅
                        self.current_asset -= bet_amount  # 베팅 금액 즉시 차감
                        self.total_profit = self.current_asset - self.initial_asset  # 총수익 업데이트
                        self.asset_labels['현재자산'].config(text=f"현재자산: {self.current_asset:,}원")
                        self.asset_labels['총수익'].config(text=f"총수익: {self.total_profit:,}원")
                        self.add_log(f"{self.next_round}회차 베팅: 방향({self.next_prediction[0]}), 줄수({self.next_prediction[1]}), 홀짝({self.next_prediction[2]}) - 각 {self.current_bet:,}원")
                    
                    current_time = datetime.now().strftime("%H:%M:%S")
                    self.status_label.config(text=f"마지막 업데이트: {current_time} (회차: {round_num})")
                else:
                    logging.info("새로운 데이터 없음")
                    
            except KeyError as e:
                logging.error(f"필수 데이터 필드 누락: {e}")
            except Exception as e:
                logging.error(f"결과 파싱 오류: {e}")
            
        except requests.RequestException as e:
            logging.error(f"네트워크 오류: {e}")
        except ValueError as e:
            logging.error(f"JSON 파싱 오류: {e}")
        except Exception as e:
            logging.error(f"데이터 업데이트 중 오류 발생: {e}")
        finally:
            self.root.after(5000, self.update_data)

if __name__ == "__main__":
    root = tk.Tk()
    app = LadderGameGUI(root)
    root.mainloop()
