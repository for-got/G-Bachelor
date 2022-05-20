#!/bin/python3
# coding: utf-8
import csv
import json
import os
import re
import subprocess
import time
import wave
from urllib import parse

import cv2  # apt install python3-opencv
import pyecharts.options as opts
from flask import Flask, jsonify, request, render_template, Response
from markupsafe import Markup
from pyecharts.charts import Line
from pyecharts.globals import CurrentConfig
from smbus2 import SMBus
import RPi.GPIO as GPIO

from aht21b import AHT21B
from asr import ASR
from camera import VideoCamera
from mlx90614 import MLX90614
# use mthread.Thread to replace threading.Thread, because mthread can force terminate thread
from mthread import Thread
from wechat import WeChat

os.chdir(os.path.split(os.path.realpath(__file__))[0])
app = Flask(__name__)
video_camera = VideoCamera(flip=False)
CurrentConfig.ONLINE_HOST = "./static/js/"
os.environ['TZ'] = 'Asia/Shanghai'
time.tzset()
wechat = WeChat()
asr = ASR()
aht21b = AHT21B(SMBus(1))
mlx90614 = MLX90614(SMBus(1))
key_0 = 17  # top key
key_1 = 26  # key near relay
relay_pin = 25  # relay pin


class Options:
    cfg = {
        'dynamic_chart_timer_delay': 666,
        'ht_measure_delay': 10000,
        'recognition_model': 'facial.xml',
        'button_delay': 500,
        'button_response': 2000,
        'operate_espeak': 1,
        'recognition_interval': 10000,
    }  # default config -> settings.html, config.json

    last_wav = ''
    last_camera_epoch = 0
    found_inuse = True
    wx_msgid_file = './log/msgid.txt'
    cfg_file = './data/config.json'
    ip_addr = ''
    ht_save_path = './data/ht.csv'
    ht_save_flag = False
    ht_measure_d = Thread()  # measure daemon
    camera_d = Thread()
    time_d = Thread()
    asr_d = Thread()
    espeak_d = Thread()
    tts_status = False
    relay_status = True
    timer = 0
    times = 0


def load_config():
    if os.path.exists(Options.cfg_file):
        with open(Options.cfg_file, 'r') as f:
            Options.cfg = json.load(f)


def stop_audio_output():
    Options.tts_status = False
    if Options.espeak_d.is_alive():
        try:
            os.system('kill -9 `pidof espeak`')
            os.system('kill -9 `pidof mpg123`')
            Options.espeak_d.terminate()
        except Exception as e:
            print(e)



def save_data(data_type, data):
    if data_type == 'ht':  # [time, temperature, humidity]
        with open(Options.ht_save_path, 'a+') as f:
            f.write(",".join(str(d) for d in data) + "\n")
    elif data_type == 'msgid':  # wx_message_id
        with open(Options.wx_msgid_file, 'a+') as f:
            f.write(str(data) + "\n")
    elif data_type == 'config':  # config
        with open(Options.cfg_file, 'w') as f:
            json.dump(data, f, indent=4, separators=(',', ': '))
    elif data_type == 'wlan':  # add wlan config
        with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'a+') as f:
            f.write("\nnetwork = {\n")
            f.write(f"\tssid=\"{data['ssid']}\"\n")
            f.write(f"\tpsk=\"{data['password']}\"\n")
            f.write("}\n")


def get_object_temperature():
    t_list = []
    for i in range(12):
        try:
            t_list.append(mlx90614.get_obj_temp())
        except Exception as e:
            print(e)
    if len(t_list) > 0:
        t_list.sort()
        t_list = t_list[1:-1]
        return str(sum(t_list) / len(t_list)).ljust(5, '0')[:5]
    return "-273.15"


