# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import os
import re
import time

import requests


class ASR:  # NOTE: file size must be less than 10M
    app_id = ""
    secret_key = ""

    api_base = "https://raasr.xfyun.cn/api"
    time_sleep = 5  # get result time interval
    result_status = 1  # 0: success, 1: processing, -1: fail
    result_text = ""

    def __init__(self, app_id=app_id, secret_key=secret_key):
        self.upload_file_path = None
        self.app_id = app_id
        self.secret_key = secret_key
        self.session = requests.Session()
        self.upload_dict_base = {'app_id': self.app_id, 'ts': '', 'signa': ''}
        self.task_id = None

    def dict_update(self):  # generate timestamp and signature
        ts = str(int(time.time()))
        m2 = hashlib.md5()
        m2.update((self.app_id + ts).encode('utf-8'))
        md5 = m2.hexdigest()
        md5 = bytes(md5, encoding='utf-8')
        signa = hmac.new(self.secret_key.encode('utf-8'), md5, hashlib.sha1).digest()
        signa = base64.b64encode(signa)
        signa = str(signa, 'utf-8')
        self.upload_dict_base['ts'] = ts
        self.upload_dict_base['signa'] = signa
        return self.upload_dict_base

    def prepare_upload(self):
        upload_dict = self.dict_update()
        upload_dict['file_len'] = str(os.path.getsize(self.upload_file_path))
        upload_dict['file_name'] = os.path.basename(self.upload_file_path)
        upload_dict['slice_num'] = 1
        # self.session.headers.update({'content-type': 'application/x-www-form-urlencoded'})
        res = self.session.post(self.api_base + '/prepare', data=upload_dict)
        print(res.json())
        return res.json()

    def upload(self):
        with open(self.upload_file_path, 'rb') as f:
            upload_file_content = f.read()
        upload_dict = self.dict_update()
        upload_dict['slice_id'] = 'aaaaaaaaaa'
        upload_dict['task_id'] = self.task_id
        files = {
            "filename": upload_dict['slice_id'],
            "content": upload_file_content
        }
        res = self.session.post(self.api_base + '/upload', data=upload_dict, files=files)
        print(res.json())
        return res.json()

    def result(self, api=''):
        upload_dict = self.dict_update()
        upload_dict['task_id'] = self.task_id
        if api == '/merge':
            upload_dict['file_name'] = os.path.basename(self.upload_file_path)
        res = self.session.post(self.api_base + api, data=upload_dict)
        print(res.json())
        return res.json()

    def try_run(self, file_path):
        self.result_status = 1
        self.upload_file_path = file_path
        self.task_id = self.prepare_upload()['data']
        self.upload()
        self.result('/merge')
        while True:
            res = self.result('/getProgress')
            if res['err_no'] != 0 and res['err_no'] != 26605:
                self.result_status = -1
                break
            else:
                res = json.loads(res['data'])
                if res['status'] == 9:
                    self.result_status = 9
                    break
            time.sleep(self.time_sleep)
        if self.result_status == 9:
            res = self.result('/getResult')['data']
            try:
                res = "".join(re.findall(r'onebest\":\"(.*?)\",\"speaker', res))
            except IndexError:
                res = ''
            self.result_text = res
            self.result_status = 0
            return res
        return 'Error'

    def run(self, file_path):
        try:
            return self.try_run(file_path)
        except Exception as e:
            print(e)
            self.result_status = -1
            return str(e)


if __name__ == '__main__':
    test = ASR()
    print(test.run('./output.wav'))
