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

class RoundInfo:
    def __init__(self, round_num):
        self.round_num = round_num
        self.bets = {
            'singles': [],  # [(type, value, amount), ...]
            'combo': None   # (direction, line, amount)
        }
        self.result = None  # (direction, line, parity)
        self.profit = 0
        self.win_amount = 0
        self.total_bet = 0
        self.correct_picks = 0
        self.total_picks = 0
        self.pattern_type = None

class LadderGameGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("파워사다리 게임 분석기")
        self.root.geometry("850x670")
        
        # 자산 및 베팅 정보 초기화
        self.initial_asset = 500000  # 초기 자산 50만원
        self.current_asset = self.initial_asset
        self.base_bet = 30000  # 기본 베팅 금액 (단식 각각 3만원)
        self.current_bet = self.base_bet
        self.hedge_bet = 20000  # 부분 헤징: 1픽 적중시 손실 -22,100원, 0픽+조합 성공시 -8,000원
        self.total_profit = 0
        self.win_count = 0
        self.lose_count = 0
        
        # 베팅 모드 설정
        self.betting_mode = tk.StringVar(value="rotation")  # 기본값: 로테이션
        self.selected_picks = {
            'pick1': tk.StringVar(value='좌'),
            'pick2': tk.StringVar(value='3')
        }
        
        # 배당률 설정
        self.odds = {
            'single': 1.93,  # 단식 배당 (좌우/홀짝/3줄4줄)
            'combination': 3.6  # 조합 배당 (좌우+3줄4줄)
        }
        
        # 베팅 패턴 (3단계 로테이션)
        self.betting_patterns = [
            ('direction_parity', '좌', '홀'),  # 1단계: 좌+홀
            ('direction_line', '좌', '3'),     # 2단계: 좌+3
            ('line_parity', '3', '홀'),       # 3단계: 3+홀
        ]
        self.current_pattern_index = 0
        
        # 예측 및 베팅 정보
        self.current_round = None
        self.next_round = None
        self.current_prediction = None
        self.next_prediction = None
        self.betting_start_round = None
        
        # 라운드 정보 추적을 위한 딕셔너리
        self.rounds = {}  # {round_num: RoundInfo}
        
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
        self.create_asset_display()
        self.create_result_display()
        self.create_stats_display()
        self.create_prediction_display()
        
        # 상태 표시 레이블
        self.status_label = ttk.Label(self.main_frame, text="마지막 업데이트: -")
        self.status_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # 데이터 초기화
        self.game_results = []
        self.last_round = None
        self.previous_prediction = None
        
        # 데이터 업데이트 시작
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
            '현재베팅': ttk.Label(asset_frame, text=f"단식 베팅: {self.current_bet:,}원 × 2, 조합 베팅: {self.hedge_bet:,}원")
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
        
        # 왼쪽 프레임 (트리뷰용)
        left_frame = ttk.Frame(result_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 오른쪽 프레임 (베팅 모드와 베팅 내역용)
        right_frame = ttk.Frame(result_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.N, tk.S), padx=10)
        
        # 결과 표시 트리뷰
        columns = ('회차', '방향', '줄수', '홀짝', '베팅금', '순이익')
        self.result_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=15)
        
        # 컬럼 설정
        for col in columns:
            self.result_tree.heading(col, text=col)
            if col in ['베팅금', '순이익']:
                self.result_tree.column(col, width=80, anchor='center')
            else:
                self.result_tree.column(col, width=70, anchor='center')
        
        # 트리뷰 스타일 설정
        style = ttk.Style()
        style.configure("Winner.Treeview.Row", background="lightgreen")
        
        # 스크롤바
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=scrollbar.set)
        
        # 트리뷰 배치
        self.result_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 베팅 모드 선택 프레임
        mode_frame = ttk.LabelFrame(right_frame, text="베팅 모드", padding="5")
        mode_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # 라디오 버튼
        ttk.Radiobutton(mode_frame, text="로테이션", variable=self.betting_mode, 
                       value="rotation").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(mode_frame, text="선택", variable=self.betting_mode, 
                       value="custom").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        # 선택 모드 콤보박스 프레임
        combo_frame = ttk.LabelFrame(right_frame, text="선택 설정", padding="5")
        combo_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # 첫번째 픽 선택
        ttk.Label(combo_frame, text="첫번째 픽:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Combobox(combo_frame, textvariable=self.selected_picks['pick1'], 
                    values=['좌', '우', '3', '4', '홀', '짝'], 
                    state='readonly', width=5).grid(row=0, column=1, padx=5)
        
        # 두번째 픽 선택
        ttk.Label(combo_frame, text="두번째 픽:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Combobox(combo_frame, textvariable=self.selected_picks['pick2'], 
                    values=['좌', '우', '3', '4', '홀', '짝'], 
                    state='readonly', width=5).grid(row=1, column=1, padx=5)
        
        # 베팅 내역 프레임
        log_frame = ttk.LabelFrame(right_frame, text="베팅 내역", padding="5")
        log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 베팅 내역 텍스트 위젯
        self.log_text = tk.Text(log_frame, height=8, width=40)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 베팅 내역 스크롤바
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

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
            
            # 베팅 시작 회차 이후의 결과에 대해서만 승리 여부 확인
            if self.betting_start_round and int(round_num) >= int(self.betting_start_round):
                round_info = self.rounds.get(round_num)
                if round_info:
                    # 총 베팅금과 당첨금을 비교하여 실제 이익이 있는지 확인
                    total_win = round_info.win_amount
                    total_bet = round_info.total_bet
                    net_profit = total_win - total_bet
                    
                    if net_profit > 0:  # 실제 이익이 있을 때만 별표시
                        result = (f"★{round_num}", direction, line, parity, 
                                f"{total_bet:,}", f"+{net_profit:,}")
                    else:
                        result = (round_num, direction, line, parity, 
                                f"{total_bet:,}", f"{net_profit:,}")
                else:
                    result = (round_num, direction, line, parity, "-", "-")
            else:
                result = (round_num, direction, line, parity, "-", "-")
            
            item = self.result_tree.insert('', 'end', values=result)
            
            # 적중 결과에 따라 태그 설정 (베팅 시작 회차 이후만)
            if self.betting_start_round and int(round_num) >= int(self.betting_start_round):
                round_info = self.rounds.get(round_num)
                if round_info:
                    # 총 베팅금과 당첨금을 비교하여 실제 이익이 있는지 확인
                    total_win = round_info.win_amount
                    total_bet = round_info.total_bet
                    net_profit = total_win - total_bet
                    
                    if net_profit > 0:  # 실제 이익이 있을 때만 파란색 표시
                        self.result_tree.tag_configure('winner', foreground='blue')
                        self.result_tree.item(item, tags=('winner',))
                    elif net_profit < 0:  # 손실일 때는 빨간색 표시
                        self.result_tree.tag_configure('loser', foreground='red')
                        self.result_tree.item(item, tags=('loser',))

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
        mode = self.betting_mode.get()
        
        if mode == "rotation":  # 로테이션 모드
            pattern_type, pick1, pick2 = self.betting_patterns[self.current_pattern_index]
            self.current_pattern_index = (self.current_pattern_index + 1) % 3
            
            if pattern_type == 'direction_parity':
                predicted_direction = pick1  # 좌
                predicted_line = None
                predicted_parity = pick2    # 홀
            elif pattern_type == 'direction_line':
                predicted_direction = pick1  # 좌
                predicted_line = pick2      # 3
                predicted_parity = None
            else:  # line_parity
                predicted_direction = None
                predicted_line = pick1      # 3
                predicted_parity = pick2    # 홀
            
        else:  # 선택 모드
            pick1 = self.selected_picks['pick1'].get()
            pick2 = self.selected_picks['pick2'].get()
            
            # 선택된 값에 따라 예측값 설정
            predicted_direction = pick1 if pick1 in ['좌', '우'] else None
            predicted_line = pick1 if pick1 in ['3', '4'] else None
            predicted_parity = pick1 if pick1 in ['홀', '짝'] else None
            
            if predicted_direction is None:
                predicted_direction = pick2 if pick2 in ['좌', '우'] else None
            if predicted_line is None:
                predicted_line = pick2 if pick2 in ['3', '4'] else None
            if predicted_parity is None:
                predicted_parity = pick2 if pick2 in ['홀', '짝'] else None
            
            pattern_type = "custom"
        
        # 헤지 베팅 예측 (우+4줄)
        hedge_direction = '우'
        hedge_line = '4'
        
        # 예측 정보 저장
        self.next_prediction = (predicted_direction, predicted_line, predicted_parity, hedge_direction, hedge_line)
        
        # 다음 회차 정보 생성 및 베팅 기록
        if self.next_round:
            round_info = RoundInfo(self.next_round)
            round_info.pattern_type = pattern_type
            
            # 단식 베팅 기록
            if predicted_direction:
                round_info.bets['singles'].append(('direction', predicted_direction, self.current_bet))
            if predicted_line:
                round_info.bets['singles'].append(('line', predicted_line, self.current_bet))
            if predicted_parity:
                round_info.bets['singles'].append(('parity', predicted_parity, self.current_bet))
            
            # 조합 베팅 기록
            round_info.bets['combo'] = (hedge_direction, hedge_line, self.hedge_bet)
            
            # 총 베팅액 계산
            round_info.total_bet = (self.current_bet * 2) + self.hedge_bet
            
            self.rounds[self.next_round] = round_info
        
        # 예측 표시 업데이트
        self.prediction_labels['방향'].config(text=f"예상 방향: {predicted_direction if predicted_direction else '-'}")
        self.prediction_labels['줄수'].config(text=f"예상 줄수: {predicted_line if predicted_line else '-'}")
        self.prediction_labels['홀짝'].config(text=f"예상 홀짝: {predicted_parity if predicted_parity else '-'}")

    def check_prediction_result(self, actual_result):
        if not self.current_prediction or not self.current_round:
            return
            
        round_num, actual_direction, actual_line, actual_parity = actual_result
        round_info = self.rounds.get(round_num)
        
        if not round_info:
            logging.error(f"{round_num}회차 정보를 찾을 수 없습니다.")
            return
            
        # 결과 저장
        round_info.result = (actual_direction, actual_line, actual_parity)
        
        # 단식 베팅 결과 확인 (각 픽별로 독립적 계산)
        win_amount = 0
        correct_picks = 0
        total_picks = len(round_info.bets['singles'])
        pick_results = []  # 각 픽별 결과 저장
        
        for bet_type, bet_value, bet_amount in round_info.bets['singles']:
            actual_value = {
                'direction': actual_direction,
                'line': actual_line,
                'parity': actual_parity
            }[bet_type]
            
            is_win = bet_value == actual_value
            if is_win:
                correct_picks += 1
                pick_win_amount = bet_amount * self.odds['single']
                win_amount += pick_win_amount
                pick_results.append({
                    'type': bet_type,
                    'value': bet_value,
                    'result': '적중',
                    'bet_amount': bet_amount,
                    'win_amount': pick_win_amount,
                    'profit': pick_win_amount  # 베팅금은 이미 차감되었으므로 당첨금만 이익으로 계산
                })
            else:
                pick_results.append({
                    'type': bet_type,
                    'value': bet_value,
                    'result': '미적중',
                    'bet_amount': bet_amount,
                    'win_amount': 0,
                    'profit': 0  # 베팅금은 이미 차감되었으므로 0으로 설정
                })
        
        # 헤지 베팅 결과 확인
        hedge_result = None
        if round_info.bets['combo']:
            hedge_direction, hedge_line, hedge_amount = round_info.bets['combo']
            hedge_win = (actual_direction == hedge_direction and actual_line == hedge_line)
            if hedge_win:
                hedge_win_amount = hedge_amount * self.odds['combination']
                win_amount += hedge_win_amount
                hedge_result = {
                    'result': '적중',
                    'bet_amount': hedge_amount,
                    'win_amount': hedge_win_amount,
                    'profit': hedge_win_amount  # 베팅금은 이미 차감되었으므로 당첨금만 이익으로 계산
                }
            else:
                hedge_result = {
                    'result': '미적중',
                    'bet_amount': hedge_amount,
                    'win_amount': 0,
                    'profit': 0  # 베팅금은 이미 차감되었으므로 0으로 설정
                }
        
        # 결과 정보 업데이트
        round_info.correct_picks = correct_picks
        round_info.total_picks = total_picks
        round_info.win_amount = win_amount
        round_info.profit = win_amount  # 베팅금은 이미 차감되었으므로 당첨금만 이익으로 계산
        
        # 자산 업데이트 (당첨금만 추가)
        self.current_asset += round_info.profit
        self.total_profit = self.current_asset - self.initial_asset
        
        # 승패 기록
        if (total_picks == 2 and correct_picks == 2) or (hedge_result and hedge_result['result'] == '적중'):
            self.win_count += 1
            self.current_bet = self.base_bet
        else:
            self.lose_count += 1
            # 연패시에도 단식 베팅을 고정하여 위험 관리 (베팅 증액 로직 제거)
            self.current_bet = self.base_bet
        
        # 결과 로깅
        pattern_desc = {
            'direction_parity': '좌+홀',
            'direction_line': '좌+3',
            'line_parity': '3+홀'
        }[round_info.pattern_type]
        
        # 상세 결과 로그 생성
        self.add_log(f"\n{round_num}회차 결과 [{pattern_desc}]")
        
        # 단식 베팅 결과
        for pick in pick_results:
            type_names = {'direction': '방향', 'line': '줄수', 'parity': '홀짝'}
            self.add_log(f"- {type_names[pick['type']]}({pick['value']}): {pick['result']} "
                        f"(베팅: {pick['bet_amount']:,}원, "
                        f"당첨: {pick['win_amount']:,}원)")
        
        # 헤지 베팅 결과
        if hedge_result:
            self.add_log(f"- 헤지(우+4줄): {hedge_result['result']} "
                        f"(베팅: {hedge_result['bet_amount']:,}원, "
                        f"당첨: {hedge_result['win_amount']:,}원)")
        
        # 최종 결과 (당첨금만 표시)
        self.add_log(f"=== 최종 결과: 당첨금 {round_info.win_amount:,}원 "
                    f"(단식 {correct_picks}/{total_picks}개 적중) ===\n")
        
        # 자산 정보 업데이트
        total_games = self.win_count + self.lose_count
        win_rate = (self.win_count / total_games * 100) if total_games > 0 else 0
        
        self.asset_labels['현재자산'].config(text=f"현재자산: {self.current_asset:,}원")
        self.asset_labels['총수익'].config(text=f"총수익: {self.total_profit:,}원")
        self.asset_labels['승률'].config(text=f"승률: {win_rate:.1f}% ({self.win_count}승 {self.lose_count}패)")
        self.asset_labels['현재베팅'].config(text=f"단식 베팅: {self.current_bet:,}원 × 2, 조합 베팅: {self.hedge_bet:,}원")

    def get_consecutive_losses(self):
        consecutive_losses = 0
        for result in self.game_results:
            round_num = result[0]
            if int(round_num) >= int(self.betting_start_round):
                # 승패 여부 확인 로직
                if self.is_loss(result):
                    consecutive_losses += 1
                else:
                    break
        return consecutive_losses

    def is_loss(self, result):
        # 승패 판정 로직
        _, direction, line, parity = result
        correct_picks = 0
        total_picks = 2  # 항상 2픽 베팅
        
        pattern_type = self.betting_patterns[(self.current_pattern_index - 2) % 3][0]
        if pattern_type == 'direction_parity':
            if direction == '좌':
                correct_picks += 1
            if parity == '홀':
                correct_picks += 1
        elif pattern_type == 'direction_line':
            if direction == '좌':
                correct_picks += 1
            if line == '3':
                correct_picks += 1
        else:  # line_parity
            if line == '3':
                correct_picks += 1
            if parity == '홀':
                correct_picks += 1
        
        hedge_win = (direction == '우' and line == '4')
        return correct_picks < 2 and not hedge_win

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
                
                # 첫 실행시 처리
                if is_first_update:
                    logging.info("첫 실행 감지, 다음 회차 베팅 준비")
                    self.current_round = round_num
                    self.next_round = str(int(round_num) + 1)
                    self.betting_start_round = self.next_round
                    
                    # 게임 결과 업데이트
                    self.game_results.insert(0, new_result)
                    if len(self.game_results) > 20:
                        self.game_results = self.game_results[:20]
                    
                    self.update_result_tree()
                    self.update_stats()
                    
                    # 다음 회차 예측 및 베팅
                    self.update_prediction()
                    self.current_prediction = self.next_prediction
                    
                    # 베팅 금액 차감 및 로그 기록
                    total_bet = (self.current_bet * 2) + self.hedge_bet
                    self.current_asset -= total_bet
                    self.total_profit = self.current_asset - self.initial_asset
                    
                    # 자산 정보 업데이트
                    self.asset_labels['현재자산'].config(text=f"현재자산: {self.current_asset:,}원")
                    self.asset_labels['총수익'].config(text=f"총수익: {self.total_profit:,}원")
                    
                    # 베팅 내역 로그
                    single_bets = []
                    if self.next_prediction[0]:  # direction
                        single_bets.append(f"방향({self.next_prediction[0]})")
                    if self.next_prediction[1]:  # line
                        single_bets.append(f"줄수({self.next_prediction[1]})")
                    if self.next_prediction[2]:  # parity
                        single_bets.append(f"홀짝({self.next_prediction[2]})")
                    
                    self.add_log(f"=== {self.next_round}회차 베팅 시작 ===")
                    self.add_log(f"{self.next_round}회차 단식베팅: {' + '.join(single_bets)} - 각 {self.current_bet:,}원")
                    self.add_log(f"{self.next_round}회차 조합베팅: 우+4줄 - {self.hedge_bet:,}원")
                
                # 새로운 회차 데이터 처리
                elif self.current_round != round_num:
                    logging.info(f"새로운 회차 발견: {round_num} (이전: {self.current_round})")
                    
                    # 이전 예측 결과 확인
                    if self.current_prediction:
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
                    
                    # 다음 회차 예측 및 베팅
                    self.current_prediction = self.next_prediction
                    self.next_prediction = None
                    self.update_prediction()
                    
                    # 베팅 금액 차감 및 로그 기록
                    total_bet = (self.current_bet * 2) + self.hedge_bet
                    self.current_asset -= total_bet
                    self.total_profit = self.current_asset - self.initial_asset
                    
                    # 자산 정보 업데이트
                    self.asset_labels['현재자산'].config(text=f"현재자산: {self.current_asset:,}원")
                    self.asset_labels['총수익'].config(text=f"총수익: {self.total_profit:,}원")
                    
                    # 베팅 내역 로그
                    single_bets = []
                    if self.next_prediction[0]:  # direction
                        single_bets.append(f"방향({self.next_prediction[0]})")
                    if self.next_prediction[1]:  # line
                        single_bets.append(f"줄수({self.next_prediction[1]})")
                    if self.next_prediction[2]:  # parity
                        single_bets.append(f"홀짝({self.next_prediction[2]})")
                    
                    self.add_log(f"{self.next_round}회차 단식베팅: {' + '.join(single_bets)} - 각 {self.current_bet:,}원")
                    self.add_log(f"{self.next_round}회차 조합베팅: 우+4줄 - {self.hedge_bet:,}원")
                
                current_time = datetime.now().strftime("%H:%M:%S")
                self.status_label.config(text=f"마지막 업데이트: {current_time} (회차: {round_num})")
                
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
