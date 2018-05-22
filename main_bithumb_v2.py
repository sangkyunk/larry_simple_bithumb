import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic
from PyQt5.QtCore import *
import datetime
####
import pybithumb
#import pykorbit
##
import time


# ---------------------------------------------------------------------------------------------------------------------
# Korbit으로 부터 현재가를 조회하는 스레드
# ---------------------------------------------------------------------------------------------------------------------
class InquiryWorker(QThread):
    # 사용자 정의 시그널 (float 값을 하나 전달)
    finished = pyqtSignal(float)

    # run 이라는 이름 변경할 수 없음
    def run(self):
        ####
        #btc_price = pykorbit.get_current_price("BTC")              # 비트코인 현재가 조회
        btc_price = pybithumb.get_current_price("BTC")              # 비트코인 현재가 조회
        #print("btc_price:", btc_price)
        ##

        if isinstance(btc_price, float):                                # 금액 조회가 정상적인 경우에만
            self.finished.emit(btc_price)                               # 일이 끝났음을 알려줌


# ---------------------------------------------------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------------------------------------------------
form_class = uic.loadUiType("window.ui")[0]
class MyWindow(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.range = None
        self.open = None
        self.target = None
        self.activate = False
        self.cur_btc_price = None

        self.email = None
        self.password = None
        self.key = None
        self.secret = None

        self.tableWidget.setRowCount(1)
        ####
        #self.create_korbit()
        self.create_bithumb()
        ##
        self.create_threads()
        print("create_thread finished")
        self.create_timers()
        print("create_timers finished")
        self.set_signal_slots()
        print("set_signal_slots finished")
        print("init finished")

    def create_korbit(self):
        self.read_secret()
        self.korbit = pykorbit.Korbit(self.email, self.password, self.key, self.secret)

    #### Bithumb 객체 만들어서 self.bithumb에 바인딩.
    def create_bithumb(self):
        self.read_secret()
        self.bithumb = pybithumb.Bithumb(self.key, self.secret)
        print("create_bithumb_finished")
        print(self.bithumb)
    ##

    def create_threads(self):
        self.inquiry_worker = InquiryWorker()
        self.inquiry_worker.finished.connect(self.display_cur_price)

    def create_timers(self):
        # 시간 출력 타이머
        self.time_timer = QTimer(self)
        self.time_timer.start(1000)
        self.time_timer.timeout.connect(self.display_cur_time)

        # 가격 조회 타이머
        self.price_timer = QTimer(self)
        self.price_timer.start(2000)
        self.price_timer.timeout.connect(self.inquiry_cur_price)

        # refresh token 갱신 타이머

        self.refresh_timer = QTimer(self)
        self.refresh_timer.start(1000 * 60 * 30)
        ####
        # bithumb에 대해서는 refresh_token이 구현되어있지 않음.
        self.refresh_timer.timeout.connect(self.refresh_token)
        ##

        # 매매를 위한 타이머
        self.trading_timer = QTimer(self)
        self.trading_timer.start(1000)
        self.trading_timer.timeout.connect(self.trading)

    def set_signal_slots(self):
        # 버튼 이벤트 추가하기
        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)

    def start(self):
        self.textEdit.insertPlainText("자동 매매 활성화\n")
        self.activate = True

    def stop(self):
        self.textEdit.insertPlainText("자동 매매 비활성화\n")
        self.activate = False

    def trading(self):
        #print("trading called")
        now = datetime.datetime.now()
        str_now = now.strftime("%H:%M:%S")                  # 현재 시간
        str_target = self.timeEdit.time().toString()          # 타겟 시간1
        target2 = self.timeEdit.time().addSecs(5)             # 타겟 시간2
        str_target2 = target2.toString()
        sell_target = self.timeEdit_2.time().toString()       # 매도 타겟 시간
        ####
        # korbit의 balances와 자료구조를 맞추어 주기 위한 수정
        #balances = self.korbit.get_balances()
        available_coin, in_use_coin, available_krw, in_use_krw = self.bithumb.get_balance("BTC")
        balances = {'btc': {'available': str(available_coin),
                            'trade_in_use': str(in_use_coin),
                            'withdrawal_in_use': '0'},
                    'krw': {'available': str(available_krw),
                            'trade_in_use': '0',
                            'withdrawal_in_use': str(in_use_krw)}
                    }
        #print('blanaces in trading(): ', balances)
        ##

        if self.activate is True:
            if str_now == str_target:
                self.set_open_range()
            elif str_now == str_target2 and self.target is None:
                self.set_open_range()
            elif str_now == sell_target:
                self.try_sell(balances)
            else:
                self.try_buy(balances)

    def try_buy(self, balances):
        if balances is not None:
            btc_balance = float(balances['btc']['available'])
            ####
            #krw_balance = int(balances['krw']['available'])
            krw_balance = int(float(balances['krw']['available'])) #bthumb은 끝에 .0이 붙어서...
            ##
        else:
            btc_balance = 0

        if self.target is not None and btc_balance == 0:
            if self.cur_btc_price is not None and self.cur_btc_price > self.target:
                ####
                # Korbit은 원화 금액을 주면 사주는데 빗섬은 단위를 줘야 하는 것 같아서
                # unit = (한화 잔고 - 한화 묶인 돈 - 거래수수료)/(현재가격)
                # 을 계산하여 사라고 넘김.
                # !!!! 테스트 해보지는 못했음!!!
                current_price = pybithumb.get_current_price("BTC")
                krw_amount = float(balances['krw']['avaliable']) - float(balances['krw']['withdrawal_in_use'])
                krw_amount -= self.bithumb.get_trading_fee()
                print("krw_amount, current_price:", krw_amount, current_price)
                # self.buy(krw_balance)
                self.buy(krw_amount/current_price)
                ##

    def try_sell(self, balances):
        if balances is not None:
            btc_balance = float(balances['btc']['available'])
        else:
            btc_balance = 0

        if btc_balance != 0:
            self.sell(btc_balance)


    #def buy(self, krw_balance):
    def buy(self, unit):
        # 원화 잔고 조회
        self.textEdit.insertPlainText("비트코인 시장가 매수\n")
        ####
        #self.korbit.buy_market_order("BTC", krw_balance)
        self.bithumb.buy_market_order("BTC", unit)
        ##
        self.tableWidget.setItem(0, 4, QTableWidgetItem("보유 중"))

    def sell(self, btc_balance):
        # 비트코인 잔고 조회
        self.textEdit.insertPlainText("비트코인 시장가 매도\n")
        ####
        #self.korbit.sell_market_order("BTC", btc_balance)
        self.bithumb.sell_market_order("BTC", btc_balance)
        ##
        self.tableWidget.setItem(0, 4, QTableWidgetItem("미보유 중"))

    def set_open_range(self):
        cur_time = QTime.currentTime().toString()
        self.textEdit.insertPlainText("시가/변동성 갱신 " + cur_time + "\n")

        try:
            ####
            #detail = pykorbit.get_market_detail("BTC")
            #if detail is not None:
            #    low, high, last, volume = detail
            #    self.range = (high - low) * 0.5
            #    self.open = last
            #    self.target = self.open + self.range

            # korbit과 bithumb의 get_market_detail("BTC")의 결과값의 구조가 다름
            detail = self.bithumb.get_market_detail("BTC")
            if detail is not None:
                low, high, avg, volume = detail
                self.range = (high - low) * 0.5
                # korbit의 get_market_detail의 세번째 리턴값이 closing price인데 반해,
                # bithumb의 get_market_detail은 세번째 리턴값이 average라서, closeing price는 지금 가격으로 대체
                self.open = pybithumb.get_current_price("BTC") # 지금 가격 불러오기
                print("self.open: ", self.open)
                self.target = self.open + self.range
            ##
        except:
            self.range = None
            self.open = None
            self.target = None
            self.textEdit.insertPlainText("시가/변동성 갱신 (실패) " + cur_time + "\n")
            print("시가/변동성 갱신 (실패) " + cur_time)

    def refresh_token(self):
        ####
        # pybithumb에는 정의되어 있지 않음.
        #self.korbit.renew_access_token()
        print("조대표님~~ please implement refresh_token()")
        ##

    def display_cur_time(self):
        now = datetime.datetime.now()
        str_time = now.strftime("%Y-%m-%d %H:%M:%S")

        if self.activate:
            state = " (자동 매매 활성화)"
        else:
            state = " (자동 매매 비활성화)"
        self.statusBar().showMessage(str_time + state)

    def inquiry_cur_price(self):
        #print("inquiry_cur_price called")
        self.inquiry_worker.start()

    @pyqtSlot(float)
    def display_cur_price(self, btc_price):
        #print("display_cur_price called")
        # 비트코인 현재가 저장
        self.cur_btc_price = btc_price
        #print("btc_price in display_cur_price:", self.cur_btc_price)
        name = QTableWidgetItem(str("BTC"))
        price = QTableWidgetItem(str(btc_price))
        self.tableWidget.setItem(0, 0, name)
        self.tableWidget.setItem(0, 1, price)

        # 시가 출력
        if self.open is not None:
            open = QTableWidgetItem(str(self.open))
            self.tableWidget.setItem(0, 2, open)

        # 목표가 출력
        if self.target is not None:
            target = QTableWidgetItem(str(self.target))
            self.tableWidget.setItem(0, 3, target)

    def read_secret(self):
        ####
        # secret_bithumb.con의 구조:
        # 첫째 줄: 이메일 (사용 안하니 아무 문자열이나...)
        # 둘째 줄: password (사용 안하니 아무 문자열이나...)
        # 셋째 줄: key (bithumb API 신청시 발급받은 것)
        # 넷째 줄: secret (bithumb API 신청시 발급받은 것)
        f = open("secret_bithumb.conf")
        lines = f.readlines()
        self.email, self.password, self.key, self.secret = (line.strip() for line in lines)
        f.close()
        #print(self.email)
        #print(self.password)
        #print(self.key)
        #print(self.secret)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MyWindow()
    win.show()
    app.exec_()
