# coding: utf-8
import json
import requests
from requests_toolbelt import MultipartEncoder


# requests_toolbelt: https://github.com/requests/toolbelt

class WeChat:
    CORPID = ""
    SECRET = ""
    openid = "admin@for-get.com"
    access_token = ""

    def __init__(self, access_token=""):
        self.access_token = access_token

    def setAccessToken(self, access_token):
        self.access_token = access_token

    def getAccessToken(self):
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        res = requests.get(url=url,
                           params={
                               'corpid': self.CORPID,
                               'corpsecret': self.SECRET
                           }
                           )
        self.access_token = res.json()["access_token"]
        return self.access_token

    def SendMsg(self, message):
        body = {
            "touser": self.openid,
            "msgtype": "text",
            "agentid": "1000002",
            "text": {"content": message}
        }
        url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
        res = requests.post(url=url,
                            params={'access_token': self.access_token},
                            data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8')
                            )
        return res.json()

    def UploadImg(self, file_name, file_path, file_type='file'):  # file_type = [image, voice, video, file]
        url = "https://qyapi.weixin.qq.com/cgi-bin/media/upload"
        mp_encoder = MultipartEncoder(
            fields={
                'media': (file_name, open(file_path, 'rb'), "application/octet-stream"),
            }
        )
        res = requests.post(url=url,
                            params={'access_token': self.access_token, 'type': file_type},
                            data=mp_encoder, headers={'Content-Type': mp_encoder.content_type}
                            )
        return res.json()['media_id']

    def SendImgMsg(self, file_name, file_path):
        media_id = self.UploadImg(file_name, file_path, 'image')
        body = {
            "touser": self.openid,
            "msgtype": "image",
            "agentid": "1000002",
            "image": {"media_id": media_id}
        }
        url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
        res = requests.post(url=url,
                            params={'access_token': self.access_token},
                            data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8')
                            )
        return res.json()

    def RevokeMsg(self, msgid):
        body = {"msgid": msgid}
        url = "https://qyapi.weixin.qq.com/cgi-bin/message/recall"
        res = requests.post(url=url,
                            params={'access_token': self.access_token},
                            data=bytes(json.dumps(body, ensure_ascii=False), encoding='utf-8')
                            )
        return res.json()