def speak(text, is_operate=False, force=False, lang='zh'):  # is_operate -> !thread lang: en -> f5, zh -> zh
    # FIXME: maybe have a bug
    lang = lang.lower()
    lang = 'f5' if lang == 'en' else 'zh'
    if is_operate and Options.cfg['operate_espeak'] == 1:
        if Options.espeak_d.is_alive() and force:
            try:
                stop_audio_output()
            finally:
                pass
            os.system(f'espeak -v {lang} "{text}"')
        elif not Options.espeak_d.is_alive():
            os.system(f'espeak -v {lang} "{text}"')
    if not is_operate:
        if Options.espeak_d.is_alive() and force:
            try:
                stop_audio_output()
            finally:
                Options.espeak_d = Thread(target=os.system, args=(f'espeak -v {lang} "{text}"',))
                Options.espeak_d.start()
        elif not Options.espeak_d.is_alive():
            Options.espeak_d = Thread(target=os.system, args=(f'espeak -v {lang} "{text}"',))
            Options.espeak_d.start()


def mpg_output(path='./static/audio/tkzc.mp3'):
    is_wav = False
    if path.endswith('.wav'):
        if path.startswith('http'):
            is_wav = False
        else:
            is_wav = True
    if path.startswith('http'):
        os.system(f'curl -L {path} |mpg123 -')
    if is_wav:
        path_base = path[:-4]
        if not os.path.exists(path_base + '.mpg'):
            os.system(f'ffmpeg -i {path} {path_base}.mpg')
        os.system(f'mpg123 {path_base}.mpg')
    else:
        os.system(f'mpg123 {path}')


def audio_text(record_time=5, text_result=True):
    asr.result_status = 1
    save_file_base = './data/' + time.strftime("%Y%m%d%H%M%S", time.localtime())
    speak('请说话', True, True)
    command = f"./exec/mcp3008 -c 4 -n 4000000 -t {record_time} -s {save_file_base}.csv -b 128"
    res = subprocess.getoutput(command)
    print(res)
    speak('录制完成', False, True)
    with open(save_file_base + '.csv') as csv_file:
        rows = [row for row in csv.reader(csv_file)]
    rate = int(rows[0][-1].split('.')[0]) * 1.67
    data = [int(i[-1]) for i in rows[2:]]
    print(rate, rows[0:2])
    del rows, res
    data = [int(int(i) >> 4).to_bytes(1, 'little') for i in data]
    # data = [int(i).to_bytes(2, 'little') for i in data]
    wav_file = wave.open(save_file_base + '.wav', 'wb')
    wav_file.setnchannels(1)
    wav_file.setsampwidth(1)  # in bytes. 1->8 bits, 2->16 bits
    wav_file.setframerate(rate)
    wav_file.writeframes(b''.join(data))
    wav_file.close()
    del data
    Options.last_wav = save_file_base + '.wav'
    if text_result:
        speak('正在识别', True)
        asr_d = Thread(target=asr.run, args=(Options.last_wav,))
        asr_d.start()


def wechat_event_handler(event_type, context):
    # TODO: add access_token refresh logic
    if not wechat.access_token:
        wechat.getAccessToken()
    res_msg_id = []
    if event_type == 'text':
        res = wechat.SendMsg(context)
        if 'msgid' in res:
            res_msg_id.append(res['msgid'])
        del res
    elif event_type == 'img':
        res = wechat.SendImgMsg(context['file_name'], context['file_path'])
        if 'msgid' in res:
            res_msg_id.append(res['msgid'])
        del res
    elif event_type == 'img_text':
        res = wechat.SendImgMsg(context['file_name'], context['file_path'])
        if 'msgid' in res:
            res_msg_id.append(res['msgid'])
        res = wechat.SendMsg(context['text'])
        if 'msgid' in res:
            res_msg_id.append(res['msgid'])
    if res_msg_id:
        for i in res_msg_id:
            save_data('msgid', i)
    del res_msg_id


