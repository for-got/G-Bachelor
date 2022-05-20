// index.js
// const app = getApp()
const { envList } = require('../../envList.js');

Page({
    data: {
        ht_info: "",
        temperature: "",
        humidity: "",
        showUploadTip: false,
        powerList: [{
            title: '摄像头测试',
            tip: '目标检测，识别并抓取陌生人照片，让您的生活更加安全！',
            showItem: false,
            item: [{
                title: '画面展示',
                page: 'Camera'
            },
                {
                    title: '识别结果',
                    page: 'imgResult'
                },
                // {
                //   title: '发送订阅消息',
                // }
            ]
        }, {
            title: '语音测试',
            tip: '通过麦克风录音，让您实现远程监听或语音识别！',
            showItem: false,
            item: [{
                title: '5秒录音',
                page: 'deployService'
            }, {
                title: '10秒录音',
                page: 'updateRecord'
            }, {
                title: '30秒录音',
                page: 'selectRecord'
            }, {
                title: '语音识别',
                page: 'sumRecord'
            }]
        }, {
            title: '功放测试',
            tip: '高品质HIFI音频播放，支持TTS语音合成，让您体验无线音乐的魅力！',
            showItem: false,
            item: [{
                title: 'Demo音频',
                page: 'getMiniProgramCode'
            },{
                title: '语音合成',
                page: 'uploadFile'
            },{
                title: '音频上传',
                page: 'uploadFile'
            }]
        }, {
            title: '环境检测',
            tip: '检测环境温度及湿度，让您对所在环境了解的更加清楚！',
            showItem: false,
            item: [{
                title: '实时温湿度检测',
                page: 'Realtime'
            },{
                title: '历史数据',
                page: 'History'
            }]
        },{
            title: '电源控制',
            tip: '远程开关其他设备，让您实现万物互联！',
            showItem: false,
            item: [{
                title: '继电器·开',
                page: 'deployService'
            },{
                title: '继电器·关',
                page: 'deployService'
            },{
                title: '定时开关',
                page: 'deployService'
            }]
        }],
        envList,
        selectedEnv: envList[0],
        haveCreateCollection: true,
    },

    onClickPowerInfo(e) {
        const index = e.currentTarget.dataset.index;
        const powerList = this.data.powerList;
        powerList[index].showItem = !powerList[index].showItem;
        if (powerList[index].title === '数据库' && !this.data.haveCreateCollection) {
            this.onClickDatabase(powerList);
        } else {
            this.setData({
                powerList
            });
        }
    },

    onChangeShowEnvChoose() {
        wx.showActionSheet({
            itemList: [this.data.temperature, this.data.humidity],
            success: (res) => {
                this.onChangeSelectedEnv(res.tapIndex);
            },
            fail (res) {
                console.log(res.errMsg);
            }
        });
    },


    onLoad(options) {
        wx.request({
            url: `https://graduation.for-get.com/api_info`,
            success: (res) => {
                console.log(res.data)
                if (res) {
                    this.setData({
                        temperature: '温度：'+res.data.res.temperature+ '℃',
                        humidity: '湿度：'+res.data.res.humidity+ '%',
                        ht_info: '温度：'+res.data.res.temperature + '℃，湿度：' + res.data.res.humidity + '%',
                    });
                } else {
                    this.setData({
                        ht_info: '连接失败！'
                    });
                }
            }
        });
    },


    onChangeSelectedEnv(index) {
        this.onLoad();
    },

    jumpPage(e) {
        wx.navigateTo({
            url: `/pages/${e.currentTarget.dataset.page}/index?envId=${this.data.selectedEnv.envId}`,
        });
    },

});
