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
        self.root.title("MINSU")
        self.root.geometry("700x740")
        
        # 자산 및 베팅 정보 초기화
        self.initial_asset = 500000  # 초기 자산 50만원
        self.current_asset = self.initial_asset
        self.base_bet = 30000  # 기본 베팅 금액 (단식 각각 3만원)
        self.current_bet = self.base_bet
        self.hedge_bet = 20000  # 부분 헤징: 1픽 적중시 손실 -22,100원, 0픽+조합 성공시 -8,000원
        self.total_profit = 0
        self.win_count = 0
        self.lose_count = 0
        self.total_net_profit = 0  # 순수익 합계 추가
        
        # 베팅 모드 설정
        self.betting_mode = tk.StringVar(value="rotation")  # 기본값: 로테이션
        self.betting_method = tk.StringVar(value="method1")  # 기본값: 방법1
        self.selected_picks = {
            'pick1': tk.StringVar(value='좌'),
            'pick2': tk.StringVar(value='3'),
            'pick3': tk.StringVar(value='홀')
        }
        
        # 배당률 설정
        self.odds = {
            'single': 1.93,  # 단식 배당 (좌우/홀짝/3줄4줄)
            'combination': 3.6  # 조합 배당 (좌우+3줄4줄)
        }
        
        # 베팅 패턴 (3단계 로테이션)
        self.betting_patterns = [
            ('pattern1', '좌', '3', '홀'),  # 1단계: 좌+3+홀
            ('pattern2', '좌', '3', '짝'),  # 2단계: 좌+3+짝
            ('pattern3', '좌', '4', '홀'),  # 3단계: 좌+4+홀
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
        
        # 베팅 방법별 금액 설정
        self.betting_methods = {
            'method1': {  # 전체 단식 금액 축소
                'single_bet': 20000,  # 단식 각 2만원
                'hedge_bet': 15000,   # 조합 1.5만원
                'picks_count': 3      # 3픽 고정
            },
            'method2': {  # 픽별 가중치
                'single_bet_a': 30000,  # 주력픽 3만원
                'single_bet_bc': 20000, # 나머지 픽 2만원
                'hedge_bet': 15000,     # 조합 1.5만원
                'picks_count': 3        # 3픽 고정
            },
            'method3': {  # 2픽 + 찬스픽
                'single_bet': 25000,    # 기본 2픽 각 2.5만원
                'chance_bet': 25000,    # 찬스픽 2.5만원
                'hedge_bet': 15000,     # 조합 1.5만원
                'picks_count': 2        # 기본 2픽 (찬스픽 추가 가능)
            },
            'method4': {  # 다중 조합
                'single_bet': 25000,    # 단식 각 2.5만원
                'hedge_bet1': 10000,    # 주 조합 1만원
                'hedge_bet2': 5000,     # 부 조합 5천원
                'picks_count': 3        # 3픽 고정
            },
            'method5': {  # 시스템 마틴
                'base_bet': 5000,       # 기본 배팅 금액
                'martin_steps': [5000, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000],  # 10단계 마틴
                'current_step': 0,      # 현재 마틴 단계
                'picks_count': 3,       # 3픽 고정
                'use_hedge': False      # 조합 베팅 사용 안함
            }
        }
        
        # 데이터 업데이트 시작
        self.update_data()

        # 베팅 모드와 방법 변경 이벤트 바인딩
        self.betting_mode.trace_add("write", self.on_betting_change)
        self.betting_method.trace_add("write", self.on_betting_change)
        self.selected_picks['pick3'].trace_add("write", self.on_betting_change)

    def create_asset_display(self):
        # 자산 정보 표시 프레임
        asset_frame = ttk.LabelFrame(self.main_frame, text="내 정보", padding="5")
        asset_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 자산 정보 레이블
        self.asset_labels = {
            '초기자산': ttk.Label(asset_frame, text=f"초기자산: {self.initial_asset:,}원"),
            '현재자산': ttk.Label(asset_frame, text=f"현재자산: {self.current_asset:,}원"),
            '총수익': ttk.Label(asset_frame, text=f"총수익: {self.total_profit:,}원"),
            '순수익합계': ttk.Label(asset_frame, text=f"순수익 합계: {self.total_net_profit:,}원"),
            '승률': ttk.Label(asset_frame, text="승률: 0%"),
            '현재베팅': ttk.Label(asset_frame, text="현재베팅: -")
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
        
        # 왼쪽 프레임 (트리뷰와 베팅내역용)
        left_frame = ttk.Frame(result_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 오른쪽 프레임 (베팅 모드와 설정용)
        right_frame = ttk.Frame(result_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.N, tk.S), padx=10)
        
        # 결과 표시 트리뷰
        columns = ('회차', '방향', '줄수', '홀짝', '베팅금', '순이익')
        self.result_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=10)
        
        # 컬럼 설정
        total_width = 0
        for col in columns:
            self.result_tree.heading(col, text=col)
            if col in ['베팅금', '순이익']:
                width = 80
                self.result_tree.column(col, width=width, anchor='center')
            else:
                width = 70
                self.result_tree.column(col, width=width, anchor='center')
            total_width += width
        
        # 트리뷰 스타일 설정
        style = ttk.Style()
        style.configure("Winner.Treeview.Row", background="lightgreen")
        
        # 트리뷰 스크롤바
        tree_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        # 트리뷰 배치
        self.result_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # 베팅 내역 프레임
        log_frame = ttk.LabelFrame(left_frame, text="베팅 내역", padding="5")
        log_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 베팅 내역 텍스트 위젯 (너비를 트리뷰와 동일하게 설정)
        char_width = total_width // 7  # 픽셀을 문자 너비로 대략 변환 (평균 폰트 너비가 약 7픽셀이라 가정)
        self.log_text = tk.Text(log_frame, height=8, width=char_width)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 베팅 내역 스크롤바
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        # 베팅 모드 선택 프레임 (오른쪽에 배치)
        mode_frame = ttk.LabelFrame(right_frame, text="베팅 모드", padding="5")
        mode_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # 로테이션/선택 모드
        ttk.Radiobutton(mode_frame, text="로테이션", variable=self.betting_mode, 
                       value="rotation").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(mode_frame, text="선택", variable=self.betting_mode, 
                       value="custom").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        
        # 베팅 방법 선택
        method_frame = ttk.LabelFrame(right_frame, text="베팅 방법", padding="5")
        method_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Radiobutton(method_frame, text="방법1: 전체 단식 축소", variable=self.betting_method, 
                       value="method1").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(method_frame, text="방법2: 픽별 가중치", variable=self.betting_method, 
                       value="method2").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(method_frame, text="방법3: 2픽+찬스픽", variable=self.betting_method, 
                       value="method3").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(method_frame, text="방법4: 다중 조합", variable=self.betting_method, 
                       value="method4").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Radiobutton(method_frame, text="방법5: 시스템 마틴", variable=self.betting_method, 
                       value="method5").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        
        # 선택 모드 콤보박스 프레임
        combo_frame = ttk.LabelFrame(right_frame, text="선택 설정", padding="5")
        combo_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # 세 개의 픽 선택
        ttk.Label(combo_frame, text="첫번째 픽:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Combobox(combo_frame, textvariable=self.selected_picks['pick1'], 
                    values=['좌', '우', '3', '4', '홀', '짝'], 
                    state='readonly', width=5).grid(row=0, column=1, padx=5)
        
        ttk.Label(combo_frame, text="두번째 픽:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Combobox(combo_frame, textvariable=self.selected_picks['pick2'], 
                    values=['좌', '우', '3', '4', '홀', '짝'], 
                    state='readonly', width=5).grid(row=1, column=1, padx=5)
        
        ttk.Label(combo_frame, text="세번째 픽:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Combobox(combo_frame, textvariable=self.selected_picks['pick3'], 
                    values=['좌', '우', '3', '4', '홀', '짝', '없음'], 
                    state='readonly', width=5).grid(row=2, column=1, padx=5)

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
        method = self.betting_method.get()
        method_config = self.betting_methods[method]
        
        # 현재 베팅 정보 업데이트
        if method == 'method5':  # 시스템 마틴
            current_bet = method_config['martin_steps'][method_config['current_step']]
            self.asset_labels['현재베팅'].config(text=f"단식 베팅: {current_bet:,}원 × 3 (마틴 {method_config['current_step'] + 1}단계)")
        elif method == 'method1':
            self.asset_labels['현재베팅'].config(text=f"단식 베팅: {method_config['single_bet']:,}원 × 3, 조합 베팅: {method_config['hedge_bet']:,}원")
        elif method == 'method2':
            self.asset_labels['현재베팅'].config(text=f"주력픽: {method_config['single_bet_a']:,}원, 일반픽: {method_config['single_bet_bc']:,}원 × 2, 조합: {method_config['hedge_bet']:,}원")
        elif method == 'method3':
            if self.selected_picks['pick3'].get() != '없음':
                self.asset_labels['현재베팅'].config(text=f"기본픽: {method_config['single_bet']:,}원 × 2, 찬스픽: {method_config['chance_bet']:,}원, 조합: {method_config['hedge_bet']:,}원")
            else:
                self.asset_labels['현재베팅'].config(text=f"기본픽: {method_config['single_bet']:,}원 × 2, 조합: {method_config['hedge_bet']:,}원")
        else:  # method4
            self.asset_labels['현재베팅'].config(text=f"단식: {method_config['single_bet']:,}원 × 3, 조합1: {method_config['hedge_bet1']:,}원, 조합2: {method_config['hedge_bet2']:,}원")
        
        if mode == "rotation":  # 로테이션 모드
            pattern_type, predicted_direction, predicted_line, predicted_parity = self.betting_patterns[self.current_pattern_index]
            self.current_pattern_index = (self.current_pattern_index + 1) % len(self.betting_patterns)
            
        else:  # 선택 모드
            pick1 = self.selected_picks['pick1'].get()
            pick2 = self.selected_picks['pick2'].get()
            pick3 = self.selected_picks['pick3'].get()
            
            predicted_direction = None
            predicted_line = None
            predicted_parity = None
            
            # 각 픽의 유형 확인 및 할당
            for pick in [pick1, pick2, pick3]:
                if pick == '없음':
                    continue
                if pick in ['좌', '우'] and predicted_direction is None:
                    predicted_direction = pick
                elif pick in ['3', '4'] and predicted_line is None:
                    predicted_line = pick
                elif pick in ['홀', '짝'] and predicted_parity is None:
                    predicted_parity = pick
        
        # 헤지 베팅 예측
        if method == 'method4':  # 다중 조합인 경우
            hedge_direction = '우'
            hedge_line = '4'
            hedge_direction2 = '우'
            hedge_parity = '짝'
        else:
            hedge_direction = '우'
            hedge_line = '4'
            hedge_direction2 = None
            hedge_parity = None
        
        # 예측 정보 저장
        self.next_prediction = (predicted_direction, predicted_line, predicted_parity, 
                              hedge_direction, hedge_line, hedge_direction2, hedge_parity)
        
        # 다음 회차 정보 생성 및 베팅 기록
        if self.next_round:
            round_info = RoundInfo(self.next_round)
            round_info.pattern_type = pattern_type if mode == "rotation" else "custom"
            
            # 베팅 방법에 따른 금액 설정
            if method == 'method5':  # 시스템 마틴
                current_bet = method_config['martin_steps'][method_config['current_step']]
                if predicted_direction:
                    round_info.bets['singles'].append(('direction', predicted_direction, current_bet))
                if predicted_line:
                    round_info.bets['singles'].append(('line', predicted_line, current_bet))
                if predicted_parity:
                    round_info.bets['singles'].append(('parity', predicted_parity, current_bet))
                # 시스템 마틴은 조합 베팅 없음
                round_info.bets['combo'] = None

                # 베팅 내역 로그
                single_bets = []
                if predicted_direction:
                    single_bets.append(f"방향({predicted_direction})")
                if predicted_line:
                    single_bets.append(f"줄수({predicted_line})")
                if predicted_parity:
                    single_bets.append(f"홀짝({predicted_parity})")
                
                self.add_log(f"=== {self.next_round}회차 베팅 시작 ===")
                self.add_log(f"{self.next_round}회차 단식베팅: {' + '.join(single_bets)} - 각 {current_bet:,}원 (마틴 {method_config['current_step'] + 1}단계)")

            elif method == 'method1':
                single_bet = method_config['single_bet']
                if predicted_direction:
                    round_info.bets['singles'].append(('direction', predicted_direction, single_bet))
                if predicted_line:
                    round_info.bets['singles'].append(('line', predicted_line, single_bet))
                if predicted_parity:
                    round_info.bets['singles'].append(('parity', predicted_parity, single_bet))
                
                round_info.bets['combo'] = (hedge_direction, hedge_line, method_config['hedge_bet'])
                
            elif method == 'method2':  # 픽별 가중치
                # 첫 번째 픽은 높은 금액
                if predicted_direction:
                    round_info.bets['singles'].append(('direction', predicted_direction, method_config['single_bet_a']))
                # 나머지 픽은 낮은 금액
                if predicted_line:
                    round_info.bets['singles'].append(('line', predicted_line, method_config['single_bet_bc']))
                if predicted_parity:
                    round_info.bets['singles'].append(('parity', predicted_parity, method_config['single_bet_bc']))
                
                round_info.bets['combo'] = (hedge_direction, hedge_line, method_config['hedge_bet'])
                
            elif method == 'method3':  # 2픽 + 찬스픽
                # 기본 2픽
                if predicted_direction:
                    round_info.bets['singles'].append(('direction', predicted_direction, method_config['single_bet']))
                if predicted_line:
                    round_info.bets['singles'].append(('line', predicted_line, method_config['single_bet']))
                # 찬스픽 (있는 경우만)
                if predicted_parity and pick3 != '없음':
                    round_info.bets['singles'].append(('parity', predicted_parity, method_config['chance_bet']))
                
                round_info.bets['combo'] = (hedge_direction, hedge_line, method_config['hedge_bet'])
                
            else:  # method4: 다중 조합
                if predicted_direction:
                    round_info.bets['singles'].append(('direction', predicted_direction, method_config['single_bet']))
                if predicted_line:
                    round_info.bets['singles'].append(('line', predicted_line, method_config['single_bet']))
                if predicted_parity:
                    round_info.bets['singles'].append(('parity', predicted_parity, method_config['single_bet']))
                
                # 두 개의 조합 베팅
                round_info.bets['combo'] = (hedge_direction, hedge_line, method_config['hedge_bet1'])
                round_info.bets['combo2'] = (hedge_direction2, None, hedge_parity, method_config['hedge_bet2'])
            
            # 총 베팅액 계산
            round_info.total_bet = sum(amount for _, _, amount in round_info.bets['singles'])
            if round_info.bets['combo']:
                round_info.total_bet += round_info.bets['combo'][2]
            if method == 'method4' and round_info.bets.get('combo2'):
                round_info.total_bet += round_info.bets['combo2'][3]
            
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
        method = self.betting_method.get()
        
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
                    'profit': hedge_win_amount
                }
            else:
                hedge_result = {
                    'result': '미적중',
                    'bet_amount': hedge_amount,
                    'win_amount': 0,
                    'profit': 0
                }
        
        # 다중 조합 결과 확인 (method4)
        hedge_result2 = None
        if method == 'method4' and round_info.bets.get('combo2'):
            hedge_direction2, _, hedge_parity, hedge_amount2 = round_info.bets['combo2']
            hedge_win2 = (actual_direction == hedge_direction2 and actual_parity == hedge_parity)
            if hedge_win2:
                hedge_win_amount2 = hedge_amount2 * self.odds['combination']
                win_amount += hedge_win_amount2
                hedge_result2 = {
                    'result': '적중',
                    'bet_amount': hedge_amount2,
                    'win_amount': hedge_win_amount2,
                    'profit': hedge_win_amount2
                }
            else:
                hedge_result2 = {
                    'result': '미적중',
                    'bet_amount': hedge_amount2,
                    'win_amount': 0,
                    'profit': 0
                }
        
        # 결과 정보 업데이트
        round_info.correct_picks = correct_picks
        round_info.total_picks = total_picks
        round_info.win_amount = win_amount
        round_info.profit = win_amount  # 베팅금은 이미 차감되었으므로 당첨금만 이익으로 계산
        
        # 순수익 계산 및 업데이트
        net_profit = win_amount - round_info.total_bet
        self.total_net_profit += net_profit
        
        # 자산 업데이트 (당첨금만 추가)
        self.current_asset += round_info.profit
        self.total_profit = self.current_asset - self.initial_asset
        
        # 승패 기록 및 마틴 단계 조정
        if method == 'method5':  # 시스템 마틴
            if correct_picks >= 2:  # 2개 이상 맞추면 승리
                self.win_count += 1
                # 승리시 마틴 단계 감소 (최소 0단계)
                self.betting_methods[method]['current_step'] = max(0, self.betting_methods[method]['current_step'] - 1)
            else:
                self.lose_count += 1
                # 패배시 마틴 단계 증가 (최대 9단계, 0-based index)
                self.betting_methods[method]['current_step'] = min(9, self.betting_methods[method]['current_step'] + 1)
        else:
            if (total_picks == 2 and correct_picks == 2) or (hedge_result and hedge_result['result'] == '적중'):
                self.win_count += 1
                self.current_bet = self.base_bet
            else:
                self.lose_count += 1
                self.current_bet = self.base_bet
        
        # 결과 로깅
        pattern_desc = {
            'pattern1': '좌+3+홀',
            'pattern2': '좌+3+짝',
            'pattern3': '좌+4+홀',
            'custom': '선택모드'  # 선택 모드일 때의 패턴 설명 추가
        }.get(round_info.pattern_type, '알 수 없음')  # 패턴을 찾지 못할 경우 '알 수 없음' 반환
        
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
        self.asset_labels['순수익합계'].config(text=f"순수익 합계: {self.total_net_profit:,}원")
        self.asset_labels['승률'].config(text=f"승률: {win_rate:.1f}% ({self.win_count}승 {self.lose_count}패)")
        self.asset_labels['현재베팅'].config(text=f"현재베팅: -")

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
                    method = self.betting_method.get()
                    method_config = self.betting_methods[method]
                    
                    if method == 'method1':
                        total_bet = (method_config['single_bet'] * 3) + method_config['hedge_bet']
                    elif method == 'method2':
                        total_bet = method_config['single_bet_a'] + (method_config['single_bet_bc'] * 2) + method_config['hedge_bet']
                    elif method == 'method3':
                        total_bet = (method_config['single_bet'] * 2) + method_config['hedge_bet']
                        if self.selected_picks['pick3'].get() != '없음':
                            total_bet += method_config['chance_bet']
                    else:  # method4
                        total_bet = (method_config['single_bet'] * 3) + method_config['hedge_bet1'] + method_config['hedge_bet2']
                    
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
                    
                    # 베팅 방법에 따른 로그 출력
                    if method == 'method1':
                        self.add_log(f"{self.next_round}회차 단식베팅: {' + '.join(single_bets)} - 각 {method_config['single_bet']:,}원")
                        self.add_log(f"{self.next_round}회차 조합베팅: 우+4줄 - {method_config['hedge_bet']:,}원")
                    elif method == 'method2':
                        self.add_log(f"{self.next_round}회차 단식베팅(주력): {single_bets[0]} - {method_config['single_bet_a']:,}원")
                        self.add_log(f"{self.next_round}회차 단식베팅(일반): {' + '.join(single_bets[1:])} - 각 {method_config['single_bet_bc']:,}원")
                        self.add_log(f"{self.next_round}회차 조합베팅: 우+4줄 - {method_config['hedge_bet']:,}원")
                    elif method == 'method3':
                        self.add_log(f"{self.next_round}회차 기본베팅: {' + '.join(single_bets[:2])} - 각 {method_config['single_bet']:,}원")
                        if len(single_bets) > 2:
                            self.add_log(f"{self.next_round}회차 찬스베팅: {single_bets[2]} - {method_config['chance_bet']:,}원")
                        self.add_log(f"{self.next_round}회차 조합베팅: 우+4줄 - {method_config['hedge_bet']:,}원")
                    else:  # method4
                        self.add_log(f"{self.next_round}회차 단식베팅: {' + '.join(single_bets)} - 각 {method_config['single_bet']:,}원")
                        self.add_log(f"{self.next_round}회차 조합1: 우+4줄 - {method_config['hedge_bet1']:,}원")
                        self.add_log(f"{self.next_round}회차 조합2: 우+짝 - {method_config['hedge_bet2']:,}원")
                
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
                    method = self.betting_method.get()
                    method_config = self.betting_methods[method]
                    
                    if method == 'method1':
                        total_bet = (method_config['single_bet'] * 3) + method_config['hedge_bet']
                    elif method == 'method2':
                        total_bet = method_config['single_bet_a'] + (method_config['single_bet_bc'] * 2) + method_config['hedge_bet']
                    elif method == 'method3':
                        total_bet = (method_config['single_bet'] * 2) + method_config['hedge_bet']
                        if self.selected_picks['pick3'].get() != '없음':
                            total_bet += method_config['chance_bet']
                    else:  # method4
                        total_bet = (method_config['single_bet'] * 3) + method_config['hedge_bet1'] + method_config['hedge_bet2']
                    
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
                    
                    self.add_log(f"{self.next_round}회차 단식베팅: {' + '.join(single_bets)} - 각 {method_config['single_bet']:,}원")
                    self.add_log(f"{self.next_round}회차 조합베팅: 우+4줄 - {method_config['hedge_bet']:,}원")
                
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

    def on_betting_change(self, *args):
        """베팅 모드나 방법이 변경될 때 호출되는 함수"""
        method = self.betting_method.get()
        method_config = self.betting_methods[method]
        
        # 현재 베팅 정보 업데이트
        if method == 'method5':  # 시스템 마틴
            current_bet = method_config['martin_steps'][method_config['current_step']]
            self.asset_labels['현재베팅'].config(text=f"단식 베팅: {current_bet:,}원 × 3 (마틴 {method_config['current_step'] + 1}단계)")
        elif method == 'method1':
            self.asset_labels['현재베팅'].config(text=f"단식 베팅: {method_config['single_bet']:,}원 × 3, 조합 베팅: {method_config['hedge_bet']:,}원")
        elif method == 'method2':
            self.asset_labels['현재베팅'].config(text=f"주력픽: {method_config['single_bet_a']:,}원, 일반픽: {method_config['single_bet_bc']:,}원 × 2, 조합: {method_config['hedge_bet']:,}원")
        elif method == 'method3':
            if self.selected_picks['pick3'].get() != '없음':
                self.asset_labels['현재베팅'].config(text=f"기본픽: {method_config['single_bet']:,}원 × 2, 찬스픽: {method_config['chance_bet']:,}원, 조합: {method_config['hedge_bet']:,}원")
            else:
                self.asset_labels['현재베팅'].config(text=f"기본픽: {method_config['single_bet']:,}원 × 2, 조합: {method_config['hedge_bet']:,}원")
        elif method == 'method4':
            self.asset_labels['현재베팅'].config(text=f"단식: {method_config['single_bet']:,}원 × 3, 조합1: {method_config['hedge_bet1']:,}원, 조합2: {method_config['hedge_bet2']:,}원")
        elif method == 'method5':
            self.asset_labels['현재베팅'].config(text=f"단식 베팅: {method_config['base_bet']:,}원 × 3 (마틴 {method_config['current_step'] + 1}단계)")

        # 다음 회차 베팅이 이미 있고, 결과가 아직 안 나왔다면 베팅 업데이트
        if self.next_round and self.next_prediction:
            # 이전 베팅 금액 환불
            if self.next_round in self.rounds:
                old_round_info = self.rounds[self.next_round]
                self.current_asset += old_round_info.total_bet
                
                # 베팅 내역 로그에 이전 베팅 취소 기록
                self.add_log(f"\n{self.next_round}회차 이전 베팅 취소")
                self.add_log(f"- 환불 금액: {old_round_info.total_bet:,}원")
            
            # 새로운 예측 및 베팅 정보 업데이트
            self.update_prediction()
            
            # 새 베팅 금액 차감
            if self.next_round in self.rounds:
                new_round_info = self.rounds[self.next_round]
                self.current_asset -= new_round_info.total_bet
                
                # 베팅 내역 로그에 새 베팅 기록
                self.add_log(f"\n{self.next_round}회차 베팅 방식 변경")
                if method == 'method5':
                    current_bet = method_config['martin_steps'][method_config['current_step']]
                    single_bets = []
                    if self.next_prediction[0]:  # direction
                        single_bets.append(f"방향({self.next_prediction[0]})")
                    if self.next_prediction[1]:  # line
                        single_bets.append(f"줄수({self.next_prediction[1]})")
                    if self.next_prediction[2]:  # parity
                        single_bets.append(f"홀짝({self.next_prediction[2]})")
                    self.add_log(f"- 단식베팅: {' + '.join(single_bets)} - 각 {current_bet:,}원 (마틴 {method_config['current_step'] + 1}단계)")
                else:
                    single_bets = []
                    if self.next_prediction[0]:  # direction
                        single_bets.append(f"방향({self.next_prediction[0]})")
                    if self.next_prediction[1]:  # line
                        single_bets.append(f"줄수({self.next_prediction[1]})")
                    if self.next_prediction[2]:  # parity
                        single_bets.append(f"홀짝({self.next_prediction[2]})")
                    
                    if method == 'method1':
                        self.add_log(f"- 단식베팅: {' + '.join(single_bets)} - 각 {method_config['single_bet']:,}원")
                        self.add_log(f"- 조합베팅: 우+4줄 - {method_config['hedge_bet']:,}원")
                    elif method == 'method2':
                        self.add_log(f"- 단식베팅(주력): {single_bets[0]} - {method_config['single_bet_a']:,}원")
                        self.add_log(f"- 단식베팅(일반): {' + '.join(single_bets[1:])} - 각 {method_config['single_bet_bc']:,}원")
                        self.add_log(f"- 조합베팅: 우+4줄 - {method_config['hedge_bet']:,}원")
                    elif method == 'method3':
                        self.add_log(f"- 기본베팅: {' + '.join(single_bets[:2])} - 각 {method_config['single_bet']:,}원")
                        if len(single_bets) > 2:
                            self.add_log(f"- 찬스베팅: {single_bets[2]} - {method_config['chance_bet']:,}원")
                        self.add_log(f"- 조합베팅: 우+4줄 - {method_config['hedge_bet']:,}원")
                    else:  # method4
                        self.add_log(f"- 단식베팅: {' + '.join(single_bets)} - 각 {method_config['single_bet']:,}원")
                        self.add_log(f"- 조합1: 우+4줄 - {method_config['hedge_bet1']:,}원")
                        self.add_log(f"- 조합2: 우+짝 - {method_config['hedge_bet2']:,}원")
                
                # 자산 정보 업데이트
                self.total_profit = self.current_asset - self.initial_asset
                self.asset_labels['현재자산'].config(text=f"현재자산: {self.current_asset:,}원")
                self.asset_labels['총수익'].config(text=f"총수익: {self.total_profit:,}원")

if __name__ == "__main__":
    root = tk.Tk()
    app = LadderGameGUI(root)
    root.mainloop()
