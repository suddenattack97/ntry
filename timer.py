from datetime import datetime, timedelta
import time

# JavaScript config를 Python dictionary로 변환
config = {
    'powerball': {'diffSec': 0, 'returnMinute': 5, 'countDownDiff': (1000 * 60 * 0) + (1000 * 25)},
    'power_ladder': {'diffSec': 29, 'returnMinute': 5, 'countDownDiff': 0},
    'speedkeno': {'diffSec': 0, 'returnMinute': 5, 'countDownDiff': 1000 * 175},
    'keno_ladder': {'diffSec': 0, 'returnMinute': 5, 'countDownDiff': 1000 * 175}
}

def get_timer_remaining_time(game_type='power_ladder'):
    # config에서 게임 설정 가져오기
    game_config = config[game_type]
    offset_seconds = game_config['diffSec']
    return_minute = game_config['returnMinute']
    countdown_diff = game_config['countDownDiff'] / 1000  # milliseconds to seconds
    
    while True:
        # 현재 시간 가져오기
        current_time = datetime.now()
        
        # 현재 시간에서 오프셋과 카운트다운 차이를 적용하여 타이머 계산
        adjusted_time = current_time + timedelta(seconds=offset_seconds + countdown_diff)
        
        # returnMinute 값을 기준으로 주기 계산 (분 단위를 초로 변환)
        cycle_seconds = return_minute * 60
        elapsed_seconds = (adjusted_time.minute * 60 + adjusted_time.second) % cycle_seconds
        remaining_time = cycle_seconds - elapsed_seconds

        # 남은 시간을 분과 초로 변환
        remaining_minutes = remaining_time // 60
        remaining_seconds = remaining_time % 60

        print(f"남은 시간: {remaining_minutes}분 {remaining_seconds}초")
        
        # 1초 대기 후 다음 계산
        time.sleep(1)
        
        # 필요한 경우 반환값 사용
        # return remaining_minutes, remaining_seconds

# 타이머 실행
if __name__ == "__main__":
    get_timer_remaining_time('power_ladder')