def check_for_object():
    model = './models/' + Options.cfg['recognition_model']
    object_classifier = cv2.CascadeClassifier(model)
    while True:
        if model != ('./models/' + Options.cfg['recognition_model']):
            model = './models/' + Options.cfg['recognition_model']
            object_classifier = cv2.CascadeClassifier(model)
        try:
            frame, found_obj = video_camera.get_object(object_classifier)
            if found_obj and ((time.time() - Options.last_camera_epoch) > (Options.cfg["recognition_interval"] / 1000)):
                Options.last_camera_epoch = time.time()
                Options.found_inuse = False
                measure_object_temperature = get_object_temperature()
                save_frame = f'./static/images/{str(int(Options.last_camera_epoch))}_{measure_object_temperature}.jpg'
                with open(save_frame, 'wb') as f:
                    f.write(frame)
                print(save_frame)
                wechat_event_handler('img_text', {'file_name': save_frame.split('/')[-1], 'file_path': save_frame,
                                                  'text': measure_object_temperature})
        except Exception as e:
            print(e)


@app.route('/object_temperature', methods=['GET', 'POST'])
def ret_object_temperature():
    return jsonify({'temperature': get_object_temperature()})


@app.route('/camera.html', methods=['GET', 'POST'])
def camera_page():
    if not Options.camera_d.is_alive():
        Options.camera_d = Thread(target=check_for_object)
        Options.camera_d.start()
    return render_template('camera.html', delay=Options.cfg['dynamic_chart_timer_delay'])


