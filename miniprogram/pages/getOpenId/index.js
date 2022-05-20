Page({

    /**
     * 页面的初始数据
     */
    data: {
        showUploadTip: false,
        haveGetOpenId: false,
        envId: '',
        openId: ''
    },

    onLoad(options) {
        this.setData({
            envId: options.envId
        });
    },

    /**
     * 获取openId
     */

    getOpenId() {
        const that = this;
        wx.request({
            url: `https://graduation.for-get.com/`,
            success(res) {
                if (res.data) {
                    that.setData({
                        haveGetOpenId: true,
                        openId: res.data
                    });
                } else {
                    that.setData({
                        showUploadTip: true
                    });
                }
            }
        });
    },


    clearOpenId() {
        this.setData({
            haveGetOpenId: false,
            openId: ''
        });
    }

});