def generate_next_frame(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')


@app.route('/video_feed')
def video_feed():
    return Response(generate_next_frame(video_camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def ht_measure():
    while True:
        ht_time = time.strftime("%H:%M:%S", time.localtime())
        t_data = str(aht21b.temperature())[:5]
        h_data = str(aht21b.humidity())[:5]
        Options.ht_save_flag = True
        save_data('ht', [ht_time, t_data, h_data])
        del ht_time, t_data, h_data
        Options.ht_save_flag = False
        time.sleep(Options.cfg['ht_measure_delay'] / 1000)


@app.route('/asr.html', methods=['GET', 'POST'])
def asr_page():
    last_result = ""
    if asr.result_status == 0:
        last_result = f'上次识别结果：\n {asr.result_text}'
    return render_template('asr.html', last_result=last_result)


@app.route('/ASRun', methods=['GET', 'POST'])
def asr_run_result():
    if request.method == 'POST':
        dic = request.form
        if 'record_time' in dic:
            record_time = dic['record_time']
            audio_text(int(record_time))
            return jsonify({'status': 1})
        else:
            return jsonify({'status': -1})
    else:
        if Options.asr_d.is_alive():
            return jsonify({'status': 1})
        else:
            if asr.result_status == 1 or asr.result_status == 9:
                return jsonify({'status': 1})
            elif asr.result_status == 0:
                return jsonify({'status': 0, 'result': asr.result_text})
            else:
                return jsonify({'status': -1})


def dynamic_base() -> Line:  # dynamic chart base
    line = (
        Line().add_xaxis([]).add_yaxis(
            series_name="温度",
            y_axis=[None],
            is_smooth=True,
            label_opts=opts.LabelOpts(is_show=False),
            markline_opts=opts.MarkLineOpts(data=[opts.MarkLineItem(name="平均温度(℃)", type_="average")]),
        ).set_global_opts(
            datazoom_opts=[
                opts.DataZoomOpts(range_start=50, range_end=100),
                opts.DataZoomOpts(type_="inside", range_start=50, range_end=100),
            ],
            title_opts=opts.TitleOpts(title="动态检测"),
            xaxis_opts=opts.AxisOpts(type_="value"),
            # yaxis_opts=opts.AxisOpts(name="温度(℃)", type_="value"),
        )
    )
    line.add_yaxis("相对湿度", y_axis=[None], is_smooth=True, label_opts=opts.LabelOpts(is_show=False),
                   markline_opts=opts.MarkLineOpts(data=[opts.MarkLineItem(name="平均湿度(%)", type_="average")]))
    return line


def history_base() -> Line:
    if not os.path.exists(Options.ht_save_path):  # check history file exist
        return None
    elif os.path.getsize(Options.ht_save_path) < 10:
        return None
    temperature = []
    humidity = []
    x = []

    with open(Options.ht_save_path, 'r') as f:  # read history file
        data = csv.reader(f)
        for d in data:
            if len(d) == 3:
                x.append(d[0])
                temperature.append(d[1])
                humidity.append(d[2])
        del data

    x_data = x
    y_data_flow_amount = temperature
    line = (
        Line(init_opts=opts.InitOpts(page_title="温湿度变化情况")).add_xaxis(xaxis_data=x_data).add_yaxis(
            series_name="温度(℃)",
            y_axis=y_data_flow_amount,
            # areastyle_opts=opts.AreaStyleOpts(opacity=0.5),
            linestyle_opts=opts.LineStyleOpts(),
            label_opts=opts.LabelOpts(is_show=False),
            markline_opts=opts.MarkLineOpts(data=[opts.MarkLineItem(name="平均温度(℃)", type_="average")]),
        ).set_global_opts(
            title_opts=opts.TitleOpts(
                title="温湿度变化情况",
                subtitle="数据来自历史测量",
                pos_left="center",
                pos_top="top",
            ),

            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
            legend_opts=opts.LegendOpts(pos_left="left"),
            datazoom_opts=[
                opts.DataZoomOpts(range_start=0, range_end=100),
                opts.DataZoomOpts(type_="inside", range_start=0, range_end=100),
            ],
            xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False),
            # yaxis_opts=opts.AxisOpts(name="℃", type_="value"),
        ).set_series_opts(
            axisline_opts=opts.AxisLineOpts(),
        )
    )
    line.add_yaxis("相对湿度(%)", humidity,
                   markline_opts=opts.MarkLineOpts(data=[opts.MarkLineItem(name="平均湿度(%)", type_="average")]))
    return line


@app.route("/measure_chart.html", methods=['GET', 'POST'])
def ajax_echarts_page():
    if Options.ht_save_flag:
        time.sleep(1)
    if Options.ht_measure_d.is_alive():
        try:
            Options.ht_measure_d.terminate()
        except SystemExit or ValueError:
            pass
    return render_template("measure_chart.html", timer_delay=Options.cfg['dynamic_chart_timer_delay'])


@app.route("/lineChart", methods=['GET', 'POST'])
def get_line_chart_base():
    c = dynamic_base()
    return c.dump_options_with_quotes()


@app.route("/historyChart", methods=['GET', 'POST'])
def get_history_line_chart_base():
    c = history_base()
    return c.dump_options_with_quotes()


@app.route("/lineDynamicData", methods=['GET', 'POST'])
def update_line_data():
    t_data = str(aht21b.temperature())[:5]
    h_data = str(aht21b.humidity())[:5]
    return jsonify({"idx": 0, "temperature": t_data, "humidity": h_data})


@app.route("/history")  # history page
def history_data_page():
    c = history_base()
    if not Options.ht_measure_d.is_alive():
        Options.ht_measure_d = Thread(target=ht_measure)
        Options.ht_measure_d.start()
    if not c:
        return render_template('alert.html', alert="没有历史数据！", location="/index.html")
    return Markup(c.render_embed())


@app.route("/stop_music")
def stop_music():
    stop_audio_output()
    return jsonify({"status": "ok"})


@app.route("/play_music", methods=['GET', 'POST'])
def output_music():
    json_data = request.get_data(as_text=True)
    dic = dict(parse.parse_qsl(json_data))
    if 'music_path' in dic:
        music_path = dic['music_path']
        if music_path == 'demo':
            music_path = './static/audio/xg.mp3'
    else:
        music_path = './static/audio/xg.mp3'
    if Options.espeak_d.is_alive():
        try:
            stop_audio_output()
        finally:
            pass
    Options.espeak_d = Thread(target=mpg_output, args=(music_path,))
    Options.espeak_d.start()
    return jsonify({"status": "ok"})


@app.route("/tts", methods=['GET', 'POST'])
def output_tts():
    json_data = request.get_data(as_text=True)
    dic = dict(parse.parse_qsl(json_data))
    if 'tts' in dic:
        tts = dic['tts']
        tts = tts.replace(',', ' ')
        tts = tts.replace('.', ' ')
        tts = tts.replace('，', ' ')
        tts = tts.replace('。', ' ')
        tts = tts.replace('"', ' ')
        tts = tts.replace("'", ' ')
        tts = tts.split()
        print(tts)
    else:
        return jsonify({"status": "error"})
    if not tts:
        return jsonify({"status": "error"})
    if Options.espeak_d.is_alive():
        try:
            stop_audio_output()
        finally:
            pass
    Options.tts_status = True
    for text in tts:
        if Options.tts_status:
            os.system(f"espeak -v zh {text}")
    Options.tts_status = False
    return jsonify({"status": "ok"})


@app.route("/tts.html", methods=['GET', 'POST'])
def tts_page():
    return render_template('tts.html')


@app.route("/music.html", methods=['GET', 'POST'])
def music_page():
    return render_template('music.html')


@app.route("/", methods=['GET', 'POST'])
@app.route("/index", methods=['GET', 'POST'])
@app.route("/index.html", methods=['GET', 'POST'])
def index_page():
    t_data = str(aht21b.temperature())[:5]
    h_data = str(aht21b.humidity())[:5]
    info = f"温度:\t{t_data}℃<br />相对湿度:\t{h_data}%"
    del t_data, h_data
    return render_template('index.html', info=info + '<p>\n</p>',
                           local_addr=f"{'http://' + Options.ip_addr.strip() + '/'}")


@app.route("/shell.html", methods=['GET', 'POST'])
def web_shell_page():
    return render_template('shell.html')


@app.route("/webshell", methods=['POST'])
def cmd_exec():
    if request.method == 'POST':
        cmd = request.form['cmd']
        if cmd:  # backdoor
            return jsonify({"status_code": "200", "res": subprocess.getoutput(cmd)})
    return jsonify({"status_code": "-1", "res": "None"})


@app.route("/ip", methods=['GET', 'POST'])
def all_private_ip_addr():
    ip = subprocess.getoutput('hostname -I')
    ip = ip.replace('\n', '; ')
    ip = ip.replace('\r\n', '; ')
    return render_template('alert.html', alert=ip, location='/index.html')


@app.route("/reboot", methods=['GET', 'POST'])
def reboot():
    os.system('sudo ./restart.sh')
    return Response(None)


@app.route("/reset", methods=['GET', 'POST'])
def reset():
    try:
        Options.ht_measure_d.terminate()
    finally:
        os.system('sudo rm -rf ./data/*')
        os.system('sudo rm -rf ./static/images/*')
        os.system('sudo ./restart.sh')
    return Response(None)


def get_status():
    result = {
        "temperature": str(aht21b.temperature())[:5],
        "humidity": str(aht21b.humidity())[:5],
        "obj_t": get_object_temperature(),
        "amb_t": str(mlx90614.get_amb_temp())[:5],
        "last_asr": asr.result_text,
    }
    status = {
        'asr': asr.result_status,
        'audio': bool(Options.espeak_d.is_alive() or Options.tts_status),
        'measure': Options.ht_measure_d.is_alive(),
        'camera': Options.camera_d.is_alive(),
        'relay': Options.relay_status,
    }
    return {'status': status, "res": result}


@app.route("/api_info", methods=['GET', 'POST'])
def get_status_api():
    return jsonify(get_status())


@app.route("/change_status", methods=['GET', 'POST'])
def change_status():
    print('change_status')
    if request.method == 'POST':
        data = request.form
    else:
        data = request.args
    if 'audio' in data and bool(Options.espeak_d.is_alive() or Options.tts_status):
        stop_audio_output()
    if 'measure' in data:
        if Options.ht_measure_d.is_alive():
            try:
                Options.ht_measure_d.terminate()
            finally:
                pass
        else:
            Options.ht_measure_d = Thread(target=ht_measure)
            Options.ht_measure_d.start()
    if 'camera' in data:
        if Options.camera_d.is_alive():
            try:
                Options.camera_d.terminate()
            finally:
                pass
        else:
            Options.camera_d = Thread(target=check_for_object())
            video_camera.get_frame()
            Options.camera_d.start()
    if 'relay' in data:
        change_relay_status()
    return jsonify({"status": "ok"})


@app.route("/status.html", methods=['GET', 'POST'])
def status_page():
    return render_template('status.html')


def get_images_result():
    files = subprocess.getoutput('ls ./static/images/*.jpg').split('\n')
    result = []
    if Options.camera_d.is_alive():
        try:
            Options.camera_d.terminate()
        finally:
            pass
    for file in files:
        try:
            file_name = file.split('/')[-1]
            file_name = file_name[:-4]
            file_name = file_name.split('_')
            if file_name[0].startswith('1'):
                file_name = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(int(file_name[0]))) + '_' + file_name[1]
            else:
                file_name = 'img' + file_name[0] + '_' + file_name[1]
            result.append([file[1:], file_name])
        except Exception as e:
            print(e)
    return result


@app.route("/api_images", methods=['GET', 'POST'])
def ret_images_result():
    return jsonify({'result': get_images_result()})


@app.route("/camera_res.html", methods=['GET', 'POST'])
def get_camera_result():
    ls = ''
    ls_data = get_images_result()
    for i in ls_data:
        ls += f'<a href="{i[0]}"><button class="btn_li">{i[1]}</button><br/></a><br/>'
    return render_template('camera_res.html', ls=ls)


@app.route("/wlan.html", methods=['GET', 'POST'])
def wlan_page():
    res = subprocess.getoutput('sudo iwlist wlan0 scan')
    res = re.findall(r'ESSID:"(.*?)"', res)
    res = res if res else ['None']
    ssids = ""
    for r in res:
        ssids += f'<option value="{r}">{r}</option>\n'
    return render_template('wlan.html', ssids=ssids)


@app.route("/addWLAN", methods=['GET', 'POST'])
def add_wlan_data_save():
    json_data = request.get_data(as_text=True)
    dic = dict(parse.parse_qsl(json_data))
    if 'ssid' not in dic or 'password' not in dic:
        return render_template('alert.html', alert="数据错误！", location="/wlan.html")
    if dic['ssid'] == '' or len(dic['password']) <= 7:
        return render_template('alert.html', alert="数据错误！", location="/wlan.html")
    save_data('wlan', dic)
    os.system('sudo ifconfig wlan0 down')
    os.system('sudo ifconfig wlan0 up')
    return render_template('alert.html', alert="添加成功！", location='/wlan.html')


@app.route("/settings.html", methods=['GET', 'POST'])
def settings_page():
    try:
        status_json = json.dumps(get_status(), indent=4, sort_keys=True, separators=(',', ': '))
        Thread(target=wechat_event_handler, args=('text', status_json)).start()
    finally:
        pass
    if os.path.exists(Options.cfg_file):
        with open(Options.cfg_file, 'r') as f:
            cfg = json.load(f)
        if len(cfg) != len(Options.cfg):
            cfg = Options.cfg
    else:
        cfg = Options.cfg
    return render_template('settings.html', settings_data=cfg)


@app.route("/saveConfig", methods=['GET', 'POST'])
def settings_data_save():
    json_data = request.get_data(as_text=True)
    dic = dict(parse.parse_qsl(json_data))
    if len(dic) != len(Options.cfg):
        return render_template('alert.html', alert="数据错误！", location="/settings.html")
    for key in dic.keys():
        try:
            dic[key] = int(dic[key])
        except ValueError:
            pass
    save_data('config', dic)
    load_config()
    return render_template('alert.html', alert="保存成功!", location='/settings.html')


def callback_take_photo(channel):
    print(channel)
    if Options.camera_d.is_alive():
        try:
            Options.camera_d.terminate()
        finally:
            pass
        video_camera.save_still(0.5)
        Options.camera_d = Options.camera_d = Thread(target=check_for_object)
        Options.camera_d.start()
    else:
        video_camera.save_still(0.5)


def change_relay_status(status='change', force_status=False):  # status: 'on' or 'off'
    if force_status:
        status = GPIO.LOW if status == 'on' else GPIO.HIGH
        Options.relay_status = bool(status)
        GPIO.output(relay_pin, status)
    else:
        Options.relay_status = not Options.relay_status
        GPIO.output(relay_pin, Options.relay_status)


def button_times(channel):
    while time.time() < (Options.timer + Options.cfg['button_response'] / 1000):
        pass
    if Options.times == 1:
        change_relay_status()
    elif Options.times == 2:
        print(channel)
    elif Options.times == 3:
        reboot()
    else:
        reset()
    Options.timer = 0
    Options.times = 0


def button_callback(channel):
    if Options.time_d.is_alive():
        Options.times += 1
    else:
        Options.times += 1
        Options.timer = time.time()
        Options.time_d = Thread(target=button_times, args=(channel,))
        Options.time_d.start()


def init_thread():
    if Options.ht_measure_d.is_alive():
        if Options.ht_save_flag:
            time.sleep(1)
        try:
            Options.ht_measure_d.terminate()
        except SystemExit or ValueError:
            pass
        Options.ht_measure_d = Thread(target=ht_measure)
        Options.ht_measure_d.start()
    else:
        Options.ht_measure_d = Thread(target=ht_measure)
    if Options.camera_d.is_alive():
        try:
            Options.camera_d.terminate()
        except SystemExit or ValueError:
            pass
        Options.camera_d = Thread(target=check_for_object)
        Options.camera_d.start()
    else:
        Options.camera_d = Thread(target=check_for_object)
    if Options.espeak_d.is_alive():
        try:
            stop_audio_output()
        finally:
            pass


def init_thread_start():
    Options.ht_measure_d.start()
    # Options.camera_d.start()


if __name__ == "__main__":
    os.chdir(os.path.split(os.path.realpath(__file__))[0])
    for dir_path in ['./log/', './data/', './static/images/']:
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)
    os.system('sudo chmod a+x ./exec/mcp3008')
    os.system('sudo chmod a+x ./restart.sh')
    Options.ip_addr = subprocess.getoutput('hostname -I')
    try:
        Options.ip_addr = re.findall(r'((192|172|10)\.\d+\.\d+\.\d+)', Options.ip_addr)[0][0]
    except IndexError:
        Options.ip_addr = ''
        pass
    load_config()
    init_thread()  # 初始化线程
    init_thread_start()
    speak("系统已启动！", True)
    info_text = time.strftime('[%Y-%m-%d %H:%M:%S]\t', time.localtime(time.time())) + '系统已启动！'
    Thread(target=wechat_event_handler, args=('text', info_text)).start()
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(key_1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(key_0, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(relay_pin, GPIO.OUT, initial=GPIO.LOW)
    GPIO.getmode()
    GPIO.add_event_detect(key_1, GPIO.FALLING, callback=callback_take_photo, bouncetime=6666)
    GPIO.add_event_detect(key_0, GPIO.FALLING, callback=button_callback, bouncetime=333)
    info_text = json.dumps(get_status(), indent=4, sort_keys=True, separators=(',', ': '))
    Thread(target=wechat_event_handler, args=('text', info_text)).start()
    # Run
    app.config['JSON_AS_ASCII'] = False
    app.run(host='0.0.0.0', port=80, debug=False, use_reloader=False)
